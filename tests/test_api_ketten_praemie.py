"""Abnahmetest für AP-06sf: `GET /ketten` trägt bei offenen Ketten den
Prämienwert der offenen Legs — `praemie_offen_eur` (Prämie bei Eröffnung,
ohne Kommission) und `praemie_aktuell_eur` (Prämie laut IBs letztem Marktwert),
beide aus Sicht des Verkäufers: Credit positiv.

Welt wie tests/test_api_ketten_unrealisiert.py (EUR, Multiplikator 10).
OOO: SELL 1 zu 3.00 → Prämie bei Eröffnung 3.00 · 1 · 10 = 30.00; Marktwert
  −20.00 → aktuell 20.00. Probe: 30.00 − 20.00 − 2.00 Kommission = 8.00 =
  unrealisiert (siehe dort).
PPP (geschlossen): kein Wert. QQQ (offen, kein Bestand): Prämie bei Eröffnung
  ist bekannt (2.00 · 1 · 10 = 20.00), aktuell nicht (kein Marktwert) → null.
Schrittansicht: derselbe Wert steht am offenen Glied.
"""

from decimal import Decimal

from test_api_ketten_unrealisiert import _je_basiswert, klient  # noqa: F401


def test_praemie_der_offenen_kette(klient):  # noqa: F811
    z = _je_basiswert(klient)["OOO"]
    assert Decimal(z["praemie_offen_eur"]) == Decimal("30.00")
    assert Decimal(z["praemie_aktuell_eur"]) == Decimal("20.00")


def test_geschlossen_und_ohne_bestand(klient):  # noqa: F811
    je = _je_basiswert(klient)
    assert je["PPP"]["praemie_offen_eur"] is None and je["PPP"]["praemie_aktuell_eur"] is None
    assert Decimal(je["QQQ"]["praemie_offen_eur"]) == Decimal("20.00")
    assert je["QQQ"]["praemie_aktuell_eur"] is None


def test_schrittansicht(klient):  # noqa: F811
    zeilen = klient.get("/ketten", params={"basiswert": "OOO", "ansicht": "schritte"}
                        ).json()["treffer"]
    assert len(zeilen) == 1
    assert Decimal(zeilen[0]["praemie_offen_eur"]) == Decimal("30.00")
