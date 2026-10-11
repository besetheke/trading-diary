"""Abnahmetests für AP-08ue: `GET /uebersicht` — die Startseite in Zahlen.
Vertrag: auftraege/AP-08ue.md. Geschrieben durch das starke Modell — für die
Umsetzung unveränderlich. Erwartungen von Hand gerechnet.

Welt wie tests/test_api_ueberleitung.py: Equity netto +56.00 am Sa 03.01.2026,
NAV 1100.00 am 05.01.2026, Bestand am 05.01.: eine Option TST (Verfall
20.03.2026), unrealisiert −20.00.

`heute` = Mi 07.01.2026 (ISO-Woche 2026-W02, Mo 05.01.):
  Woche 05.01.–07.01. → 0.00; Monat 01.01.–07.01. → 56.00; Jahr → 56.00.
`heute` = So 04.01.2026 (Woche 29.12.2025–04.01.2026) → Woche 56.00.
Kontowert 1100.00 (Stand 05.01.), unrealisiert −20.00 (Stand 05.01.), eine
offene Position, nächster Verfall 20.03.2026 TST (1 Position).
"""

from decimal import Decimal

from test_api_ueberleitung import klient  # noqa: F401  (Fixture)


def test_uebersicht_mitte_der_woche(klient):  # noqa: F811
    d = klient.get("/uebersicht", params={"heute": "2026-01-07"}).json()
    assert d["heute"] == "2026-01-07"
    assert (d["kontowert_stand"], Decimal(d["kontowert_eur"])) == ("2026-01-05", Decimal("1100.00"))
    assert Decimal(d["realisiert_woche_eur"]) == 0
    assert Decimal(d["realisiert_monat_eur"]) == Decimal("56.00")
    assert Decimal(d["realisiert_jahr_eur"]) == Decimal("56.00")
    assert (d["bestand_stand"], Decimal(d["unrealisiert_eur"])) == ("2026-01-05", Decimal("-20.00"))
    assert d["offene_positionen"] == 1
    assert [(v["verfall"], v["basiswert"], v["anzahl"]) for v in d["verfaelle"]] == [
        ("2026-03-20", "TST", 1)]


def test_uebersicht_woche_endet_sonntag(klient):  # noqa: F811
    d = klient.get("/uebersicht", params={"heute": "2026-01-04"}).json()
    assert Decimal(d["realisiert_woche_eur"]) == Decimal("56.00")


def test_verfall_vor_heute_zaehlt_nicht(klient):  # noqa: F811
    d = klient.get("/uebersicht", params={"heute": "2026-03-21"}).json()
    assert d["verfaelle"] == []


def test_leere_datenbank(migrated_db):
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    d = TestClient(erzeuge_app(migrated_db)).get(
        "/uebersicht", params={"heute": "2026-01-07"}).json()
    assert d["kontowert_stand"] is None and d["kontowert_eur"] is None
    assert Decimal(d["realisiert_jahr_eur"]) == 0
    assert d["bestand_stand"] is None and d["offene_positionen"] == 0
    assert d["verfaelle"] == []
