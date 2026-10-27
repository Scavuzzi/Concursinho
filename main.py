import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
import webbrowser
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import customtkinter as ctk

from tjpb import TjpbPanel

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageTk = None

APP_NAME = "Painel de Estudos"
APP_ID = "concursinho-pomodoro"
APP_WM_CLASS = "ConcursinhoPomodoro"
os.environ["RESOURCE_NAME"] = APP_WM_CLASS

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

BASE_PATH = Path(__file__).resolve().parent
ENV_FILE = BASE_PATH / ".env"
PROGRESSO_FILE = BASE_PATH / "progresso.json"
CONFIG_FILE = BASE_PATH / "config.json"
HISTORY_FILE = BASE_PATH / "historico.json"
TJPB_PROGRESS_FILE = BASE_PATH / "tjpb-progresso.json"
TRAY_LOG_FILE = BASE_PATH / "tray.log"
ASSETS_PATH = BASE_PATH / "assets"
APP_ICON_FILE = ASSETS_PATH / "app-icon.png"
TRAY_ICON_FILE = ASSETS_PATH / "tray-icon.png"
TRAY_HELPER_FILE = BASE_PATH / "tray_helper.py"
OBSIDIAN_NOTE_URI = (
    "obsidian://open?vault=Segundo%20C%C3%A9rebro&"
    "file=Projetos%2FEstudos%2FConcursinho"
)


def load_local_env(path: Path) -> None:
    if not path.exists():
        return

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_local_env(ENV_FILE)


DEFAULT_CONFIG = {
    "focus_minutes": 25,
    "break_minutes": 5,
    "pdf_command": "auto",
    "materials_path": str(BASE_PATH / "Materiais"),
}

AUTO_PDF_COMMANDS = {"", "auto", "default", "sistema", "xdg-open {file}"}

THEME = {
    "bg": "#1a1b26",
    "panel": "#24283b",
    "panel_alt": "#1f2335",
    "card": "#292e42",
    "card_hover": "#343a52",
    "border": "#414868",
    "text": "#c0caf5",
    "muted": "#9aa5ce",
    "subtle": "#565f89",
    "blue": "#7aa2f7",
    "cyan": "#7dcfff",
    "green": "#9ece6a",
    "purple": "#bb9af7",
    "purple_dark": "#7c3aed",
    "lavender": "#c4b5fd",
    "magenta": "#f0a6ca",
    "yellow": "#e0af68",
    "red": "#f7768e",
}


