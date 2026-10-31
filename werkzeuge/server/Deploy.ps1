<#
Deploy der Trading Station auf den Server (AP-15). Auf dem Server wird nicht entwickelt:
der Stand kommt per Git (GitHub, Branch master), dieses Skript holt ihn und startet neu.

  .\werkzeuge\server\Deploy.ps1 -Trocken            # nur zeigen, was passieren wuerde
  .\werkzeuge\server\Deploy.ps1                     # aktualisieren, migrieren, neu starten, pruefen
  .\werkzeuge\server\Deploy.ps1 -Erstinstallation   # Repos klonen und einrichten (leerer Server)
  .\werkzeuge\server\Deploy.ps1 -VolleTests         # statt Rauchtest die ganze Journal-Suite (ca. 12 min)

Ablauf je Lauf:
  1. Vorbedingungen: git, python 3.12, (npm fuer die Oberflaeche), saubere Arbeitsbaeume.
  2. Roller-Dienst und Journal-Server anhalten (offene Orders bleiben bei IB; der
     Wiederanlauf-Abgleich des Rollers raeumt nach dem Start auf).
  3. git pull --ff-only je Repo (nie Merge, nie lokale Aenderungen).
  4. Abhaengigkeiten, Sicherung journal.db, alembic upgrade head, Oberflaeche bauen.
  5. Roller-Tests (Sekunden) und Journal-Rauchtest laufen VOR dem Start der Dienste; scheitern
     sie, bleiben die Dienste aus und das Skript meldet es (kein halb fertiger Stand mit
     laufendem Dienst). Danach Dienste starten und python -m roller.pruefung (ohne Tests).
Bricht bei jedem Fehler ab; nichts wird geloescht. Unversionierte Dateien (z. B. .vscode/)
blockieren nicht, nur Aenderungen an versionierten Dateien.
#>
param(
    [string]$Basis = "C:\10_Coding",
    [switch]$Erstinstallation,
    [switch]$Trocken,
    [switch]$VolleTests,
    [switch]$Neustart   # intern: Selbstaufruf, nachdem sich dieses Skript durch den Pull geaendert hat
)
$ErrorActionPreference = "Stop"

$repos = @(
    @{ Name = "trading-diary"; Url = "https://github.com/besetheke/trading-diary.git" },
    @{ Name = "options-roller"; Url = "https://github.com/besetheke/options-roller.git" },
    @{ Name = "momentum-lab";  Url = "https://github.com/besetheke/momentum-lab.git" }
)
$journal = Join-Path $Basis "trading-diary"
$roller = Join-Path $Basis "options-roller"

function Schritt([string]$text) { Write-Host "`n=== $text" -ForegroundColor Cyan }
function Tu([string]$text, [scriptblock]$aktion) {
    if ($Trocken) { Write-Host "  (trocken) $text"; return }
    Write-Host "  $text"
    & $aktion
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Fehlgeschlagen: $text (Code $LASTEXITCODE)" }
}

# ------------------------------------------------------------------ 1. Vorbedingungen
Schritt "Vorbedingungen"
foreach ($werkzeug in @("git", "python")) {
    if (-not (Get-Command $werkzeug -ErrorAction SilentlyContinue)) { throw "$werkzeug fehlt im PATH" }
}
$pyVersion = (& python -c "import sys; print('%d.%d' % sys.version_info[:2])")
if ([version]$pyVersion -lt [version]"3.12") { throw "Python $pyVersion - benoetigt wird 3.12" }
$npm = [bool](Get-Command npm -ErrorAction SilentlyContinue)
Write-Host "  git ok, Python $pyVersion, npm $(if ($npm) { 'ok' } else { 'FEHLT (Oberflaeche wird nicht gebaut)' })"

