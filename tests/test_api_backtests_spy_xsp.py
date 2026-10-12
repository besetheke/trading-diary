"""Abnahmetest für AP-12b: Ein Backtest kann gegen mehrere Bots gleichzeitig
laufen (Nutzer 12.10.2026: „SPY: IF7 und XSP: IF7 sind dieselbe Strategie,
separat behandeln"). Jeder bestätigte Bot paart die OO-Trades für sich; ein
Trade des einen Bots nimmt dem anderen keinen Partner weg.

Welt: OO-Fixture (oo_beispiel.csv), Zeile R5 „-26 SPY -IF- 11:51", 1 Kontrakt,
P/L +50.00, am 02.03.2026 11:51. Live zwei Bots mit derselben Struktur (685P/
687C verkauft, 678P/695C gekauft):
  8001 „SPY: IF7"  11:51:40  Gewinn +45.00
  8002 „XSP: IF7"  11:51:20  Gewinn +30.00
Ohne Trennung gewänne nur der nähere (8002) den Partner. Beide bestätigt:
  SPY: IF7 — 1 Paar, Backtest 50.00, Bot 45.00, Differenz −5.00
  XSP: IF7 — 1 Paar, Backtest 50.00, Bot 30.00, Differenz −20.00
"""

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from ingest.optionomega import import_optionomega_file  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import import_runs, optionapp_trades  # noqa: E402

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "optionomega" / "oo_beispiel.csv"
IF = "-26 SPY -IF- 11:51"
LEGS = [("SELL", "P", 685), ("SELL", "C", 687), ("BUY", "P", 678), ("BUY", "C", 695)]
BOTS = [("8001", "SPY: IF7", "SPY", datetime(2026, 3, 2, 11, 51, 40), "45"),
        ("8002", "XSP: IF7", "XSP", datetime(2026, 3, 2, 11, 51, 20), "30")]


@pytest.fixture
def klient(migrated_db):
    instrumente, ausfuehrungen, conid = [], [], 500
    for oa, _, basis, zeit, _ in BOTS:
        for i, (seite, right, strike) in enumerate(LEGS):
            conid += 1
            instrumente.append(dict(
                conid=conid, symbol=f"{basis} 260302{right}{strike}", underlying=basis,
                asset_class="OPT", expiry=zeit.date(), strike=Decimal(strike), right=right,
                multiplikator=Decimal("100"), waehrung="USD"))
            ausfuehrungen.append(dict(
                exec_id=f"{oa}-{i}", conid=conid, side=seite, preis=Decimal("1"),
                handelszeit=zeit, waehrung="USD", kommission_waehrung="USD",
                buchungskurs=Decimal("0.9"), oa_trade=oa))
    befuelle(migrated_db, instrumente_=instrumente, ausfuehrungen=ausfuehrungen)
    with create_db_engine(migrated_db).begin() as v:
        lauf = v.execute(insert(import_runs).values(
            quelle="optionapp", datei_hash="oa-spy", importiert_am=datetime(2026, 3, 9),
            qualitaetsstufe="B", zeilen_gesamt=2, zeilen_neu=2)).inserted_primary_key[0]
        for oa, strategie, _, zeit, profit in BOTS:
            v.execute(insert(optionapp_trades).values(
                import_run_id=lauf, oa_trade=oa, entry_zeit=zeit, schluss_zeit=zeit,
                strategie=strategie, name_roh=f"Bot [{oa}]", strikes_roh="-",
                menge_zaehler=Decimal("1"), menge_nenner=Decimal("1"), stop_roh="-",
                profit=Decimal(profit), profit_waehrung="$", status="EXPIRED",
                roh_json=json.dumps({})))
    import_optionomega_file(migrated_db, FIXTURE)
    return TestClient(erzeuge_app(migrated_db, mit_journal=True))


def test_beide_bots_paaren_getrennt(klient):
    for bot in ("SPY: IF7", "XSP: IF7"):
        klient.post("/journal/backtests/zuordnung",
                    json={"oo_strategie": IF, "oa_strategie": bot, "status": "bestaetigt"})
    v = {z["oa_strategie"]: z for z in klient.get("/backtests").json()["vergleich"]
         if z["oo_strategie"] == IF}
    assert set(v) == {"SPY: IF7", "XSP: IF7"}
    spy, xsp = v["SPY: IF7"], v["XSP: IF7"]
    assert (spy["paare"], Decimal(spy["summe_backtest"]), Decimal(spy["summe_live"]),
            Decimal(spy["differenz"])) == (1, Decimal("50"), Decimal("45"), Decimal("-5"))
    assert (xsp["paare"], Decimal(xsp["summe_backtest"]), Decimal(xsp["summe_live"]),
            Decimal(xsp["differenz"])) == (1, Decimal("50"), Decimal("30"), Decimal("-20"))