def read_json(path: Path, fallback):
    backup_path = path.with_name(f"{path.name}.bak")
    for candidate in (path, backup_path):
        if not candidate.exists():
            continue

        try:
            with candidate.open("r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue

    return fallback


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    backup_path = path.with_name(f"{path.name}.bak")

    try:
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
            file.flush()
            os.fsync(file.fileno())

        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as current_file:
                    json.load(current_file)
                shutil.copy2(path, backup_path)
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass

        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def log_tray(message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    try:
        with TRAY_LOG_FILE.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


@dataclass(frozen=True)
class PdfItem:
    path: Path
    subject: str
    title: str
    kind: str
    number: int | None
    course_code: str | None
    file_hash: str | None

    @property
    def key(self) -> str:
        return str(self.path)

    @property
    def badge(self) -> str:
        if self.kind == "simulado":
            return "Simulado"
        if self.kind == "aula":
            return "Aula"
        return "PDF"

    @property
    def meta(self) -> str:
        details = []
        if self.course_code:
            details.append(f"Curso {self.course_code}")
        if self.file_hash:
            details.append(f"ID {self.file_hash.upper()}")
        details.append(self.path.name)
        return "  |  ".join(details)

    def matches(self, query: str) -> bool:
        if not query:
            return True

        haystack = f"{self.subject} {self.title} {self.kind} {self.meta}".casefold()
        return query.casefold() in haystack


class NotificationService:
    @staticmethod
    def send(title: str, message: str) -> None:
        try:
            subprocess.run(["notify-send", "-i", str(APP_ICON_FILE), title, message], check=False)
        except Exception:
            pass


class AppIcon:
    @staticmethod
    def ensure_file(color: str = THEME["purple"]) -> Path | None:
        if Image is None or ImageDraw is None:
            return None

        ASSETS_PATH.mkdir(exist_ok=True)
        image = AppIcon.build_image(color)
        image.save(APP_ICON_FILE)
        return APP_ICON_FILE

    @staticmethod
    def build_image(color: str):
        image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.ellipse((18, 22, 110, 114), fill=THEME["panel"], outline=color, width=8)
        draw.arc((32, 36, 96, 100), start=105, end=405, fill=THEME["lavender"], width=9)
        draw.rounded_rectangle((54, 8, 74, 30), radius=7, fill=color)
        draw.rounded_rectangle((45, 15, 83, 25), radius=5, fill=color)

        font = ImageFont.load_default()
        if ImageFont is not None:
            try:
                font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
            except Exception:
                font = ImageFont.load_default()

        text = "25"
        box = draw.textbbox((0, 0), text, font=font)
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]
        draw.text(
            ((128 - text_width) / 2, (128 - text_height) / 2 + 4),
            text,
            fill=THEME["text"],
            font=font,
        )
        return image

    @staticmethod
    def ensure_tray_file(color: str = THEME["lavender"]) -> Path | None:
        if Image is None or ImageDraw is None:
            return None

        ASSETS_PATH.mkdir(exist_ok=True)
        image = AppIcon.build_tray_image(color)
        image.save(TRAY_ICON_FILE)
        return TRAY_ICON_FILE

    @staticmethod
    def build_tray_image(color: str, size: int = 64):
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        scale = size / 32

        # A tray icon has only a few pixels. Use a simple high-contrast stopwatch,
        # without a filled square background, so KDE/Xfce panels do not squash it
        # into a colored block.
        def xy(values):
            return tuple(round(v * scale) for v in values)

        draw.ellipse(xy((4, 6, 28, 30)), outline=color, width=max(2, round(4 * scale)))
        draw.arc(xy((4, 6, 28, 30)), start=110, end=365, fill=THEME["green"], width=max(2, round(3 * scale)))
        draw.rounded_rectangle(xy((12, 1, 20, 8)), radius=max(1, round(2 * scale)), fill=color)
        draw.line(xy((16, 17, 16, 10)), fill=THEME["text"], width=max(1, round(2 * scale)))
        draw.line(xy((16, 17, 22, 20)), fill=THEME["text"], width=max(1, round(2 * scale)))
        draw.ellipse(xy((13, 14, 19, 20)), fill=THEME["text"])
        return image


class TrayIndicator:
    def __init__(self, app: "PomodoroApp") -> None:
        self.app = app
        self.process = None
        self.fifo_path = Path(f"/tmp/{APP_ID}-{os.getpid()}.fifo")
        self.reader_thread = None
        self.stderr_thread = None
        self.available = TRAY_HELPER_FILE.exists()

    def start(self) -> None:
        if not self.available:
            log_tray("Tray indisponível: tray_helper.py não encontrado.")
            return

        if self.start_qt_tray():
            self.app.after(900, self.ensure_qt_tray_is_alive)
            return

        log_tray("Tray indisponível: helper PySide6 falhou ao iniciar.")

    def start_qt_tray(self) -> bool:
        tray_icon = self.prepare_tray_icon(THEME["lavender"])
        if tray_icon is None:
            log_tray("Qt tray não iniciou: não foi possível gerar ícone.")
            return False

        try:
            if self.fifo_path.exists():
                self.fifo_path.unlink()
            os.mkfifo(self.fifo_path)
        except Exception:
            log_tray("Qt tray não iniciou: não foi possível criar FIFO.")
            return False

        args = [
            sys.executable,
            str(TRAY_HELPER_FILE),
            "--icon",
            str(tray_icon),
            "--fifo",
            str(self.fifo_path),
            "--tooltip",
            APP_NAME,
        ]

        try:
            self.process = subprocess.Popen(
                args,
                stdin=subprocess.PIPE,
                text=True,
                cwd=BASE_PATH,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            self.reader_thread = threading.Thread(target=self.read_fifo_commands, daemon=True)
            self.reader_thread.start()
            self.stderr_thread = threading.Thread(target=self.log_qt_tray_stderr, daemon=True)
            self.stderr_thread.start()
            log_tray(f"Tray ativa via PySide6/QSystemTrayIcon. Ícone: {tray_icon}")
            return True
        except Exception:
            self.cleanup_fifo()
            self.process = None
            log_tray("Qt tray falhou ao iniciar processo.")
            return False

    def log_qt_tray_stderr(self) -> None:
        if not self.process or not self.process.stderr:
            return

        try:
            for line in self.process.stderr:
                text = line.strip()
                if text:
                    log_tray(f"qt tray stderr: {text}")
        except Exception:
            pass

    def prepare_tray_icon(self, color: str) -> Path | None:
        tray_icon = AppIcon.ensure_tray_file(color)
        return tray_icon

    def ensure_qt_tray_is_alive(self) -> None:
        if self.process and self.process.poll() is None:
            return

        self.cleanup_fifo()
        self.process = None
        log_tray("Qt tray encerrou após iniciar.")

    def read_fifo_commands(self) -> None:
        while True:
            try:
                with self.fifo_path.open("r", encoding="utf-8") as fifo:
                    command = fifo.read().strip()
            except Exception:
                break

            if command == "show":
                self.show_window()
            elif command == "toggle":
                self.toggle_timer()
            elif command == "quit":
                self.quit_app()
                break

    def send_helper(self, command: str) -> None:
        if not self.process or not self.process.stdin:
            return

        try:
            self.process.stdin.write(command + "\n")
            self.process.stdin.flush()
        except Exception:
            pass

    def update(self, status: str, color: str) -> None:
        self.send_helper(f"tooltip:{status}")

    def stop(self) -> None:
        if self.process:
            self.send_helper("quit")
            try:
                self.process.terminate()
            except Exception:
                pass
            self.process = None
        self.cleanup_fifo()

    def cleanup_fifo(self) -> None:
        try:
            if self.fifo_path.exists():
                self.fifo_path.unlink()
        except Exception:
            pass

    def show_window(self) -> None:
        self.app.after(0, self.app.restore_window)

    def toggle_timer(self) -> None:
        self.app.after(0, self.app.toggle_timer)

    def quit_app(self) -> None:
        self.app.after(0, self.app.close_app)


class ConfigManager:
    def __init__(self) -> None:
        self.values = self.load()

    def load(self) -> dict:
        data = read_json(CONFIG_FILE, {})
        config = DEFAULT_CONFIG | data
        env_materials_path = os.environ.get("CONCURSINHO_MATERIAIS_PATH", "").strip()
        if env_materials_path:
            config["materials_path"] = env_materials_path
        config["focus_minutes"] = self.coerce_minutes(config.get("focus_minutes"), DEFAULT_CONFIG["focus_minutes"])
        config["break_minutes"] = self.coerce_minutes(config.get("break_minutes"), DEFAULT_CONFIG["break_minutes"])
        config["pdf_command"] = self.normalize_pdf_command(config.get("pdf_command"))
        config["materials_path"] = self.normalize_path(config.get("materials_path"))
        return config

    def save(self, focus_minutes: int, break_minutes: int, pdf_command: str, materials_path: str) -> None:
        self.values = {
            "focus_minutes": self.coerce_minutes(focus_minutes, DEFAULT_CONFIG["focus_minutes"]),
            "break_minutes": self.coerce_minutes(break_minutes, DEFAULT_CONFIG["break_minutes"]),
            "pdf_command": self.normalize_pdf_command(pdf_command),
            "materials_path": self.normalize_path(materials_path),
        }
        write_json(CONFIG_FILE, self.values)

    @staticmethod
    def coerce_minutes(value, fallback: int) -> int:
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(1, min(minutes, 180))

    @staticmethod
    def normalize_path(value) -> str:
        path_text = str(value or "").strip() or DEFAULT_CONFIG["materials_path"]
        path = Path(path_text).expanduser()
        if not path.is_absolute():
            path = BASE_PATH / path
        return str(path.resolve())

    @staticmethod
    def normalize_pdf_command(value) -> str:
        command = str(value or "").strip()
        if command.casefold() in AUTO_PDF_COMMANDS:
            return DEFAULT_CONFIG["pdf_command"]
        return command


class HistoryManager:
    def __init__(self) -> None:
        self.data = read_json(HISTORY_FILE, {"pomodoros": [], "completion_events": []})
        self.data.setdefault("pomodoros", [])
        self.data.setdefault("completion_events", [])

    def save(self) -> None:
        write_json(HISTORY_FILE, self.data)

    def add_completion_event(self, pdf: PdfItem, action: str) -> None:
        self.data["completion_events"].append(
            {
                "date": date.today().isoformat(),
                "at": datetime.now().isoformat(timespec="seconds"),
                "action": action,
                "subject": pdf.subject,
                "pdf_key": pdf.key,
                "title": pdf.title,
            }
        )
        self.save()

    def add_pomodoro(self, subject: str | None, minutes: int) -> None:
        self.data["pomodoros"].append(
            {
                "date": date.today().isoformat(),
                "ended_at": datetime.now().isoformat(timespec="seconds"),
                "subject": subject or "Sem disciplina",
                "minutes": minutes,
            }
        )
        self.save()

    def completed_since(self, completed: set[str], days: int) -> int:
        cutoff = date.today() - timedelta(days=days - 1)
        pdfs = set()
        for event in self.data["completion_events"]:
            if event.get("action") != "completed":
                continue
            event_date = self.parse_date(event.get("date"))
            pdf_key = event.get("pdf_key")
            if event_date and event_date >= cutoff and pdf_key in completed:
                pdfs.add(pdf_key)
        return len(pdfs)

    def pomodoro_stats(self, days: int) -> tuple[int, int]:
        cutoff = date.today() - timedelta(days=days - 1)
        sessions = 0
        minutes = 0
        for item in self.data["pomodoros"]:
            item_date = self.parse_date(item.get("date"))
            if item_date and item_date >= cutoff:
                sessions += 1
                minutes += int(item.get("minutes") or 0)
        return sessions, minutes

    @staticmethod
    def parse_date(value: str | None) -> date | None:
        try:
            return date.fromisoformat(value or "")
        except ValueError:
            return None


class StudyManager:
    PDF_PATTERN = re.compile(
        r"curso-(?P<course>\d+)-(?P<kind>aula|simulado)-(?P<number>\d+)-(?P<hash>[a-z0-9]+)-completo\.pdf$",
        re.IGNORECASE,
    )

    def __init__(self, materials_path: Path) -> None:
        self.materials_path = materials_path
        self.completed = self.load_progress()
        self.structure = self.scan_materials()

    def load_progress(self) -> set[str]:
        data = read_json(PROGRESSO_FILE, [])
        return set(data if isinstance(data, list) else [])

    def save_progress(self) -> None:
        write_json(PROGRESSO_FILE, sorted(self.completed))

    def scan_materials(self) -> dict[str, list[PdfItem]]:
        if not self.materials_path.exists():
            return {}

        structure = {}
        for folder in sorted(self.materials_path.iterdir(), key=lambda item: item.name.casefold()):
            if not folder.is_dir():
                continue

            subject = self.clean_subject_name(folder.name)
            pdfs = [
                self.build_pdf_item(pdf, subject)
                for pdf in folder.iterdir()
                if pdf.suffix.casefold() == ".pdf" and not pdf.name.startswith(".")
            ]
            if pdfs:
                structure[subject] = sorted(pdfs, key=self.sort_pdf)

        return structure

    def build_pdf_item(self, path: Path, subject: str) -> PdfItem:
        match = self.PDF_PATTERN.match(path.name)
        if not match:
            return PdfItem(
                path=path,
                subject=subject,
                title=path.stem.replace("-", " ").title(),
                kind="pdf",
                number=None,
                course_code=None,
                file_hash=None,
            )

        kind = match.group("kind").lower()
        number = int(match.group("number"))
        title = f"{kind.capitalize()} {number:02d}"
        return PdfItem(
            path=path,
            subject=subject,
            title=title,
            kind=kind,
            number=number,
            course_code=match.group("course"),
            file_hash=match.group("hash"),
        )

    def clean_subject_name(self, folder_name: str) -> str:
        name = folder_name.replace(" - 2024", "")
        name = name.replace("(Analista de TI - Desenvolvimento de Software) ", "")
        name = name.replace("Passo Estratégico de ", "")
        name = name.replace("Estratégico de ", "")
        return name.strip()

    def all_pdfs(self) -> list[PdfItem]:
        return [pdf for pdfs in self.structure.values() for pdf in pdfs]

    def simulados(self) -> list[PdfItem]:
        return [pdf for pdf in self.all_pdfs() if pdf.kind == "simulado"]

    def sort_pdf(self, item: PdfItem) -> tuple[int, int, str]:
        kind_order = {"aula": 0, "simulado": 1, "pdf": 2}
        number = item.number if item.number is not None else 9999
        return (kind_order.get(item.kind, 9), number, item.path.name.casefold())

    def subject_stats(self, subject: str) -> tuple[int, int, float]:
        pdfs = self.structure.get(subject, [])
        total = len(pdfs)
        done = sum(1 for pdf in pdfs if pdf.key in self.completed)
        percent = done / total if total else 0
        return done, total, percent

    def overall_stats(self) -> tuple[int, int, float]:
        pdfs = self.all_pdfs()
        total = len(pdfs)
        done = sum(1 for pdf in pdfs if pdf.key in self.completed)
        percent = done / total if total else 0
        return done, total, percent

    def next_recommended(self, subject: str | None = None) -> PdfItem | None:
        groups = [self.structure.get(subject, [])] if subject else self.structure.values()
        for kind in ("aula", "pdf", "simulado"):
            for pdfs in groups:
                for pdf in pdfs:
                    if pdf.kind == kind and pdf.key not in self.completed:
                        return pdf
        return None


class PomodoroApp(ctk.CTk):
    def __init__(self) -> None:
        os.environ["RESOURCE_NAME"] = APP_WM_CLASS
        super().__init__(className=APP_WM_CLASS)

        self.config_manager = ConfigManager()
        self.history = HistoryManager()
        self.sm = StudyManager(Path(self.config_manager.values["materials_path"]))
        self.selected_subject = next(iter(self.sm.structure), None)
        self.subject_buttons: dict[str, ctk.CTkFrame] = {}

        self.focus_seconds = self.config_manager.values["focus_minutes"] * 60
        self.break_seconds = self.config_manager.values["break_minutes"] * 60
        self.time_left = self.focus_seconds
        self.timer_running = False
        self.current_mode = "Foco"
        self.timer_subject = None
        self.tray = TrayIndicator(self)
        self.window_icon = None

        self.subject_search_var = ctk.StringVar()
        self.pdf_search_var = ctk.StringVar()
        self.review_search_var = ctk.StringVar()
        self.focus_var = ctk.StringVar(value=str(self.config_manager.values["focus_minutes"]))
        self.break_var = ctk.StringVar(value=str(self.config_manager.values["break_minutes"]))
        self.command_var = ctk.StringVar(value=self.config_manager.values["pdf_command"])
        self.materials_var = ctk.StringVar(value=self.config_manager.values["materials_path"])

        self.configure(fg_color=THEME["bg"])
        self.title(f"{self.format_time()} Foco | {APP_NAME}")
        self.configure_window_identity()
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self.grid_columnconfigure(0, minsize=320)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_main_content()
        self.bind_variable_updates()
        self.refresh_screen()
        self.tray.start()
        self.update_timer_visuals()
        self.tick_timer()

    def configure_window_identity(self) -> None:
        icon_file = AppIcon.ensure_file()
        if icon_file is not None:
            try:
                self.window_icon = ctk.CTkImage(light_image=Image.open(icon_file), dark_image=Image.open(icon_file))
                tk_icon = ImageTk.PhotoImage(Image.open(icon_file))
                self.iconphoto(True, tk_icon)
                self._tk_icon = tk_icon
            except Exception:
                pass

        try:
            self.tk.call("wm", "class", self._w, APP_WM_CLASS)
        except Exception:
            pass

    def bind_variable_updates(self) -> None:
        self.subject_search_var.trace_add("write", lambda *_: self.refresh_sidebar())
        self.pdf_search_var.trace_add("write", lambda *_: self.refresh_pdf_list())
        self.review_search_var.trace_add("write", lambda *_: self.refresh_review_list())

    def button_options(self, variant: str = "primary") -> dict:
        styles = {
            "primary": (THEME["purple"], THEME["lavender"], THEME["bg"]),
            "secondary": (THEME["panel_alt"], THEME["card_hover"], THEME["text"]),
            "danger": (THEME["red"], THEME["magenta"], THEME["bg"]),
            "subtle": (THEME["card"], THEME["card_hover"], THEME["text"]),
        }
        fg, hover, text = styles[variant]
        return {
            "fg_color": fg,
            "hover_color": hover,
            "text_color": text,
            "border_width": 1,
            "border_color": THEME["border"],
        }

    def create_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(self, width=320, corner_radius=0, fg_color=THEME["panel_alt"])
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(3, weight=1)
        self.sidebar.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            self.sidebar,
            text="Plano de Ataque",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        title.grid(row=0, column=0, padx=22, pady=(24, 4), sticky="ew")

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="Tokyo Night edition",
            text_color=THEME["lavender"],
            anchor="w",
        )
        subtitle.grid(row=1, column=0, padx=22, pady=(0, 14), sticky="ew")

        self.subject_search = ctk.CTkEntry(
            self.sidebar,
            textvariable=self.subject_search_var,
            placeholder_text="Filtrar disciplina...",
            fg_color=THEME["panel"],
            border_color=THEME["border"],
            text_color=THEME["text"],
            placeholder_text_color=THEME["subtle"],
        )
        self.subject_search.grid(row=2, column=0, padx=16, pady=(0, 12), sticky="ew")

        self.subject_list = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.subject_list.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.subject_list.grid_columnconfigure(0, weight=1)

        self.stats_card = self.create_side_card(row=4)
        self.today_stat = self.side_stat_label(self.stats_card, "Hoje: 0 PDFs | 0 pomodoros")
        self.today_stat.grid(row=0, column=0, padx=14, pady=(12, 2), sticky="ew")
        self.week_stat = self.side_stat_label(self.stats_card, "Semana: 0 PDFs | 0 min")
        self.week_stat.grid(row=1, column=0, padx=14, pady=2, sticky="ew")
        self.total_stat = self.side_stat_label(self.stats_card, "Total: 0/0 PDFs")
        self.total_stat.grid(row=2, column=0, padx=14, pady=(2, 12), sticky="ew")

        self.overall_card = self.create_side_card(row=5)
        self.overall_label = ctk.CTkLabel(
            self.overall_card,
            text="Progresso geral",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        self.overall_label.grid(row=0, column=0, padx=14, pady=(12, 2), sticky="ew")

        self.overall_progress = ctk.CTkProgressBar(
            self.overall_card,
            height=10,
            progress_color=THEME["purple"],
            fg_color=THEME["border"],
        )
        self.overall_progress.grid(row=1, column=0, padx=14, pady=6, sticky="ew")

        self.overall_numbers = ctk.CTkLabel(
            self.overall_card,
            text="0/0 PDFs",
            text_color=THEME["muted"],
            anchor="w",
        )
        self.overall_numbers.grid(row=2, column=0, padx=14, pady=(0, 12), sticky="ew")

        notes_button = ctk.CTkButton(
            self.sidebar,
            text="Abrir caderno no Obsidian",
            command=self.open_obsidian_notebook,
            **self.button_options("secondary"),
        )
        notes_button.grid(row=6, column=0, padx=16, pady=(0, 16), sticky="ew")

    def create_side_card(self, row: int) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self.sidebar,
            corner_radius=8,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["border"],
        )
        card.grid(row=row, column=0, padx=16, pady=(4, 12), sticky="ew")
        card.grid_columnconfigure(0, weight=1)
        return card

    def side_stat_label(self, parent, text: str):
        return ctk.CTkLabel(parent, text=text, text_color=THEME["muted"], anchor="w")

    def create_main_content(self) -> None:
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.grid(row=0, column=1, padx=22, pady=22, sticky="nsew")
        self.main.grid_columnconfigure(0, weight=1)
        self.main.grid_rowconfigure(0, weight=1)

        self.tabs = ctk.CTkTabview(
            self.main,
            corner_radius=8,
            fg_color=THEME["panel_alt"],
            segmented_button_fg_color=THEME["panel"],
            segmented_button_selected_color=THEME["purple"],
            segmented_button_selected_hover_color=THEME["lavender"],
            segmented_button_unselected_color=THEME["panel"],
            segmented_button_unselected_hover_color=THEME["card_hover"],
            text_color=THEME["text"],
        )
        self.tabs.grid(row=0, column=0, sticky="nsew")

        self.study_tab = self.tabs.add("Estudo")
        self.review_tab = self.tabs.add("Revisão")
        self.tjpb_tab = self.tabs.add("TJPB 2026")
        self.settings_tab = self.tabs.add("Configurações")

        self.create_study_tab()
        self.create_review_tab()
        self.create_settings_tab()
        self.tjpb_panel = TjpbPanel(
            self, self.tjpb_tab, ctk, THEME, read_json, write_json, TJPB_PROGRESS_FILE
        )
        self.tabs.set("TJPB 2026")

    def create_study_tab(self) -> None:
        self.study_tab.grid_columnconfigure(0, weight=1)
        self.study_tab.grid_rowconfigure(2, weight=1)

        self.top_row = ctk.CTkFrame(self.study_tab, fg_color="transparent")
        self.top_row.grid(row=0, column=0, padx=12, pady=(12, 6), sticky="ew")
        self.top_row.grid_columnconfigure(0, weight=1)
        self.top_row.grid_columnconfigure(1, minsize=360)

        self.next_card = ctk.CTkFrame(
            self.top_row,
            corner_radius=8,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["purple"],
        )
        self.next_card.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")
        self.next_card.grid_columnconfigure(0, weight=1)

        self.next_label = ctk.CTkLabel(
            self.next_card,
            text="Próxima aula recomendada",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME["lavender"],
            anchor="w",
        )
        self.next_label.grid(row=0, column=0, padx=14, pady=(10, 0), sticky="ew")

        self.next_title = ctk.CTkLabel(
            self.next_card,
            text="Nenhuma recomendação disponível",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        self.next_title.grid(row=1, column=0, padx=14, pady=(2, 0), sticky="ew")

        self.next_meta = ctk.CTkLabel(self.next_card, text="", text_color=THEME["muted"], anchor="w")
        self.next_meta.grid(row=2, column=0, padx=14, pady=(0, 10), sticky="ew")

        self.next_open_button = ctk.CTkButton(
            self.next_card,
            text="Estudar agora",
            width=118,
            command=self.study_recommended,
            **self.button_options("primary"),
        )
        self.next_open_button.grid(row=0, column=1, rowspan=3, padx=(8, 14), pady=14, sticky="e")

        self.timer = ctk.CTkFrame(
            self.top_row,
            corner_radius=8,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.timer.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")
        self.timer.grid_columnconfigure(0, weight=1)
        self.timer.grid_columnconfigure((1, 2, 3), weight=1)

        self.mode_label = ctk.CTkLabel(
            self.timer,
            text="FOCO",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME["purple"],
            anchor="w",
        )
        self.mode_label.grid(row=0, column=0, padx=14, pady=(10, 0), sticky="ew")

        self.clock_label = ctk.CTkLabel(
            self.timer,
            text=self.format_time(),
            font=ctk.CTkFont(size=34, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        self.clock_label.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")

        self.start_button = ctk.CTkButton(
            self.timer,
            text="Iniciar",
            width=86,
            command=self.start_timer,
            **self.button_options("primary"),
        )
        self.start_button.grid(row=0, column=1, rowspan=2, padx=(4, 4), pady=18, sticky="ew")

        self.pause_button = ctk.CTkButton(
            self.timer,
            text="Pausar",
            width=86,
            command=self.pause_timer,
            **self.button_options("secondary"),
        )
        self.pause_button.grid(row=0, column=2, rowspan=2, padx=4, pady=18, sticky="ew")

        self.reset_button = ctk.CTkButton(
            self.timer,
            text="Resetar",
            width=86,
            command=self.reset_timer,
            **self.button_options("danger"),
        )
        self.reset_button.grid(row=0, column=3, rowspan=2, padx=(4, 14), pady=18, sticky="ew")

        self.header = ctk.CTkFrame(
            self.study_tab,
            corner_radius=8,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.header.grid(row=1, column=0, padx=12, pady=6, sticky="ew")
        self.header.grid_columnconfigure(0, weight=1)
        self.header.grid_columnconfigure(1, minsize=180)

        self.subject_title = ctk.CTkLabel(
            self.header,
            text="Sem materiais",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
            justify="left",
            wraplength=680,
        )
        self.subject_title.grid(row=0, column=0, padx=18, pady=(12, 0), sticky="ew")

        self.subject_summary = ctk.CTkLabel(
            self.header,
            text="Configure a pasta dos PDFs para começar.",
            text_color=THEME["muted"],
            anchor="w",
            justify="left",
        )
        self.subject_summary.grid(row=1, column=0, padx=18, pady=(0, 12), sticky="ew")

        self.subject_progress = ctk.CTkProgressBar(
            self.header,
            height=12,
            progress_color=THEME["purple"],
            fg_color=THEME["border"],
        )
        self.subject_progress.grid(row=0, column=1, padx=18, pady=(16, 4), sticky="ew")

        self.subject_percent = ctk.CTkLabel(
            self.header,
            text="0%",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=THEME["lavender"],
            anchor="center",
        )
        self.subject_percent.grid(row=1, column=1, padx=18, pady=(0, 12), sticky="ew")

        self.pdf_panel = ctk.CTkFrame(
            self.study_tab,
            corner_radius=8,
            fg_color=THEME["panel_alt"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.pdf_panel.grid(row=2, column=0, padx=12, pady=(6, 12), sticky="nsew")
        self.pdf_panel.grid_columnconfigure(0, weight=1)
        self.pdf_panel.grid_rowconfigure(1, weight=1)

        self.pdf_search = ctk.CTkEntry(
            self.pdf_panel,
            textvariable=self.pdf_search_var,
            placeholder_text="Buscar aula, simulado, curso ou hash...",
            fg_color=THEME["panel"],
            border_color=THEME["border"],
            text_color=THEME["text"],
            placeholder_text_color=THEME["subtle"],
        )
        self.pdf_search.grid(row=0, column=0, padx=12, pady=12, sticky="ew")

        self.pdf_list = ctk.CTkScrollableFrame(self.pdf_panel, corner_radius=8, fg_color="transparent")
        self.pdf_list.grid(row=1, column=0, padx=4, pady=(0, 8), sticky="nsew")
        self.pdf_list.grid_columnconfigure(0, weight=1)

    def create_review_tab(self) -> None:
        self.review_tab.grid_columnconfigure(0, weight=1)
        self.review_tab.grid_rowconfigure(2, weight=1)

        title = ctk.CTkLabel(
            self.review_tab,
            text="Revisão e Simulados",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        title.grid(row=0, column=0, padx=16, pady=(18, 4), sticky="ew")

        self.review_summary = ctk.CTkLabel(
            self.review_tab,
            text="Simulados separados das aulas para revisão rápida.",
            text_color=THEME["muted"],
            anchor="w",
        )
        self.review_summary.grid(row=1, column=0, padx=16, pady=(0, 10), sticky="ew")

        self.review_panel = ctk.CTkFrame(
            self.review_tab,
            corner_radius=8,
            fg_color=THEME["panel_alt"],
            border_width=1,
            border_color=THEME["border"],
        )
        self.review_panel.grid(row=2, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.review_panel.grid_columnconfigure(0, weight=1)
        self.review_panel.grid_rowconfigure(1, weight=1)

        self.review_search = ctk.CTkEntry(
            self.review_panel,
            textvariable=self.review_search_var,
            placeholder_text="Filtrar simulado ou disciplina...",
            fg_color=THEME["panel"],
            border_color=THEME["border"],
            text_color=THEME["text"],
            placeholder_text_color=THEME["subtle"],
        )
        self.review_search.grid(row=0, column=0, padx=12, pady=12, sticky="ew")

        self.review_list = ctk.CTkScrollableFrame(self.review_panel, corner_radius=8, fg_color="transparent")
        self.review_list.grid(row=1, column=0, padx=4, pady=(0, 8), sticky="nsew")
        self.review_list.grid_columnconfigure(0, weight=1)

    def create_settings_tab(self) -> None:
        self.settings_tab.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(
            self.settings_tab,
            corner_radius=8,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["border"],
        )
        container.grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        container.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            container,
            text="Configurações",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 14), sticky="ew")

        self.add_setting_row(container, 1, "Foco (min)", self.focus_var)
        self.add_setting_row(container, 2, "Pausa (min)", self.break_var)
        self.add_setting_row(container, 3, "Comando PDF", self.command_var)
        self.add_setting_row(container, 4, "Pasta dos PDFs", self.materials_var)

        hint = ctk.CTkLabel(
            container,
            text='Use "auto" para abrir com o app padrao do sistema. Comando customizado aceita {file}.',
            text_color=THEME["muted"],
            anchor="w",
        )
        hint.grid(row=5, column=0, columnspan=2, padx=18, pady=(4, 12), sticky="ew")

        self.settings_status = ctk.CTkLabel(container, text="", text_color=THEME["lavender"], anchor="w")
        self.settings_status.grid(row=6, column=0, padx=18, pady=(0, 18), sticky="ew")

        save_button = ctk.CTkButton(
            container,
            text="Salvar configurações",
            command=self.save_settings,
            **self.button_options("primary"),
        )
        save_button.grid(row=6, column=1, padx=18, pady=(0, 18), sticky="e")

        desktop_card = ctk.CTkFrame(
            self.settings_tab,
            corner_radius=8,
            fg_color=THEME["panel"],
            border_width=1,
            border_color=THEME["border"],
        )
        desktop_card.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="ew")
        desktop_card.grid_columnconfigure(0, weight=1)

        desktop_title = ctk.CTkLabel(
            desktop_card,
            text="Integração com EndeavourOS",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        desktop_title.grid(row=0, column=0, padx=18, pady=(16, 4), sticky="ew")

        desktop_text = ctk.CTkLabel(
            desktop_card,
            text=f"WM_CLASS: {APP_WM_CLASS}  |  .desktop: concursinho-pomodoro.desktop",
            text_color=THEME["muted"],
            anchor="w",
        )
        desktop_text.grid(row=1, column=0, padx=18, pady=(0, 16), sticky="ew")

    def add_setting_row(self, parent, row: int, label: str, variable: ctk.StringVar) -> None:
        label_widget = ctk.CTkLabel(parent, text=label, text_color=THEME["text"], anchor="w")
        label_widget.grid(row=row, column=0, padx=18, pady=8, sticky="w")
        entry = ctk.CTkEntry(
            parent,
            textvariable=variable,
            fg_color=THEME["panel_alt"],
            border_color=THEME["border"],
            text_color=THEME["text"],
        )
        entry.grid(row=row, column=1, padx=18, pady=8, sticky="ew")

    def refresh_screen(self) -> None:
        self.refresh_sidebar()
        self.refresh_header()
        self.refresh_recommended()
        self.refresh_pdf_list()
        self.refresh_review_list()
        self.refresh_stats()

    def refresh_sidebar(self) -> None:
        for widget in self.subject_list.winfo_children():
            widget.destroy()
        self.subject_buttons.clear()

        query = self.subject_search_var.get().strip().casefold()
        for subject in self.sm.structure:
            if query and query not in subject.casefold():
                continue

            done, total, percent = self.sm.subject_stats(subject)
            selected = subject == self.selected_subject
            card = ctk.CTkFrame(
                self.subject_list,
                corner_radius=8,
                border_width=1,
                border_color=THEME["lavender"] if selected else THEME["border"],
                fg_color=THEME["purple"] if selected else THEME["panel"],
            )
            card.grid(sticky="ew", padx=4, pady=4)
            card.grid_columnconfigure(0, weight=1)

            title = ctk.CTkLabel(
                card,
                text=subject,
                font=ctk.CTkFont(size=13, weight="bold" if selected else "normal"),
                text_color=THEME["bg"] if selected else THEME["text"],
                anchor="w",
                justify="left",
                wraplength=230,
            )
            title.grid(row=0, column=0, padx=12, pady=(10, 0), sticky="ew")

            meta = ctk.CTkLabel(
                card,
                text=f"{done}/{total} concluídos  |  {percent:.0%}",
                text_color=THEME["bg"] if selected else THEME["lavender"],
                anchor="w",
                justify="left",
            )
            meta.grid(row=1, column=0, padx=12, pady=(0, 10), sticky="ew")

            for widget in (card, title, meta):
                widget.bind("<Button-1>", lambda _event, item=subject: self.select_subject(item))

            self.subject_buttons[subject] = card

        done, total, percent = self.sm.overall_stats()
        self.overall_progress.set(percent)
        self.overall_numbers.configure(text=f"{done}/{total} PDFs concluídos  |  {percent:.0%}")

    def refresh_stats(self) -> None:
        done, total, _ = self.sm.overall_stats()
        today_completed = self.history.completed_since(self.sm.completed, 1)
        week_completed = self.history.completed_since(self.sm.completed, 7)
        today_sessions, today_minutes = self.history.pomodoro_stats(1)
        week_sessions, week_minutes = self.history.pomodoro_stats(7)
        self.today_stat.configure(text=f"Hoje: {today_completed} PDFs | {today_sessions} pomodoros | {today_minutes} min")
        self.week_stat.configure(text=f"Semana: {week_completed} PDFs | {week_sessions} pomodoros | {week_minutes} min")
        self.total_stat.configure(text=f"Total: {done}/{total} PDFs concluídos")

    def refresh_header(self) -> None:
        if not self.selected_subject:
            self.subject_title.configure(text="Nenhuma disciplina encontrada")
            self.subject_summary.configure(text="Coloque os PDFs dentro de subpastas da pasta configurada.")
            self.subject_progress.set(0)
            self.subject_percent.configure(text="0%")
            return

        done, total, percent = self.sm.subject_stats(self.selected_subject)
        pending = total - done
        self.subject_title.configure(text=self.selected_subject)
        self.subject_summary.configure(
            text=f"{total} PDFs na trilha  |  {done} finalizados  |  {pending} pendentes"
        )
        self.subject_progress.set(percent)
        self.subject_percent.configure(text=f"{percent:.0%} da disciplina")

    def refresh_recommended(self) -> None:
        self.recommended_pdf = self.sm.next_recommended(self.selected_subject) or self.sm.next_recommended()
        if not self.recommended_pdf:
            self.next_title.configure(text="Tudo concluído por aqui")
            self.next_meta.configure(text="Sem pendências encontradas na pasta configurada.")
            self.update_recommended_button()
            return

        pdf = self.recommended_pdf
        self.next_title.configure(text=f"{pdf.subject}  |  {pdf.title}")
        self.next_meta.configure(text=pdf.meta)
        self.update_recommended_button()

    def refresh_pdf_list(self) -> None:
        for widget in self.pdf_list.winfo_children():
            widget.destroy()

        if not self.selected_subject:
            self.add_empty_label(self.pdf_list, "Nenhum PDF encontrado na pasta configurada.")
            return

        query = self.pdf_search_var.get().strip()
        pdfs = [pdf for pdf in self.sm.structure[self.selected_subject] if pdf.matches(query)]
        if not pdfs:
            self.add_empty_label(self.pdf_list, "Nenhum PDF bateu com o filtro.")
            return

        for row, pdf in enumerate(pdfs):
            self.create_pdf_card(self.pdf_list, row, pdf, show_subject=False)

    def refresh_review_list(self) -> None:
        for widget in self.review_list.winfo_children():
            widget.destroy()

        query = self.review_search_var.get().strip()
        simulados = [pdf for pdf in self.sm.simulados() if pdf.matches(query)]
        done = sum(1 for pdf in simulados if pdf.key in self.sm.completed)
        self.review_summary.configure(text=f"{len(simulados)} simulados filtrados  |  {done} concluídos")

        if not simulados:
            self.add_empty_label(self.review_list, "Nenhum simulado encontrado.")
            return

        current_subject = None
        row = 0
        for pdf in simulados:
            if pdf.subject != current_subject:
                current_subject = pdf.subject
                heading = ctk.CTkLabel(
                    self.review_list,
                    text=current_subject,
                    font=ctk.CTkFont(size=16, weight="bold"),
                    text_color=THEME["lavender"],
                    anchor="w",
                )
                heading.grid(row=row, column=0, padx=12, pady=(12, 2), sticky="ew")
                row += 1
            self.create_pdf_card(self.review_list, row, pdf, show_subject=False)
            row += 1

    def add_empty_label(self, parent, text: str) -> None:
        empty = ctk.CTkLabel(parent, text=text, text_color=THEME["muted"])
        empty.grid(row=0, column=0, padx=20, pady=20, sticky="ew")

    def create_pdf_card(self, parent, row: int, pdf: PdfItem, show_subject: bool) -> None:
        done = pdf.key in self.sm.completed
        card = ctk.CTkFrame(
            parent,
            corner_radius=8,
            fg_color=THEME["card"],
            border_width=1,
            border_color=THEME["lavender"] if done else THEME["border"],
        )
        card.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
        card.grid_columnconfigure(1, weight=1)

        badge_color = THEME["lavender"] if done else (THEME["purple"] if pdf.kind == "aula" else THEME["magenta"])
        badge = ctk.CTkLabel(
            card,
            text=pdf.badge,
            width=78,
            height=24,
            corner_radius=6,
            fg_color=badge_color,
            text_color=THEME["bg"],
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        badge.grid(row=0, column=0, rowspan=2, padx=(12, 10), pady=10, sticky="n")

        title_text = f"{pdf.subject}  |  {pdf.title}" if show_subject else pdf.title
        title = ctk.CTkLabel(
            card,
            text=title_text,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=THEME["text"],
            anchor="w",
        )
        title.grid(row=0, column=1, padx=0, pady=(8, 0), sticky="ew")

        meta = ctk.CTkLabel(
            card,
            text=pdf.meta,
            text_color=THEME["muted"],
            anchor="w",
            wraplength=700,
        )
        meta.grid(row=1, column=1, padx=0, pady=(0, 8), sticky="ew")

        checkbox = ctk.CTkCheckBox(
            card,
            text="Concluído",
            text_color=THEME["text"],
            fg_color=THEME["purple"],
            hover_color=THEME["lavender"],
            border_color=THEME["subtle"],
            width=112,
            command=lambda item=pdf: self.toggle_pdf(item),
        )
        checkbox.grid(row=0, column=2, rowspan=2, padx=12, pady=12, sticky="e")
        if done:
            checkbox.select()

        open_button = ctk.CTkButton(
            card,
            text="Abrir PDF",
            width=96,
            command=lambda item=pdf: self.open_pdf(item),
            **self.button_options("subtle"),
        )
        open_button.grid(row=0, column=3, rowspan=2, padx=(0, 12), pady=12, sticky="e")

    def select_subject(self, subject: str) -> None:
        self.selected_subject = subject
        self.refresh_screen()

    def toggle_pdf(self, pdf: PdfItem) -> None:
        if pdf.key in self.sm.completed:
            self.sm.completed.discard(pdf.key)
            self.history.add_completion_event(pdf, "reopened")
        else:
            self.sm.completed.add(pdf.key)
            self.history.add_completion_event(pdf, "completed")
        self.sm.save_progress()
        self.refresh_screen()

    def update_recommended_button(self) -> None:
        has_recommendation = getattr(self, "recommended_pdf", None) is not None
        state = "normal" if has_recommendation and not self.timer_running else "disabled"
        text = "Foco em andamento" if self.timer_running else "Estudar agora"
        self.next_open_button.configure(state=state, text=text)

    def study_recommended(self) -> None:
        pdf = getattr(self, "recommended_pdf", None)
        if pdf is None or self.timer_running:
            return

        if not self.open_pdf(pdf):
            return

        self.selected_subject = pdf.subject
        self.timer_subject = pdf.subject
        self.current_mode = "Foco"
        self.time_left = self.focus_seconds
        self.refresh_screen()
        self.start_timer()

    def open_path_with_default_app(self, path: Path) -> None:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
            return

        command = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([command, str(path)], cwd=BASE_PATH)

    def build_pdf_command_args(self, command: str, path: Path) -> list[str]:
        args = shlex.split(command)
        path_text = str(path)
        if any("{file}" in arg for arg in args):
            return [arg.replace("{file}", path_text) for arg in args]
        return args + [path_text]

    def open_pdf(self, pdf: PdfItem) -> bool:
        command = self.config_manager.values["pdf_command"]
        try:
            if command.casefold() in AUTO_PDF_COMMANDS:
                self.open_path_with_default_app(pdf.path)
            else:
                subprocess.Popen(self.build_pdf_command_args(command, pdf.path), cwd=BASE_PATH)
            return True
        except Exception:
            NotificationService.send("Não consegui abrir o PDF", pdf.path.name)
            return False

    def save_settings(self) -> None:
        focus = ConfigManager.coerce_minutes(self.focus_var.get(), DEFAULT_CONFIG["focus_minutes"])
        pause = ConfigManager.coerce_minutes(self.break_var.get(), DEFAULT_CONFIG["break_minutes"])
        command = ConfigManager.normalize_pdf_command(self.command_var.get())
        materials_path = ConfigManager.normalize_path(self.materials_var.get())
        previous_subject = self.selected_subject
        self.config_manager.save(focus, pause, command, materials_path)
        self.sm = StudyManager(Path(self.config_manager.values["materials_path"]))
        self.selected_subject = previous_subject if previous_subject in self.sm.structure else next(iter(self.sm.structure), None)
        self.focus_seconds = focus * 60
        self.break_seconds = pause * 60
        if not self.timer_running:
            self.time_left = self.focus_seconds if self.current_mode == "Foco" else self.break_seconds
            self.update_timer_visuals()
        self.focus_var.set(str(focus))
        self.break_var.set(str(pause))
        self.command_var.set(command)
        self.materials_var.set(self.config_manager.values["materials_path"])
        self.refresh_screen()
        self.settings_status.configure(text="Configurações salvas.")
        self.tjpb_panel.reload()

    def open_obsidian_notebook(self) -> None:
        webbrowser.open(OBSIDIAN_NOTE_URI)

    def restore_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def close_app(self) -> None:
        self.tray.stop()
        self.destroy()

    def toggle_timer(self) -> None:
        if self.timer_running:
            self.pause_timer()
        else:
            self.start_timer()

    def start_timer(self) -> None:
        if self.timer_running:
            return

        self.timer_running = True
        if getattr(self, "timer_subject", None) is None:
            self.timer_subject = self.selected_subject
        self.start_button.configure(text="Rodando")
        self.set_timer_presence()
        if self.current_mode == "Foco" and self.time_left == self.focus_seconds:
            subject = self.timer_subject or "sem disciplina selecionada"
            NotificationService.send("Foco iniciado", f"Sessão ativa em {subject}")

    def pause_timer(self) -> None:
        self.timer_running = False
        self.start_button.configure(text="Continuar")
        self.set_timer_presence()

    def reset_timer(self) -> None:
        self.timer_running = False
        self.current_mode = "Foco"
        self.timer_subject = None
        self.time_left = self.focus_seconds
        self.start_button.configure(text="Iniciar")
        self.update_timer_visuals()

    def tick_timer(self) -> None:
        if self.timer_running:
            self.time_left -= 1
            if self.time_left <= 0:
                self.handle_timer_end()
            else:
                self.update_clock_label()

        self.after(1000, self.tick_timer)

    def handle_timer_end(self) -> None:
        if self.current_mode == "Foco":
            subject = getattr(self, "timer_subject", None) or self.selected_subject
            self.history.add_pomodoro(subject, self.config_manager.values["focus_minutes"])
            NotificationService.send("Ciclo de foco terminado", "Hora de respirar. Pausa iniciada.")
            self.current_mode = "Pausa"
            self.time_left = self.break_seconds
        else:
            NotificationService.send("Pausa concluída", "Pronto para o próximo PDF?")
            self.current_mode = "Foco"
            self.time_left = self.focus_seconds

        self.timer_running = True
        self.refresh_stats()
        self.update_timer_visuals()

    def update_timer_visuals(self) -> None:
        if self.current_mode == "Foco":
            self.mode_label.configure(text="FOCO", text_color=THEME["purple"])
        else:
            self.mode_label.configure(text="PAUSA", text_color=THEME["lavender"])
        self.update_clock_label()

    def update_clock_label(self) -> None:
        timer_text = self.format_time()
        self.clock_label.configure(text=timer_text)
        if hasattr(self, "tjpb_panel"):
            self.tjpb_panel.clock.configure(text=f"{timer_text} · {self.current_mode}")
        self.set_timer_presence(timer_text)

    def format_time(self) -> str:
        minutes, seconds = divmod(max(self.time_left, 0), 60)
        return f"{minutes:02d}:{seconds:02d}"

    def set_timer_presence(self, timer_text: str | None = None) -> None:
        timer_text = timer_text or self.format_time()
        state = "rodando" if self.timer_running else "pausado"
        mode = self.current_mode
        status = f"{timer_text} {mode} ({state})"
        self.title(f"{status} | {APP_NAME}")
        os.environ["RESOURCE_NAME"] = APP_WM_CLASS

        color = THEME["lavender"] if mode == "Pausa" else THEME["purple"]
        if not self.timer_running:
            color = THEME["yellow"]
        self.tray.update(status, color)
        self.update_recommended_button()


if __name__ == "__main__":
    app = PomodoroApp()
    app.mainloop()
