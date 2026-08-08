import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from main import PomodoroApp, read_json, write_json


class JsonStorageTests(unittest.TestCase):
    def test_write_creates_valid_json_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"

            write_json(path, {"version": 1})
            write_json(path, {"version": 2})

            self.assertEqual(read_json(path, {}), {"version": 2})
            self.assertEqual(read_json(path.with_name("state.json.bak"), {}), {"version": 1})
            self.assertFalse(path.with_name("state.json.tmp").exists())

    def test_read_recovers_from_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            backup = path.with_name("state.json.bak")
            path.write_text("{arquivo quebrado", encoding="utf-8")
            backup.write_text('{"recovered": true}', encoding="utf-8")

            self.assertEqual(read_json(path, {}), {"recovered": True})


class RecommendedStudyTests(unittest.TestCase):
    def test_recommendation_selects_subject_and_starts_focus(self):
        pdf = SimpleNamespace(subject="Raciocínio Lógico")
        events = []
        app = SimpleNamespace(
            recommended_pdf=pdf,
            timer_running=False,
            current_mode="Pausa",
            time_left=10,
            focus_seconds=1500,
            selected_subject="Português",
            open_pdf=lambda item: events.append(("open", item)) or True,
            refresh_screen=lambda: events.append(("refresh", None)),
            start_timer=lambda: events.append(("start", None)),
        )

        PomodoroApp.study_recommended(app)

        self.assertEqual(app.selected_subject, "Raciocínio Lógico")
        self.assertEqual(app.current_mode, "Foco")
        self.assertEqual(app.time_left, 1500)
        self.assertEqual([event[0] for event in events], ["open", "refresh", "start"])

    def test_recommendation_does_not_interrupt_running_focus(self):
        events = []
        app = SimpleNamespace(
            recommended_pdf=SimpleNamespace(subject="Português"),
            timer_running=True,
            open_pdf=lambda item: events.append(item) or True,
        )

        PomodoroApp.study_recommended(app)

        self.assertEqual(events, [])

    def test_recommendation_does_not_start_when_pdf_fails_to_open(self):
        events = []
        app = SimpleNamespace(
            recommended_pdf=SimpleNamespace(subject="Português"),
            timer_running=False,
            open_pdf=lambda item: False,
            refresh_screen=lambda: events.append("refresh"),
            start_timer=lambda: events.append("start"),
        )

        PomodoroApp.study_recommended(app)

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
