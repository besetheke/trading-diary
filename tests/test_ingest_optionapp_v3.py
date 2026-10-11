"""Abnahmetests für AP-13r3: Exportformat der neuen OA-Version. Vertrag:
auftraege/AP-13r3.md. Geschrieben durch das starke Modell — für die Umsetzung
unveränderlich. Fixtures frei erfunden (`fixtures/optionapp/erzeugen_v3.py`).

Abbildung auf das bisherige Datenmodell (von Hand):
  Id → oa_trade; Name → name_roh „<Name> [<Id>]"; Strategy ohne Randleerzeichen;
  leeres Stops → „kein Stop" (stop_roh „-", wie im alten Format); Profit (USD)
  → profit, profit_waehrung „$" (wie bisher gespeichert); Zeiten als Datum.
  7001: EXPIRED, Profit 144.24, kein Stop, zwei Legs.
  7002: CLOSED, Stop 1.5 → stop_wert 1.5.
  7003: RUNNING in Restlaufzeitform → keine Legs.
Verträglichkeit: 7001 im alten Format (Name „IF7  [7001]", Strich, „144,24 $")
und danach im neuen ist derselbe Trade — nichts neu, kein Abbruch.
Abweichung: 7001 mit anderem Schlusskurs bricht ab (Vertrag 10); mit
`abweichende_behalten=True` bleibt der gespeicherte Stand, 7001 wird gemeldet
und 7004 trotzdem gebucht.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ingest.optionapp import import_optionapp_file
from journal.db import create_db_engine
from journal.schema import optionapp_legs, optionapp_trades

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optionapp"


def _trades(db_pfad) -> dict:
    with create_db_engine(db_pfad).connect() as verbindung:
        return {z["oa_trade"]: dict(z)
                for z in verbindung.execute(select(optionapp_trades)).mappings()}


def _anzahl_legs(db_pfad, trade_id) -> int:
    with create_db_engine(db_pfad).connect() as verbindung:
        return len(verbindung.execute(select(optionapp_legs).where(
            optionapp_legs.c.optionapp_trade_id == trade_id)).all())


def test_neues_format_wird_gelesen(migrated_db):
    e = import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx")
    assert (e.zeilen_gesamt, e.zeilen_neu) == (3, 3)
    t = _trades(migrated_db)
    a = t["7001"]
    assert a["name_roh"] == "IF7 [7001]"
    assert a["strategie"] == "XSP: IF7"
    assert a["entry_zeit"] == datetime(2026, 9, 3, 11, 20, 44)
    assert a["schluss_zeit"] == datetime(2026, 9, 3, 16, 0, 0)
    assert (a["stop_roh"], a["stop_wert"]) == ("-", None)
    assert (a["profit"], a["profit_waehrung"]) == (Decimal("144.24"), "$")
    assert (a["offen_preis"], a["schluss_preis"]) == (Decimal("-1.45"), Decimal("0"))
    assert (a["menge_zaehler"], a["menge_nenner"]) == (Decimal("1"), Decimal("1"))
    assert _anzahl_legs(migrated_db, a["id"]) == 2
    assert t["7002"]["stop_wert"] == Decimal("1.5")
    assert t["7003"]["status"] == "RUNNING"
    assert _anzahl_legs(migrated_db, t["7003"]["id"]) == 0


def test_altes_und_neues_format_sind_derselbe_trade(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_v3_alt_7001.xlsx")
    e = import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx")
    assert (e.zeilen_neu, e.zeilen_fortgeschrieben) == (2, 0)
    assert _trades(migrated_db)["7001"]["name_roh"] == "IF7  [7001]"  # Bestand bleibt


def test_abweichung_bricht_ab(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx")
    with pytest.raises(ValueError) as fehler:
        import_optionapp_file(migrated_db, FIXTURES / "oa_v3_abweichend.xlsx")
    assert "7001" in str(fehler.value)
    assert "7004" not in _trades(migrated_db)


def test_abweichung_behalten_und_melden(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx")
    e = import_optionapp_file(
        migrated_db, FIXTURES / "oa_v3_abweichend.xlsx", abweichende_behalten=True)
    assert e.abweichend == ("7001",)
    assert (e.zeilen_neu, e.zeilen_fortgeschrieben) == (1, 0)
    t = _trades(migrated_db)
    assert t["7001"]["schluss_preis"] == Decimal("0")
    assert "7004" in t
