"""Abnahmetests für AP-07fu: `GET /auswertung` liefert Wochenwerte und das
unrealisierte Ergebnis offener Positionen der Auswahl.

Welt wie tests/test_api_filter.py (dieselbe Fixture): AAA +56.00 am Sa 03.01.2026,
BBB −14.00 am Do 05.02., CCC +52.00 am So 01.03., DDD offen (SELL 3.00 am 05.03.),
kein Bestand laut IB importiert.

Wochen (ISO, von Hand): 2026-W01 (29.12.2025–04.01.2026) +56.00, 2026-W06
(02.02.–08.02.) −14.00, 2026-W09 (23.02.–01.03.) +52.00.
Unrealisiert: ohne Bestandszeile kein Wert — DDD zählt als „ohne Kurs".
"""

from decimal import Decimal

from test_api_filter import klient  # noqa: F401  (Fixture)


def test_wochen(klient):  # noqa: F811
    daten = klient.get("/auswertung").json()
    assert [(w["schluessel"], w["beginn"], w["ende"], Decimal(w["summe_netto_eur"]))
            for w in daten["wochen"]] == [
        ("2026-W01", "2025-12-29", "2026-01-04", Decimal("56.00")),
        ("2026-W06", "2026-02-02", "2026-02-08", Decimal("-14.00")),
        ("2026-W09", "2026-02-23", "2026-03-01", Decimal("52.00")),
    ]


def test_unrealisiert_ohne_bestand(klient):  # noqa: F811
    u = klient.get("/auswertung").json()["unrealisiert"]
    assert u["stichtag"] is None
    assert Decimal(u["eur"]) == 0
    assert (u["anzahl_legs"], u["ohne_kurs"]) == (0, 1)


def test_unrealisiert_folgt_dem_filter(klient):  # noqa: F811
    """AAA ist geschlossen — keine offenen Legs in der Auswahl."""
    u = klient.get("/auswertung", params={"basiswert": "AAA"}).json()["unrealisiert"]
    assert (u["anzahl_legs"], u["ohne_kurs"]) == (0, 0)
