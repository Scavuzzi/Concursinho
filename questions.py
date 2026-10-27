"""Offline question bank shared by the desktop and the JSONL Android format."""
import csv
import hashlib
import io
import json
import random
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path


ERROR_REASONS = ("Não sabia o conteúdo", "Interpretação", "Distração", "Cálculo", "Chute")


def validate_question(raw):
    if not isinstance(raw, dict):
        raise ValueError("Cada questão precisa ser um objeto JSON.")
    q = dict(raw)
    for field, limit in [("id",240),("subject",120),("topic",160),("stem",50000),("source",500)]:
        if not isinstance(q.get(field),str) or not q[field].strip() or len(q[field])>limit:
            raise ValueError(f"Campo {field} inválido.")
        q[field] = q[field].strip()
    choices=q.get("options")
    if not isinstance(choices,list) or not 2<=len(choices)<=5 or any(not isinstance(v,str) or not v.strip() or len(v)>30000 for v in choices):
        raise ValueError("Forneça de duas a cinco alternativas.")
    q["options"]=[v.strip() for v in choices]
    if type(q.get("answer")) is not int or not 0<=q["answer"]<len(choices):
        raise ValueError("Gabarito inválido.")
    for field in ["explanation","board","role","sourceUrl","answerSourceUrl"]:
        if not isinstance(q.get(field,""),str): raise ValueError(f"Campo {field} inválido.")
        q.setdefault(field,"")
    return q


def fingerprint(q):
    normalized="\n".join(" ".join(s.lower().split()) for s in [q["stem"],*q["options"]])
    return hashlib.sha256(normalized.encode()).hexdigest()


