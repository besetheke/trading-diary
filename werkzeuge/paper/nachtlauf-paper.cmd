@echo off
rem Nachtlauf fuer das PAPER-Journal: Flex-Statement des Paper-Kontos abrufen, importieren, Rebuild.
rem Eigene Datenbank und eigene Zugangsdaten (flex-paper.cmd); beruehrt journal.db des echten Kontos nie.
rem Aufruf durch die Aufgabenplanung wie nachtlauf.cmd. Kein "set"/"echo" der Zugangsdaten.
setlocal EnableExtensions

set "STAMM=%USERPROFILE%\.trading-journal\paper"
if not exist "%STAMM%\flex-paper.cmd" (
    echo FEHLER: %STAMM%\flex-paper.cmd fehlt - zuerst Einrichten-Paper.ps1. 1>&2
    exit /b 1
)
call "%STAMM%\flex-paper.cmd"
set "JOURNAL_DB=%STAMM%\journal-paper.db"

pushd "%~dp0..\.."
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo FEHLER: .venv fehlt - zuerst setup.cmd ausfuehren. 1>&2
    popd
    exit /b 1
)
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TAG=%%T"
set "LOG=%STAMM%\logs\nachtlauf-%TAG%.log"
echo === Nachtlauf Paper %TAG% === > "%LOG%"
".venv\Scripts\python.exe" -m journal abrufen --rebuild >> "%LOG%" 2>&1
set "CODE=%errorlevel%"
popd
exit /b %CODE%
