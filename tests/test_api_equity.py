"""Abnahmetests für die Equity-Kurve der API (AP-06e).

Geschrieben durch das starke Modell — für die Umsetzung unveränderlich.
Eigene, kleine Testwelt (statt `fixtures_rebuild`): eine einzelne EUR-
Struktur mit von Hand nachgerechnetem Ergebnis (Regel 8).

SELL 10.00 am 2026-01-02, BUY 4.00 am 2026-01-03, Multiplikator 10,
Kommission -2.00 je Ausführung (Vorgabe aus `fixtures_rebuild._VORGABEN`):
brutto = (10.00 - 4.00) * 10 = 60.00, netto = 60.00 - 4.00 = 56.00,
geschlossen am 2026-01-03 (Zeitpunkt der schließenden Ausführung).
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

_INSTRUMENTE = [
    dict(conid=9001, symbol="TST  260320P100", underlying="TST", asset_class="OPT",
         expiry=date(2026, 3, 20), strike=Decimal("100"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
]

_AUSFUEHRUNGEN = [
    dict(exec_id="T1", conid=9001, side="SELL", preis=Decimal("10.00"),
         handelszeit=datetime(2026, 1, 2, 10, 0, 0), buchungskurs=Decimal("1")),
    dict(exec_id="T2", conid=9001, side="BUY", preis=Decimal("4.00"),
         handelszeit=datetime(2026, 1, 3, 10, 0, 0), buchungskurs=Decimal("1")),
]


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=_AUSFUEHRUNGEN, instrumente_=_INSTRUMENTE)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


@pytest.fixture
def leerer_klient(migrated_db):
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_equity_handgerechnet(klient):
    antwort = klient.get("/equity")
    assert antwort.status_code == 200
    daten = antwort.json()

    assert len(daten["tage"]) == 1
    tag = daten["tage"][0]
    assert tag["datum"] == "2026-01-03"
    assert tag["netto_eur"] == "56.00"
    assert tag["kumuliert_eur"] == "56.00"
    assert tag["drawdown_eur"] == "0.00"
    assert tag["anzahl_strukturen"] == 1
    assert tag["anzahl_strukturen_kurs_fehlt"] == 0

    assert len(daten["monate"]) == 1
    monat = daten["monate"][0]
    assert monat["monat"] == "2026-01"
    assert monat["summe_netto_eur"] == "56.00"
    assert monat["durchschnitt_netto_eur"] == "56.00"
    assert monat["trefferquote"] == "1.0000"

    assert daten["max_drawdown_eur"] == "0.00"
    assert daten["max_drawdown_datum"] is None


def test_geld_ist_zeichenkette_nie_zahl(klient):
    rohtext = klient.get("/equity").text
    assert '"netto_eur":"56.00"' in rohtext.replace(" ", "")


def test_equity_ist_leer_ohne_bestand(leerer_klient):
    daten = leerer_klient.get("/equity").json()
    assert daten == {
        "tage": [], "monate": [], "max_drawdown_eur": "0.00", "max_drawdown_datum": None,
    }
