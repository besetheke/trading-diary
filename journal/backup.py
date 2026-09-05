"""Backup mit ``VACUUM INTO`` (§3).

VACUUM INTO liest einen Snapshot und schreibt ihn in eine neue Datei, ohne
die Quelldatenbank zu sperren — die Kopie ist damit auch bei laufendem
Schreibzugriff konsistent (Abnahme AP-01), und der Options Roller wird nicht
blockiert (§4.1). Kein Dateikopieren bei aktivem WAL.

Aufruf: python -m journal.backup <quelldatei> <zieldatei>
Der Zielpfad ist konfigurierbar; ein bestehendes Ziel wird nicht still
überschrieben. Die Aufbewahrung (§3: letzte 14 Stände) rotiert der
Aufrufer — sie ist nicht Teil dieses Skripts.
"""

import argparse
import pathlib
import sqlite3
import sys


def create_backup(quelldatei: str | pathlib.Path, zieldatei: str | pathlib.Path) -> pathlib.Path:
    """Erzeugt eine konsistente Kopie der Quelldatenbank unter zieldatei."""
    quelle = pathlib.Path(quelldatei)
    ziel = pathlib.Path(zieldatei)

    if not quelle.is_file():
        raise FileNotFoundError(f"Quelldatenbank nicht gefunden: {quelle}")
    if ziel.exists():
        raise FileExistsError(f"Zieldatei existiert bereits, wird nicht überschrieben: {ziel}")
    ziel.parent.mkdir(parents=True, exist_ok=True)

    # mode=ro: das Backup schließt die Quelle nur lesend. as_uri() percent-
    # encoded Sonderzeichen in Pfaden (Leerzeichen, '#').
    verbindung = sqlite3.connect(f"{quelle.resolve().as_uri()}?mode=ro", uri=True, timeout=5.0)
    try:
        verbindung.execute("VACUUM INTO ?", (str(ziel),))
    finally:
        verbindung.close()
    return ziel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Konsistentes SQLite-Backup mit VACUUM INTO."
    )
    parser.add_argument("quelldatei", help="Pfad der SQLite-Datenbankdatei")
    parser.add_argument("zieldatei", help="Pfad der Backup-Kopie (darf nicht existieren)")
    argumente = parser.parse_args(argv)

    ziel = create_backup(argumente.quelldatei, argumente.zieldatei)
    print(f"Backup geschrieben: {ziel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
