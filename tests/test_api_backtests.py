"""Abnahmetest für AP-12a: ``GET /backtests``, ``GET /backtests/paare``,
``POST /journal/backtests/zuordnung``.

Welt: OO-Export ``fixtures/optionomega/oo_beispiel.csv`` (R1–R7, siehe
``erzeugen_beispiel.py``) und Live-Trades (OA-Nummer, OA-Strategie, OA-Gewinn
in USD), US-Ostküstenzeit wie OO:

  7001 SPX: IC +Vo/n   03-02 09:33  IC 6805/6905 Flügel 30, 1×   +210
  7002 SPX: IC +Vo/n   03-03 09:32  IC 6810/6910 Flügel 30, 2×  −1100
  7003 SPX: IC +Vo/n   03-04 13:00  IC 6820/6920 Flügel 30, 1×   +100
  7004 XSP: IF         03-02 11:52  XSP 685P/687C, 678P/695C, 1×  +45
  7005 SPX: Andere     03-02 09:32  Put-Vertikale 6800/6770      +30
  7006 SPX: ORB L PBF  03-03 11:16  6855P S 2, 6825P B 1, 6885P B 1 +380

Von Hand:
- Paare: R1↔7001, R2↔7002, R5↔7004, R7↔7006. R3 (09:32) und 7003 (13:00)
  liegen 208 Minuten auseinander; 7005 hat eine andere Signatur.
- Vorschläge (alle Anteil 1,0000, eindeutig):
  „-26 -IC Test- 9:32" → „SPX: IC +Vo/n" 2 Treffer, 03-02 … 03-03;
  „-26 SPY -IF- 11:51" → „XSP: IF" 1 Treffer; „0DTE -PBF-" → „SPX: ORB L PBF"
  1 Treffer. „-26 -DC Jahr-" ohne Zuordnung (1 Trade).
- Vergleich je Kontrakt:
  IC: Backtest 224 + (−500) = −276; Live 210 + (−1100 ÷ 2) = −340; Δ −64.
      nur Backtest: R3 (03-04 liegt im Live-Zeitraum 03-02 … 03-04) +200.
      nur Live: 7003 (03-04 liegt im Backtest-Zeitraum 03-02 … 03-05, kein
      OO-Partner) +100.
      offen: R4 (Backtest Completed) → 1.
  IF: 50 gegen 45, Δ −5. PBF: 800 ÷ 2 = 400 gegen 380 ÷ 1 = 380, Δ −20.
- Ablehnen nimmt IF aus dem Vergleich, IF steht dann „ohne Zuordnung"; ein
  von Hand bestätigtes Paar ohne Treffer erscheint mit Treffer 0 und leerem
  Vergleich.
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
IC, IF, PBF = "-26 -IC Test- 9:32", "-26 SPY -IF- 11:51", "0DTE -PBF-"

LIVE = [
    # oa, strategie, zeit, basiswert, profit, legs (seite, right, strike, menge)
    ("7001", "SPX: IC +Vo/n", datetime(2026, 3, 2, 9, 33), "SPX", "210",
     [("SELL", "P", 6805, 1), ("SELL", "C", 6905, 1),
      ("BUY", "P", 6775, 1), ("BUY", "C", 6935, 1)]),
    ("7002", "SPX: IC +Vo/n", datetime(2026, 3, 3, 9, 32), "SPX", "-1100",
     [("SELL", "P", 6810, 2), ("SELL", "C", 6910, 2),
      ("BUY", "P", 6780, 2), ("BUY", "C", 6940, 2)]),
    ("7003", "SPX: IC +Vo/n", datetime(2026, 3, 4, 13, 0), "SPX", "100",
     [("SELL", "P", 6820, 1), ("SELL", "C", 6920, 1),
      ("BUY", "P", 6790, 1), ("BUY", "C", 6950, 1)]),
    ("7004", "XSP: IF", datetime(2026, 3, 2, 11, 52), "XSP", "45",
     [("SELL", "P", 685, 1), ("SELL", "C", 687, 1),
      ("BUY", "P", 678, 1), ("BUY", "C", 695, 1)]),
    ("7005", "SPX: Andere", datetime(2026, 3, 2, 9, 32), "SPX", "30",
     [("SELL", "P", 6800, 1), ("BUY", "P", 6770, 1)]),
    ("7006", "SPX: ORB L PBF", datetime(2026, 3, 3, 11, 16), "SPX", "380",
     [("SELL", "P", 6855, 2), ("BUY", "P", 6825, 1), ("BUY", "P", 6885, 1)]),
]


def _live_anlegen(db):
    instrumente, ausfuehrungen, conid = {}, [], 100
    for oa, _, zeit, basis, _, legs in LIVE:
        for i, (seite, right, strike, menge) in enumerate(legs):
            schluessel = (basis, right, strike, zeit.date())
            if schluessel not in instrumente:
                conid += 1
                instrumente[schluessel] = dict(
                    conid=conid, symbol=f"{basis} {zeit:%y%m%d}{right}{strike}",
                    underlying=basis, asset_class="OPT", expiry=zeit.date(),
                    strike=Decimal(strike), right=right, multiplikator=Decimal("100"),
                    waehrung="USD")
            ausfuehrungen.append(dict(
                exec_id=f"{oa}-{i}", conid=instrumente[schluessel]["conid"], side=seite,
                menge=Decimal(menge), preis=Decimal("1"), handelszeit=zeit, waehrung="USD",
                kommission_waehrung="USD", buchungskurs=Decimal("0.9"), oa_trade=oa))
    befuelle(db, instrumente_=list(instrumente.values()), ausfuehrungen=ausfuehrungen)
    with create_db_engine(db).begin() as v:
        lauf = v.execute(insert(import_runs).values(
            quelle="optionapp", datei_hash="oa-test", importiert_am=datetime(2026, 3, 9),
            qualitaetsstufe="B", zeilen_gesamt=6, zeilen_neu=6)).inserted_primary_key[0]
        for oa, strategie, zeit, _, profit, _ in LIVE:
            v.execute(insert(optionapp_trades).values(
                import_run_id=lauf, oa_trade=oa, entry_zeit=zeit, schluss_zeit=zeit,
                strategie=strategie, name_roh=f"Bot [{oa}]", strikes_roh="-",
                menge_zaehler=Decimal("1"), menge_nenner=Decimal("1"), stop_roh="-",
                profit=Decimal(profit), profit_waehrung="$", status="EXPIRED",
                roh_json=json.dumps({})))


@pytest.fixture
def klient(migrated_db):
    _live_anlegen(migrated_db)
    import_optionomega_file(migrated_db, FIXTURE)
    return TestClient(erzeuge_app(migrated_db, mit_journal=True))


def _vergleich(d):
    return {(z["oo_strategie"], z["oa_strategie"]): z for z in d["vergleich"]}


def test_vorschlaege(klient):
    d = klient.get("/backtests").json()
    assert [(z["oo_strategie"], z["oa_strategie"], z["erkennung"], z["status"], z["treffer"],
             Decimal(z["anteil"]), z["eindeutig"], z["erster"], z["letzter"])
            for z in d["zuordnungen"]] == [
        (IC, "SPX: IC +Vo/n", "heuristik", "vorschlag", 2, Decimal("1"), True,
         "2026-03-02", "2026-03-03"),
        (IF, "XSP: IF", "heuristik", "vorschlag", 1, Decimal("1"), True,
         "2026-03-02", "2026-03-02"),
        (PBF, "SPX: ORB L PBF", "heuristik", "vorschlag", 1, Decimal("1"), True,
         "2026-03-03", "2026-03-03"),
    ]
    assert [z["oo_anzahl"] for z in d["zuordnungen"]] == [4, 1, 1]
    assert d["ohne_zuordnung"] == [{"oo_strategie": "-26 -DC Jahr-", "anzahl": 1}]


def test_vergleich(klient):
    v = _vergleich(klient.get("/backtests").json())
    ic = v[(IC, "SPX: IC +Vo/n")]
    assert (ic["paare"], Decimal(ic["summe_backtest"]), Decimal(ic["summe_live"]),
            Decimal(ic["differenz"])) == (2, Decimal("-276"), Decimal("-340"), Decimal("-64"))
    assert (ic["nur_backtest"], Decimal(ic["summe_nur_backtest"]), ic["nur_live"],
            Decimal(ic["summe_nur_live"]), ic["offen"]) == (
        1, Decimal("200"), 1, Decimal("100"), 1)
    f = v[(IF, "XSP: IF")]
    assert (f["paare"], Decimal(f["differenz"]), f["nur_backtest"], f["nur_live"]) == (
        1, Decimal("-5"), 0, 0)
    p = v[(PBF, "SPX: ORB L PBF")]
    assert (Decimal(p["summe_backtest"]), Decimal(p["summe_live"]), Decimal(p["differenz"])) == (
        Decimal("400"), Decimal("380"), Decimal("-20"))


def test_paare_im_einzelnen(klient):
    z = klient.get("/backtests/paare", params={"oo_strategie": IC,
                                                "oa_strategie": "SPX: IC +Vo/n"}).json()
    kurz = [(x["art"], x["oa_trade"], x["kontrakte_backtest"], x["kontrakte_live"],
             None if x["pl_backtest"] is None else Decimal(x["pl_backtest"]),
             None if x["pl_live"] is None else Decimal(x["pl_live"])) for x in z]
    assert kurz == [
        ("paar", "7001", 1, 1, Decimal("224"), Decimal("210")),
        ("paar", "7002", 1, 2, Decimal("-500"), Decimal("-550")),
        ("nur_backtest", None, 1, None, Decimal("200"), None),
        ("nur_live", "7003", None, 1, None, Decimal("100")),
        ("offen", None, 1, None, None, None),
    ]


def test_entscheidungen(klient):
    r = klient.post("/journal/backtests/zuordnung",
                    json={"oo_strategie": IF, "oa_strategie": "XSP: IF", "status": "abgelehnt"})
    assert r.status_code == 200
    r = klient.post("/journal/backtests/zuordnung",
                    json={"oo_strategie": "-26 -DC Jahr-", "oa_strategie": "SPX: Andere",
                          "status": "bestaetigt"})
    assert r.status_code == 200
    d = klient.get("/backtests").json()
    z = {(x["oo_strategie"], x["oa_strategie"]): x for x in d["zuordnungen"]}
    assert (z[(IF, "XSP: IF")]["status"], z[(IF, "XSP: IF")]["erkennung"]) == (
        "abgelehnt", "manuell")
    dc = z[("-26 -DC Jahr-", "SPX: Andere")]
    assert (dc["status"], dc["erkennung"], dc["treffer"]) == ("bestaetigt", "manuell", 0)
    # IF hat keine andere Zuordnung — abgelehnt heißt wieder „ohne Zuordnung";
    # „DC Jahr" ist durch die Bestätigung zugeordnet.
    assert d["ohne_zuordnung"] == [{"oo_strategie": IF, "anzahl": 1}]
    v = _vergleich(d)
    assert (IF, "XSP: IF") not in v
    assert v[("-26 -DC Jahr-", "SPX: Andere")]["paare"] == 0
    # Zurücknehmen: wieder Vorschlag.
    klient.post("/journal/backtests/zuordnung",
                json={"oo_strategie": IF, "oa_strategie": "XSP: IF", "status": "vorschlag"})
    assert (IF, "XSP: IF") in _vergleich(klient.get("/backtests").json())


def test_unbekannter_status_ist_422(klient):
    r = klient.post("/journal/backtests/zuordnung",
                    json={"oo_strategie": IF, "oa_strategie": "XSP: IF", "status": "egal"})
    assert r.status_code == 422


def test_ohne_daten(migrated_db):
    d = TestClient(erzeuge_app(migrated_db)).get("/backtests").json()
    assert d == {"zuordnungen": [], "vergleich": [], "ohne_zuordnung": []}
