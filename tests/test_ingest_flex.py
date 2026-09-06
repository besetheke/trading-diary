"""Abnahmetests für AP-02 (Ingest Flex Query), geschrieben nach §11.2 des
Plans durch das starke Modell — für das günstige Modell unveränderlich.

Vertrag an die Umsetzung:

- Einstiegspunkt ist ``ingest.flex.import_flex_file(db_pfad, datei_pfad)``;
  Rückgabe ist ein Objekt mit ``zeilen_gesamt`` und ``zeilen_neu``.
- Bis ``ingest/flex.py`` existiert, springt dieses Modul still ab; sobald es
  existiert, laufen alle Tests scharf.
- Der Ereigniscode ``P`` ist im Schema nicht klassifizierbar (erfüllt keinen
  der vier Werte aus §1.4). Der Import ordnet ihn ``unbekannt`` zu; dafür ist
  eine Migration nötig, die den CHECK auf ``executions.ereignistyp`` um
  ``'unbekannt'`` erweitert. Hintergrund in OFFENE_FRAGEN.md (OF-07).
"""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import insert, select

pytest.importorskip("ingest.flex")

from ingest.flex import import_flex_file  # noqa: E402

from journal.schema import executions, import_runs  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flex"


def _importiere(db_pfad, dateiname):
    return import_flex_file(db_pfad, FIXTURES / dateiname)


def _exec_zeile(db_pfad, exec_id):
    from journal.db import create_db_engine

    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        zeile = verbindung.execute(
            select(executions).where(executions.c.exec_id == exec_id)
        ).mappings().one_or_none()
    return zeile


def _exec_ids(db_pfad):
    from journal.db import create_db_engine

    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return {z[0] for z in verbindung.execute(select(executions.c.exec_id))}


def test_import_reports_total_and_new_rows(migrated_db):
    ergebnis = _importiere(migrated_db, "activity_2026_01.xml")
    assert ergebnis.zeilen_gesamt == 10
    assert ergebnis.zeilen_neu == 10

    from journal.db import create_db_engine

    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        lauf = verbindung.execute(select(import_runs)).mappings().one()
    assert lauf["quelle"] == "flex"
    assert lauf["qualitaetsstufe"] == "A"
    assert lauf["zeilen_gesamt"] == 10
    assert lauf["zeilen_neu"] == 10


def test_double_import_creates_no_new_rows(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zweiter = _importiere(migrated_db, "activity_2026_01.xml")
    assert zweiter.zeilen_neu == 0
    assert zweiter.zeilen_gesamt == 10
    assert len(_exec_ids(migrated_db)) == 10


def test_overlapping_files_unite_without_duplicates(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zweiter = _importiere(migrated_db, "activity_2026_02_overlap.xml")
    assert zweiter.zeilen_gesamt == 3
    assert zweiter.zeilen_neu == 2
    assert _exec_ids(migrated_db) == {f"900000{i}" for i in range(1, 9)} | {
        "9000009",
        "9000010",
        "9000011",
        "9000012",
    }


def test_event_rows_classified_from_notes(migrated_db):
    _importiere(migrated_db, "activity_events.xml")
    assert _exec_zeile(migrated_db, "9100001")["ereignistyp"] == "expiry"
    assert _exec_zeile(migrated_db, "9100002")["ereignistyp"] == "exercise"
    assert _exec_zeile(migrated_db, "9100003")["ereignistyp"] == "assignment"


def test_trade_rows_without_notes_are_trades(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    assert _exec_zeile(migrated_db, "9000001")["ereignistyp"] == "trade"


def test_unclassified_event_code_p_is_stored_as_unbekannt(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "9000008")
    assert zeile is not None, "P-Zeile darf nicht still verworfen werden"
    assert zeile["ereignistyp"] == "unbekannt"
    assert zeile["ereignis_code"] == "P"


def test_exec_batch_is_first_two_segments_of_ib_exec_id(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    combo_kopf = _exec_zeile(migrated_db, "9000001")
    combo_bein = _exec_zeile(migrated_db, "9000002")
    assert combo_kopf["exec_batch"] == "0001.0002"
    assert combo_bein["exec_batch"] == "0001.0002"
    ereignis = _exec_zeile(migrated_db, "9000006")
    assert not ereignis["exec_batch"], "ohne ibExecID bleibt exec_batch leer"


def test_structured_order_reference_populates_oa_fields(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "9000001")
    assert zeile["oa_trade"] == "42"
    assert zeile["oa_leg"] == "1"
    assert zeile["oa_rolle"] == "Open Order"
    assert zeile["oa_order"] == "1"
    ziel = _exec_zeile(migrated_db, "9000010")
    assert ziel["oa_rolle"] == "Profit Target"


def test_generic_order_reference_keeps_oa_fields_empty(migrated_db):
    _importiere(migrated_db, "activity_generic_orderref.xml")
    for exec_id in ("9200001", "9200002", "9200003"):
        zeile = _exec_zeile(migrated_db, exec_id)
        assert zeile["order_reference"], "Rohwert ist zu erhalten"
        for feld in ("oa_trade", "oa_leg", "oa_rolle", "oa_order"):
            assert not zeile[feld], f"{feld} muss bei generischer Referenz leer bleiben"


def test_unknown_asset_category_fails_with_named_value(migrated_db):
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "activity_unknown_assetcategory.xml")
    assert "WARRANT" in str(fehler.value)


def test_sections_land_in_own_tables(migrated_db):
    from sqlalchemy import text

    from journal.db import create_db_engine

    _importiere(migrated_db, "activity_2026_01.xml")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        for tabelle, erwartet in (
            ("flex_securities_info", 4),
            ("flex_cash_transactions", 2),
            ("flex_open_positions", 1),
            ("flex_transfers", 0),
        ):
            anzahl = verbindung.execute(text(f"SELECT count(*) FROM {tabelle}")).scalar_one()
            assert anzahl == erwartet, f"{tabelle}: {anzahl} statt {erwartet}"


def test_executions_carry_amounts_as_decimal(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "9000001")
    assert zeile["menge"] == Decimal("2")
    assert zeile["preis"] == Decimal("3.10")
    assert zeile["kommission"] == Decimal("-2.00")
    assert zeile["expiry"].isoformat() == "2026-02-20"


def test_executions_carry_import_run_and_quality(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "9000009")
    assert zeile["qualitaetsstufe"] == "A"
    from journal.db import create_db_engine

    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        lauf_id = verbindung.execute(
            select(import_runs.c.id)
        ).scalar_one()
    assert zeile["import_run_id"] == lauf_id


def test_import_run_reference_blocks_orphans(migrated_db):
    """executions.import_run_id ist ein Fremdschlüssel; ein Import ohne
    Importlauf kann nicht passieren — das Schema erzwingt es."""
    from datetime import datetime

    from sqlalchemy.exc import IntegrityError

    from journal.db import create_db_engine

    _importiere(migrated_db, "activity_2026_01.xml")
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung, pytest.raises(IntegrityError):
        verbindung.execute(
            insert(executions).values(
                exec_id="ORPHAN",
                konto="U7777777",
                conid=1,
                symbol="X",
                side="BUY",
                menge=Decimal("1"),
                preis=Decimal("1"),
                waehrung="USD",
                handelszeit=datetime(2026, 1, 1),
                ereignistyp="trade",
                roh_json="{}",
                qualitaetsstufe="A",
                import_run_id=999_999,
            )
        )
