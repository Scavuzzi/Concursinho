"""Build a traceable starter bank from the public exams already in the project.

Requires PyMuPDF only for rebuilding. Never guesses an answer: unmatched,
cancelled or ambiguous records are excluded and counted in the report.
"""
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def plain(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.lower()) if not unicodedata.combining(c))


def lines(page):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            yield "".join(s["text"] for s in line["spans"]), line["bbox"], line["spans"]


def answer_key(page, folder, heading_pattern=None):
    candidates = []
    for text, box, _ in lines(page):
        norm = plain(text)
        matches = (re.fullmatch(heading_pattern, norm.strip()) if heading_pattern else
                   "sistemas" in norm and ("tipo" in norm or "turno" in norm)
                   and re.search(r"(?:tipo\s*1\b| - 1 - )", norm))
        if matches:
            candidates.append((box[3], norm))
    if len(candidates) != 1:
        raise ValueError(f"{folder}: expected one heading for the Systems / type 1 answer key, got {candidates}")
    start = candidates[0][0]
    end = page.rect.height
    for text, box, _ in lines(page):
        norm = plain(text)
        is_heading = re.search(r"\s[-–]\s(?:tipo\s*)?[1-4](?:\s*[-–]\s*turno\s.*)?$", norm.strip())
        if box[1] > start and (is_heading or ("tipo" in norm or "turno" in norm) and (
            "analista" in norm or "tecnico" in norm or "arquiteto" in norm
        )):
            end = min(end, box[1])
    words = [w for w in page.get_text("words") if start < w[1] < end]
    letters = [w for w in words if re.fullmatch(r"[ABCDE*]", w[4])]
    result = {}
    for number in words:
        if not number[4].isdigit() or not 1 <= int(number[4]) <= 100:
            continue
        x, y = (number[0] + number[2]) / 2, (number[1] + number[3]) / 2
        same_row = [a for a in letters if abs((a[1]+a[3])/2-y) < 3 and 0 < a[0]-number[2] < 32]
        below = [a for a in letters if 0 < (a[1]+a[3])/2-y < 25 and abs((a[0]+a[2])/2-x) < 7]
        matches = same_row or below
        if len(matches) == 1:
            n = int(number[4])
            if n in result:
                raise ValueError(f"Repeated answer {folder}/{n}; wrong section boundary")
            result[n] = matches[0][4]
    if not result or sorted(result) != list(range(1, max(result)+1)):
        raise ValueError(f"{folder}: incomplete/nonconsecutive answer key: {sorted(result)}")
    return result


TOPICS = [
    ("Banco de dados", "SQL e modelagem", r"\bsql\b|\bsqlite\b|\bselect\b|\bsqbd\b|\bsgbd\b|banco[s]? de dados|normaliza[cç][aã]o|postgres|mongodb|\bacid\b|chave estrangeira"),
    ("Engenharia de software", "Testes e qualidade", r"testes? (?:de|unit|func|automat|integr)|\bselenium\b|\bjunit\b|\btdd\b|\bbdd\b|cobertura de|caixa.preta|caixa.branca|qualidade de software"),
    ("Engenharia de software", "Agilidade e requisitos", r"\bscrum\b|\bkanban\b|\bbacklog\b|\bsprint\b|\bsafe\b|requisitos?|pontos de fun[cç][aã]o|\bifpug\b|\bapf\b|hist[oó]rias? de usu[aá]rio"),
    ("Arquitetura de software", "Padrões, APIs e integração", r"microsservi[cç]|\brest\b|\bsoap\b|\bsolid\b|\bmvc\b|\bmvp\b|design pattern|padr[oõ]es de projeto|\bgoF\b|\bapi\b|arquitetura|\bdomain.driven|\bddd\b|singleton|factory|observer|\bgrasp\b"),
    ("Segurança da informação", "Segurança e desenvolvimento seguro", r"seguran[cç]a|criptograf|\bowasp\b|vulnerabil|\bxss\b|\bcsrf\b|\blgpd\b|autentica|autoriza|\boauth\b|\bssl\b|\btls\b|\bfirewall\b|assinatura digital|malware"),
    ("DevOps e nuvem", "Entrega, contêineres e infraestrutura", r"\bdocker\b|kubernetes|\bdevops\b|\bgit\b|\bci/cd\b|terraform|computa[cç][aã]o em nuvem|\bcloud\b|\bsaas\b|\bpaas\b|\biaas\b|\bjenkins\b|\bazure\b|\baws\b"),
    ("Inteligência artificial", "Modelos, aprendizado e dados", r"intelig[eê]ncia artificial|machine learning|aprendizado de m[aá]quina|redes neurais|\bllm\b|\brag\b|\bnlp\b|minera[cç][aã]o de dados|\btransformer\b|\bprompt\b"),
    ("Redes e sistemas", "Redes, sistemas operacionais e hardware", r"\btcp\b|\budp\b|\bip[v46]*\b|\bdns\b|\bhttp\b|\bosi\b|\bethernet\b|roteador|endere[cç]amento|\blinux\b|sistemas? operacion|mem[oó]ria|processador|escalonamento|\bipv[46]\b"),
    ("Desenvolvimento de sistemas", "Linguagens, algoritmos e estruturas", r"\bjava\b|\bpython\b|\bc\+\+|\bc#|\bphp\b|javascript|typescript|\bhtml\b|\bcss\b|\bxml\b|\bjson\b|algoritmo|orienta[cç][aã]o a objetos|polimorfismo|heran[cç]a|encapsulamento|recurs|estrutura[s]? de dados|compilador|\buml\b|\bbpmn\b|\breact\b|\bangular\b|programa[cç][aã]o"),
    ("Gestão e governança de TI", "Gestão de projetos e serviços", r"\bitil\b|\bcobit\b|\bpmbok\b|\bpmi\b|governan[cç]a|gest[aã]o de projetos|gest[aã]o de servi[cç]os|\bcmmi\b|\bmps.br\b|\bcmm\b"),
]


