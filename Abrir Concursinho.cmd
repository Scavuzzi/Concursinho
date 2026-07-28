@echo off
setlocal
cd /d "%~dp0"

if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" "main.py"
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "main.py"
    exit /b 0
)

where pyw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pyw -3 "main.py"
    exit /b 0
)

where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw "main.py"
    exit /b 0
)

echo Nao encontrei o Python. Prepare o ambiente conforme o README.md.
pause
