"""Abnahmetests für `GET /performance` (AP-08p). Welt wie tests/test_api_ueberleitung.py:
Einzahlung 1000.00 am 01.01.2026, Kontowert 1100.00 am Mo 05.01.2026 (einziger
NAV-Tag), Equity netto 56.00 am Sa 03.01.2026.

Von Hand: ein Tag, Index 1, Drawdown 0. Wochen (ISO): 2026-W01 (29.12.–04.01.) mit
realisiert 56.00, 2026-W02 (05.01.–11.01.) mit dem NAV-Tag; Gewinn je Tag am ersten
Tag 0 (kein Vortag). Monat 2026-01: realisiert 56.00.
"""

from decimal import Decimal

from test_api_ueberleitung import klient  # noqa: F401  (Fixture)


def test_tage_und_drawdown(klient):  # noqa: F811
    daten = klient.get("/performance").json()
    assert [(t["datum"], Decimal(t["index"]), Decimal(t["drawdown_prozent"]))
            for t in daten["tage"]] == [("2026-01-05", Decimal("1"), Decimal("0"))]
    assert Decimal(daten["max_drawdown_prozent"]) == 0
    assert Decimal(daten["kontowert_ende"]) == Decimal("1100.00")


def test_wochen_und_monate(klient):  # noqa: F811
    daten = klient.get("/performance").json()
    assert [(w["schluessel"], w["beginn"], w["ende"], Decimal(w["realisiert"]))
            for w in daten["wochen"]] == [
        ("2026-W01", "2025-12-29", "2026-01-04", Decimal("56.00")),
        ("2026-W02", "2026-01-05", "2026-01-11", Decimal("0")),
    ]
    assert [(m["schluessel"], Decimal(m["realisiert"])) for m in daten["monate"]] == [
        ("2026-01", Decimal("56.00"))]
    assert Decimal(daten["realisiert_zeitraum"]) == Decimal("56.00")


def test_von_nach_bis_ist_422(klient):  # noqa: F811
    assert klient.get("/performance", params={"von": "2026-02-01", "bis": "2026-01-01"}
                      ).status_code == 422
