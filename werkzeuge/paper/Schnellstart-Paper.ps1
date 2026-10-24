# Startet das Journal fuer das PAPER-Konto (eigene Datenbank, Port 8001) und oeffnet es im Browser. Das echte Journal
# (Port 8000, journal.db) laeuft unabhaengig daneben. Die Roller-Anbindung zeigt den Roller-Dienst auf Port 8600.
# Vorher einmal: Einrichten-Paper.ps1
Add-Type -AssemblyName System.Windows.Forms
$projekt = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))   # Repo-Wurzel (das Skript liegt in werkzeuge, Unterordner paper)
Set-Location $projekt

$stamm = Join-Path $env:USERPROFILE ".trading-journal\paper"
$db = Join-Path $stamm "journal-paper.db"
$port = 8001
if (-not (Test-Path $db)) {
    [System.Windows.Forms.MessageBox]::Show("Paper-Datenbank fehlt - zuerst Einrichten-Paper.ps1.", "Journal Paper") | Out-Null
    return
}
function Test-Laeuft {
    try { return (Invoke-WebRequest -Uri "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 5).StatusCode -eq 200 } catch { return $false }
}
if (Test-Laeuft) { Start-Process "http://127.0.0.1:$port/start"; return }

$env:JOURNAL_DB = $db
$env:ROLLER_STATUS_PORT = "8600"
$env:JOURNAL_UI = Join-Path $projekt "ui\dist"     # Oberflaeche aus dem Projekt (die Datenbank liegt ausserhalb)
$logs = Join-Path $stamm "logs"
Start-Process -FilePath ".venv\Scripts\pythonw.exe" `
    -ArgumentList "-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", "$port" `
    -WorkingDirectory $projekt -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $logs "server.log") -RedirectStandardError (Join-Path $logs "server-fehler.log")
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-Laeuft) { Start-Process "http://127.0.0.1:$port/start"; return }
}
[System.Windows.Forms.MessageBox]::Show("Journal Paper antwortet nicht. Log: $logs", "Journal Paper") | Out-Null
