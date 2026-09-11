<#
.SYNOPSIS
  Startet Claude Code fuer ein Arbeitspaket mit dem im Auftrag hinterlegten Modell.

.BEISPIELE
  .\ap.ps1 AP-02              Paket bearbeiten
  .\ap.ps1 AP-02 -Review      Diff-Review durch das starke Modell
  .\ap.ps1 -Liste             Alle Auftraege mit Modell und Status
  .\ap.ps1 AP-01 -Fertig      Status auf 'fertig' setzen, nach bestandenem Review
#>
param(
    [Parameter(Position = 0)][string]$Paket,
    [switch]$Review,
    [switch]$Liste,
    [switch]$Fertig,
    [switch]$Trocken
)

$ErrorActionPreference = "Stop"
$Wurzel        = $PSScriptRoot
$AuftragsOrdner = Join-Path $Wurzel "auftraege"
$PlanDatei     = "plan/trading-journal-projektplan.md"

$Settings = @{
    "stark"    = ".claude/settings.json"
    "guenstig" = ".claude/settings-guenstig.json"
}

function Kopf-Lesen($datei) {
    $inhalt = Get-Content $datei -Raw -Encoding UTF8
    $ergebnis = @{ modell = "stark"; status = "offen"; titel = ""; aendert_tests = $false }
    if ($inhalt -match '(?m)^modell:\s*(\S+)')  { $ergebnis.modell = $Matches[1].ToLower() }
    if ($inhalt -match '(?m)^status:\s*(\S+)')  { $ergebnis.status = $Matches[1] }
    if ($inhalt -match '(?m)^titel:\s*(.+)$')   { $ergebnis.titel  = $Matches[1].Trim() }
    if ($inhalt -match '(?m)^aendert_tests:\s*ja') { $ergebnis.aendert_tests = $true }
    return $ergebnis
}

if ($Liste) {
    Write-Host ""
    Write-Host ("{0,-8} {1,-10} {2,-12} {3}" -f "Paket","Modell","Status","Titel")
    Write-Host ("-" * 78)
    Get-ChildItem $AuftragsOrdner -Filter "AP-*.md" | Sort-Object Name | ForEach-Object {
        $k = Kopf-Lesen $_.FullName
        $farbe = if ($k.status -eq "fertig") { "DarkGray" } elseif ($k.modell -eq "stark") { "Cyan" } else { "Green" }
        Write-Host ("{0,-8} {1,-10} {2,-12} {3}" -f $_.BaseName, $k.modell, $k.status, $k.titel) -ForegroundColor $farbe
    }
    Write-Host ""
    exit 0
}

if (-not $Paket) {
    Write-Host "Verwendung: .\ap.ps1 <Paket> [-Review] | .\ap.ps1 -Liste" -ForegroundColor Yellow
    exit 1
}

$Paket = $Paket.ToUpper()
$AuftragsDatei = Join-Path $AuftragsOrdner "$Paket.md"
if (-not (Test-Path $AuftragsDatei)) {
    Write-Host "Kein Auftrag gefunden: $AuftragsDatei" -ForegroundColor Red
    Write-Host "Vorlage kopieren: auftraege\_vorlage.md" -ForegroundColor Yellow
    exit 1
}

$Kopf = Kopf-Lesen $AuftragsDatei

if ($Fertig) {
    $inhalt = Get-Content $AuftragsDatei -Raw -Encoding UTF8
    if ($inhalt -notmatch '(?m)^status:\s*\S+') {
        Write-Host "Kein status-Feld im Auftragskopf gefunden." -ForegroundColor Red
        exit 1
    }
    $neu = $inhalt -replace '(?m)^status:\s*\S+', 'status: fertig'
    Set-Content $AuftragsDatei -Value $neu -Encoding UTF8 -NoNewline
    Write-Host "$Paket auf 'fertig' gesetzt." -ForegroundColor Green
    Write-Host "Erinnerung: Review durchgefuehrt? Diff auf tests/ und fixtures/ geprueft?" -ForegroundColor Yellow
    exit 0
}

