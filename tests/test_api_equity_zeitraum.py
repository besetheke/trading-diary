"""Abnahmetests für AP-08f2: `GET /equity?von=…&bis=…` (Z1/Z2 aus
auftraege/AP-08f.md). Unveränderlich.

Testwelt wie tests/test_api_equity.py: eine EUR-Struktur, geschlossen am
2026-01-03, netto 56.00 (von Hand: (10.00 - 4.00) * 10 - 4.00).
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


def test_zeitraum_einschliesslich(klient):
    """Beide Enden einschließlich: von=bis=Schließungstag enthält den Tag."""
    daten = klient.get("/equity", params={"von": "2026-01-03", "bis": "2026-01-03"}).json()
    assert [t["datum"] for t in daten["tage"]] == ["2026-01-03"]
    assert daten["tage"][0]["kumuliert_eur"] == "56.00"


def test_zeitraum_nach_dem_tag_ist_leer(klient):
    daten = klient.get("/equity", params={"von": "2026-01-04"}).json()
    assert daten == {
        "tage": [], "monate": [], "max_drawdown_eur": "0.00", "max_drawdown_datum": None,
    }


def test_zeitraum_vor_dem_tag_ist_leer(klient):
    daten = klient.get("/equity", params={"bis": "2026-01-02"}).json()
    assert daten["tage"] == []


@pytest.mark.parametrize("params", [{"von": "gestern"}, {"bis": "2026-13-01"}])
def test_ungueltiges_datum_ist_422(klient, params):
    assert klient.get("/equity", params=params).status_code == 422


def test_von_nach_bis_ist_422(klient):
    antwort = klient.get("/equity", params={"von": "2026-02-01", "bis": "2026-01-01"})
    assert antwort.status_code == 422
