@echo off
rem CI-Gate vor jeder Abgabe (CLAUDE.md): ruff check . und pytest.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo .venv fehlt - zuerst setup.cmd ausfuehren.
    exit /b 1
)
rem --no-cache: ein Prueftor, dessen Ergebnis von einem Cache abhaengen kann,
rem taugt nicht als Abnahmekriterium (Befund im Review von AP-02a).
.venv\Scripts\python.exe -m ruff check . --no-cache || goto :fehler
.venv\Scripts\python.exe -m pytest || goto :fehler
exit /b 0

:fehler
exit /b 1