# Review laeuft grundsaetzlich auf dem starken Modell.
$Modell = if ($Review) { "stark" } else { $Kopf.modell }
if (-not $Settings.ContainsKey($Modell)) {
    Write-Host "Unbekanntes Modell '$Modell' im Auftragskopf. Erlaubt: stark, guenstig" -ForegroundColor Red
    exit 1
}
$SettingsDatei = $Settings[$Modell]
if (-not (Test-Path (Join-Path $Wurzel $SettingsDatei))) {
    Write-Host "Settings-Datei fehlt: $SettingsDatei" -ForegroundColor Red
    exit 1
}

if ($Review) {
    $Prompt = @"
Du bist Reviewer, nicht Umsetzer. Pruefe die Arbeit am Arbeitspaket $Paket.

Vorgehen:
1. Lies $PlanDatei, Abschnitt zu $Paket, und auftraege/$Paket.md.
2. Lies CLAUDE.md.
3. Sieh dir 'git diff' an.

Pruefe in dieser Reihenfolge:
- Sind Tests oder Fixtures veraendert worden? Das ist ein Abbruchgrund.
- Sind die Abnahmekriterien des Arbeitspakets tatsaechlich erfuellt, oder nur
  scheinbar? Pruefe die Testinhalte, nicht nur ob sie gruen sind.
- Verstoesse gegen die Regeln in CLAUDE.md, besonders Decimal statt float,
  Reinheit der engine-Module, Pflichtfeld 'erkennung'.
- Fachliche Fehler gemessen am Plan.

Aendere keinen Code. Liefere eine Befundliste, nach Schwere sortiert, und ein
klares Urteil: abnahmefaehig ja oder nein.
"@
    Write-Host "REVIEW $Paket  ->  starkes Modell" -ForegroundColor Cyan
}
else {
    $Prompt = @"
Bearbeite das Arbeitspaket $Paket.

1. Lies CLAUDE.md. Die Regeln dort gelten ohne Ausnahme.
2. Lies $PlanDatei und dort den Abschnitt zu $Paket, inklusive der
   Abnahmekriterien.
3. Lies auftraege/$Paket.md fuer den konkreten Auftrag.

Setze ausschliesslich dieses Arbeitspaket um. Erweitere den Umfang nicht.
Fertig bist du, wenn die Abnahmekriterien erfuellt sind und 'pytest' sowie
'ruff check .' sauber durchlaufen.

Aendere unter keinen Umstaenden Dateien unter tests/, fixtures/, plan/ oder
.claude/. Faellt ein Test, ist der Code falsch. Ist die Anforderung unklar,
trage sie in OFFENE_FRAGEN.md ein und brich ab.

Melde am Ende: welche Abnahmekriterien erfuellt sind, welche nicht, und was du
in OFFENE_FRAGEN.md eingetragen hast.
"@
    $farbe = if ($Modell -eq "stark") { "Cyan" } else { "Green" }
    Write-Host "$Paket : $($Kopf.titel)" -ForegroundColor White
    Write-Host "Modell: $Modell  ($SettingsDatei)" -ForegroundColor $farbe
    if ($Kopf.aendert_tests) {
        if ($Modell -ne "stark") {
            Write-Host "ABBRUCH: Paket darf Tests aendern, laeuft aber nicht auf dem starken Modell." -ForegroundColor Red
            exit 1
        }
        Write-Host "ACHTUNG: Dieses Paket darf Test-Erwartungen aendern." -ForegroundColor Yellow
        Write-Host "         Pruefe im Review jede Aenderung unter tests/ gegen das Auftragsdokument." -ForegroundColor Yellow
    }
}

if ($Trocken) {
    Write-Host "`n--- Trockenlauf, es wird nichts gestartet ---" -ForegroundColor Yellow
    Write-Host "claude --settings $SettingsDatei" -ForegroundColor DarkGray
    Write-Host $Prompt
    exit 0
}

Push-Location $Wurzel
try {
    & claude --settings $SettingsDatei $Prompt
}
finally {
    Pop-Location
}
