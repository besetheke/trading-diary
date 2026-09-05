@echo off
rem Einmalige Einrichtung: virtuelle Umgebung und Abhaengigkeiten.
cd /d "%~dp0"
if not exist .venv (
    echo Lege .venv an ...
    python -m venv .venv || exit /b 1
)
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -e ".[dev]" || exit /b 1
.venv\Scripts\python.exe -m ruff --version
echo Fertig. Tests mit test.cmd, Gate mit check.cmd.
