"""Abnahmetest für AP-13ab: `GET /oa-abgleich`. Welt: OA-Export
`oa_fortschreibung_2.xlsx` (6001 EXPIRED +174.24 $, 6002 CLOSED +48.48 $, 6003
EXPIRED +118.48 $, alle „XSP: IF7") und IB-Ausführungen mit Orderreferenz
(USD, Multiplikator 100, Kommission −2.00 je Ausführung):
  6001: SELL 1.7824, BUY 0.00 → 178.24 − 4.00 = 174.24 → gleich
  6002: SELL 0.88, BUY 0.40   →  48.00 − 4.00 =  44.00 → Δ −4.48, sonst
  6003: keine Ausführung      → fehlt
Strategie XSP: IF7 (USD): 3 Trades, 1 gleich, 1 abweichend, 1 fehlt;
OA 222.72, IB 218.24, Δ −4.48. In `abweichungen` stehen 6002 und 6003.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from ingest.optionapp import import_optionapp_file  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optionapp"


def _opt(conid, strike):
    return dict(conid=conid, symbol=f"XSP 260306P{strike}", underlying="XSP", asset_class="OPT",
                expiry=date(2026, 3, 6), strike=Decimal(strike), right="P",
                multiplikator=Decimal("100"), waehrung="USD")


def _x(exec_id, conid, side, preis, zeit, oa):
    return dict(exec_id=exec_id, conid=conid, side=side, preis=Decimal(preis), handelszeit=zeit,
                waehrung="USD", kommission_waehrung="USD", buchungskurs=Decimal("0.9"),
                oa_trade=oa)


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, instrumente_=[_opt(1, "520"), _opt(2, "521")], ausfuehrungen=[
        _x("A1", 1, "SELL", "1.7824", datetime(2026, 3, 2, 11, 21), "6001"),
        _x("A2", 1, "BUY", "0", datetime(2026, 3, 6, 16, 0), None),
        _x("B1", 2, "SELL", "0.88", datetime(2026, 3, 3, 12, 0), "6002"),
        _x("B2", 2, "BUY", "0.40", datetime(2026, 3, 5, 15, 0), "6002"),
    ])
    rebuild(migrated_db)
    import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_2.xlsx")
    return TestClient(erzeuge_app(migrated_db))


def test_abgleich(klient):
    d = klient.get("/oa-abgleich").json()
    s = d["strategien"]
    assert len(s) == 1
    z = s[0]
    assert (z["strategie"], z["waehrung"], z["anzahl"], z["gleich"], z["abweichend"],
            z["fehlt"]) == ("XSP: IF7", "USD", 3, 1, 1, 1)
    assert (Decimal(z["summe_oa"]), Decimal(z["summe_ib"]), Decimal(z["differenz"])) == (
        Decimal("222.72"), Decimal("218.24"), Decimal("-4.48"))
    abw = {t["oa_trade"]: t for t in d["abweichungen"]}
    assert sorted(abw) == ["6002", "6003"]
    assert (abw["6002"]["grund"], Decimal(abw["6002"]["differenz"])) == ("sonst", Decimal("-4.48"))
    assert abw["6003"]["grund"] == "fehlt"


def test_von_nach_bis_ist_422(klient):
    assert klient.get("/oa-abgleich", params={"von": "2026-02-01", "bis": "2026-01-01"}
                      ).status_code == 422
