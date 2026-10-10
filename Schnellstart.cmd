@echo off
rem Schnellstart: startet die Trading-Journal-Weboberflaeche (API + ui/dist)
rem und oeffnet sie im Standardbrowser. Fenster offen lassen - Beenden mit
rem Strg+C oder durch Schliessen dieses Fensters.
title Trading-Journal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo .venv fehlt - zuerst setup.cmd ausfuehren.
    pause
    exit /b 1
)
if not exist ui\dist\index.html (
    echo Oberflaeche ist nicht gebaut: ui\dist fehlt.
    echo In ui\ einmalig "npm run build" ausfuehren.
    pause
    exit /b 1
)
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8000/'"
.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
