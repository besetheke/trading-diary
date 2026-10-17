"""CLI des Journals (AP-02): ``journal import <datei>`` — seit AP-04p
zusätzlich ``journal rebuild``, seit AP-04d ``journal
kandidaten-ausschreiben`` und ``journal kandidaten-einlesen``, seit AP-06
``journal kennzahlen``, seit AP-13y ``journal import-optionapp``, seit
AP-02a2k ``journal abrufen`` (nächtlicher Abruf der Flex-Query).

Der Datenbankpfad kommt aus ``--db``, sonst aus der Umgebungsvariablen
``JOURNAL_DB``, sonst gilt ``journal.db`` (OF-06). Aufgerufen als
``python -m journal import <datei>`` oder — nach ``pip install -e .`` — als
``journal import <datei>``.
"""

import argparse
import os
import pathlib
import sys
from datetime import date

from analytics.backtest import als_csv as backtest_als_csv
from analytics.backtest import backtest_bericht
from analytics.degradation import als_csv as degradation_als_csv
from analytics.degradation import degradations_bericht
from analytics.equity import als_csv as equity_als_csv
from analytics.equity import equity_bericht
from analytics.kennzahlen import als_csv, kennzahlen_bericht
from analytics.kommission import als_csv as kommission_als_csv
from analytics.kommission import kommissions_bericht
from analytics.steuer import als_csv as steuer_als_csv
from ingest import flex_abruf
from ingest.flex import import_flex_file, nachtragen_realisiert
from ingest.optionapp import import_optionapp_file, import_optionapp_ordner
from ingest.optionomega import (
    OoFormatFehler,
    import_optionomega_file,
    import_optionomega_ordner,
)
from journal.durchsicht import kandidaten_ausschreiben, urteile_einlesen
from journal.kampagnen_durchsicht import kampagnen_ausschreiben, kampagnen_urteile_einlesen
from journal.rebuild import rebuild
from journal.steuer import steuer_bericht


def _oo_bericht(name: str, ergebnis) -> None:
    if ergebnis.schon_importiert:
        print(f"Option Omega {name}: bereits importiert")
        return
    print(f"Option Omega {name}: {ergebnis.zeilen_gesamt} Zeilen, {ergebnis.zeilen_neu} neu, "
          f"{ergebnis.zeilen_aktualisiert} aktualisiert")


