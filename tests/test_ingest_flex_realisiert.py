"""Abnahmetests für AP-02p: IBs realisiertes Ergebnis je Ausführung
(`fifoPnlRealized`) in eigener Tabelle `flex_ib_realized`. Unveränderlich —
Vertrag in auftraege/AP-02p.md.

Hintergrund (OF-78): Beim Import gewinnt die erste Quelle — `executions` wird
nie überschrieben (Regel 4). Eine ältere Abfrage ohne `fifoPnlRealized` ließ das
Feld deshalb für immer leer, obwohl spätere Dateien es lieferten (11.949 Zeilen
im Echtbestand). Die neue Tabelle hält den IB-Wert getrennt und nimmt ihn auch
dann auf, wenn die Ausführung selbst schon bekannt ist.

Fixtures: fixtures/flex/activity_realisiert.xml (frei erfunden) mit vier
Ausführungen — 8000001 +150.00 USD (Kurs 0.9300), 8000002 **ohne** das Feld,
8000003 −40.50 EUR, 8000004 eine echte 0 (eröffnend) — und
activity_realisiert_nachtrag.xml, dieselben vier, 8000002 jetzt mit 10.00 USD.

Von Hand: Basiswährung 150.00 × 0.9300 = 139.50; 0; −40.50 × 1 = −40.50.
Nach dem Nachtrag zusätzlich 10.00 × 0.9300 = 9.30 → Summe 139.50 − 40.50 + 9.30
= 108.30.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from ingest.flex import import_flex_file, nachtragen_realisiert
from journal.db import create_db_engine
from journal.schema import executions, flex_ib_realized

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flex"


def _zeilen(db):
    with create_db_engine(db).connect() as v:
        return [dict(z) for z in v.execute(
            select(flex_ib_realized).order_by(flex_ib_realized.c.exec_id)).mappings()]


def _ausfuehrungen(db):
    with create_db_engine(db).connect() as v:
        return [dict(z) for z in v.execute(
            select(executions).order_by(executions.c.exec_id)).mappings()]


def _summe_eur(zeilen):
    return sum((z["fifo_pnl_realized"] * z["fx_rate_to_base"] for z in zeilen), Decimal("0"))


def test_zeilen_mit_wert_werden_aufgenommen_leere_nicht(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert.xml")
    zeilen = _zeilen(migrated_db)
    assert [z["exec_id"] for z in zeilen] == ["8000001", "8000003", "8000004"]
    erste = zeilen[0]
    assert erste["konto"] == "U7777777"
    assert erste["quell_schluessel"] == "trade:8000001"
    assert erste["handelstag"] == date(2026, 1, 5)
    assert erste["conid"] == 110001
    assert erste["waehrung"] == "USD"
    assert erste["fifo_pnl_realized"] == Decimal("150.00")
    assert erste["fx_rate_to_base"] == Decimal("0.9300")


def test_eine_echte_null_bleibt_erhalten(migrated_db):
    """0 heißt „IB meldet 0" (eröffnende Zeile) — das ist etwas anderes als
    „kein Wert geliefert" und zählt für die Abdeckung."""
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert.xml")
    null = [z for z in _zeilen(migrated_db) if z["exec_id"] == "8000004"]
    assert [z["fifo_pnl_realized"] for z in null] == [Decimal("0")]


def test_summe_in_basiswaehrung(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert.xml")
    assert _summe_eur(_zeilen(migrated_db)) == Decimal("99.00")   # 139.50 + 0 − 40.50


def test_nachtrag_ergaenzt_den_fehlenden_wert_ohne_executions_anzufassen(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert.xml")
    vorher = _ausfuehrungen(migrated_db)
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert_nachtrag.xml")

    zeilen = _zeilen(migrated_db)
    assert [z["exec_id"] for z in zeilen] == ["8000001", "8000002", "8000003", "8000004"]
    nachtrag = next(z for z in zeilen if z["exec_id"] == "8000002")
    assert nachtrag["fifo_pnl_realized"] == Decimal("10.00")
    assert _summe_eur(zeilen) == Decimal("108.30")
    # Die Ausführungen sind unverändert (Regel 4): gleiche Zeilen, gleicher Inhalt.
    assert _ausfuehrungen(migrated_db) == vorher


def test_wiederholter_import_verdoppelt_nichts(migrated_db):
    for _ in range(2):
        import_flex_file(migrated_db, FIXTURES / "activity_realisiert_nachtrag.xml")
    assert len(_zeilen(migrated_db)) == 4
    with create_db_engine(migrated_db).connect() as v:
        assert v.execute(select(func.count()).select_from(executions)).scalar_one() == 4


def test_bestehender_wert_wird_nie_ueberschrieben(migrated_db):
    """Erst mit 10.00, dann eine Datei ohne den Wert: 10.00 bleibt."""
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert_nachtrag.xml")
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert.xml")
    zeilen = _zeilen(migrated_db)
    assert next(z for z in zeilen if z["exec_id"] == "8000002")["fifo_pnl_realized"] == Decimal(
        "10.00")


def test_nachtragen_fuer_eine_bereits_importierte_datei(migrated_db):
    """Die Datenbank kennt die Datei schon (Hash), die Tabelle ist noch leer —
    so liegt der Echtbestand: `nachtragen_realisiert` liest nur das Feld nach."""
    import_flex_file(migrated_db, FIXTURES / "activity_realisiert_nachtrag.xml")
    with create_db_engine(migrated_db).begin() as v:
        v.execute(flex_ib_realized.delete())
    assert _zeilen(migrated_db) == []

    ergebnis = nachtragen_realisiert(migrated_db, FIXTURES / "activity_realisiert_nachtrag.xml")

    assert ergebnis == 4
    assert [z["exec_id"] for z in _zeilen(migrated_db)] == [
        "8000001", "8000002", "8000003", "8000004"]
    # Wiederholt: nichts Neues.
    assert nachtragen_realisiert(migrated_db, FIXTURES / "activity_realisiert_nachtrag.xml") == 0


def test_nachtragen_verlangt_eine_importierte_datei(migrated_db):
    with pytest.raises(ValueError, match="importiert"):
        nachtragen_realisiert(migrated_db, FIXTURES / "activity_realisiert.xml")
