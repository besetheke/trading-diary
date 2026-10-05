"""CLI des Journals (AP-02): ``journal import <datei>`` — seit AP-04p
zusätzlich ``journal rebuild``, seit AP-04d ``journal
kandidaten-ausschreiben`` und ``journal kandidaten-einlesen``, seit AP-06
``journal kennzahlen``, seit AP-13y ``journal import-optionapp``.

Der Datenbankpfad kommt aus ``--db``, sonst aus der Umgebungsvariablen
``JOURNAL_DB``, sonst gilt ``journal.db`` (OF-06). Aufgerufen als
``python -m journal import <datei>`` oder — nach ``pip install -e .`` — als
``journal import <datei>``.
"""

import argparse
import os
import pathlib
import sys

from analytics.kennzahlen import als_csv, kennzahlen_bericht
from analytics.kommission import als_csv as kommission_als_csv
from analytics.kommission import kommissions_bericht
from analytics.steuer import als_csv as steuer_als_csv
from ingest.flex import import_flex_file
from ingest.optionapp import import_optionapp_file
from journal.durchsicht import kandidaten_ausschreiben, urteile_einlesen
from journal.rebuild import rebuild
from journal.steuer import steuer_bericht


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
    oa_importer = unterbefehle.add_parser(
        "import-optionapp",
        help="OptionApp-Trade-Export idempotent in die Datenbank importieren (AP-13)",
    )
    oa_importer.add_argument("datei", type=pathlib.Path, help="Pfad zur XLSX-Exportdatei")
    oa_importer.add_argument(
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
    ausschreiber = unterbefehle.add_parser(
        "kandidaten-ausschreiben",
        help="Offene Rollkandidaten als XLSX ausschreiben (AP-04d)",
    )
    ausschreiber.add_argument(
        "datei", type=pathlib.Path, help="Pfad zur Zieldatei (darf nicht bestehen)"
    )
    ausschreiber.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    einleser = unterbefehle.add_parser(
        "kandidaten-einlesen",
        help="Entscheidungen aus einer ausgeschriebenen Datei übernehmen (AP-04d)",
    )
    einleser.add_argument("datei", type=pathlib.Path, help="Pfad zur Kandidatendatei")
    einleser.add_argument(
        "--ueberschreiben",
        action="store_true",
        help="Gespeicherte Entscheidungen ändern, statt bei Widerspruch abzubrechen",
    )
    einleser.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    kennzahl = unterbefehle.add_parser(
        "kennzahlen",
        help="Kennzahlen je Kette/Struktur als CSV schreiben; fx_rates und "
        "metrics_by_chain vollständig neu (AP-06)",
    )
    kennzahl.add_argument("datei", type=pathlib.Path, help="Pfad zur Zieldatei (CSV)")
    kennzahl.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    kennzahl.add_argument(
        "--sicht",
        choices=("kette", "konto"),
        default="kette",
        help="Auswertungssicht (Default: kette — die strategische Sicht, AP-06 E1)",
    )
    kennzahl.add_argument(
        "--nur-stufe-a",
        action="store_true",
        help="Nur Ketten/Strukturen der Qualitätsstufe A (E6)",
    )
    kennzahl.add_argument(
        "--kommission",
        type=pathlib.Path,
        default=None,
        metavar="DATEI",
        help="Zusätzlich die Kommissionsattribution als eigene CSV schreiben (AP-06, Tranche II)",
    )
    steuer = unterbefehle.add_parser(
        "steuer",
        help="Steuerliche Auswertung: Töpfe je Jahr, Details, Erträge, Fehler (AP-10)",
    )
    steuer.add_argument("datei", type=pathlib.Path, help="Pfad zur Zieldatei (CSV)")
    steuer.add_argument(
        "--jahr",
        type=int,
        default=None,
        help="Nur Zeilen dieses Zuflussjahres; die Fehlerliste bleibt vollständig",
    )
    steuer.add_argument(
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
    elif argumente.befehl == "import-optionapp":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = import_optionapp_file(db_pfad, argumente.datei)
        except (FileNotFoundError, ValueError) as fehler:
            # Defekt der Quelle: benannt abbrechen, kein Traceback — die
            # Transaktion hat nichts geschrieben (AP-02, AP-13).
            print(f"Import fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"OptionApp-Import {argumente.datei.name}: {ergebnis.zeilen_gesamt} "
            f"Trades gelesen, {ergebnis.zeilen_neu} neu, "
            f"{ergebnis.zeilen_uebersprungen} übersprungen"
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
            f"{ergebnis.overrides_verwaist} verwaist; "
            f"{ergebnis.kandidaten_offen} offene Rollkandidaten; "
            f"OA-Abgleich: {ergebnis.oa_zugeordnet} zugeordnet, "
            f"{ergebnis.oa_fehler} ohne eindeutige Kette; "
            f"{ergebnis.campaign_kandidaten_offen} offene Campaign-Kandidaten"
        )
        if ergebnis.overrides_verwaist > 0:
            # Vertrag 20: Verwaistes wird niemals übergangen — der Aufruf
            # muss es bemerken, daher Rückgabe 1.
            print(
                "Verwaiste Overrides benannt (siehe Standardfehlerausgabe).",
                file=sys.stderr,
            )
            return 1
    elif argumente.befehl == "kandidaten-ausschreiben":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = kandidaten_ausschreiben(db_pfad, argumente.datei)
        except (FileExistsError, ValueError) as fehler:
            # Bestehende Datei oder ungültiges Ziel: benannt abbrechen, kein
            # Traceback — es wurde nichts geschrieben (AP-04d, Vertrag 18).
            print(f"Ausschreiben fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Ausgeschrieben nach {argumente.datei}: {ergebnis.gruppen} Gruppen, "
            f"{ergebnis.kandidaten} Kandidaten"
        )
    elif argumente.befehl == "kandidaten-einlesen":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = urteile_einlesen(
                db_pfad, argumente.datei, ueberschreiben=argumente.ueberschreiben
            )
        except ValueError as fehler:
            # Widerspruch in der Datei oder den gespeicherten Entscheidungen:
            # benannt abbrechen, kein Traceback — die kurze Transaktion hat
            # nichts geschrieben (AP-04d, Vertrag 18).
            print(f"Einlesen fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Einlesen {argumente.datei.name}: {ergebnis.neu_bestaetigt} neu "
            f"bestätigt, {ergebnis.neu_abgelehnt} neu abgelehnt, "
            f"{ergebnis.unveraendert} unverändert, {ergebnis.geaendert} geändert, "
            f"{ergebnis.unentschieden} unentschieden"
        )
        print("Jetzt `journal rebuild` ausführen, damit die Entscheidungen wirksam werden.")
    elif argumente.befehl == "kennzahlen":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = kennzahlen_bericht(
                db_pfad,
                sicht=argumente.sicht,
                nur_qualitaetsstufe_a=argumente.nur_stufe_a,
            )
        except ValueError as fehler:
            # Widerspruch in den Daten: benannt abbrechen, kein Traceback —
            # die Transaktion hat nichts geschrieben (AP-06v, Regel 8).
            print(f"Kennzahlen fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        # UTF-8 mit BOM wie der Kandidaten-Export (Regel 13): Excel öffnet die
        # Datei ohne Encoding-Rätsel; Zeilenende fest auf \n, damit die Datei
        # auf jedem Betriebssystem bytgleich ausfällt.
        with open(argumente.datei, "w", encoding="utf-8-sig", newline="\n") as datei:
            datei.write(als_csv(ergebnis) + "\n")
        print(
            f"Kennzahlen nach {argumente.datei}: {len(ergebnis.ketten)} Ketten, "
            f"{len(ergebnis.strukturen)} Strukturen, {len(ergebnis.fehler)} Fehler, "
            f"Summe netto EUR {ergebnis.summe_netto_eur}"
        )
        if argumente.kommission is not None:
            kommission = kommissions_bericht(
                db_pfad,
                sicht=argumente.sicht,
                nur_qualitaetsstufe_a=argumente.nur_stufe_a,
            )
            # UTF-8 mit BOM wie der Kennzahlen-Bericht (Regel 13): Excel öffnet
            # die Datei ohne Encoding-Rätsel; Zeilenende fest auf \n, damit die
            # Datei auf jedem Betriebssystem bytgleich ausfällt (AP-06w, E6).
            with open(argumente.kommission, "w", encoding="utf-8-sig", newline="\n") as datei:
                datei.write(kommission_als_csv(kommission) + "\n")
            print(
                f"Kommissionsattribution nach {argumente.kommission}: "
                f"{len(kommission.gruppen)} Gruppen, "
                f"{kommission.anzahl_ketten_gesamt} Ketten gesamt"
            )
    elif argumente.befehl == "steuer":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        ergebnis = steuer_bericht(db_pfad)
        # UTF-8 mit BOM wie der Kennzahlen-Bericht (Regel 13): Excel öffnet
        # die Datei ohne Encoding-Rätsel; Zeilenende fest auf \n, damit die
        # Datei auf jedem Betriebssystem bytgleich ausfällt. Exit-Code 0 nur
        # mit geschriebenem Dateikörper (AP-10v, Vertrag 13).
        with open(argumente.datei, "w", encoding="utf-8-sig", newline="\n") as datei:
            datei.write(steuer_als_csv(ergebnis, jahr=argumente.jahr))
        print(
            f"Steuer nach {argumente.datei}: {len(ergebnis.toepfe)} Topfzeilen, "
            f"{len(ergebnis.details)} Legs bewertet, {len(ergebnis.ungeklaert)} "
            f"Basis ungeklärt, {len(ergebnis.ertraege)} Ertragszeilen, "
            f"{len(ergebnis.fehler)} Fehler"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
