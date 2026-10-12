"""Abnahmetest für AP-12c: Ursachen und Monatsfilter an `GET /backtests`.
Welt von tests/test_api_backtests.py (OO-Fixture + Live 7001–7006). Strategie
IC, Paare R1↔7001 und R2↔7002:
  R1↔7001: Strikes verschoben (6800/6900 gegen 6805/6905), Zeit +1 Min, Backtest
    224, Bot 210 → Δ −14, über der Toleranz von 10 → Strikeauswahl.
  R2↔7002: Backtest 1 Kontrakt −500, Bot 2 Kontrakte −1100 (−550 je Kontrakt)
    → Kontraktzahl, Δ −50, Kontrakteffekt (2 − 1) · (−550) = −550 USD.
Summe der Ursachen −14 − 50 = −64 = Differenz (wie dort).
Monatsfilter: `bis=2026-03-02` lässt nur den 2.3. gelten (R1↔7001, R5↔7004,
7005): IC 1 Paar, Differenz −14.
"""

from decimal import Decimal

from test_api_backtests import IC, klient  # noqa: F401


def _ic(d):
    return next(z for z in d["vergleich"] if z["oo_strategie"] == IC)


def test_ursachen(klient):  # noqa: F811
    z = _ic(klient.get("/backtests").json())
    u = {x["ursache"]: (x["anzahl"], Decimal(x["summe"])) for x in z["ursachen"]}
    assert u == {"strikeauswahl": (1, Decimal("-14")), "kontrakte": (1, Decimal("-50"))}
    assert Decimal(z["kontrakt_effekt"]) == Decimal("-550")


def test_paare_tragen_die_ursache(klient):  # noqa: F811
    zeilen = klient.get("/backtests/paare", params={"oo_strategie": IC,
                                                    "oa_strategie": "SPX: IC +Vo/n"}).json()
    je = {z["oa_trade"]: z for z in zeilen if z["art"] == "paar"}
    assert (je["7001"]["ursache"], je["7001"]["zeitversatz_min"]) == ("strikeauswahl", 1)
    assert je["7002"]["ursache"] == "kontrakte"


def test_monatsfilter(klient):  # noqa: F811
    z = _ic(klient.get("/backtests", params={"von": "2026-03-02", "bis": "2026-03-02"}).json())
    assert (z["paare"], Decimal(z["differenz"])) == (1, Decimal("-14"))