foreach ($r in $repos) {
    $ordner = Join-Path $Basis $r.Name
    if (-not (Test-Path $ordner)) {
        if (-not $Erstinstallation) { throw "$ordner fehlt - mit -Erstinstallation klonen" }
        Tu "git clone $($r.Url)" { git clone $r.Url $ordner }
        continue
    }
    $schmutz = git -C $ordner status --porcelain --untracked-files=no
    if ($schmutz) {
        $text = "$ordner hat lokale Aenderungen - auf dem Server wird nicht entwickelt:`n$($schmutz -join "`n")"
        if ($Trocken) { Write-Warning $text } else { throw $text }
    }
}

# Selbstpruefung (auch im Trockenlauf): jede Datei, die das Skript aufruft, muss existieren. Ein
# Pfadfehler soll hier auffallen und nicht erst nach dem Anhalten der Dienste.
$erwartet = @("$journal\setup.cmd", "$journal\test.cmd", "$journal\backup.cmd", "$journal\Schnellstart.ps1",
              "$roller\Start-Dienst.ps1", "$roller\Beenden-Dienst.ps1", "$roller\requirements.txt")
foreach ($datei in $erwartet) {
    if (-not (Test-Path $datei)) {
        $text = "Datei fehlt (oder Pfad kaputt): $datei"
        if ($Trocken -or $Erstinstallation) { Write-Warning $text } else { throw $text }
    }
}

# ------------------------------------------------------------------ 1b. Vorabpruefung der Downloads
# Alle festgeschriebenen Abhaengigkeiten des NEUEN Stands muessen ladbar sein, BEVOR die Dienste angehalten werden
# (AP-17g, M08): sonst bliebe bei einem Netzfehler mitten im Deploy alles aus. Die Lock-Datei kommt aus dem Remote-Stand
# (fetch), geladen wird nur in einen Temp-Ordner. Bei Fehler bricht das Skript ab, die Dienste laufen weiter.
Schritt "Vorabpruefung: Abhaengigkeiten ladbar (Dienste laufen noch)"
Tu "requirements-lock.txt des Remote-Stands mit pip download pruefen" {
    foreach ($name in @("trading-diary", "options-roller")) {
        $ordner = Join-Path $Basis $name
        if (-not (Test-Path (Join-Path $ordner ".git"))) { continue }
        git -C $ordner fetch --quiet
        if ($LASTEXITCODE -ne 0) { throw "$name`: git fetch fehlgeschlagen - Abbruch, Dienste laufen weiter" }
        $lock = $null
        try { $lock = git -C $ordner show "@{u}:requirements-lock.txt" } catch { $lock = $null }
        if ($LASTEXITCODE -ne 0 -or -not $lock) { $global:LASTEXITCODE = 0; Write-Host "    ${name}: keine requirements-lock.txt im Remote-Stand (uebersprungen)"; continue }
        $tmp = Join-Path $env:TEMP "deploy-pruefung-$name"
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
        New-Item -ItemType Directory -Path $tmp | Out-Null
        $datei = Join-Path $tmp "requirements-lock.txt"
        $lock | Set-Content -Path $datei -Encoding ASCII
        & python -m pip download --disable-pip-version-check --no-deps -q -r $datei -d $tmp
        $code = $LASTEXITCODE
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
        if ($code -ne 0) { throw "${name}: Abhaengigkeiten nicht ladbar (pip download, Code $code) - Abbruch, Dienste laufen weiter" }
        Write-Host "    ${name}: alle festgeschriebenen Pakete ladbar"
    }
    $global:LASTEXITCODE = 0
}

# ------------------------------------------------------------------ 2. Anhalten
Schritt "Dienste anhalten"
# Live-Dienst MIT Orders (--live-orders) merken: er wird nach dem Deploy bewusst NICHT automatisch neu gestartet, denn der
# Start verlangt die Eingabe "ECHTGELD" am Fenster. Statt seiner startet der lesende Live-Dienst; offene Orders (Profit-
# Targets) bleiben bei IB bestehen.
$liveMitOrders = [bool](Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
    Where-Object { $_.CommandLine -match "roller\.dienst" -and $_.CommandLine -match "--live-orders" })
