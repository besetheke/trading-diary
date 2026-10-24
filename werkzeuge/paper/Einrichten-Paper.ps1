# Richtet das Journal fuer das PAPER-Konto ein: eigene Datenbank, eigene Zugangsdaten-Vorlage, eigener Port.
# Das echte Journal (journal.db, Port 8000) bleibt unberuehrt: der Import lehnt ein fremdes Konto ohnehin ab
# (Einzelkonto-Grenze, AP-17e), deshalb bekommt Paper eine EIGENE Datenbank.
#
#   .\werkzeuge\paper\Einrichten-Paper.ps1
#
# Danach: %USERPROFILE%\.trading-journal\paper\flex-paper.cmd ausfuellen (Token und Query-ID der Flex-Abfrage fuer
# das Paper-Konto DU...), dann Schnellstart-Paper.ps1 und nachtlauf-paper.cmd (Aufgabenplanung).
$projekt = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $projekt

$stamm = Join-Path $env:USERPROFILE ".trading-journal\paper"
New-Item -ItemType Directory -Force -Path $stamm, (Join-Path $stamm "flex"), (Join-Path $stamm "logs") | Out-Null

$db = Join-Path $stamm "journal-paper.db"
$env:JOURNAL_DB = $db
if (-not (Test-Path ".venv\Scripts\python.exe")) { Write-Error ".venv fehlt - zuerst setup.cmd"; exit 1 }
& ".venv\Scripts\python.exe" -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Error "alembic upgrade fehlgeschlagen"; exit 1 }

$vorlage = Join-Path $stamm "flex-paper.cmd"
if (-not (Test-Path $vorlage)) {
    @"
@echo off
rem Zugangsdaten der Flex-Abfrage fuer das PAPER-Konto (DU...). Diese Datei nie weitergeben oder einchecken.
set "FLEX_TOKEN="
set "FLEX_QUERY_ID="
set "FLEX_ZIEL=%USERPROFILE%\.trading-journal\paper\flex"
"@ | Set-Content -Path $vorlage -Encoding ASCII
    Write-Output "Vorlage angelegt: $vorlage  (Token und Query-ID eintragen)"
}
Write-Output "Paper-Datenbank bereit: $db"
