"""Abnahmetests für AP-07fm: Mehrfachauswahl in den Positionsfiltern. Vertrag:
auftraege/AP-07fm.md. Geschrieben durch das starke Modell — für die Umsetzung
unveränderlich. Erwartungen von Hand gerechnet.

Regel: Basiswert, Anlageklasse, Währung, Strategie, Seite und Endzustand
dürfen mehrfach angegeben werden (`?basiswert=AAA&basiswert=BBB`). Innerhalb
eines Filters gilt ODER, zwischen Filtern UND. Leere Werte zählen nicht; ein
einzelner Wert wirkt wie bisher.

Welt 1 (tests/test_api_filter.py): AAA EUR +56.00 (03.01.), BBB EUR −14.00
(05.02.), CCC USD +52.00 € = 26.00 USD (01.03.), DDD EUR offen; Strategie „IC1"
an AAA und CCC.
  basiswert AAA|BBB → 2 Ketten, Summe 56 − 14 = 42.00
  basiswert AAA|CCC → 108.00; je Währung EUR 56.00, USD 26.00
  waehrung EUR|USD → wie ohne Filter: 94.00 (vier Ketten)
  strategie IC1|XYZ → AAA und CCC: 108.00
  basiswert „" und AAA → nur AAA: 56.00
Welt 2 (tests/test_api_filter_lose_legs.py): AAA EUR Option +56.00; loses Leg
XXX USD Aktie −1008.00.
  basiswert AAA|XXX → beide: −952.00 (das lose Leg zählt über seinen Basiswert)
  anlageklasse OPT|STK → beide: −952.00
"""

from decimal import Decimal

import pytest
from test_api_filter import klient  # noqa: F401  (Fixture Welt 1)
from test_api_filter_lose_legs import klient as klient_lose  # noqa: F401  (Welt 2)


def _summe(k, params):
    return Decimal(k.get("/auswertung", params=params).json()["ergebnis"]["summe_netto_eur"])


def test_ketten_mehrere_basiswerte(klient):  # noqa: F811
    d = klient.get("/ketten", params=[("basiswert", "AAA"), ("basiswert", "BBB")]).json()
    assert d["gesamt"] == 2
    assert sorted(k["underlying"] for k in d["treffer"]) == ["AAA", "BBB"]


def test_auswertung_mehrere_basiswerte(klient):  # noqa: F811
    assert _summe(klient, [("basiswert", "AAA"), ("basiswert", "BBB")]) == Decimal("42.00")
    d = klient.get("/auswertung", params=[("basiswert", "AAA"), ("basiswert", "CCC")]).json()
    assert Decimal(d["ergebnis"]["summe_netto_eur"]) == Decimal("108.00")
    assert [(z["waehrung"], Decimal(z["summe"])) for z in d["netto_je_waehrung"]] == [
        ("EUR", Decimal("56.00")), ("USD", Decimal("26.00"))]


def test_mehrere_waehrungen(klient):  # noqa: F811
    d = klient.get("/auswertung", params=[("waehrung", "EUR"), ("waehrung", "USD")]).json()
    assert Decimal(d["ergebnis"]["summe_netto_eur"]) == Decimal("94.00")
    assert d["ergebnis"]["anzahl_ketten"] == 4


def test_mehrere_strategien(klient):  # noqa: F811
    assert _summe(klient, [("strategie", "IC1"), ("strategie", "XYZ")]) == Decimal("108.00")


def test_leere_werte_zaehlen_nicht(klient):  # noqa: F811
    assert _summe(klient, [("basiswert", ""), ("basiswert", "AAA")]) == Decimal("56.00")


def test_lose_legs_mehrere_basiswerte(klient_lose):  # noqa: F811
    assert _summe(klient_lose, [("basiswert", "AAA"), ("basiswert", "XXX")]) == Decimal(
        "-952.00")
    assert _summe(klient_lose, [("anlageklasse", "OPT"), ("anlageklasse", "STK")]) == Decimal(
        "-952.00")


@pytest.mark.parametrize("feld", ["seite", "endzustand"])
def test_mehrfach_bei_kettenfeldern(klient, feld):  # noqa: F811
    """Seite und Endzustand: alle vorkommenden Werte zusammen = ohne Filter
    (94.00), solange jede Kette einen Wert trägt."""
    werte = sorted({k[feld] for k in klient.get("/ketten").json()["treffer"]
                    if k[feld] is not None})
    assert werte, "Welt ohne Werte"
    assert _summe(klient, [(feld, w) for w in werte]) == Decimal("94.00")
