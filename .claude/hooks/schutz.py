#!/usr/bin/env python3
"""PreToolUse-Hook: blockt Schreibzugriffe auf geschuetzte Pfade.

Zwei Profile, weil der Schutz asymmetrisch sein muss:

  --profil locker   fuer das starke Modell. Es legt in AP-01 das Testgeruest und
                    die Fixtures selbst an und muss sie schreiben duerfen.
                    Geschuetzt bleiben nur Plan und Konfiguration.
  --profil streng   fuer das guenstige Modell. Tests und Fixtures sind ab AP-01
                    fertig und unveraenderlich.

Ohne Angabe gilt streng — im Zweifel wird mehr geschuetzt, nicht weniger.

Exit-Code 2 bricht den Werkzeugaufruf ab, bevor die Rechtepruefung greift.
Exit-Code 0 laesst ihn zu.

Bewusst defensiv: bei unbekanntem Eingabeformat wird NICHT geblockt, damit der
Hook nicht die gesamte Arbeit lahmlegt. Der Schutz ist eine Bremse gegen
Versehen, kein Sicherheitsmechanismus gegen boesen Willen. Die eigentliche
Garantie bleibt das Diff-Review.
"""
import json
import sys
from pathlib import PurePosixPath

PROFILE = {
    "streng": ("tests/", "fixtures/", ".claude/", "plan/"),
    "locker": (".claude/", "plan/"),
}


def pfade_finden(objekt):
    """Sammelt alles, was nach einem Dateipfad aussieht, rekursiv."""
    treffer = []
    if isinstance(objekt, dict):
        for schluessel, wert in objekt.items():
            if schluessel in ("file_path", "path", "notebook_path", "filePath"):
                if isinstance(wert, str):
                    treffer.append(wert)
            else:
                treffer.extend(pfade_finden(wert))
    elif isinstance(objekt, list):
        for eintrag in objekt:
            treffer.extend(pfade_finden(eintrag))
    return treffer


def normieren(pfad: str) -> str:
    p = pfad.replace("\\", "/")
    if ":" in p[:3]:            # Windows-Laufwerksbuchstabe
        p = p.split(":", 1)[1]
    p = p.lstrip("/")
    try:
        p = str(PurePosixPath(p))
    except ValueError:
        pass
    return p


def profil_lesen() -> tuple:
    profil = "streng"
    argumente = sys.argv[1:]
    for i, arg in enumerate(argumente):
        if arg == "--profil" and i + 1 < len(argumente):
            profil = argumente[i + 1].strip().lower()
        elif arg.startswith("--profil="):
            profil = arg.split("=", 1)[1].strip().lower()
    return PROFILE.get(profil, PROFILE["streng"])


def main() -> int:
    geschuetzt = profil_lesen()
    roh = sys.stdin.read()
    if not roh.strip():
        return 0
    try:
        daten = json.loads(roh)
    except json.JSONDecodeError:
        # Unbekanntes Format: nicht blind durchwinken, sondern den Rohtext
        # grob nach geschuetzten Pfaden absuchen.
        flach = roh.replace("\\\\", "/").replace("\\", "/")
        for praefix in geschuetzt:
            if praefix in flach:
                sys.stderr.write(
                    f"BLOCKIERT: Eingabe war kein gueltiges JSON und verweist auf "
                    f"einen geschuetzten Pfad ('{praefix}'). Im Zweifel wird "
                    f"blockiert. Siehe CLAUDE.md, Regel 1.\n"
                )
                return 2
        return 0

    for pfad in pfade_finden(daten):
        norm = normieren(pfad)
        for praefix in geschuetzt:
            if norm.startswith(praefix) or f"/{praefix}" in f"/{norm}":
                sys.stderr.write(
                    f"BLOCKIERT: Schreibzugriff auf geschuetzten Pfad '{pfad}'.\n"
                    f"Dieser Pfad ist im aktiven Schutzprofil unveraenderlich "
                    f"(CLAUDE.md, Regel 1).\n"
                    f"Schlaegt ein Test fehl, ist der Code falsch oder die "
                    f"Anforderung unklar. Im zweiten Fall: Eintrag in "
                    f"OFFENE_FRAGEN.md und Abbruch.\n"
                )
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
