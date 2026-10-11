"""Abnahmetests für AP-07fv: `GET /auswertung` — aufsummierter Verlauf Tag für Tag und
das realisierte Ergebnis je Positionswährung.

Welt wie tests/test_api_filter.py: AAA +56.00 EUR am 03.01.2026, BBB −14.00 EUR am
05.02., CCC USD (Kurs 2) am 01.03.: nativ (5.00 − 2.00)·10 − 4.00 = 26.00 USD,
in EUR 52.00; DDD offen, kein Bestand laut IB.

Verlauf (von Hand): jeder Kalendertag vom 03.01. bis 01.03. (58 Tage), Wert =
Summe bis einschließlich des Tages: 03.01. 56.00, 04.01. 56.00 (unverändert),
05.02. 42.00, 01.03. 94.00.
Je Währung (nativ, geschlossene Strukturen; auf oberster Ebene, `ergebnis` bleibt
unverändert — test_api_filter vergleicht es vollständig)
Endpunkt der gestrichelten Linie: realisiert + unrealisiert = 94.00 + 0 = 94.00
(kein Bestand laut IB).: EUR 56 − 14 = 42.00; USD 26.00.
"""

from decimal import Decimal

from test_api_filter import klient  # noqa: F401  (Fixture)


def test_verlauf_taeglich(klient):  # noqa: F811
    v = klient.get("/auswertung").json()["verlauf"]
    assert len(v) == 58
    werte = {p["datum"]: Decimal(p["kumuliert_eur"]) for p in v}
    assert werte["2026-01-03"] == Decimal("56.00")
    assert werte["2026-01-04"] == Decimal("56.00")
    assert werte["2026-02-04"] == Decimal("56.00")
    assert werte["2026-02-05"] == Decimal("42.00")
    assert werte["2026-03-01"] == Decimal("94.00")
    assert v[0]["datum"] == "2026-01-03" and v[-1]["datum"] == "2026-03-01"


def test_realisiert_je_waehrung(klient):  # noqa: F811
    je = klient.get("/auswertung").json()["netto_je_waehrung"]
    assert [(z["waehrung"], Decimal(z["summe"])) for z in je] == [
        ("EUR", Decimal("42.00")), ("USD", Decimal("26.00"))]


def test_je_waehrung_folgt_dem_filter(klient):  # noqa: F811
    je = klient.get("/auswertung", params={"waehrung": "USD"}).json()[
        "netto_je_waehrung"]
    assert [(z["waehrung"], Decimal(z["summe"])) for z in je] == [("USD", Decimal("26.00"))]


def test_ohne_treffer_leerer_verlauf(klient):  # noqa: F811
    daten = klient.get("/auswertung", params={"basiswert": "ZZZ"}).json()
    assert daten["verlauf"] == []
    assert daten["netto_je_waehrung"] == []


def test_endpunkt_mit_unrealisiert(klient):  # noqa: F811
    u = klient.get("/auswertung").json()["unrealisiert"]
    assert Decimal(u["mit_realisiert_eur"]) == Decimal("94.00")
    u = klient.get("/auswertung", params={"basiswert": "BBB"}).json()["unrealisiert"]
    assert Decimal(u["mit_realisiert_eur"]) == Decimal("-14.00")
