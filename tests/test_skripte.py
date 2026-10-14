"""Schutz der Betriebsskripte (AP-15): Deploy.ps1 und die Start-/Stopp-Skripte.

Anlass (14.10.2026): In `Deploy.ps1` war aus dem Pfad zu `test.cmd` beim Schreiben der Datei ein
Tabulatorzeichen geworden; der Rauchtest brach auf dem Server ab, obwohl der Trockenlauf sauber
durchlief. Geprüft wird deshalb, ohne die Skripte auszuführen:
- keine Steuerzeichen und keine Tabulatoren,
- jeder Pfad der Form "$journal\\<datei>" oder "$roller\\<datei>" im Skript zeigt auf eine Datei,
  die es im jeweiligen Projekt gibt (Roller nur, wenn sein Ordner neben dem Journal liegt),
- das Skript lässt sich fehlerfrei parsen (nur wenn PowerShell vorhanden ist).
"""

import pathlib
import re
import shutil
import subprocess

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
SKRIPTE = [
    WURZEL / "werkzeuge" / "server" / "Deploy.ps1",
    WURZEL / "Schnellstart.ps1",
    WURZEL / "Beenden.ps1",
]
STEUERZEICHEN = re.compile("[\x00-\x08\x09\x0b\x0c\x0e-\x1f]")
PFAD = re.compile(r'"[$](journal|roller)[\\]([A-Za-z0-9_.-]+[.](?:cmd|ps1|txt))"')


@pytest.mark.parametrize("skript", SKRIPTE, ids=lambda p: p.name)
def test_keine_steuerzeichen(skript):
    zeilen = skript.read_text(encoding="utf-8").splitlines()
    schlecht = [n for n, z in enumerate(zeilen, 1) if STEUERZEICHEN.search(z)]
    assert not schlecht, f"{skript.name}: Steuerzeichen oder Tabs in den Zeilen {schlecht}"


def test_deploy_pfade_zeigen_auf_vorhandene_dateien():
    text = (WURZEL / "werkzeuge" / "server" / "Deploy.ps1").read_text(encoding="utf-8")
    roller = WURZEL.parent / "options-roller"
    gefunden = PFAD.findall(text)
    assert gefunden, "kein Pfad erkannt - Muster prüfen"
    fehlend = []
    for ordner, name in gefunden:
        basis = WURZEL if ordner == "journal" else roller
        if ordner == "roller" and not basis.exists():
            continue
        if not (basis / name).exists():
            fehlend.append(f"{ordner}/{name}")
    assert not fehlend, f"Deploy.ps1 nennt Dateien, die es nicht gibt: {fehlend}"


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell nicht vorhanden")
@pytest.mark.parametrize("skript", SKRIPTE, ids=lambda p: p.name)
def test_skript_laesst_sich_parsen(skript):
    befehl = (
        "$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile("
        f"'{skript}',[ref]$null,[ref]$e); "
        "if($e){ $e | ForEach-Object { $_.Message }; exit 1 }"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", befehl],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
