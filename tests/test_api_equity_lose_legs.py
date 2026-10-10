"""Abnahmetests für AP-06i über die API: lose Legs in `GET /equity` und
`GET /kapital`. Geschrieben durch das starke Modell — unveränderlich.

Testwelt (Rebuild, frei erfunden): eine Aktie in USD, eröffnet durch eine
Zuteilung ohne zugehörige Optionsstruktur — die Kettenbildung kann sie nicht
fortsetzen, das Leg bleibt ohne Struktur (wie 185 Legs im Echtbestand, OF-78).

  BUY 100 zu 50.00 (ereignistyp 'assignment') am 2026-01-02,
  SELL 100 zu 45.00 am 2026-01-05, Kommission -2.00 je Ausführung,
  buchungskurs 0.9.
  → ((45 - 50) × 100 - 4) × 0.9 = -504 × 0.9 = -453.60 am 2026-01-05.
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
    dict(conid=950, symbol="LOSE", underlying="LOSE", asset_class="STK",
         expiry=None, strike=None, right=None,
         multiplikator=Decimal("1"), waehrung="USD"),
]

_AUSFUEHRUNGEN = [
    dict(exec_id="Z1", conid=950, side="BUY", menge=Decimal("100"),
         preis=Decimal("50.00"), waehrung="USD", kommission_waehrung="USD",
         ereignistyp="assignment", handelszeit=datetime(2026, 1, 2, 22, 0, 0),
         buchungskurs=Decimal("0.9")),
    dict(exec_id="Z2", conid=950, side="SELL", menge=Decimal("-100"),
         preis=Decimal("45.00"), waehrung="USD", kommission_waehrung="USD",
         handelszeit=datetime(2026, 1, 5, 15, 0, 0), buchungskurs=Decimal("0.9")),
]


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=_AUSFUEHRUNGEN, instrumente_=_INSTRUMENTE)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_equity_enthaelt_loses_leg(klient):
    daten = klient.get("/equity").json()
    assert len(daten["tage"]) == 1
    tag = daten["tage"][0]
    assert tag["datum"] == "2026-01-05"
    assert tag["netto_eur"] == "-453.60"
    assert tag["kumuliert_eur"] == "-453.60"
    assert tag["anzahl_strukturen"] == 0
    assert tag["anzahl_lose_legs"] == 1
    assert tag["anzahl_lose_legs_kurs_fehlt"] == 0
    monat = daten["monate"][0]
    assert monat["summe_netto_eur"] == "-453.60"
    assert monat["lose_legs_eur"] == "-453.60"
    assert monat["anzahl_lose_legs"] == 1
    assert daten["max_drawdown_eur"] == "-453.60"
    assert daten["max_drawdown_datum"] == "2026-01-05"


def test_kapital_enthaelt_loses_leg(klient):
    """Kapital übernimmt die Equity-Tage (AP-06g) — ohne Einzahlungen ist
    das Endkapital das Ergebnis."""
    daten = klient.get("/kapital").json()
    assert daten["ergebnis_im_zeitraum"] == "-453.60"


def test_zeitraum_vor_dem_schliessungstag_ist_leer(klient):
    daten = klient.get("/equity", params={"bis": date(2026, 1, 4).isoformat()}).json()
    assert daten["tage"] == []
