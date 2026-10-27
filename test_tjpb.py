import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from main import PomodoroApp, read_json, write_json
from tjpb import CHECKLIST_NAME, TjpbCatalog, TjpbPanel, obsidian_note_uri, resolve_tjpb_root


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_loads_only_official_content_and_stable_topic_ids(self):
        path = self.root / CHECKLIST_NAME
        path.write_text(
            "## 1. Português\n\n- [ ] Crase.\n## 14. UI\n- [x] Acessibilidade.\n"
            "## 15. Preparação\n- [ ] Exercício sugerido.\n## Recomendações\n- [ ] Revisar.\n",
            encoding="utf-8",
        )
        first = TjpbCatalog(self.root)
        self.assertEqual([t.text for t in first.topics], ["Crase.", "Acessibilidade."])
        path.write_text(path.read_text(encoding="utf-8").replace("## 1.", "## 2."), encoding="utf-8")
        second = TjpbCatalog(self.root)
        self.assertEqual([t.key for t in first.topics], [t.key for t in second.topics])

    def test_uses_local_relative_files_and_excludes_preliminary_answers(self):
        folder = "01_TJRR_2024_FGV"
        directory = self.root / "Provas anteriores" / folder
        directory.mkdir(parents=True)
        for name in ["prova", "gabarito_definitivo", "gabarito_preliminar"]:
            (directory / f"{name}.pdf").write_bytes(b"fixture")
        payload = {"files": [
            {"folder": folder, "kind": kind, "path": "/old/computer/ignored.pdf"}
            for kind in ["prova", "gabarito_definitivo", "gabarito_preliminar"]
        ] + [{"folder": "../../outside", "kind": "prova"}]}
        (self.root / "Provas anteriores" / "manifesto_downloads.json").write_text(json.dumps(payload), encoding="utf-8")
        catalog = TjpbCatalog(self.root)
        self.assertEqual(len(catalog.exams), 1)
        exam = catalog.exams[0]
        self.assertEqual(exam.files["prova"], directory / "prova.pdf")
        self.assertNotIn("gabarito_preliminar", exam.files)

    def test_missing_or_malformed_materials_are_reported_without_crashing(self):
        self.assertEqual(len(TjpbCatalog(self.root).errors), 2)
        directory = self.root / "Provas anteriores"
        directory.mkdir()
        (directory / "manifesto_downloads.json").write_text('{"files": null}', encoding="utf-8")
        self.assertEqual(TjpbCatalog(self.root).exams, [])

    def test_root_follows_configured_vault_and_can_be_overridden(self):
        with patch.dict(os.environ, {"CONCURSINHO_TJPB_PATH": ""}):
            self.assertEqual(resolve_tjpb_root(self.root / "Concursinho" / "Materiais"), self.root / "TJPB 2026")
        with patch.dict(os.environ, {"CONCURSINHO_TJPB_PATH": str(self.root)}):
            self.assertEqual(resolve_tjpb_root(Path("unused")), self.root)

    def test_obsidian_uri_uses_actual_vault_name(self):
        (self.root / ".obsidian").mkdir()
        note = self.root / "Estudos" / "Minha nota.md"
        uri = obsidian_note_uri(note)
        self.assertTrue(uri.startswith("obsidian://open?"))
        self.assertIn("file=Estudos%2FMinha%20nota.md", uri)


class ProgressAndFocusTests(unittest.TestCase):
    def test_toggle_persists_and_unmarks_only_the_selected_item(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.json"
            panel = SimpleNamespace(completed={"topic:one"}, progress_path=path,
                                    write_json=write_json, render=lambda: None)
            TjpbPanel.toggle(panel, "exam:two", True)
            self.assertEqual(set(read_json(path, [])), {"topic:one", "exam:two"})
            TjpbPanel.toggle(panel, "topic:one", False)
            self.assertEqual(read_json(path, []), ["exam:two"])

    def test_tjpb_focus_does_not_interrupt_running_or_paused_sessions(self):
        for running, remaining in [(True, 1500), (False, 1000)]:
            with self.subTest(running=running):
                events = []
                panel = SimpleNamespace(
                    app=SimpleNamespace(timer_running=running, current_mode="Foco", time_left=remaining,
                                        focus_seconds=1500, start_timer=lambda: events.append("start")),
                    status=SimpleNamespace(configure=lambda **kwargs: None),
                )
                TjpbPanel.start_focus(panel)
                self.assertEqual(events, [])

    def test_focus_is_tagged_with_tjpb_group(self):
        events = []
        panel = SimpleNamespace(
            app=SimpleNamespace(timer_running=False, current_mode="Foco", time_left=1500,
                                focus_seconds=1500, start_timer=lambda: events.append("start")),
            group=SimpleNamespace(get=lambda: "Banco de dados"), view=SimpleNamespace(get=lambda: "Conteúdo"),
            status=SimpleNamespace(configure=lambda **kwargs: None),
        )
        TjpbPanel.start_focus(panel)
        self.assertEqual(panel.app.timer_subject, "TJPB · Banco de dados")
        self.assertEqual(events, ["start"])

    @patch("main.NotificationService.send")
    def test_completion_logs_the_session_subject_even_if_sidebar_changes(self, _notify):
        recorded = []
        app = SimpleNamespace(
            current_mode="Foco", timer_subject="TJPB · Português", selected_subject="Biblioteca anterior",
            config_manager=SimpleNamespace(values={"focus_minutes": 25}), break_seconds=300,
            history=SimpleNamespace(add_pomodoro=lambda subject, minutes: recorded.append((subject, minutes))),
            refresh_stats=lambda: None, update_timer_visuals=lambda: None,
        )
        PomodoroApp.handle_timer_end(app)
        self.assertEqual(recorded, [("TJPB · Português", 25)])


if __name__ == "__main__":
    unittest.main()
