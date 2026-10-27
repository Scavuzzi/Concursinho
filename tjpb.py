"""Catálogo local do TJPB; notas e PDFs continuam no cofre do Obsidian."""

import hashlib
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote


EXAM_DATE = date(2027, 1, 24)
CHECKLIST_NAME = "01 - Checklist completo - Desenvolvimento de Sistemas.md"
INDEX_NAME = "03 - Provas anteriores - Índice.md"
CATALOG_NAME = "Provas anteriores/manifesto_downloads.json"
EXAM_INFO = {
    "01_TJRR_2024_FGV": ("TJRR 2024 · Desenvolvimento de Sistemas", "FGV · Tipo 1", 3, None),
    "02_TJAP_2024_FGV": ("TJAP 2024 · Desenvolvimento de Sistemas", "FGV · Tipo 1", 10, None),
    "03_TJRJ_2026_FGV": ("TJRJ 2026 · Analista de Sistemas", "FGV · Tipo 1", 13, None),
    "04_TJSC_2026_FGV": ("TJSC 2026 · Analista de Sistemas", "FGV · Tipo 1", 12, None),
    "05_TJRN_2023_FGV": ("TJRN 2023 · Análise de Sistemas", "FGV · Tipo 1", 2, 1),
    "06_TJDFT_2022_FGV": ("TJDFT 2022 · Análise de Sistemas", "FGV · Tipo 1", 6, 3),
    "07_TJSE_2023_FGV": ("TJSE 2023 · Análise de Sistemas", "FGV · Tipo 1", 2, None),
    "08_TRF1_2024_FGV": ("TRF1 2024 · Análise de Sistemas de Informação", "FGV · Tipo 1", 4, None),
    "09_TJPB_2012_FAPERP": ("TJPB 2012 · Desenvolvimento de Sistemas", "FAPERP · Tipo A · histórico", 29, None),
}


