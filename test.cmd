@echo off
rem Entspricht `make test` (Windows, siehe AP-01).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo .venv fehlt - zuerst setup.cmd ausfuehren.
    exit /b 1
)
.venv\Scripts\python.exe -m pytest %*
