@echo off
rem Konsistentes Backup mit VACUUM INTO (§3): backup.cmd <quelldatei> <zieldatei>
rem Der Zielpfad ist frei waehlbar (z. B. Netzlaufwerk). Die Aufbewahrung
rem (letzte 14 Staende) rotiert der Aufrufer im Taskplaner-Skript.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo .venv fehlt - zuerst setup.cmd ausfuehren.
    exit /b 1
)
.venv\Scripts\python.exe -m journal.backup %*
