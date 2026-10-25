# ruff: noqa: E501
"""Historische Bewertung zum Endtag (AP-17g, M06 zweite Stufe), von Hand gerechnet.

Welt (frei erfunden, EUR, Multiplikator 10): OOO SELL 1 zu 3,00 am 02.02.2026 (Kommission -2,00), geschlossen am 12.10.2026 (BUY zu 1,00,
Kommission 0). Bestände laut IB: 09.10.2026 (OOO: Menge -1, Marktwert -20,00, Kurs 1) und 20.10.2026 (ein anderes Instrument) als jüngster.
Einstand -3,00 · 1 · 10 - (-2,00) = -28,00 → unrealisiert -20,00 - (-28,00) = 8,00 EUR.

  Endtag 10.10.: Bestand vom 09.10. (1 Tag davor); OOO war an dem Tag offen          → 8,00 zum Stichtag 09.10., 1 Leg
  Endtag 17.10.: Bestand vom 09.10. liegt 8 Tage davor (mehr als 7)                    → keine Bewertung, Stichtag leer
  Endtag 25.10.: nach dem jüngsten Bestand; OOO ist geschlossen, PPP (SELL 2,00, -2,00)
                 offen mit Marktwert -15,00: Einstand -20 + 2 = -18 → -15 + 18 = 3,00     → aktueller Bestand, 1 Leg, 3,00
"""
import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import flex_open_positions, import_runs  # noqa: E402


def _instrument(conid, basis):
    return dict(conid=conid, symbol=f"{basis}  261218P100", underlying=basis, asset_class="OPT", expiry=date(2026, 12, 18),
                strike=Decimal("100"), right="P", multiplikator=Decimal("10"), waehrung="EUR")


def _ausf(exec_id, conid, side, preis, zeit, kommission="-2.00"):
    return dict(exec_id=exec_id, conid=conid, side=side, preis=Decimal(preis), handelszeit=zeit, buchungskurs=Decimal("1"),
                kommission=Decimal(kommission))


def _bestand(lauf, schluessel, tag, conid, menge, wert):
    return dict(import_run_id=lauf, konto="U1234567", quell_schluessel=schluessel, stichtag=tag, conid=conid, symbol="X",
                asset_class="OPT", menge=Decimal(menge), kostenbasis_preis=Decimal("2.80"), fifo_pnl_unrealisiert=Decimal("0"),
                waehrung="EUR", roh_json=json.dumps({"levelOfDetail": "SUMMARY", "fxRateToBase": "1", "positionValue": wert}))


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, instrumente_=[_instrument(9201, "OOO"), _instrument(9202, "PPP")], ausfuehrungen=[
        _ausf("O1", 9201, "SELL", "3.00", datetime(2026, 2, 2, 10, 0)),
        _ausf("O2", 9201, "BUY", "1.00", datetime(2026, 10, 12, 10, 0), kommission="0"),
        _ausf("P1", 9202, "SELL", "2.00", datetime(2026, 10, 15, 10, 0)),
    ])
    rebuild(migrated_db)
    with create_db_engine(migrated_db).begin() as v:
        lauf = v.execute(select(import_runs.c.id)).scalars().first()
        v.execute(insert(flex_open_positions).values(_bestand(lauf, "op:1", date(2026, 10, 9), 9201, "-1", "-20.00")))
        v.execute(insert(flex_open_positions).values(_bestand(lauf, "op:2", date(2026, 10, 20), 9202, "-1", "-15.00")))
    return TestClient(erzeuge_app(migrated_db))


def _unrealisiert(klient, bis):
    return klient.get("/auswertung", params={"bis": bis}).json()["unrealisiert"]


def test_endtag_kurz_nach_dem_bestand_wird_zu_diesem_bestand_bewertet(klient):
    u = _unrealisiert(klient, "2026-10-10")
    assert u["stichtag"] == "2026-10-09" and u["anzahl_legs"] == 1 and Decimal(u["eur"]) == Decimal("8.00")


def test_zu_alter_bestand_gibt_keine_bewertung(klient):
    u = _unrealisiert(klient, "2026-10-17")
    assert u["stichtag"] is None and u["anzahl_legs"] == 0


def test_endtag_nach_dem_juengsten_bestand_bleibt_die_aktuelle_bewertung(klient):
    u = _unrealisiert(klient, "2026-10-25")
    assert u["stichtag"] == "2026-10-20" and u["anzahl_legs"] == 1 and Decimal(u["eur"]) == Decimal("3.00")


def test_ohne_endtag_gilt_der_aktuelle_bestand(klient):
    assert klient.get("/auswertung").json()["unrealisiert"]["stichtag"] == "2026-10-20"
