#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.local/share/applications"
TARGET_FILE="$TARGET_DIR/concursinho-pomodoro.desktop"

mkdir -p "$TARGET_DIR"
chmod +x "$APP_DIR/run.sh"

cat > "$TARGET_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Painel de Estudos
GenericName=Pomodoro e checklist de PDFs
Comment=Painel desktop para estudar PDFs de concurso com Pomodoro e progresso
Exec="$APP_DIR/run.sh"
Path=$APP_DIR
Icon=$APP_DIR/assets/app-icon.png
Terminal=false
Categories=Education;
StartupNotify=true
StartupWMClass=ConcursinhoPomodoro
Keywords=concurso;estudos;pomodoro;pdf;
DESKTOP

chmod +x "$TARGET_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$TARGET_DIR" >/dev/null 2>&1 || true
fi

echo "Instalado em $TARGET_FILE"
