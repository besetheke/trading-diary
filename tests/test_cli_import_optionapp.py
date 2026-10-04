"""Abnahmetests für AP-13y: `journal import-optionapp <datei> [--db]`.

Vertrag: auftraege/AP-13y.md. Diese Datei ist unveränderlich. Der Befehl
verdrahtet nur den vorhandenen, getesteten Parser (`ingest.optionapp.
import_optionapp_file`, AP-13) — dieselbe Form wie der Flex-Import (`journal
import`). Alle Daten stammen aus den erfundenen Fixtures unter
`fixtures/optionapp/`; `fixtures/golden/` wird nicht gelesen (Regel 2).

Startzustand: ROT, weil der Befehl noch nicht existiert (argparse beendet mit
SystemExit 2 bei unbekanntem Unterbefehl).
"""

from pathlib import Path

from sqlalchemy import func, select

from journal.cli import main
from journal.db import create_db_engine
from journal.schema import optionapp_trades

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optionapp"


def _anzahl_trades(db_pfad) -> int:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return verbindung.execute(select(func.count()).select_from(optionapp_trades)).scalar_one()


def test_import_legt_die_trades_an_und_meldet_zaehlwerte(migrated_db, capsys):
    """oa_standard.xlsx hat vier Trades (Nummern 1001-1004)."""
    datei = FIXTURES / "oa_standard.xlsx"
    assert main(["import-optionapp", str(datei), "--db", str(migrated_db)]) == 0
    assert _anzahl_trades(migrated_db) == 4
    assert (
        "OptionApp-Import oa_standard.xlsx: 4 Trades gelesen, 4 neu, 0 übersprungen"
        in capsys.readouterr().out
    )


def test_zweiter_lauf_derselben_datei_legt_nichts_neu_an(migrated_db, capsys):
    """Idempotenz kommt aus dem Parser (gleicher Dateihash); der Befehl meldet
    sie ehrlich: 4 gelesen, 0 neu, 4 übersprungen."""
    datei = FIXTURES / "oa_standard.xlsx"
    assert main(["import-optionapp", str(datei), "--db", str(migrated_db)]) == 0
    capsys.readouterr()
    assert main(["import-optionapp", str(datei), "--db", str(migrated_db)]) == 0
    assert _anzahl_trades(migrated_db) == 4
    assert (
        "OptionApp-Import oa_standard.xlsx: 4 Trades gelesen, 0 neu, 4 übersprungen"
        in capsys.readouterr().out
    )


def test_defekte_datei_bricht_benannt_ab_ohne_traceback(migrated_db, capsys):
    """Ein Defekt der Quelle (Leg-Grammatik) ist ein ValueError des Parsers:
    Rückgabe 1, Meldung auf stderr, nichts geschrieben."""
    datei = FIXTURES / "oa_grammatik_defekt.xlsx"
    assert main(["import-optionapp", str(datei), "--db", str(migrated_db)]) == 1
    assert "Import fehlgeschlagen:" in capsys.readouterr().err
    assert _anzahl_trades(migrated_db) == 0


def test_fehlende_datei_bricht_benannt_ab(migrated_db, tmp_path, capsys):
    assert main(["import-optionapp", str(tmp_path / "gibt_es_nicht.xlsx"),
                 "--db", str(migrated_db)]) == 1
    assert "Import fehlgeschlagen:" in capsys.readouterr().err
    assert _anzahl_trades(migrated_db) == 0
