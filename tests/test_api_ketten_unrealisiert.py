"""Abnahmetests für AP-07ku: `GET /ketten` trägt je Kette das unrealisierte
Ergebnis ihrer offenen Legs (dieselbe Rechnung wie das Unrealisierte der
Auswertung, AP-07fu: IBs letzter Marktwert gegen den Einstand des Journals).
Vertrag: auftraege/AP-07ku.md. Geschrieben durch das starke Modell — für die
Umsetzung unveränderlich. Erwartungen von Hand gerechnet.

Welt (frei erfunden, EUR, Multiplikator 10, Kommission −2.00 je Ausführung):
  OOO  SELL 1 zu 3.00 am 02.02.2026, offen. Bestand laut IB (09.10.2026):
       Menge −1, Marktwert −20.00, Kurs 1.
       Einstand −3.00·1·10 − (−2.00) = −28.00 → unrealisiert −20.00 − (−28.00)
       = 8.00 EUR.
  PPP  SELL 10.00 am 02.01., BUY 4.00 am 03.01. → geschlossen: kein Wert (null),
       0 Legs ohne Kurs.
  QQQ  SELL 1 zu 2.00 am 05.03., offen, kein Bestand laut IB → kein Wert (null),
       1 Leg ohne Kurs.
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
    return dict(conid=conid, symbol=f"{basis}  261218P100", underlying=basis,
                asset_class="OPT", expiry=date(2026, 12, 18), strike=Decimal("100"),
                right="P", multiplikator=Decimal("10"), waehrung="EUR")


def _ausf(exec_id, conid, side, preis, zeit):
    return dict(exec_id=exec_id, conid=conid, side=side, preis=Decimal(preis),
                handelszeit=zeit, buchungskurs=Decimal("1"))


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, instrumente_=[
        _instrument(9201, "OOO"), _instrument(9202, "PPP"), _instrument(9203, "QQQ")],
        ausfuehrungen=[
            _ausf("O1", 9201, "SELL", "3.00", datetime(2026, 2, 2, 10, 0)),
            _ausf("P1", 9202, "SELL", "10.00", datetime(2026, 1, 2, 10, 0)),
            _ausf("P2", 9202, "BUY", "4.00", datetime(2026, 1, 3, 10, 0)),
            _ausf("Q1", 9203, "SELL", "2.00", datetime(2026, 3, 5, 10, 0)),
        ])
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(select(import_runs.c.id)).scalars().first()
        verbindung.execute(insert(flex_open_positions).values(
            import_run_id=lauf, konto="U1234567", quell_schluessel="op:1",
            stichtag=date(2026, 10, 9), conid=9201, symbol="OOO  261218P100",
            asset_class="OPT", menge=Decimal("-1"), kostenbasis_preis=Decimal("2.80"),
            fifo_pnl_unrealisiert=Decimal("8.00"), waehrung="EUR",
            roh_json=json.dumps({
                "levelOfDetail": "SUMMARY", "fxRateToBase": "1", "positionValue": "-20.00",
                "fifoPnlUnrealized": "8.00", "markPrice": "2.00", "costBasisPrice": "2.80"})))
    return TestClient(erzeuge_app(migrated_db))


def _je_basiswert(k):
    return {z["underlying"]: z for z in k.get("/ketten").json()["treffer"]}


def test_offene_kette_mit_bestand(klient):
    z = _je_basiswert(klient)["OOO"]
    assert Decimal(z["unrealisiert_eur"]) == Decimal("8.00")
    assert z["offene_legs_ohne_kurs"] == 0


def test_geschlossene_kette(klient):
    z = _je_basiswert(klient)["PPP"]
    assert z["unrealisiert_eur"] is None
    assert z["offene_legs_ohne_kurs"] == 0


def test_offene_kette_ohne_bestand(klient):
    z = _je_basiswert(klient)["QQQ"]
    assert z["unrealisiert_eur"] is None
    assert z["offene_legs_ohne_kurs"] == 1
