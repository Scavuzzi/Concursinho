#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

if [[ -x "$APP_DIR/venv/bin/python" ]]; then
    exec "$APP_DIR/venv/bin/python" "$APP_DIR/main.py"
fi

exec python "$APP_DIR/main.py"
