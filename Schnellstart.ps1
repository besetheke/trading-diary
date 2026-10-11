# Startet die Trading-Journal-Weboberflaeche (API + ui/dist) ohne sichtbares
# Konsolenfenster (pythonw.exe) und oeffnet sie im Standardbrowser. Laeuft
# bereits ein Server auf Port 8000, wird nur der Browser geoeffnet.
#
# stdout/stderr werden bewusst in eine Datei umgeleitet: ohne explizite
# Umleitung erbt pythonw.exe aus diesem (verschachtelten) Kontext ungueltige
# Konsolen-Handles und stirbt beim ersten Log-Write sofort wieder.
Add-Type -AssemblyName System.Windows.Forms

$projekt = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projekt

$logOrdner = "$env:USERPROFILE\.trading-journal\logs"
New-Item -ItemType Directory -Force -Path $logOrdner | Out-Null
# Start-Process lehnt identische Pfade fuer Standardausgabe und -fehler ab.
$serverLogOut = Join-Path $logOrdner "server.log"
$serverLogErr = Join-Path $logOrdner "server-fehler.log"

# Die Wurzel statt openapi.json: Das Schema wird erst beim ersten Aufruf
# erzeugt und braucht auf einem kalten Rechner laenger als eine Sekunde. Das
# Zeitlimit ist grosszuegig, damit ein langsamer Start nicht als "nicht
# gestartet" gilt (11.10.2026: Fehlalarm bei laufendem Server).
function Test-ServerLaeuft {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/" -UseBasicParsing -TimeoutSec 5
        return $r.StatusCode -eq 200
    } catch {
        return $false
    }
}

if (Test-ServerLaeuft) {
    Start-Process "http://127.0.0.1:8000/"
    return
}

if (-not (Test-Path ".venv\Scripts\pythonw.exe")) {
    [System.Windows.Forms.MessageBox]::Show(
        ".venv fehlt - zuerst setup.cmd ausfuehren.", "Trading-Journal",
        [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    return
}
if (-not (Test-Path "ui\dist\index.html")) {
    [System.Windows.Forms.MessageBox]::Show(
        "Oberflaeche ist nicht gebaut (ui\dist fehlt). In ui\ einmal `"npm run build`" ausfuehren.",
        "Trading-Journal",
        [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    return
}

Start-Process -FilePath ".venv\Scripts\pythonw.exe" `
    -ArgumentList "-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $projekt -WindowStyle Hidden `
    -RedirectStandardOutput $serverLogOut -RedirectStandardError $serverLogErr

# Bis zu 30 Sekunden warten (alle halbe Sekunde pruefen). Ein Fehler zeigt sich
# nur, wenn der Server wirklich nicht antwortet.
$bereit = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-ServerLaeuft) { $bereit = $true; break }
}

if (-not $bereit) {
    [System.Windows.Forms.MessageBox]::Show(
        "Trading-Journal ist nicht gestartet. Log: $serverLogErr", "Trading-Journal",
        [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    return
}

Start-Process "http://127.0.0.1:8000/"