def _oa_bericht(name: str, ergebnis) -> None:
    # Format aus AP-13y; „fortgeschrieben" (AP-13r2) nur, wenn es vorkam.
    zusatz = (
        f", {ergebnis.zeilen_fortgeschrieben} fortgeschrieben"
        if ergebnis.zeilen_fortgeschrieben
        else ""
    )
    print(
        f"OptionApp-Import {name}: {ergebnis.zeilen_gesamt} Trades gelesen, "
        f"{ergebnis.zeilen_neu} neu, {ergebnis.zeilen_uebersprungen} übersprungen{zusatz}"
    )
    if ergebnis.zeilen_angereichert:
        print(f"  Angereichert (Zeilenbild des neuen Exports): {ergebnis.zeilen_angereichert}")
    if ergebnis.abweichend:
        print(
            f"  Abweichend vom gespeicherten Stand, unverändert gelassen: "
            f"{', '.join(ergebnis.abweichend)}",
            file=sys.stderr,
        )


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
    nachtrager = unterbefehle.add_parser(
        "nachtragen-realisiert",
        help="IBs fifoPnlRealized aus bereits importierten Flex-Dateien nachtragen (AP-02p)",
    )
    nachtrager.add_argument("dateien", type=pathlib.Path, nargs="+", help="Flex-XML-Dateien")
    nachtrager.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    oa_importer = unterbefehle.add_parser(
        "import-optionapp",
        help="OptionApp-Trade-Export idempotent in die Datenbank importieren (AP-13)",
    )
    oa_importer.add_argument(
        "datei",
        type=pathlib.Path,
        help="Pfad zur XLSX-Exportdatei oder zu einem Ordner mit Exporten (AP-13r2)",
    )
    oa_importer.add_argument(
        "--anreichern",
        action="store_true",
        help="Gleiche Trades übernehmen das vollständigere Zeilenbild des neuen "
        "Exports (Gewinn in Originalwährung; AP-13ab)",
    )
    oa_importer.add_argument(
        "--abweichende-behalten",
        action="store_true",
        help="Trades, die vom gespeicherten Stand abweichen, unverändert lassen und "
        "melden statt abzubrechen (AP-13r3)",
    )
    oa_importer.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    oo_importer = unterbefehle.add_parser(
        "import-optionomega",
        help="Option-Omega-Backtest-Export (CSV) einlesen (AP-12a)",
    )
    oo_importer.add_argument(
        "datei", type=pathlib.Path,
        help="CSV-Datei oder Ordner mit Exporten (neuester zuletzt)",
    )
    oo_importer.add_argument(
        "--db", default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    bt_bericht = unterbefehle.add_parser(
        "backtest-bericht",
        help="Paare Backtest ↔ Bot mit Ursache der Abweichung als CSV schreiben (AP-12c)",
    )
    bt_bericht.add_argument("datei", type=pathlib.Path, help="Pfad zur Zieldatei (CSV)")
    bt_bericht.add_argument("--von", type=date.fromisoformat, default=None,
                            help="Erster Eröffnungstag (JJJJ-MM-TT)")
    bt_bericht.add_argument("--bis", type=date.fromisoformat, default=None,
                            help="Letzter Eröffnungstag (JJJJ-MM-TT)")
    bt_bericht.add_argument(
        "--db", default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    abrufer = unterbefehle.add_parser(
        "abrufen",
        help="Flex-Statement über den Flex Web Service abrufen, speichern und "
        "importieren (AP-02a2)",
    )
    abrufer.add_argument(
        "--ziel",
        type=pathlib.Path,
        default=None,
        help="Zielordner für das Statement (Default: Umgebungsvariable FLEX_ZIEL; "
        "liegt nie im Projektverzeichnis)",
    )
    abrufer.add_argument(
        "--query-id",
        default=None,
        help="Query-ID der Flex-Query (Default: Umgebungsvariable FLEX_QUERY_ID)",
    )
    abrufer.add_argument(
        "--rebuild",
        action="store_true",
        help="Nach dem Import Legs, Strukturen und Ketten neu aufbauen",
    )
    abrufer.add_argument(
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
    kampagnen_ausschreiber = unterbefehle.add_parser(
        "kampagnen-ausschreiben",
        help="Offene Campaign-Kandidaten als XLSX ausschreiben (AP-05d)",
    )
    kampagnen_ausschreiber.add_argument(
        "datei", type=pathlib.Path, help="Pfad zur Zieldatei (darf nicht bestehen)"
    )
    kampagnen_ausschreiber.add_argument(
        "--db",
        default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    kampagnen_einleser = unterbefehle.add_parser(
        "kampagnen-einlesen",
        help="Kampagnen-Klassifikationen aus einer ausgeschriebenen Datei übernehmen (AP-05d)",
    )
    kampagnen_einleser.add_argument("datei", type=pathlib.Path, help="Pfad zur Kandidatendatei")
    kampagnen_einleser.add_argument(
        "--ueberschreiben",
        action="store_true",
        help="Gespeicherte Entscheidungen ändern, statt bei Widerspruch abzubrechen",
    )
    kampagnen_einleser.add_argument(
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
    kennzahl.add_argument(
        "--degradation",
        type=pathlib.Path,
        default=None,
        metavar="DATEI",
        help="Zusätzlich die Roll-Degradation als eigene CSV schreiben "
        "(AP-06, Tranche III; nur mit --sicht kette)",
    )
    kennzahl.add_argument(
        "--equity",
        type=pathlib.Path,
        default=None,
        metavar="DATEI",
        help="Zusätzlich Equity-Kurve und Drawdown als eigene CSV schreiben "
        "(AP-06, Tranche IV; immer Kontosicht, unabhängig von --sicht)",
    )
    steuer_z = unterbefehle.add_parser(
        "steuer-zufluss",
        help="Steuer nach Zufluss je Zahlungsstrom (AP-10c): Töpfe, Quellensteuer, Datenlücken",
    )
    steuer_z.add_argument("datei", type=pathlib.Path, help="Pfad zur Zieldatei (CSV)")
    steuer_z.add_argument("--jahr", type=int, default=None, help="Nur Zeilen dieses Zuflussjahres")
    steuer_z.add_argument(
        "--db", default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    steuer_l = unterbefehle.add_parser(
        "steuer-listen",
        help="Einzelfall-Listen für den Steuerberater (CSV mit Kontodaten, außerhalb des Repos)",
    )
    steuer_l.add_argument("ordner", type=pathlib.Path, help="Zielordner für die CSV-Dateien")
    steuer_l.add_argument(
        "--db", default=None,
        help="SQLite-Datei (Default: Umgebungsvariable JOURNAL_DB, sonst journal.db)",
    )
    steuer = unterbefehle.add_parser(
        "steuer",
        help="ALTVERFAHREN (AP-10, Schließungsjahr): Töpfe je Jahr, Details, Erträge, Fehler — "
        "nicht zur Übernahme in die Steuererklärung; Neufassung: steuer-zufluss",
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
    elif argumente.befehl == "nachtragen-realisiert":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        for datei in argumente.dateien:
            try:
                neu = nachtragen_realisiert(db_pfad, datei)
            except (FileNotFoundError, ValueError) as fehler:
                print(f"Nachtragen fehlgeschlagen: {fehler}", file=sys.stderr)
                return 1
            print(f"Nachgetragen {datei.name}: {neu} Zeilen mit IB-Wert neu")
    elif argumente.befehl == "import-optionapp":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            behalten = argumente.abweichende_behalten
            if argumente.datei.is_dir():
                ergebnisse = import_optionapp_ordner(
                    db_pfad, argumente.datei, abweichende_behalten=behalten,
                    anreichern=argumente.anreichern,
                )
            else:
                ergebnisse = [
                    (
                        argumente.datei.name,
                        import_optionapp_file(
                            db_pfad, argumente.datei, abweichende_behalten=behalten,
                            anreichern=argumente.anreichern,
                        ),
                    )
                ]
        except (FileNotFoundError, ValueError) as fehler:
            # Defekt der Quelle: benannt abbrechen, kein Traceback — die
            # Transaktion hat nichts geschrieben (AP-02, AP-13).
            print(f"Import fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        for name, ergebnis in ergebnisse:
            _oa_bericht(name, ergebnis)
    elif argumente.befehl == "import-optionomega":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            if argumente.datei.is_dir():
                ergebnisse = import_optionomega_ordner(db_pfad, argumente.datei)
            else:
                ergebnisse = [(argumente.datei.name,
                               import_optionomega_file(db_pfad, argumente.datei))]
        except (FileNotFoundError, OoFormatFehler) as fehler:
            print(f"Import fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        for name, ergebnis in ergebnisse:
            _oo_bericht(name, ergebnis)
    elif argumente.befehl == "backtest-bericht":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        bericht = backtest_bericht(db_pfad, von=argumente.von, bis=argumente.bis)
        # UTF-8 mit BOM wie die anderen Berichte (Regel 13).
        with open(argumente.datei, "w", encoding="utf-8-sig", newline="\n") as datei:
            datei.write(backtest_als_csv(bericht) + "\n")
        zeilen = sum(len(v.details) for v in bericht.vergleich)
        print(f"Backtest-Bericht nach {argumente.datei}: {len(bericht.vergleich)} Zuordnungen, "
              f"{zeilen} Zeilen")
    elif argumente.befehl == "abrufen":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        # Zugangsdaten → Ziel → Abruf → Speichern → Import → Rebuild: in
        # dieser Reihenfolge (Vertrag). Der Token kommt nur aus der
        # Umgebung — nie als Argument, nie in einer Ausgabe.
        token = os.environ.get("FLEX_TOKEN", "")
        if not token:
            print("Abruf fehlgeschlagen: FLEX_TOKEN ist nicht gesetzt.", file=sys.stderr)
            return 1
        query_id = argumente.query_id or os.environ.get("FLEX_QUERY_ID", "")
        if not query_id:
            print(
                "Abruf fehlgeschlagen: keine Query-ID (--query-id oder FLEX_QUERY_ID).",
                file=sys.stderr,
            )
            return 1
        ziel = argumente.ziel or os.environ.get("FLEX_ZIEL", "")
        if not ziel:
            print(
                "Abruf fehlgeschlagen: kein Zielordner (--ziel oder FLEX_ZIEL) — "
                "Statements enthalten Kontodaten und gehören außerhalb des Repos.",
                file=sys.stderr,
            )
            return 1
        ziel_pfad = pathlib.Path(ziel)
        try:
            flex_abruf.ziel_pruefen(ziel_pfad)
            # standard_transport wird bei jedem Aufruf im Modul nachgeschlagen
            # (Vertrag) — so ersetzen es die Tests per monkeypatch.
            xml = flex_abruf.abrufen(
                token, query_id, transport=flex_abruf.standard_transport
            )
            pfad = flex_abruf.statement_speichern(xml, ziel_pfad)
        except (flex_abruf.AbrufFehler, ValueError) as fehler:
            print(f"Abruf fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(f"Abruf: Statement nach {pfad}")
        try:
            ergebnis = import_flex_file(db_pfad, pfad)
        except (FileNotFoundError, ValueError) as fehler:
            # Die Datei bleibt zur Prüfung liegen; ein Rebuild folgt nicht
            # (Vertrag AP-02a2).
            print(f"Import fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Import {pfad.name}: {ergebnis.zeilen_gesamt} Zeilen gelesen, "
            f"{ergebnis.zeilen_neu} neu, {ergebnis.zeilen_uebersprungen} übersprungen"
        )
        # AP-13r2: neue OA-Exporte vor dem Rebuild einlesen, damit neue Trades
        # ihre Strategie bekommen. Ordner aus OA_ORDNER, sonst „oa" neben dem
        # Flex-Zielordner; fehlt er, geschieht nichts.
        oa_ordner = pathlib.Path(os.environ.get("OA_ORDNER") or ziel_pfad.parent / "oa")
        if oa_ordner.is_dir():
            try:
                # AP-13r3: Im nächtlichen Lauf hält ein abweichender alter Trade
                # die neuen nicht auf — er bleibt und wird gemeldet.
                for name, oa_ergebnis in import_optionapp_ordner(
                    db_pfad, oa_ordner, abweichende_behalten=True
                ):
                    _oa_bericht(name, oa_ergebnis)
            except (FileNotFoundError, ValueError) as fehler:
                # Ein defekter OA-Export hält den Flex-Abruf nicht auf; er
                # wird benannt und bleibt zur Prüfung liegen.
                print(f"OptionApp-Import fehlgeschlagen: {fehler}", file=sys.stderr)
        # AP-12a: OO-Backtests aus OO_ORDNER, sonst „oo" neben dem
        # Flex-Zielordner; fehlt er, geschieht nichts.
        oo_ordner = pathlib.Path(os.environ.get("OO_ORDNER") or ziel_pfad.parent / "oo")
        if oo_ordner.is_dir():
            try:
                for name, oo_ergebnis in import_optionomega_ordner(db_pfad, oo_ordner):
                    _oo_bericht(name, oo_ergebnis)
            except OoFormatFehler as fehler:
                print(f"Option-Omega-Import fehlgeschlagen: {fehler}", file=sys.stderr)
        if argumente.rebuild:
            try:
                lauf = rebuild(db_pfad)
            except ValueError as fehler:
                # Widerspruch in den Daten oder den Overrides: benannt
                # abbrechen — die kurze Transaktion hat nichts geschrieben.
                print(f"Rebuild fehlgeschlagen: {fehler}", file=sys.stderr)
                return 1
            print(
                f"Rebuild {db_pfad}: {lauf.legs} Legs, {lauf.structures} Strukturen, "
                f"{lauf.chains} Ketten, {lauf.chain_links} Kettenglieder, "
                f"{lauf.nicht_strukturiert} unstrukturiert; "
                f"Overrides: {lauf.overrides_angewandt} angewandt, "
                f"{lauf.overrides_verwaist} verwaist; "
                f"{lauf.kandidaten_offen} offene Rollkandidaten; "
                f"OA-Abgleich: {lauf.oa_zugeordnet} zugeordnet, "
                f"{lauf.oa_fehler} ohne eindeutige Kette; "
                f"{lauf.campaign_kandidaten_offen} offene Campaign-Kandidaten; "
                f"Roller: {lauf.roller_neu} neu verknüpft, "
                f"{lauf.roller_ohne_kette} ohne Journal-Kette"
            )
            if lauf.overrides_verwaist > 0:
                # Vertrag 20 (AP-04v): Verwaistes wird nie übergangen.
                print(
                    "Verwaiste Overrides benannt (siehe Standardfehlerausgabe).",
                    file=sys.stderr,
                )
                return 1
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
            f"{ergebnis.campaign_kandidaten_offen} offene Campaign-Kandidaten; "
            f"Roller: {ergebnis.roller_neu} neu verknüpft, "
            f"{ergebnis.roller_ohne_kette} ohne Journal-Kette"
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
    elif argumente.befehl == "kampagnen-ausschreiben":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = kampagnen_ausschreiben(db_pfad, argumente.datei)
        except (FileExistsError, ValueError) as fehler:
            # Bestehende Datei oder ungültiges Ziel: benannt abbrechen, kein
            # Traceback — es wurde nichts geschrieben (AP-05d).
            print(f"Ausschreiben fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Ausgeschrieben nach {argumente.datei}: {ergebnis.gruppen} Gruppen, "
            f"{ergebnis.kandidaten} Kandidaten"
        )
    elif argumente.befehl == "kampagnen-einlesen":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        try:
            ergebnis = kampagnen_urteile_einlesen(
                db_pfad, argumente.datei, ueberschreiben=argumente.ueberschreiben
            )
        except ValueError as fehler:
            # Widerspruch in der Datei oder den gespeicherten Entscheidungen:
            # benannt abbrechen, kein Traceback — die kurze Transaktion hat
            # nichts geschrieben (AP-05d).
            print(f"Einlesen fehlgeschlagen: {fehler}", file=sys.stderr)
            return 1
        print(
            f"Einlesen {argumente.datei.name}: {ergebnis.neu_bestaetigt} neu "
            f"bestätigt, {ergebnis.neu_abgelehnt} neu abgelehnt, "
            f"{ergebnis.kampagnen_neu} Kampagnen neu, "
            f"{ergebnis.verknuepfungen_neu} Verknüpfungen neu, "
            f"{ergebnis.unveraendert} unverändert, {ergebnis.geaendert} geändert, "
            f"{ergebnis.unentschieden} unentschieden"
        )
        print("Jetzt `journal rebuild` ausführen, damit die Entscheidungen wirksam werden.")
    elif argumente.befehl == "kennzahlen":
        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        if argumente.degradation is not None and argumente.sicht != "kette":
            # E8 (AP-06d): Degradation nur auf der Kettensicht — Abbruch VOR
            # jeder Ausgabe: keine Datei, auch nicht die Kennzahlen-CSV,
            # und kein Schreibzugriff auf die Datenbank.
            print(
                f"Degradation fehlgeschlagen: --degradation läuft nur auf der "
                f"Kettensicht, --sicht {argumente.sicht} ist damit unvereinbar "
                "(AP-06d, E8)",
                file=sys.stderr,
            )
            return 1
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
        if argumente.degradation is not None:
            # E8: die Degradations-CSV schreiben — dass --sicht hier 'kette'
            # ist, hat der Wächter oben vor jeder Ausgabe sichergestellt.
            degradation = degradations_bericht(
                db_pfad, nur_qualitaetsstufe_a=argumente.nur_stufe_a
            )
            # UTF-8 mit BOM wie der Kennzahlen-Bericht (Regel 13): Excel öffnet
            # die Datei ohne Encoding-Rätsel; Zeilenende fest auf \n, damit die
            # Datei auf jedem Betriebssystem bytgleich ausfällt (AP-06w, E6).
            with open(argumente.degradation, "w", encoding="utf-8-sig", newline="\n") as datei:
                datei.write(degradation_als_csv(degradation) + "\n")
            print(
                f"Degradation nach {argumente.degradation}: "
                f"{len(degradation.gruppen)} Gruppen, "
                f"{degradation.abdeckung[0].offene_kandidaten} offene Kandidaten"
            )
        if argumente.equity is not None:
            # Immer Kontosicht (AP-06e, E1) — unabhängig von --sicht, das nur
            # den Hauptbericht steuert.
            equity = equity_bericht(db_pfad, nur_qualitaetsstufe_a=argumente.nur_stufe_a)
            # UTF-8 mit BOM wie der Kennzahlen-Bericht (Regel 13): Excel öffnet
            # die Datei ohne Encoding-Rätsel; Zeilenende fest auf \n, damit die
            # Datei auf jedem Betriebssystem bytgleich ausfällt (AP-06w, E6).
            with open(argumente.equity, "w", encoding="utf-8-sig", newline="\n") as datei:
                datei.write(equity_als_csv(equity) + "\n")
            print(
                f"Equity-Kurve nach {argumente.equity}: {len(equity.tage)} Tage, "
                f"{len(equity.monate)} Monate, "
                f"maximaler Drawdown {equity.max_drawdown_eur} EUR"
            )
    elif argumente.befehl == "steuer-zufluss":
        from analytics.steuer_zufluss import als_csv as zufluss_csv
        from journal.steuer_zufluss import steuer_zufluss_bericht

        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        ergebnis = steuer_zufluss_bericht(db_pfad)
        with open(argumente.datei, "w", encoding="utf-8-sig", newline="\n") as datei:
            datei.write(zufluss_csv(ergebnis, jahr=argumente.jahr))
        print(
            f"Steuer nach Zufluss nach {argumente.datei}: {len(ergebnis.stroeme)} Zahlungsströme, "
            f"{len(ergebnis.datenluecken)} Datenlücken, {len(ergebnis.regeln_offen)} offene Regeln "
            "(Arbeitsstand, ungeprüft — keine Steuerberatung)"
        )
    elif argumente.befehl == "steuer-listen":
        from journal.steuer_zufluss import listen_schreiben, steuer_zufluss_bericht

        db_pfad = argumente.db or os.environ.get("JOURNAL_DB", "journal.db")
        anzahl = listen_schreiben(steuer_zufluss_bericht(db_pfad), argumente.ordner)
        for name, n in anzahl.items():
            print(f"{argumente.ordner / name}: {n} Zeilen")
    elif argumente.befehl == "steuer":
        print(
            "ALTVERFAHREN — Schließungsjahr, nicht zur Übernahme in die Steuererklärung; "
            "die Neufassung ist `steuer-zufluss`.",
            file=sys.stderr,
        )
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
