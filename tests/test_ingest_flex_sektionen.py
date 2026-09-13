"""Ergänzte Abnahmetests für AP-02: Flex-Sektionen ohne Duplikate.

Nachgereicht nach dem Review von AP-02, geschrieben nach §11.2 des Plans
durch das starke Modell — für das günstige Modell unveränderlich.

Hintergrund: Die Abnahme „zwei überlappende Dateien erzeugen die
Vereinigungsmenge ohne Duplikate" gilt für den ganzen Import, nicht nur für
``executions``. Der nächtliche rollierende Abruf (§6.2) liefert jede Nacht
eine überlappende Datei mit neuem ``whenGenerated`` — also neuem Datei-Hash.
Doppelte Zinsen, Gebühren oder Kapitalmaßnahmen verfälschen E8, AP-03 und
AP-10.

Vertrag an die Umsetzung:

- Jede Zeile der Sektionstabellen ``flex_cash_transactions``,
  ``flex_corporate_actions``, ``flex_transfers`` und ``flex_open_positions``
  trägt das Konto (``konto``).
- Eine Zeile, die schon importiert ist, wird nicht erneut angelegt — gleich,
  ob sie aus derselben Datei, einem erneuten Abruf oder einer überlappenden
  Datei stammt.
- Zwei inhaltsgleiche Buchungen ohne ``transactionID`` in derselben Datei sind
  zwei Buchungen; keine darf still verschwinden.
- Offene Positionen sind Bestände zu einem Stichtag (``stichtag``): aus
  ``reportDate``, fehlt es, aus ``toDate`` des FlexStatements.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, text

pytest.importorskip("ingest.flex")

from ingest.flex import import_flex_file  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import flex_cash_transactions, flex_open_positions  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flex"

SEKTIONSTABELLEN = (
    "flex_cash_transactions",
    "flex_corporate_actions",
    "flex_transfers",
    "flex_open_positions",
)


def _importiere(db_pfad, datei):
    return import_flex_file(db_pfad, datei if isinstance(datei, Path) else FIXTURES / datei)


def _neuabruf(dateiname, tmp_path):
    """Dieselbe Datei, erneut abgerufen: nur ``whenGenerated`` ändert sich."""
    inhalt = (FIXTURES / dateiname).read_text(encoding="utf-8")
    neu, ersetzt = re.subn(r'whenGenerated="[^"]*"', 'whenGenerated="20991231;235959"', inhalt)
    assert ersetzt == 1, "Fixture muss genau einen whenGenerated-Stempel tragen"
    ziel = tmp_path / f"neuabruf_{dateiname}"
    ziel.write_text(neu, encoding="utf-8")
    return ziel


def _anzahl(db_pfad, tabelle):
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return verbindung.execute(text(f"SELECT count(*) FROM {tabelle}")).scalar_one()


def _anzahlen(db_pfad):
    return {tabelle: _anzahl(db_pfad, tabelle) for tabelle in SEKTIONSTABELLEN}


def test_redownload_of_same_period_does_not_duplicate_sections(migrated_db, tmp_path):
    _importiere(migrated_db, "activity_2026_01.xml")
    vorher = _anzahlen(migrated_db)
    zweiter = _importiere(migrated_db, _neuabruf("activity_2026_01.xml", tmp_path))
    assert zweiter.zeilen_neu == 0
    assert _anzahlen(migrated_db) == vorher
    assert vorher["flex_cash_transactions"] == 2
    assert vorher["flex_open_positions"] == 1
    assert _anzahl(migrated_db, "flex_securities_info") == 4
    assert _anzahl(migrated_db, "executions") == 10


def test_overlapping_files_unite_sections_without_duplicates(migrated_db):
    _importiere(migrated_db, "activity_2026_03a.xml")
    zweiter = _importiere(migrated_db, "activity_2026_03b.xml")
    assert zweiter.zeilen_gesamt == 2
    assert zweiter.zeilen_neu == 1
    assert _anzahlen(migrated_db) == {
        "flex_cash_transactions": 3,
        "flex_corporate_actions": 1,
        "flex_transfers": 1,
        "flex_open_positions": 2,
    }
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        betraege = sorted(verbindung.execute(select(flex_cash_transactions.c.betrag)).scalars())
    assert betraege == [Decimal("-10.00"), Decimal("0.80"), Decimal("25.00")]


def test_overlap_in_reverse_order_gives_the_same_union(migrated_db):
    _importiere(migrated_db, "activity_2026_03b.xml")
    _importiere(migrated_db, "activity_2026_03a.xml")
    assert _anzahlen(migrated_db) == {
        "flex_cash_transactions": 3,
        "flex_corporate_actions": 1,
        "flex_transfers": 1,
        "flex_open_positions": 2,
    }
    assert _anzahl(migrated_db, "executions") == 2


def test_identical_bookings_without_id_are_both_kept(migrated_db, tmp_path):
    _importiere(migrated_db, "activity_identische_buchungen.xml")
    assert _anzahl(migrated_db, "flex_cash_transactions") == 2, (
        "zwei inhaltsgleiche Buchungen sind zwei Buchungen — keine darf verschwinden"
    )
    _importiere(migrated_db, _neuabruf("activity_identische_buchungen.xml", tmp_path))
    assert _anzahl(migrated_db, "flex_cash_transactions") == 2


def test_duplicate_transaction_id_within_file_fails_and_writes_nothing(migrated_db):
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "activity_doppelte_buchungs_id.xml")
    assert "7100009" in str(fehler.value)
    assert _anzahl(migrated_db, "flex_cash_transactions") == 0
    assert _anzahl(migrated_db, "import_runs") == 0


def test_open_positions_are_snapshots_per_stichtag(migrated_db):
    _importiere(migrated_db, "activity_2026_03a.xml")
    _importiere(migrated_db, "activity_2026_03b.xml")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        bestaende = verbindung.execute(
            select(flex_open_positions.c.stichtag, flex_open_positions.c.menge)
            .where(flex_open_positions.c.conid == 200001)
            .order_by(flex_open_positions.c.stichtag)
        ).all()
    assert [(z.stichtag, z.menge) for z in bestaende] == [
        (date(2026, 3, 15), Decimal("110")),
        (date(2026, 3, 31), Decimal("210")),
    ]


def test_open_position_without_report_date_uses_statement_end(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        stichtag = verbindung.execute(select(flex_open_positions.c.stichtag)).scalar_one()
    assert stichtag == date(2026, 1, 31)


def test_section_rows_carry_the_account(migrated_db):
    _importiere(migrated_db, "activity_2026_03a.xml")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        for tabelle in SEKTIONSTABELLEN:
            konten = verbindung.execute(text(f"SELECT DISTINCT konto FROM {tabelle}")).scalars()
            assert list(konten) == ["U7777777"], tabelle
