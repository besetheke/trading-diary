"""Abnahmetests für AP-02n: Kontowert (NAV je Tag), Change in NAV und Cash
Report aus dem Flex-Export. Vertrag: auftraege/AP-02n.md. Unveränderlich.

Fixtures: fixtures/flex/activity_nav.xml und activity_nav_overlap.xml — frei
erfundene Werte; fixtures/golden/ wird nicht gelesen.
"""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ingest.flex import import_flex_file
from journal.db import create_db_engine
from journal.schema import flex_cash_report, flex_change_in_nav, flex_nav_tage, import_runs

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flex"


def _zeilen(db, tabelle, ordnung):
    with create_db_engine(db).connect() as v:
        return [dict(z) for z in v.execute(select(tabelle).order_by(ordnung)).mappings()]


def test_nav_je_tag_mit_vortag(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    tage = _zeilen(migrated_db, flex_nav_tage, flex_nav_tage.c.datum)
    assert [t["datum"] for t in tage] == [date(2025, 12, 31), date(2026, 1, 2), date(2026, 1, 5)]
    erster = tage[0]
    assert erster["konto"] == "U7777777"
    assert erster["quell_schluessel"] == "nav:2025-12-31"
    assert erster["waehrung"] == "EUR"
    assert (erster["cash"], erster["aktien"], erster["optionen"], erster["gesamt"]) == (
        Decimal("-1000.50"), Decimal("5000.00"), Decimal("-200.25"), Decimal("3798.15"))
    # Leeres Feld bleibt leer, keine stille 0 (commodities="" am 2025-12-31).
    assert erster["rohstoffe"] is None
    assert (erster["dividenden_abgrenzung"], erster["zins_abgrenzung"]) == (
        Decimal("1.10"), Decimal("-2.20"))
    assert tage[1]["rohstoffe"] == Decimal("12.50")
    # Rohsatz vollständig erhalten — auch Felder ohne eigene Spalte.
    assert json.loads(erster["roh_json"])["totalShort"] == "-1202.95"


def test_change_in_nav(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    (z,) = _zeilen(migrated_db, flex_change_in_nav, flex_change_in_nav.c.von)
    assert (z["von"], z["bis"], z["quell_schluessel"]) == (
        date(2026, 1, 2), date(2026, 1, 5), "cinav:2026-01-02|2026-01-05")
    assert (z["anfangswert"], z["endwert"], z["realisiert"], z["veraenderung_unrealisiert"]) == (
        Decimal("3798.15"), Decimal("4077.00"), Decimal("150.00"), Decimal("80.85"))
    assert z["marktbewertung"] is None  # mtm="" bei Option "Realized & Unrealized"
    assert (z["dividenden"], z["zinsen"], z["kommissionen"], z["waehrungseffekt"], z["twr"]) == (
        Decimal("5.00"), Decimal("-2.00"), Decimal("-4.00"), Decimal("49.00"), Decimal("7.34"))
    assert z["ein_auszahlungen"] == Decimal("0")


def test_cash_report_je_waehrung(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    zeilen = _zeilen(migrated_db, flex_cash_report, flex_cash_report.c.waehrung)
    assert [z["waehrung"] for z in zeilen] == ["EUR", "USD"]
    usd = zeilen[1]
    assert usd["quell_schluessel"] == "cash:2026-01-02|2026-01-05|USD|Currency"
    assert usd["ebene"] == "Currency"
    assert (usd["anfangsbestand"], usd["endbestand"], usd["kommissionen"], usd["dividenden"],
            usd["zinsen"], usd["waehrungseffekt"]) == (
        Decimal("-1600.00"), Decimal("-1500.00"), Decimal("-3.00"), Decimal("5.50"),
        Decimal("-1.75"), Decimal("12.30"))
    assert zeilen[0]["waehrungseffekt"] is None


def test_erneuter_import_legt_nichts_an(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    assert len(_zeilen(migrated_db, flex_nav_tage, flex_nav_tage.c.datum)) == 3
    assert len(_zeilen(migrated_db, flex_change_in_nav, flex_change_in_nav.c.von)) == 1
    assert len(_zeilen(migrated_db, flex_cash_report, flex_cash_report.c.waehrung)) == 2


def test_ueberlappung_erste_quelle_gewinnt(migrated_db):
    """Bewegungsdaten werden nie überschrieben (wie die übrigen Flex-
    Sektionen): Der 2026-01-05 behält 4077.00, obwohl die zweite Datei 9999.99
    meldet; 2026-01-06 und 2026-01-07 kommen hinzu."""
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    import_flex_file(migrated_db, FIXTURES / "activity_nav_overlap.xml")
    tage = {t["datum"]: t["gesamt"] for t in _zeilen(migrated_db, flex_nav_tage,
                                                         flex_nav_tage.c.datum)}
    assert tage == {
        date(2025, 12, 31): Decimal("3798.15"),
        date(2026, 1, 2): Decimal("4060.00"),
        date(2026, 1, 5): Decimal("4077.00"),
        date(2026, 1, 6): Decimal("4100.00"),
        date(2026, 1, 7): Decimal("4120.00"),
    }
    assert len(_zeilen(migrated_db, flex_change_in_nav, flex_change_in_nav.c.von)) == 2
    assert len(_zeilen(migrated_db, flex_cash_report, flex_cash_report.c.waehrung)) == 3


def _datei_mit(tmp_path, nav_attribute: str) -> Path:
    ziel = tmp_path / "defekt.xml"
    ziel.write_text(
        '<FlexQueryResponse><FlexStatements count="1">'
        '<FlexStatement accountId="U7777777" fromDate="20260102" toDate="20260102">'
        f'<EquitySummaryInBase><EquitySummaryByReportDateInBase currency="EUR" {nav_attribute} />'
        "</EquitySummaryInBase></FlexStatement></FlexStatements></FlexQueryResponse>",
        encoding="utf-8",
    )
    return ziel


@pytest.mark.parametrize(
    ("attribute", "meldung"),
    [
        ('reportDate="20260102"', "total"),
        ('total="100.00"', "reportDate"),
        ('reportDate="20260102" total="viel"', "keine Zahl"),
    ],
)
def test_defekte_nav_zeile_bricht_ab_ohne_zu_schreiben(migrated_db, tmp_path, attribute, meldung):
    with pytest.raises(ValueError, match=meldung):
        import_flex_file(migrated_db, _datei_mit(tmp_path, attribute))
    assert _zeilen(migrated_db, flex_nav_tage, flex_nav_tage.c.datum) == []
    assert _zeilen(migrated_db, import_runs, import_runs.c.id) == []
