"""Tk interface for the local question bank. No server or account is required."""
import json
import queue
import threading
import time
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox

from questions import ERROR_REASONS, QuestionBank, advice


class QuestionPanel:
    def __init__(self,app,frame,ctk,theme,database_path=None):
        self.app,self.frame,self.ctk,self.theme=app,frame,ctk,theme
        self.bank=None
        self.current=None
        self.answered=False
        self.busy=False
        self.started=0
        self.event_id=""
        self.jobs=queue.Queue()
        self.subject=ctk.StringVar(value="Todos os assuntos")
        self.topic=ctk.StringVar(value="Todos os tópicos")
        self.board=ctk.StringVar(value="Todas as bancas")
        self.mode=ctk.StringVar(value="Todas")
        self.avoid=ctk.BooleanVar(value=True)
        self.view=ctk.StringVar(value="Praticar")
        self.period=ctk.StringVar(value="Tudo")
        self.choice=ctk.IntVar(value=-1)
        self.reason=ctk.StringVar(value="Não informado")
        self.options=[]
        self.base=Path(__file__).resolve().parent
        frame.grid_columnconfigure(0,weight=1)
        frame.grid_rowconfigure(3,weight=1)
        header=ctk.CTkFrame(frame,fg_color="transparent")
        header.grid(row=0,column=0,sticky="ew",padx=16,pady=(16,8))
        header.grid_columnconfigure(0,weight=1)
        self.label(header,"Questões · um passo de cada vez",0,True)
        self.status=ctk.CTkLabel(header,text="Carregando o banco...",text_color=theme['muted'])
        self.status.grid(row=1,column=0,sticky="w")
        self.navigation=ctk.CTkSegmentedButton(frame,values=["Praticar","Desempenho"],variable=self.view,command=lambda _:self.render())
        self.navigation.grid(row=1,column=0,padx=16,pady=8,sticky="ew")
        filters=ctk.CTkFrame(frame,fg_color="transparent")
        filters.grid(row=2,column=0,padx=16,pady=6,sticky="ew")
        for i in range(3):filters.grid_columnconfigure(i,weight=1)
        self.subject_menu=ctk.CTkOptionMenu(filters,variable=self.subject,values=["Todos os assuntos"],command=self.subject_changed)
        self.subject_menu.grid(row=0,column=0,padx=(0,6),pady=4,sticky="ew")
        self.topic_menu=ctk.CTkOptionMenu(filters,variable=self.topic,values=["Todos os tópicos"],command=lambda _:self.clear_question())
        self.topic_menu.grid(row=0,column=1,padx=6,pady=4,sticky="ew")
        self.board_menu=ctk.CTkOptionMenu(filters,variable=self.board,values=["Todas as bancas"],command=lambda _:self.clear_question())
        self.board_menu.grid(row=0,column=2,padx=(6,0),pady=4,sticky="ew")
        self.mode_menu=ctk.CTkOptionMenu(filters,variable=self.mode,values=["Todas","Não respondidas","Últimos erros"],command=lambda _:self.clear_question())
        self.mode_menu.grid(row=1,column=0,padx=(0,6),pady=4,sticky="ew")
        self.repeat=ctk.CTkCheckBox(filters,text="Evitar repetição no ciclo",variable=self.avoid,command=self.clear_question)
        self.repeat.grid(row=1,column=1,columnspan=2,padx=6,pady=4,sticky="w")
        self.content=ctk.CTkScrollableFrame(frame,fg_color=theme['panel'])
        self.content.grid(row=3,column=0,padx=16,pady=8,sticky="nsew")
        self.content.grid_columnconfigure(0,weight=1)
        footer=ctk.CTkFrame(frame,fg_color="transparent")
        footer.grid(row=4,column=0,padx=16,pady=(0,12),sticky="ew")
        for i,(text,fn) in enumerate([("Importar questões",self.import_bank),("Exportar indicadores",self.export_csv),("Backup completo",self.backup)]):
            ctk.CTkButton(footer,text=text,command=fn,**app.button_options('secondary')).grid(row=0,column=i,padx=(0,8),pady=4)
        try:
            self.bank=QuestionBank(database_path or self.base/'question-bank.sqlite3')
            self.bank.seed(self.base/'mobile/assets/data/questoes.jsonl')
            self.update_facets()
            self.status.configure(text=f"{self.bank.count()} questões · offline · classificação inicial sugerida")
            self.render()
        except Exception as error:
            self.status.configure(text="Banco indisponível; o plano e os PDFs continuam acessíveis.")
            self.label(self.content,f"Não foi possível abrir o banco: {error}",0)
        frame.after(100,self.poll_jobs)
        frame.bind('<Destroy>',self.on_destroy,add='+')

    def label(self,parent,text,row,bold=False,color=None):
        item=self.ctk.CTkLabel(parent,text=text,anchor="w",justify="left",wraplength=720,
            text_color=color or self.theme['text'],font=self.ctk.CTkFont(size=18 if bold else 13,weight='bold' if bold else 'normal'))
        item.grid(row=row,column=0,padx=12,pady=6,sticky="ew")
        return item

    def subject_value(self):return None if self.subject.get()=='Todos os assuntos' else self.subject.get()

    def update_facets(self):
        self.subject_menu.configure(values=['Todos os assuntos',*self.bank.facets('subject')])
        self.topic_menu.configure(values=['Todos os tópicos',*self.bank.facets('topic',self.subject_value())])
        self.board_menu.configure(values=['Todas as bancas',*self.bank.facets('board')])

    def subject_changed(self,_):
        if self.busy or not self.bank:return
        self.topic.set('Todos os tópicos');self.update_facets();self.clear_question()

    def clear_question(self):
        if self.busy:return
        self.current=None;self.answered=False;self.render()

    def next(self):
        if self.busy or not self.bank:return
        try:
            q,restarted=self.bank.draw(subject=self.subject_value(),topic=None if self.topic.get()=='Todos os tópicos' else self.topic.get(),
                board=None if self.board.get()=='Todas as bancas' else self.board.get(),
                mode={'Todas':'all','Não respondidas':'unanswered','Últimos erros':'errors'}[self.mode.get()],avoid_repeats=self.avoid.get())
            self.current=q;self.answered=False;self.choice.set(-1);self.reason.set('Não informado')
            self.started=time.monotonic();self.event_id=str(uuid.uuid4())
            self.status.configure(text='Novo ciclo aleatório: todas as questões do recorte já foram sorteadas.' if restarted else f'{self.bank.count()} questões no banco')
            self.render()
            self.content._parent_canvas.yview_moveto(0)
        except Exception as error:messagebox.showerror('Sorteio',str(error),parent=self.frame)

    def answer(self):
        if not self.current or self.answered or self.choice.get()<0:return
        try:
            self.correct=self.bank.answer(self.current['id'],self.choice.get(),self.event_id,int((time.monotonic()-self.started)*1000))
            self.answered=True;self.render()
        except Exception as error:messagebox.showerror('Resposta não salva',str(error),parent=self.frame)

    def tag_error(self,reason):
        if reason=='Não informado':return
        try:self.bank.tag_error(self.event_id,reason)
        except Exception as error:messagebox.showerror('Motivo do erro',str(error),parent=self.frame)

    def render(self):
        if not self.bank:return
        for child in self.content.winfo_children():child.destroy()
        stats=self.view.get()=='Desempenho'
        self.subject_menu.configure(state='disabled' if self.busy else 'normal')
        self.navigation.configure(state='disabled' if self.busy else 'normal')
        for control in [self.topic_menu,self.board_menu,self.mode_menu,self.repeat]:control.configure(state='disabled' if stats or self.busy else 'normal')
        if stats:self.render_report();return
        q=self.current
        if not q:
            self.label(self.content,'Uma questão aleatória, com ou sem filtros.',0,True)
            self.label(self.content,'Escolha um recorte ou deixe todos os assuntos. A confirmação registra a tentativa; pular não conta como erro.',1)
            self.ctk.CTkButton(self.content,text='Sortear questão',command=self.next).grid(row=2,column=0,padx=12,pady=16,sticky='w')
            return
        self.label(self.content,q['source'],0,True)
        self.label(self.content,f"{q['subject']} · {q['topic']}",1,color=self.theme['yellow'])
        self.label(self.content,'Classificação inicial sugerida; use Ajustar classificação se necessário.' if q.get('classification')=='suggested' else 'Classificação fornecida ou revisada pelo usuário.',2)
        statement=self.ctk.CTkTextbox(self.content,height=190,wrap='word',font=self.ctk.CTkFont(size=15))
        statement.grid(row=3,column=0,padx=12,pady=12,sticky='ew');statement.insert('1.0',q['stem']);statement.configure(state='disabled')
        self.options=[]
        for i,text in enumerate(q['options']):
            box=self.ctk.CTkFrame(self.content,fg_color=self.theme['card'])
            box.grid(row=4+i,column=0,padx=12,pady=4,sticky='ew');box.grid_columnconfigure(1,weight=1)
            radio=self.ctk.CTkRadioButton(box,text=chr(65+i),width=42,variable=self.choice,value=i,state='disabled' if self.answered else 'normal')
            radio.grid(row=0,column=0,padx=12,pady=12)
            color=self.theme['green'] if self.answered and i==q['answer'] else self.theme['red'] if self.answered and i==self.choice.get() else self.theme['text']
            self.ctk.CTkLabel(box,text=text,justify='left',anchor='w',wraplength=650,text_color=color).grid(row=0,column=1,padx=10,pady=10,sticky='ew')
            self.options.append(radio)
        row=4+len(q['options'])
        if self.answered:
            self.label(self.content,'Você acertou.' if self.correct else 'Vamos entender esse erro.',row,True,color=self.theme['green'] if self.correct else self.theme['red']);row+=1
            self.label(self.content,f"Gabarito: {chr(65+q['answer'])}\n{q.get('explanation') or 'Sem comentário revisado.'}",row);row+=1
            if not self.correct:
                self.ctk.CTkOptionMenu(self.content,variable=self.reason,values=['Não informado',*ERROR_REASONS],command=self.tag_error).grid(row=row,column=0,padx=12,pady=8,sticky='w');row+=1
        actions=self.ctk.CTkFrame(self.content,fg_color='transparent');actions.grid(row=row,column=0,padx=12,pady=12,sticky='ew')
        if not self.answered:self.ctk.CTkButton(actions,text='Confirmar resposta',command=self.answer).grid(row=0,column=0,padx=(0,8),pady=4)
        self.ctk.CTkButton(actions,text='Próxima aleatória' if self.answered else 'Pular sem responder',command=self.next,**self.app.button_options('secondary')).grid(row=0,column=1,padx=(0,8),pady=4)
        source=self.base/'mobile/assets/pdfs'/f"{q.get('documentId','')}.pdf"
        if source.resolve().parent==(self.base/'mobile/assets/pdfs').resolve() and source.is_file():
            self.ctk.CTkButton(actions,text='Ver prova original',command=lambda:self.app.open_path_with_default_app(source),**self.app.button_options('secondary')).grid(row=1,column=0,padx=(0,8),pady=4)
            self.label(self.content,f"Confira figuras, código e trechos sublinhados no PDF original (página {(q.get('clips') or [{}])[0].get('page',1)}).",row+1)
        self.ctk.CTkButton(actions,text='Ajustar classificação',command=self.reclassify,**self.app.button_options('secondary')).grid(row=1,column=1,padx=(0,8),pady=4)
        self.label(self.content,f"Fonte: {q.get('sourceUrl','')}\nGabarito: {q.get('answerSourceUrl','')}",row+2,color=self.theme['muted'])

    def reclassify(self):
        if not self.current:return
        subject=self.ctk.CTkInputDialog(text='Assunto desta questão:',title='Ajustar classificação').get_input()
        if not subject:return
        topic=self.ctk.CTkInputDialog(text='Tópico desta questão:',title='Ajustar classificação').get_input()
        if not topic:return
        try:
            self.current=self.bank.reclassify(self.current['id'],subject,topic)
            self.subject.set('Todos os assuntos');self.topic.set('Todos os tópicos');self.update_facets();self.render()
        except Exception as error:messagebox.showerror('Classificação',str(error),parent=self.frame)

    def render_report(self):
        self.ctk.CTkSegmentedButton(self.content,values=['Tudo','7 dias','30 dias'],variable=self.period,command=lambda _:self.render()).grid(row=0,column=0,padx=12,pady=8,sticky='w')
        report=self.bank.report({'Tudo':0,'7 dias':7,'30 dias':30}[self.period.get()],self.subject_value())
        self.label(self.content,f"{report['attempts']} tentativas · {report['correct']} acertos · {report['attempts']-report['correct']} erros · {report['unique_questions']} questões diferentes",1,True)
        self.label(self.content,'Barras: primeira resposta de cada questão no período. Verde = acerto; vermelho = erro. Menos de 10 questões ainda é amostra inicial.',2)
        if not report['topics']:self.label(self.content,'Responda questões para começar seu diagnóstico. Assuntos sem respostas não têm domínio medido.',3);return
        row=3
        for t in report['topics']:
            card=self.ctk.CTkFrame(self.content,fg_color=self.theme['card']);card.grid(row=row,column=0,padx=12,pady=8,sticky='ew');card.grid_columnconfigure(0,weight=1)
            self.label(card,f"{t['subject']} · {t['topic']}",0,True)
            ratio=t['correct']/t['answered']
            bar=self.ctk.CTkProgressBar(card,progress_color=self.theme['green'],fg_color=self.theme['red'],height=12)
            bar.grid(row=1,column=0,padx=12,pady=8,sticky='ew');bar.set(ratio)
            status='Amostra inicial' if t['answered']<10 else 'Ponto forte' if ratio>=.8 else 'Prioridade de revisão' if ratio<.6 else 'Em desenvolvimento'
            self.label(card,f"{ratio:.0%} · {t['correct']} acertos / {t['answered']-t['correct']} erros · {t['answered']} diferentes · {status}",2)
            self.label(card,advice(t['subject'],t['answered'],t['correct'],t['dominant_reason']),3)
            self.ctk.CTkButton(card,text='Treinar este tópico',command=lambda s=t['subject'],p=t['topic']:self.train_topic(s,p),**self.app.button_options('secondary')).grid(row=4,column=0,padx=12,pady=8,sticky='w')
            row+=1
        self.label(self.content,'Motivos dos erros · todas as tentativas',row,True);row+=1
        for r in report['reasons']:
            self.label(self.content,f"{r['reason']}: {r['n']}",row);row+=1
        self.label(self.content,'Evolução diária · todas as tentativas',row,True);row+=1
        for d in report['daily'][-14:]:
            self.label(self.content,f"{d['day']} · {d['c']}/{d['n']} acertos ({d['c']/d['n']:.0%})",row);row+=1

    def train_topic(self,subject,topic):
        self.subject.set(subject);self.topic.set(topic);self.board.set('Todas as bancas');self.mode.set('Todas');self.view.set('Praticar');self.update_facets();self.next()

    def import_bank(self):
        if self.busy or not self.bank:return
        filename=filedialog.askopenfilename(parent=self.frame,title='Importar banco',filetypes=[('Questões JSONL/JSON','*.jsonl *.ndjson *.json')])
        if not filename:return
        self.busy=True;self.status.configure(text='Importando lote. Você pode continuar usando as outras abas.');self.render()
        def worker():
            try:
                path=Path(filename)
                with path.open(encoding='utf-8-sig') as f:
                    if path.suffix.lower()=='.json':
                        if path.stat().st_size>30*1024*1024:raise ValueError('Para mais de 30 MB use JSONL.')
                        data=json.load(f);items=data if isinstance(data,list) else data.get('questions') if data.get('schemaVersion')==1 else None
                        if not isinstance(items,list):raise ValueError('Use uma lista ou schemaVersion 1 com questions.')
                        result=self.bank.import_lines(map(json.dumps,items))
                    else:result=self.bank.import_lines(f)
                self.jobs.put(('ok',result))
            except Exception as error:self.jobs.put(('error',str(error)))
        threading.Thread(target=worker,daemon=True).start()

    def poll_jobs(self):
        try:
            while True:
                mode,value=self.jobs.get_nowait();self.busy=False
                if mode=='ok':
                    self.update_facets();self.status.configure(text=f"{value['added']} novas · {value['duplicates']} já existentes · {value['excluded']} anuladas excluídas")
                else:messagebox.showerror('Lote não importado',value,parent=self.frame);self.status.configure(text='Nenhuma questão deste lote foi adicionada.')
                self.render()
        except queue.Empty:pass
        if self.frame.winfo_exists():self.frame.after(100,self.poll_jobs)

    def export_csv(self):
        if self.busy or not self.bank:return
        filename=filedialog.asksaveasfilename(parent=self.frame,defaultextension='.csv',initialfile='concursinho-desempenho.csv')
        if filename:
            try:self.bank.export_csv(filename,{'Tudo':0,'7 dias':7,'30 dias':30}[self.period.get()],self.subject_value())
            except Exception as error:messagebox.showerror('Exportar',str(error),parent=self.frame)

    def backup(self):
        if self.busy or not self.bank:return
        filename=filedialog.asksaveasfilename(parent=self.frame,defaultextension='.sqlite3',initialfile='concursinho-banco-backup.sqlite3')
        if filename:
            try:
                if Path(filename).resolve()==self.bank.path.resolve():raise ValueError('Escolha outro arquivo para o backup.')
                self.bank.backup(filename);self.status.configure(text='Backup completo salvo, incluindo questões, classificações e respostas.')
            except Exception as error:messagebox.showerror('Backup',str(error),parent=self.frame)

    def on_destroy(self,event):
        # CustomTkinter forwards frame bindings through its internal canvas.
        if self.bank:
            bank,self.bank=self.bank,None
            bank.close()
