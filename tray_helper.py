import argparse
import os
import sys
import threading

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


class Bridge(QObject):
    tooltip_changed = Signal(str)
    quit_requested = Signal()


def send_command(fifo_path: str, command: str) -> None:
    try:
        with open(fifo_path, "w", encoding="utf-8") as fifo:
            fifo.write(command)
    except Exception:
        pass


def read_stdin(bridge: Bridge) -> None:
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        if line == "quit":
            bridge.quit_requested.emit()
            break

        if line.startswith("tooltip:"):
            bridge.tooltip_changed.emit(line.removeprefix("tooltip:"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--icon", required=True)
    parser.add_argument("--fifo", required=True)
    parser.add_argument("--tooltip", default="Painel de Estudos")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not os.path.exists(args.icon):
        print(f"Ícone não encontrado: {args.icon}", file=sys.stderr)
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("QSystemTrayIcon indisponível neste ambiente.", file=sys.stderr)
        return 2

    bridge = Bridge()
    tray = QSystemTrayIcon()
    tray.setIcon(QIcon(args.icon))
    tray.setToolTip(args.tooltip)

    menu = QMenu()

    show_action = QAction("Mostrar painel", menu)
    show_action.triggered.connect(lambda: send_command(args.fifo, "show"))
    menu.addAction(show_action)

    toggle_action = QAction("Pausar/continuar", menu)
    toggle_action.triggered.connect(lambda: send_command(args.fifo, "toggle"))
    menu.addAction(toggle_action)

    menu.addSeparator()

    quit_action = QAction("Sair", menu)
    quit_action.triggered.connect(lambda: send_command(args.fifo, "quit"))
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: send_command(args.fifo, "show")
        if reason == QSystemTrayIcon.ActivationReason.Trigger
        else None
    )

    bridge.tooltip_changed.connect(tray.setToolTip)
    bridge.quit_requested.connect(app.quit)

    stdin_thread = threading.Thread(target=read_stdin, args=(bridge,), daemon=True)
    stdin_thread.start()

    tray.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
