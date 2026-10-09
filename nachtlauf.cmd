@echo off
rem AP-02a2k: Nachtauftrag - Flex-Statement abrufen, importieren, Rebuild,
rem Backup. Aufruf durch die Windows-Aufgabenplanung (START.md, Abschnitt
rem "Naechtlicher Abruf"). Zugangsdaten stehen NICHT hier: Sie werden aus
rem %USERPROFILE%\.trading-journal\flex.cmd gelesen, falls vorhanden.
rem Kein "set" und kein "echo" der Zugangsdaten - der Token erscheint nie.
setlocal EnableExtensions

set "STAMM=%USERPROFILE%\.trading-journal"
if exist "%STAMM%\flex.cmd" call "%STAMM%\flex.cmd"

rem Projektverzeichnis = Ablageort dieser Datei.
pushd "%~dp0"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo FEHLER: .venv fehlt - zuerst setup.cmd ausfuehren. 1>&2
    popd
    exit /b 1
)

if not exist "%STAMM%\logs" mkdir "%STAMM%\logs"
rem Datum als JJJJMMTT - einmalig vor dem eigentlichen Lauf; danach laeuft
rem genau ein Python-Prozess nach dem anderen, nie zwei gleichzeitig.
for /f %%T in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd"') do set "TAG=%%T"
set "LOG=%STAMM%\logs\nachtlauf-%TAG%.log"

echo === Nachtlauf %TAG% === > "%LOG%"
".venv\Scripts\python.exe" -m journal abrufen --rebuild >> "%LOG%" 2>&1
set "CODE=%errorlevel%"
if "%CODE%"=="0" goto backup
popd
exit /b %CODE%

:backup
if not defined FLEX_BACKUP_ZIEL goto fertig
call backup.cmd journal.db "%FLEX_BACKUP_ZIEL%\journal-%TAG%.db" >> "%LOG%" 2>&1
set "CODE=%errorlevel%"
if not "%CODE%"=="0" (
    popd
    exit /b %CODE%
)
rem Nur die 14 neuesten Sicherungen journal-*.db behalten (aeltere loeschen).
for /f "skip=14 delims=" %%D in ('dir /b /a-d /o-d "%FLEX_BACKUP_ZIEL%\journal-*.db"') do (
    echo Entferne alte Sicherung %%D >> "%LOG%"
    del "%FLEX_BACKUP_ZIEL%\%%D"
)

:fertig
popd
exit /b 0
