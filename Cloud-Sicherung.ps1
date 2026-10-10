# Kopiert die juengste lokale Datenbank-Sicherung in die Cloud, aber nur wenn
# sie sich von der zuletzt dort abgelegten Kopie unterscheidet (SHA256-
# Vergleich statt fester Zeitabstaende). Haelt danach maximal -MaxKopien
# Dateien im Zielordner, aeltere werden geloescht (Rotation wie lokal in
# nachtlauf.cmd, nur mit anderem Zaehlwert und anderem Ort).
param(
    [Parameter(Mandatory = $true)][string]$QuellOrdner,
    [Parameter(Mandatory = $true)][string]$ZielOrdner,
    [int]$MaxKopien = 10
)

New-Item -ItemType Directory -Force -Path $ZielOrdner | Out-Null

$neueste = Get-ChildItem -Path $QuellOrdner -Filter "journal-*.db" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1

if (-not $neueste) {
    Write-Output "Keine lokale Sicherung gefunden in $QuellOrdner"
    exit 0
}

$letzteCloud = Get-ChildItem -Path $ZielOrdner -Filter "journal-*.db" -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending | Select-Object -First 1

$kopieren = $true
if ($letzteCloud) {
    $hashNeu = (Get-FileHash -Path $neueste.FullName -Algorithm SHA256).Hash
    $hashAlt = (Get-FileHash -Path $letzteCloud.FullName -Algorithm SHA256).Hash
    if ($hashNeu -eq $hashAlt) {
        $kopieren = $false
    }
}

if ($kopieren) {
    Copy-Item -Path $neueste.FullName -Destination (Join-Path $ZielOrdner $neueste.Name) -Force
    Write-Output "Cloud-Sicherung kopiert: $($neueste.Name)"
} else {
    Write-Output "Cloud-Sicherung uebersprungen (unveraendert seit $($letzteCloud.Name))"
}

$alle = Get-ChildItem -Path $ZielOrdner -Filter "journal-*.db" -ErrorAction SilentlyContinue |
    Sort-Object Name -Descending
if ($alle.Count -gt $MaxKopien) {
    $alle | Select-Object -Skip $MaxKopien | ForEach-Object {
        Write-Output "Entferne alte Cloud-Sicherung: $($_.Name)"
        Remove-Item $_.FullName -Force
    }
}
