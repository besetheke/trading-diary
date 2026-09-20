"""CLI des Journals (AP-02): ``journal import <datei>`` — seit AP-04p
zusätzlich ``journal rebuild``.

Der Datenbankpfad kommt aus ``--db``, sonst aus der Umgebungsvariablen
``JOURNAL_DB``, sonst gilt ``journal.db`` (OF-06). Aufgerufen als
``python -m journal import <datei>`` oder — nach ``pip install -e .`` — als
``journal import <datei>``.
"""

import argparse
import os
import pathlib
import sys

from ingest.flex import import_flex_file
from journal.rebuild import rebuild


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="journal",
        description="Trading-Journal: Import und Pflege der Datenbank",
    )
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)
    importer = unterbefehle.add_parser(
        "import",
        help="Flex-Query-XML idempotent in die Datenbank importieren (AP-02)",
    )
    importer.add_argument("datei", type=pathlib.Path, help="Pfad zur Flex-XML-Datei")
    importer.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    rebuilder = unterbefehle.add_parser(
        "rebuild",
        help="Legs, Strukturen, Ketten und Kettenglieder aus executions neu aufbauen (AP-04p)",
    )
    rebuilder.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    argumente = parser.parse_args(argv)

    if argumente.befehl == "import":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = import_flex_file(db_pfad, argumente.datei)
        except (FileNotFoundError, ValueError) as fehler:
            # Datenfehler der Quelle: benannt abbrechen, kein Traceback —
            # die Transaktion hat nichts geschrieben (AP-02).
            print(f"Import fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Import {argumente.datei.name}: {ergebnis.zeilen_gesamt} Zeilen gelesen, "
            f"{ergebnis.zeilen_neu} neu, {ergebnis.zeilen_uebersprungen} übersprungen"
        )
    elif argumente.befehl == "rebuild":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = rebuild(db_pfad)
        except ValueError as fehler:
            # Widerspruch in den Daten oder den Overrides: benannt abbrechen,
            # kein Traceback — die kurze Transaktion hat nichts geschrieben.
            print(f"Rebuild fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Rebuild {db_pfad}: {ergebnis.legs} Legs, {ergebnis.structures} Strukturen, "
            f"{ergebnis.chains} Ketten, {ergebnis.chain_links} Kettenglieder, "
            f"{ergebnis.nicht_strukturiert} unstrukturiert; "
            f"Overrides: {ergebnis.overrides_angewandt} angewandt, "
            f"{ergebnis.overrides_verwaist} verwaist"
        )
        if ergebnis.overrides_verwaist > 0:
            # Vertrag 20: Verwaistes wird niemals übergangen — der Aufruf
            # muss es bemerken, daher Rückgabe 1.
            print(
                "Verwaiste Overrides benannt (siehe Standardfehlerausgabe).",
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