def resolve_tjpb_root(materials_path: Path) -> Path:
    override = os.environ.get("CONCURSINHO_TJPB_PATH", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    # Materiais: Estudos/Concursinho/Materiais. TJPB é uma pasta irmã.
    return materials_path.resolve().parent.parent / "TJPB 2026"


def obsidian_note_uri(path: Path) -> str:
    for parent in path.resolve().parents:
        if (parent / ".obsidian").is_dir():
            relative = path.resolve().relative_to(parent).as_posix()
            return f"obsidian://open?vault={quote(parent.name, safe='')}&file={quote(relative, safe='')}"
    return path.resolve().as_uri()


@dataclass(frozen=True)
class Topic:
    key: str
    group: str
    text: str


@dataclass(frozen=True)
class Exam:
    key: str
    title: str
    description: str
    files: dict[str, Path]
    answer_page: int
    mirror_page: int | None


class TjpbCatalog:
    def __init__(self, root: Path):
        self.root = root
        self.errors = []
        self.topics = []
        self.exams = []
        self.load_topics()
        self.load_exams()

    @property
    def groups(self):
        return list(dict.fromkeys(topic.group for topic in self.topics))

    def load_topics(self):
        try:
            content = (self.root / CHECKLIST_NAME).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            self.errors.append("Checklist não encontrado na pasta TJPB 2026.")
            return
        group = None
        for line in content.splitlines():
            if line.startswith("## "):
                match = re.match(r"^## (\d+)\.\s+(.+)$", line)
                group = match.group(2) if match and 1 <= int(match.group(1)) <= 14 else None
            match = re.match(r"^- \[[ xX]\] (.+)$", line)
            if group and match:
                text = match.group(1)
                identity = unicodedata.normalize("NFC", f"{group}\n{text}")
                key = "topic:" + hashlib.sha256(identity.encode()).hexdigest()[:20]
                self.topics.append(Topic(key, group, text))
        if not self.topics:
            self.errors.append("Nenhum tópico do edital foi encontrado no checklist.")

    def load_exams(self):
        try:
            payload = json.loads((self.root / CATALOG_NAME).read_text(encoding="utf-8"))
            records = payload["files"]
            if not isinstance(records, list):
                raise ValueError("files precisa ser uma lista")
        except (OSError, UnicodeError, ValueError, KeyError, TypeError):
            self.errors.append("Catálogo de provas não encontrado ou inválido.")
            return
        grouped = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            folder, kind = record.get("folder"), record.get("kind")
            if not isinstance(folder, str) or not isinstance(kind, str):
                continue
            if folder not in EXAM_INFO or kind not in {"prova", "gabarito_definitivo", "espelho_discursiva"}:
                continue
            # Reconstituir a partir da pasta atual permite usar o cofre em outro PC.
            # Caminhos absolutos do manifesto não são executados nem usados.
            path = self.root / "Provas anteriores" / folder / f"{kind}.pdf"
            if path.is_file():
                grouped.setdefault(folder, {})[kind] = path
            else:
                self.errors.append(f"Arquivo ausente: {folder}/{kind}.pdf")
        for folder, info in EXAM_INFO.items():
            files = grouped.get(folder, {})
            if "prova" in files:
                self.exams.append(Exam("exam:" + folder, info[0], info[1], files, info[2], info[3]))


class TjpbPanel:
    """Integração visual com os componentes e o Pomodoro existentes."""

    def __init__(self, app, tab, ctk, theme, read_json, write_json, progress_path):
        self.app, self.ctk, self.theme = app, ctk, theme
        self.write_json, self.progress_path = write_json, progress_path
        saved = read_json(progress_path, [])
        self.completed = {key for key in saved if isinstance(key, str)} if isinstance(saved, list) else set()
        self.catalog = TjpbCatalog(resolve_tjpb_root(Path(app.config_manager.values["materials_path"])))
        self.view = ctk.StringVar(value="Conteúdo")
        self.group = ctk.StringVar(value="Todos os blocos")
        self.query = ctk.StringVar()
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(5, weight=1)

        header = ctk.CTkFrame(tab, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="TJPB · Desenvolvimento de Sistemas", font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=theme["text"], anchor="w").grid(row=0, column=0, sticky="w")
        remaining = (EXAM_DATE - date.today()).days
        deadline = f"{remaining} dias para a prova" if remaining >= 0 else "Data prevista da prova já passou"
        ctk.CTkLabel(header, text=f"24/01/2027 · {deadline} · FGV", text_color=theme["muted"],
                     anchor="w").grid(row=1, column=0, sticky="w")

        links = ctk.CTkFrame(tab, fg_color="transparent")
        links.grid(row=1, column=0, padx=14, pady=4, sticky="ew")
        for column, (title, name) in enumerate([
            ("Plano no Obsidian", CHECKLIST_NAME), ("Provas e fontes", INDEX_NAME),
            ("Edital atualizado", "04 - Retificação de 26-10-2026.md"),
        ]):
            ctk.CTkButton(links, text=title, command=lambda n=name: self.open_note(n),
                          **app.button_options("secondary")).grid(row=column // 2, column=column % 2, padx=(0, 8), pady=3)
        ctk.CTkButton(links, text="Atualizar materiais", command=self.reload,
                      **app.button_options("secondary")).grid(row=1, column=1, padx=(0, 8), pady=3)

        controls = ctk.CTkFrame(tab, fg_color=theme["panel"])
        controls.grid(row=2, column=0, padx=14, pady=6, sticky="ew")
        controls.grid_columnconfigure(0, weight=1)
        self.clock = ctk.CTkLabel(controls, text=app.format_time(), font=ctk.CTkFont(size=20, weight="bold"),
                                  text_color=theme["lavender"])
        self.clock.grid(row=0, column=0, padx=12, pady=8, sticky="w")
        ctk.CTkButton(controls, text="Iniciar foco TJPB", width=130, command=self.start_focus,
                      **app.button_options()).grid(row=0, column=1, padx=4)
        ctk.CTkButton(controls, text="Pausar", width=75, command=app.pause_timer,
                      **app.button_options("secondary")).grid(row=0, column=2, padx=4)
        ctk.CTkButton(controls, text="Reiniciar", width=80, command=app.reset_timer,
                      **app.button_options("secondary")).grid(row=0, column=3, padx=(4, 12))

        navigation = ctk.CTkFrame(tab, fg_color="transparent")
        navigation.grid(row=3, column=0, padx=14, pady=4, sticky="ew")
        navigation.grid_columnconfigure(0, weight=1)
        ctk.CTkSegmentedButton(navigation, values=["Conteúdo", "Provas anteriores", "Discursiva"],
                               variable=self.view, command=lambda _: self.render()).grid(row=0, column=0, sticky="w")
        self.group_menu = ctk.CTkOptionMenu(navigation, values=["Todos os blocos"] + self.catalog.groups,
                                           variable=self.group, command=lambda _: self.render(), width=310)
        self.group_menu.grid(row=1, column=0, pady=8, sticky="ew")
        ctk.CTkEntry(navigation, textvariable=self.query, placeholder_text="Buscar assunto ou prova...").grid(
            row=2, column=0, pady=(0, 5), sticky="ew")
        self.query.trace_add("write", lambda *_: self.render())

        self.summary = ctk.CTkLabel(tab, text="", text_color=theme["muted"], anchor="w")
        self.summary.grid(row=4, column=0, padx=16, pady=3, sticky="ew")
        self.list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.list.grid(row=5, column=0, padx=8, pady=4, sticky="nsew")
        self.list.grid_columnconfigure(0, weight=1)
        self.status = ctk.CTkLabel(tab, text="Progresso salvo no aplicativo; as notas continuam no Obsidian.",
                                   text_color=theme["muted"], anchor="w", wraplength=700)
        self.status.grid(row=6, column=0, padx=16, pady=(4, 10), sticky="ew")
        self.render()

    def open_note(self, name):
        import webbrowser
        path = self.catalog.root / name
        if path.is_file():
            webbrowser.open(obsidian_note_uri(path))
        else:
            self.status.configure(text=f"Material não encontrado: {name}")

    def reload(self):
        self.catalog = TjpbCatalog(resolve_tjpb_root(Path(self.app.config_manager.values["materials_path"])))
        self.status.configure(text="Materiais atualizados. Progresso salvo no aplicativo.")
        self.group_menu.configure(values=["Todos os blocos"] + self.catalog.groups)
        if self.group.get() not in self.catalog.groups:
            self.group.set("Todos os blocos")
        self.render()

    def toggle(self, key, value):
        updated = self.completed | {key} if value else self.completed - {key}
        try:
            self.write_json(self.progress_path, sorted(updated))
        except OSError:
            self.status.configure(text="Não foi possível salvar o progresso. Confira a permissão da pasta do aplicativo.")
            self.render()
            return
        self.completed = updated
        self.render()

    def start_focus(self):
        app = self.app
        if app.timer_running:
            self.status.configure(text="Já há um Pomodoro em andamento. Pause ou conclua antes de trocar o foco.")
            return
        if app.current_mode != "Foco" or app.time_left != app.focus_seconds:
            self.status.configure(text="Há uma sessão pausada. Retome na aba Estudo ou use Reiniciar para começar outra.")
            return
        group = self.group.get() if self.view.get() == "Conteúdo" else self.view.get()
        app.timer_subject = f"TJPB · {group}"
        app.start_timer()
        self.status.configure(text=f"Foco iniciado: {group}.")

    def open_pdf(self, path, title):
        # Reutiliza o comando de PDF configurado e o tratamento de falha do app.
        from types import SimpleNamespace
        if not path.is_file():
            self.status.configure(text="PDF não encontrado. Use Atualizar materiais para conferir o acervo.")
            return
        if not self.app.open_pdf(SimpleNamespace(path=path, title=title)):
            self.status.configure(text=f"Não foi possível abrir: {title}")

    def label(self, parent, text, row, bold=False):
        label = self.ctk.CTkLabel(parent, text=text, text_color=self.theme["text"], anchor="w", justify="left",
                                  wraplength=480, font=self.ctk.CTkFont(size=14, weight="bold" if bold else "normal"))
        label.grid(row=row, column=0, padx=12, pady=7, sticky="ew")
        return label

    def render(self):
        for widget in self.list.winfo_children():
            widget.destroy()
        query = self.query.get().strip().casefold()
        topic_done = sum(t.key in self.completed for t in self.catalog.topics)
        exam_done = sum(e.key in self.completed for e in self.catalog.exams)
        self.summary.configure(text=f"Conteúdo: {topic_done}/{len(self.catalog.topics)} tópicos · Provas resolvidas: {exam_done}/{len(self.catalog.exams)}")
        if self.catalog.errors:
            self.status.configure(text=" ".join(self.catalog.errors))
        mode = self.view.get()
        self.group_menu.configure(state="normal" if mode == "Conteúdo" else "disabled")
        if mode == "Discursiva":
            self.render_discursive()
            return
        if mode == "Provas anteriores":
            for row, exam in enumerate(e for e in self.catalog.exams if query in f"{e.title} {e.description}".casefold()):
                self.render_exam(row, exam)
            if not self.list.winfo_children():
                self.label(self.list, "Nenhuma prova encontrada para esta busca.", 0)
            return
        row, previous_group = 0, None
        for topic in self.catalog.topics:
            if self.group.get() not in {"Todos os blocos", topic.group} or query not in f"{topic.group} {topic.text}".casefold():
                continue
            if topic.group != previous_group:
                self.label(self.list, topic.group, row, True)
                row += 1
                previous_group = topic.group
            card = self.ctk.CTkFrame(self.list, fg_color=self.theme["card"])
            card.grid(row=row, column=0, padx=6, pady=3, sticky="ew")
            card.grid_columnconfigure(0, weight=1)
            self.label(card, topic.text, 0)
            variable = self.ctk.BooleanVar(value=topic.key in self.completed)
            self.ctk.CTkCheckBox(card, text="Estudado", width=95, variable=variable,
                                command=lambda k=topic.key, v=variable: self.toggle(k, v.get())).grid(row=1, column=0, padx=12, pady=(0, 10), sticky="w")
            row += 1
        if row == 0:
            self.label(self.list, "Nenhum tópico encontrado. Confira a pasta de materiais ou ajuste a busca.", 0)

    def render_exam(self, row, exam):
        card = self.ctk.CTkFrame(self.list, fg_color=self.theme["card"])
        card.grid(row=row, column=0, padx=6, pady=6, sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        self.label(card, exam.title, 0, True)
        self.label(card, f"{exam.description} · Gabarito na página {exam.answer_page} do PDF", 1)
        actions = self.ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=2, column=0, padx=12, pady=(0, 10), sticky="w")
        for column, (kind, title) in enumerate([("prova", "Abrir prova"), ("gabarito_definitivo", "Gabarito"), ("espelho_discursiva", "Espelho")]):
            if kind in exam.files:
                self.ctk.CTkButton(actions, text=title, width=100, command=lambda p=exam.files[kind], t=title: self.open_pdf(p, t),
                                   **self.app.button_options("secondary")).grid(row=0, column=column, padx=(0, 6), pady=3)
        variable = self.ctk.BooleanVar(value=exam.key in self.completed)
        self.ctk.CTkCheckBox(card, text="Prova resolvida", variable=variable,
                            command=lambda k=exam.key, v=variable: self.toggle(k, v.get())).grid(row=3, column=0, padx=12, pady=(0, 12), sticky="w")

    def render_discursive(self):
        text = (
            "Uma questão com 30 linhas, valendo 40 pontos. A correção depende da classificação na objetiva.\n\n"
            "Treino sugerido: escrever uma resposta por semana, cronometrar, responder todos os comandos e revisar precisão técnica, clareza e Português.\n\n"
            "Use as discursivas do TJRN e TJDFT e consulte os espelhos depois de responder. São critérios daqueles concursos; os temas não são previsão da prova do TJPB.\n\n"
            "Exercícios possíveis: justificar arquitetura, definir requisitos e critérios de aceitação, explicar autenticação, propor testes e discutir dados pessoais e IA.\n\n"
            "Na visão Provas anteriores, cada caderno tem seu gabarito separado e, quando disponível, seu espelho. O plano completo no Obsidian inclui a sugestão de ciclo semanal."
        )
        self.label(self.list, "Treino de discursiva", 0, True)
        self.label(self.list, text, 1)