def classify(text, section, specific):
    if "portugues" in plain(section):
        for topic,pattern in [
            ('Concordância e regência',r'concord[aâ]ncia|reg[eê]ncia|\bcrase\b'),
            ('Pontuação e ortografia',r'pontua[cç][aã]o|v[ií]rgula|ortografia|ortogr[aá]fic|h[ií]fen'),
            ('Coesão e referenciação',r'pronome|retomad|referencia[cç]|coes[aã]o|antecedente'),
            ('Semântica e figuras de linguagem',r'figura|met[aá]fora|ant[ií]tese|paradoxo|significado|sentido|sin[oô]nim|ant[oô]nim'),
            ('Morfossintaxe',r'verb[oa]|ora[cç][aã]o|adjetiv|substantiv|sint[aá]tic|adv[eé]rbi'),
        ]:
            if re.search(pattern,text,re.I):return 'Língua Portuguesa',topic
        return 'Língua Portuguesa','Interpretação e estrutura textual'
    if any(x in plain(section) for x in ["logico", "matematica"]):
        return "Raciocínio lógico", "Lógica e matemática"
    if not specific:
        return "TI — classificação pendente", "Fora do recorte de TI"
    if re.search(r'\btcp\b|\budp\b|\bipv[46]\b|\bdns\b|redes de computadores|sistema[s]? operaciona|processador|arquitetura de computadores', text, re.I):
        return 'Redes e sistemas', 'Redes, sistemas operacionais e hardware'
    if re.search(r'\bxml\b|\bhtml\b|\bcss\b|\bjavascript\b|\bpython\b|linguagem java',text,re.I):
        return 'Desenvolvimento de sistemas', 'Linguagens, algoritmos e estruturas'
    if re.search(r'acessibilidade|\be-mag\b|interface[s]? de usu[aá]rio|usabilidade',text,re.I):
        return 'Interfaces e acessibilidade', 'Experiência e acessibilidade'
    for subject, topic, pattern in TOPICS:
        if re.search(pattern, text, re.I):
            return subject, topic
    return "TI — classificação pendente", "Revisão geral"


def refine(subject,topic,text):
    rules={
        'Banco de dados':[
            ('Consultas SQL',r'\bselect\b|\bsql\b|consulta|\bjoin\b'),
            ('Modelagem e normalização',r'modelagem|normaliza[cç]|entidade|relacionamento|chave'),
            ('SGBDs e administração',r'postgres|mysql|oracle|\bh2\b|banco de dados|sgbd'),
        ],
        'Desenvolvimento de sistemas':[
            ('Python',r'\bpython\b'),('Java e JVM',r'\bjava\b|\bjvm\b|\bjpa\b'),
            ('Web e formatos de dados',r'\bhtml\b|\bxml\b|\bcss\b|javascript|typescript|\bjson\b'),
            ('Orientação a objetos',r'orienta[cç][aã]o a objetos|heran[cç]a|polimorfismo|encapsulamento'),
            ('Modelagem UML e BPMN',r'\buml\b|\bbpmn\b|diagrama'),
        ],
        'Engenharia de software':[
            ('Scrum, Kanban e agilidade',r'scrum|kanban|sprint|agilidade|metodologia[s]? [aá]ge'),
            ('Requisitos e estimativas',r'requisito|pontos de fun[cç]|\bifpug\b|\bapf\b'),
        ],
        'Redes e sistemas':[
            ('Arquitetura de computadores',r'mem[oó]ria|processador|von neumann|hardware|computadores modernos'),
            ('Sistemas operacionais',r'sistema[s]? operacion|linux|windows|escalonamento'),
            ('Redes e protocolos',r'tcp|udp|redes|protocolo|rotea|endere[cç]o'),
        ],
        'Segurança da informação':[
            ('Criptografia',r'criptograf|cifra|assim[eé]tric|assinatura digital'),
            ('Segurança de aplicações',r'owasp|vulnerabil|\bxss\b|\bcsrf\b|inje[cç][aã]o'),
            ('Identidade e controle de acesso',r'autentica|autoriza|oauth|controle de acesso'),
        ],
    }
    for candidate,pattern in rules.get(subject,[]):
        if re.search(pattern,text,re.I):return candidate
    return topic