class QuestionBank:
    def __init__(self,path,rng=None):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.rng=rng or random.SystemRandom()
        self.db=sqlite3.connect(self.path,check_same_thread=False)
        self.db.row_factory=sqlite3.Row
        if self.db.execute('PRAGMA user_version').fetchone()[0] not in (0,1):
            self.db.close()
            raise ValueError('Versão do banco não suportada por este aplicativo.')
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS questions (
              id TEXT PRIMARY KEY,fingerprint TEXT NOT NULL UNIQUE,
              subject TEXT NOT NULL,topic TEXT NOT NULL,board TEXT NOT NULL,payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS q_filters ON questions(subject,topic,board);
            CREATE TABLE IF NOT EXISTS attempts (
              id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,
              question_id TEXT NOT NULL REFERENCES questions(id),choice INTEGER NOT NULL,
              correct INTEGER NOT NULL,duration_ms INTEGER NOT NULL,answered_at TEXT NOT NULL,
              reason TEXT NOT NULL DEFAULT '');
            CREATE INDEX IF NOT EXISTS a_question ON attempts(question_id,id);
            CREATE INDEX IF NOT EXISTS a_date ON attempts(answered_at);
            CREATE TABLE IF NOT EXISTS draws(question_id TEXT PRIMARY KEY REFERENCES questions(id));
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            PRAGMA user_version=1;
        """)

    def count(self):
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]

    def import_lines(self,records,seed_revision=None):
        with self.lock,self.db:
            before=self.count()
            accepted=excluded=0
            for number,line in enumerate(records,1):
                if not line.strip(): continue
                if len(line)>250000: raise ValueError(f"Linha {number}: tamanho excessivo.")
                try:
                    raw=json.loads(line)
                    if isinstance(raw,dict) and raw.get("annulled") is True:
                        excluded+=1
                        continue
                    q=validate_question(raw)
                except (ValueError,TypeError) as error:
                    raise ValueError(f"Linha {number}: {error}") from error
                self.db.execute("INSERT OR IGNORE INTO questions VALUES (?,?,?,?,?,?)",
                    (q["id"],fingerprint(q),q["subject"],q["topic"],q["board"],json.dumps(q,ensure_ascii=False)))
                accepted+=1
            after=self.count()
            if seed_revision:
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES (?,?)",(f"seed:{seed_revision}","done"))
            return {"added":after-before,"duplicates":accepted-(after-before),"excluded":excluded}

    def seed(self,path,revision="fgv-2026-10-27-v1"):
        with self.lock:
            if self.db.execute("SELECT 1 FROM metadata WHERE key=?",(f"seed:{revision}",)).fetchone():return
            with Path(path).open(encoding="utf-8") as records:
                self.import_lines(records,revision)

    def facets(self,field,subject=None):
        if field not in ("subject","topic","board"):raise ValueError("Filtro inválido.")
        with self.lock:
            return [r[0] for r in self.db.execute(f"SELECT DISTINCT {field} FROM questions"+(" WHERE subject=?" if subject else "")+f" ORDER BY {field} COLLATE NOCASE",(subject,) if subject else ())]

    def draw(self,subject=None,topic=None,board=None,mode="all",avoid_repeats=True):
        clauses,args=["1=1"],[]
        for key,value in [("subject",subject),("topic",topic),("board",board)]:
            if value:
                clauses.append(f"q.{key}=?");args.append(value)
        if mode=="unanswered":clauses.append("NOT EXISTS(SELECT 1 FROM attempts a WHERE a.question_id=q.id)")
        if mode=="errors":clauses.append("EXISTS(SELECT 1 FROM attempts a WHERE a.question_id=q.id AND a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.question_id=q.id) AND a.correct=0)")
        where=" AND ".join(clauses)
        signature=json.dumps([subject,topic,board,mode,avoid_repeats],ensure_ascii=False)
        with self.lock,self.db:
            eligible=self.db.execute(f"SELECT COUNT(*) FROM questions q WHERE {where}",args).fetchone()[0]
            if not eligible:return None,False
            previous=self.db.execute("SELECT value FROM metadata WHERE key='draw_filter'").fetchone()
            if not previous or previous[0]!=signature:
                self.db.execute("DELETE FROM draws")
                self.db.execute("INSERT OR REPLACE INTO metadata VALUES('draw_filter',?)",(signature,))
            without_seen=" AND NOT EXISTS(SELECT 1 FROM draws d WHERE d.question_id=q.id)" if avoid_repeats else ""
            available=self.db.execute(f"SELECT COUNT(*) FROM questions q WHERE {where}{without_seen}",args).fetchone()[0]
            restarted=not available
            if restarted:
                self.db.execute("DELETE FROM draws");available=eligible
            selected=self.db.execute(f"SELECT q.id FROM questions q WHERE {where}{without_seen} ORDER BY q.id LIMIT 1 OFFSET ?",[*args,self.rng.randrange(available)]).fetchone()
            row=self.db.execute('SELECT payload FROM questions WHERE id=?',(selected[0],)).fetchone()
            q=json.loads(row[0])
            if avoid_repeats:self.db.execute("INSERT OR IGNORE INTO draws VALUES(?)",(q["id"],))
            return q,restarted

    def answer(self,question_id,choice,event_id,duration_ms=0,at=None,reason=""):
        with self.lock,self.db:
            row=self.db.execute("SELECT payload FROM questions WHERE id=?",(question_id,)).fetchone()
            if not row:raise ValueError("Questão não encontrada.")
            q=json.loads(row[0])
            if type(choice) is not int or not 0<=choice<len(q["options"]):raise ValueError("Alternativa inválida.")
            correct=choice==q["answer"]
            at=(at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat().replace("+00:00","Z")
            self.db.execute("INSERT OR IGNORE INTO attempts(event_id,question_id,choice,correct,duration_ms,answered_at,reason) VALUES(?,?,?,?,?,?,?)",
                (event_id,question_id,choice,int(correct),max(0,min(duration_ms,86400000)),at,reason if not correct and reason in ERROR_REASONS else ""))
            return correct

    def tag_error(self,event_id,reason):
        if reason not in ERROR_REASONS:raise ValueError("Motivo inválido.")
        with self.lock,self.db:self.db.execute("UPDATE attempts SET reason=? WHERE event_id=? AND correct=0",(reason,event_id))

    def reclassify(self,question_id,subject,topic):
        with self.lock,self.db:
            row=self.db.execute('SELECT payload FROM questions WHERE id=?',(question_id,)).fetchone()
            if not row:raise ValueError('Questão não encontrada.')
            q=validate_question({**json.loads(row[0]),'subject':subject,'topic':topic,'classification':'reviewed-by-user'})
            self.db.execute('UPDATE questions SET subject=?,topic=?,payload=? WHERE id=?',(q['subject'],q['topic'],json.dumps(q,ensure_ascii=False),q['id']))
            return q

    def report(self,days=0,subject=None):
        cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat().replace("+00:00","Z") if days else ""
        extra=" AND q.subject=?" if subject else ""
        args=[cutoff,*([subject] if subject else [])]
        with self.lock:
            summary=dict(self.db.execute(f"SELECT COUNT(*) attempts,COALESCE(SUM(a.correct),0) correct,COUNT(DISTINCT a.question_id) unique_questions FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.answered_at>=?{extra}",args).fetchone())
            summary["topics"]=[dict(r) for r in self.db.execute(f"""SELECT q.subject,q.topic,COUNT(*) answered,SUM(a.correct) correct FROM attempts a JOIN questions q ON q.id=a.question_id
                WHERE a.answered_at>=?{extra} AND a.id=(SELECT MIN(b.id) FROM attempts b WHERE b.question_id=a.question_id AND b.answered_at>=?)
                GROUP BY q.subject,q.topic ORDER BY CAST(SUM(a.correct) AS REAL)/COUNT(*),COUNT(*) DESC""",[*args,cutoff])]
            summary["reasons"]=[dict(r) for r in self.db.execute(f"SELECT CASE WHEN a.reason='' THEN 'Não informado' ELSE a.reason END reason,COUNT(*) n FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.correct=0 AND a.answered_at>=?{extra} GROUP BY reason ORDER BY n DESC",args)]
            summary["daily"]=[dict(r) for r in self.db.execute(f"SELECT date(a.answered_at,'localtime') day,COUNT(*) n,SUM(a.correct) c FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.answered_at>=?{extra} GROUP BY day ORDER BY day",args)]
            by_topic={}
            for r in self.db.execute(f"SELECT q.subject,q.topic,a.reason,COUNT(*) n FROM attempts a JOIN questions q ON q.id=a.question_id WHERE a.correct=0 AND a.reason<>'' AND a.answered_at>=?{extra} GROUP BY q.subject,q.topic,a.reason ORDER BY n DESC",args):
                by_topic.setdefault((r['subject'],r['topic']),r['reason'])
            for t in summary['topics']:t['dominant_reason']=by_topic.get((t['subject'],t['topic']))
            summary["bank_size"]=self.count()
            return summary

    def backup(self,path):
        with self.lock:
            target=sqlite3.connect(path)
            try:self.db.backup(target)
            finally:target.close()

    def export_csv(self,path,days=0,subject=None):
        report=self.report(days,subject)
        with Path(path).open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.writer(f,delimiter=";")
            writer.writerow(["assunto","topico","primeiras_respostas","acertos","erros","percentual_acertos"])
            for row in report["topics"]:
                texts=[("'"+v if v.startswith(('=','+','-','@','\t','\r')) else v) for v in (row['subject'],row['topic'])]
                writer.writerow([*texts,row["answered"],row["correct"],row["answered"]-row["correct"],round(100*row["correct"]/row["answered"],1)])

    def close(self):
        with self.lock:self.db.close()


def advice(subject,answered,correct,reason=None):
    if answered<10:return f"Responda mais {10-answered} questões diferentes antes de avaliar seu domínio."
    if correct/answered>=.8:return "Mantenha revisões espaçadas e confirme a retenção com questões novas."
    if reason=='Interpretação':return 'Leia o comando primeiro, destaque negações e explique por que cada alternativa falha.'
    if reason=='Distração':return 'Faça séries curtas e confira o comando e a alternativa marcada antes de confirmar.'
    if reason=='Cálculo':return 'Refaça os passos sem consultar a solução e identifique onde o cálculo saiu do caminho.'
    if "Banco" in subject:return "Pratique as consultas num banco de teste e compare o resultado de cada alternativa."
    if "Desenvolvimento" in subject or "Arquitetura" in subject:return "Construa um exemplo pequeno do conceito e explique por que as outras alternativas falham."
    return "Revise a teoria do tópico, registre a causa do erro e retome com questões diferentes."