if ($liveMitOrders) { Write-Warning "Der Live-Dienst mit Orders laeuft und wird fuer den Deploy beendet." }
Tu "Roller-Dienst beenden" { if (Test-Path "$roller\Beenden-Dienst.ps1") { & "$roller\Beenden-Dienst.ps1" } }
Tu "Journal-Server beenden" {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -match "uvicorn api\.app:app" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
}

# ------------------------------------------------------------------ 3. Code holen
Schritt "Code holen (fast-forward)"
$hashVorher = (Get-FileHash $PSCommandPath).Hash
foreach ($r in $repos) {
    $ordner = Join-Path $Basis $r.Name
    if (-not (Test-Path $ordner)) { continue }
    Tu "$($r.Name): git pull --ff-only" { git -C $ordner pull --ff-only }
    if (-not $Trocken) { Write-Host "    Stand: $(git -C $ordner log --oneline -1)" }
    # Hat der Pull dieses Skript veraendert, laeuft der Rest noch mit der alten Fassung (14.10.2026:
    # ein Fehler im Skript blieb deshalb einen Lauf lang bestehen). Dann mit der neuen neu starten.
    if ($r.Name -eq "trading-diary" -and -not $Trocken -and -not $Neustart `
            -and (Get-FileHash $PSCommandPath).Hash -ne $hashVorher) {
        Write-Host "  Deploy.ps1 wurde aktualisiert - Neustart mit der neuen Fassung" -ForegroundColor Yellow
        $neu = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $PSCommandPath, "-Basis", $Basis, "-Neustart")
        if ($Erstinstallation) { $neu += "-Erstinstallation" }
        if ($VolleTests) { $neu += "-VolleTests" }
        & powershell @neu
        exit $LASTEXITCODE
    }
}

# ------------------------------------------------------------------ 4. Einrichten
Schritt "Journal: Abhaengigkeiten, Sicherung, Migration, Oberflaeche"
Tu "setup.cmd" { & cmd /c "$journal\setup.cmd" }
if (Test-Path "$journal\journal.db") {
    $stempel = Get-Date -Format "yyyyMMdd-HHmmss"
    New-Item -ItemType Directory -Force -Path "$journal\backups" | Out-Null
    Tu "Sicherung journal.db -> backups\vor-deploy-$stempel.db" {
        & cmd /c "$journal\backup.cmd" "$journal\journal.db" "$journal\backups\vor-deploy-$stempel.db"
    }
}
Tu "alembic upgrade head" { Push-Location $journal; try { & ".venv\Scripts\python.exe" -m alembic upgrade head } finally { Pop-Location } }
if ($npm) {
    Tu "Oberflaeche bauen (npm ci, npm run build)" {
        Push-Location "$journal\ui"; try { npm ci --no-audit --no-fund; npm run build } finally { Pop-Location }
    }
}

Schritt "Roller: Abhaengigkeiten"
Tu "venv + requirements" {
    Push-Location $roller
    try {
        if (-not (Test-Path ".venv")) { python -m venv .venv }
        # ibapi steht nicht auf PyPI: aus der installierten TWS API (Standardpfad C:\TWS)
        if (-not (Test-Path ".venv\Lib\site-packages\ibapi")) {
            if (Test-Path "C:\TWS\source\pythonclient") {
                & ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check "C:\TWS\source\pythonclient"
            } else { throw "ibapi fehlt: TWS API 'Latest' nach C:\TWS installieren" }
        }
        # Festgeschriebener Stand (AP-17g, M08), sonst die offenen Mindestversionen
        $anforderungen = if (Test-Path "requirements-lock.txt") { "requirements-lock.txt" } else { "requirements.txt" }
        & ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r $anforderungen
    } finally { Pop-Location }
}
if (-not (Test-Path "$roller\config.json")) {
    Write-Warning "options-roller\config.json fehlt - aus config.beispiel.json anlegen (AP-15, Schritt 'Konfiguration')"
}

$lab = Join-Path $Basis "momentum-lab"
if ((Test-Path $lab) -and (Test-Path "$lab\pyproject.toml")) {
    Schritt "Momentum Lab: Abhaengigkeiten"
    Tu "pip install -e ." { Push-Location $lab; try { if (-not (Test-Path ".venv")) { python -m venv .venv }; & ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -e . } finally { Pop-Location } }
}

# ------------------------------------------------------------------ 5. Tests, dann Starten
Schritt "Tests (vor dem Start der Dienste)"
Tu "Roller-Tests" { Push-Location $roller; try { & ".venv\Scripts\python.exe" -m pytest -q } finally { Pop-Location } }
if ($VolleTests) {
    Tu "Journal-Tests (voll)" { & cmd /c "$journal\test.cmd" -q }
} else {
    # Rauchtest: Schnittstellen zum Roller, Journal-API, Oberflaechen-Routen, Rebuild-Kern, Import
    Tu "Journal-Rauchtest" {
        & cmd /c "$journal\test.cmd" -q -x tests/test_api_roller.py tests/test_api_roller_befehl.py tests/test_api_roller_befehl_aufnehmen.py tests/test_api_roller_historie.py tests/test_api_system.py tests/test_api_journal.py tests/test_ui_routen.py tests/test_roller_verknuepfung.py tests/test_skripte.py
    }
}

Schritt "Starten und pruefen"
if (Test-Path "$roller\config.json") {
    Tu "Roller-Dienst starten" { & "$roller\Start-Dienst.ps1" }
}
# Lesender Live-Dienst (Port 8601, nur Shorts-Uebersicht des Live-Kontos). Ohne Orders-Dienst auf demselben Port.
if (Test-Path "$roller\Start-Dienst-Live-Lesen.ps1") {
    Tu "Live-Lesedienst starten" { & "$roller\Start-Dienst-Live-Lesen.ps1" }
}
# Das Journal braucht den Statusport des Live-Dienstes (sonst zeigt die Station nur Paper).
$env:ROLLER_LIVE_STATUS_PORT = "8601"
Tu "Journal-Server starten" {
    $log = "$env:USERPROFILE\.trading-journal\logs"
    New-Item -ItemType Directory -Force -Path $log | Out-Null
    Start-Process -FilePath "$journal\.venv\Scripts\pythonw.exe" `
        -ArgumentList "-m", "uvicorn", "api.app:app", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $journal -WindowStyle Hidden `
        -RedirectStandardOutput "$log\server.log" -RedirectStandardError "$log\server-fehler.log"
    Start-Sleep -Seconds 5
}
Tu "Roller-Pruefung" { Push-Location $roller; try { & ".venv\Scripts\python.exe" -m roller.pruefung } finally { Pop-Location } }
# Smoke-Test (AP-17g, M08): jede Seite und jeder API-Weg der Oberflaeche antwortet. Ein Befund stoppt den Deploy nicht
# (die Dienste laufen), wird aber laut gemeldet.
Tu "Smoke-Test der Oberflaeche" {
    & "$journal\.venv\Scripts\python.exe" "$journal\werkzeuge\smoke.py" "http://127.0.0.1:8000"
    if ($LASTEXITCODE -ne 0) { Write-Warning "Smoke-Test meldet Befunde (siehe oben) - Oberflaeche pruefen"; $global:LASTEXITCODE = 0 }
}

Schritt "Fertig"
Write-Host "  Station: http://127.0.0.1:8000/start"
if ($liveMitOrders) {
    Write-Host "  ACHTUNG: Der Live-Dienst mit Orders laeuft NICHT mehr (nur der lesende). Offene Profit-Targets liegen bei IB." -ForegroundColor Yellow
    Write-Host "  Wieder starten: cd $roller; .\Start-Dienst-Live.ps1  (Eingabe ECHTGELD)" -ForegroundColor Yellow
}
if (Test-Path "$roller\config.json") {
    Push-Location $roller
    try { & ".venv\Scripts\python.exe" -m roller.live_einrichten --pruefen } finally { Pop-Location }
    $global:LASTEXITCODE = 0
}