def build():
    catalog = json.loads((MOBILE / "assets/data/catalog.json").read_text(encoding="utf-8"))
    sources = json.loads((MOBILE / "assets/data/sources.json").read_text(encoding="utf-8"))["exams"]
    records, excluded = [], Counter()
    report = []
    selected = [e for i,e in enumerate(catalog["exams"]) if i < 8 or e.get("questionBank")]
    for exam in selected:
        folder = exam["id"].removeprefix("exam:")
        original = next(d for d in catalog["documents"] if d["id"] == exam["documents"]["prova"])
        key = next(d for d in catalog["documents"] if d["id"] == exam["documents"]["gabarito_definitivo"])
        proof = fitz.open(MOBILE / original["asset"])
        layout = [list(lines(page)) for page in proof]
        key_doc = fitz.open(MOBILE / key["asset"])
        config = exam.get("questionBank", {})
        answers = answer_key(key_doc[key["initialPage"] - 1], folder, config.get("keyHeading"))
        if config.get("questions") and len(answers) != config["questions"]:
            raise ValueError(f"{folder}: answer count differs from the booklet cover")
        regions, anchors = [], []
        section, specific = "Conhecimentos gerais", False
        for page_index, page in enumerate(proof):
            if page_index == 0:
                continue
            for column in range(2):
                # Original source coordinates; retain vectors, diagrams and code.
                x0, x1 = (30, 291) if column == 0 else (307, 575)
                region_id = len(regions)
                regions.append((page_index, (x0, 48 if config else 52, x1, 797)))
                for text, box, spans in layout[page_index]:
                    if not (x0 <= box[0] < x1 and 42 < box[1] < 790):
                        continue
                    if len(text.strip()) < 100 and any(s['flags'] & 16 and s['size'] >= 12 for s in spans):
                        section = text.strip()
                        if 'especificos' in plain(section):
                            specific = True
                    t = text.strip()
                    if t.isdigit() and 1 <= int(t) <= len(answers) and any(s["flags"] & 16 for s in spans) and box[0] < x0 + 24:
                        anchors.append((int(t), region_id, box[1]-2, section, specific))
        # The anchor sequence itself must agree with the official numbering.
        # Some booklets restart numbering for the essay after the objective.
        anchors = anchors[:len(answers)]
        numbers = [a[0] for a in anchors]
        if numbers != list(range(1, len(answers)+1)):
            raise ValueError(f"{folder}: question anchors do not match answer key: {numbers}")
        accepted = 0
        for ix, (n, region_id, start_y, section, specific) in enumerate(anchors):
            if answers[n] == "*":
                excluded["cancelled"] += 1
                continue
            end_region, end_y = (anchors[ix+1][1], anchors[ix+1][2]-3) if ix+1 < len(anchors) else (region_id, 797)
            chunks, clips = [], []
            for region in range(region_id, end_region+1):
                pno, rect = regions[region]
                x0, y0, x1, y1 = rect
                if region == region_id: y0 = start_y
                if region == end_region: y1 = end_y
                if config:
                    # Section titles between the last option and the next
                    # question belong to the following section, not option E.
                    y1 = min(y1, 785)
                    for title, box, spans in layout[pno]:
                        norm = plain(title).strip()
                        if x0 <= box[0] < x1 and y0 < box[1] < y1 and any(s['flags'] & 16 and s['size'] >= 12 for s in spans) and re.match(r'^(?:conhecimentos\b|legislacao especifica\b|modulo\b|especificos\b)', norm):
                            y1 = min(y1, box[1]-3)
                if y1-y0 < 3: continue
                clip = fitz.Rect(x0,y0,x1,y1)
                raw = proof[pno].get_text(clip=clip, sort=True).strip()
                if raw:
                    clips.append({"page":pno+1,"rect":[round(v,2) for v in clip]})
                    chunks.append(raw)
            raw = "\n".join(chunks)
            raw = re.sub(r"^\d+\s*\n", "", raw)
            choices = list(re.finditer(r"(?m)^\s*\(([A-E])\)\s*", raw))
            if [m[1] for m in choices] != list("ABCDE"):
                excluded["ambiguous_options"] += 1
                continue
            stem = raw[:choices[0].start()].strip()
            options = [raw[m.end(): choices[j+1].start() if j<4 else len(raw)].strip() for j,m in enumerate(choices)]
            if not stem or any(not o for o in options):
                excluded["empty_text"] += 1
                continue
            if re.search(r"(?i)texto (?:I\b|II\b|acima|anterior)|texto a seguir.*quest[oõ]es|texto [12]\b|(?:definid|apresentad|descrit)[ao]s? anteriormente|quest[aã]o anterior|(?:tabelas?|diagramas?|figuras?|esquemas?) (?:acima|anteriores?)", stem):
                excluded["shared_context"] += 1
                continue
            if config and re.search(r'(?i)(?:do|no|ao|nesse|desse|neste|deste)\s+texto\b|(?:fragmento|trecho|periodo|par[aá]grafo) (?:acima|anterior)|(?:o|ao) texto\s*(?:\d|[IVX]+)\b', stem):
                excluded["shared_context"] += 1
                continue
            # Distractors often mention unrelated technologies: classify the
            # command/stem, never use the alternatives as taxonomy evidence.
            subject, topic = classify(stem, section, specific)
            topic = refine(subject,topic,stem)
            if any(x in plain(stem) for x in ["regimento interno", "lei estadual", "estatuto dos servidores", "constituicao federal", "lei organica"]):
                excluded["outside_ti_scope"] += 1
                continue
            if subject.startswith("TI —"):
                excluded["unclassified"] += 1
                continue
            src = next(s for s in sources if s["folder"] == folder and s["kind"] == "prova")
            ans_src = next(s for s in sources if s["folder"] == folder and s["kind"] == "gabarito_definitivo")
            records.append({
                "id":f"{folder}:tipo1:q{n}","subject":subject,"topic":topic,
                "stem":stem,"options":options,"answer":ord(answers[n])-65,
                "explanation":"Gabarito definitivo da banca. Esta questão ainda não tem resolução comentada revisada.",
                "board":"FGV","year":int(folder.split('_')[2]),"role":exam["title"],
                "source":f"{exam['title']} · Tipo 1 · questão {n}",
                "sourceUrl":src["url"],"answerSourceUrl":ans_src["url"],
                "documentId":original["id"],"clips":clips,
                "classification":"suggested",
                "originalSection": section,
            })
            accepted += 1
        report.append({"exam":folder,"officialQuestions":len(answers),"included":accepted,"proofSha256":src_hash(MOBILE/original["asset"]),"keySha256":src_hash(MOBILE/key["asset"])})
    # Shared general questions occur in several TI specialties. Count each
    # normalized stem/options only once and never resolve conflicting keys by
    # silently picking one of the official sources.
    unique = {}
    for record in records:
        fp = hashlib.sha256('\n'.join(' '.join(s.lower().split()) for s in [record['stem'],*record['options']]).encode()).hexdigest()
        if fp in unique:
            if unique[fp]['answer'] != record['answer']:
                raise ValueError(f"Conflicting official answers: {unique[fp]['id']} / {record['id']}")
            excluded['duplicate_content'] += 1
        else:
            unique[fp] = record
    records = list(unique.values())
    counts = Counter(q['id'].split(':tipo1:')[0] for q in records)
    for item in report:
        item['included'] = counts[item['exam']]
    destination = MOBILE / "assets/data/questoes.jsonl"
    destination.write_text("".join(json.dumps(q,ensure_ascii=False)+"\n" for q in records),encoding="utf-8")
    (ROOT/"data/question-bank-build.json").write_text(json.dumps({"revision":"2026-10-27-v2","included":len(records),"subjects":dict(Counter(q['subject'] for q in records)),"excluded":dict(excluded),"exams":report,"note":"Initial classification is suggested, not a reviewed subject taxonomy. All answers are matched to the type-1 final answer key; cancelled/ambiguous items are excluded. Identical stem/options across specialties are deduplicated before counting."},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"included":len(records),"excluded":dict(excluded),"subjects":dict(Counter(q['subject'] for q in records))},ensure_ascii=False,indent=2))


def src_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    build()
