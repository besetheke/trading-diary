"""Abnahmetests für AP-06sc: `GET /strategien`. Welt wie tests/test_api_filter.py:
AAA +56.00 (03.01.2026) und CCC +52.00 € (01.03.) mit Strategie „IC1", BBB
−14.00 (05.02.) ohne Strategie, DDD offen ohne Strategie.

Von Hand: IC1 — 2 Positionen, Summe 108.00, Trefferquote 1.0000, kein Verlust
→ Profit-Faktor null, Drawdown 0. Ohne Strategie — 1 geschlossen (−14.00),
1 offen, Trefferquote 0.0000, Profit-Faktor 0.0000, Drawdown −14.00.
Überleitung: realisiert gesamt 94.00 = 108.00 − 14.00 + 0 (ohne Position)
+ 0 (Abgrenzung; DDD hat keine geschlossenen Teile).
Zeitraum bis 31.01.2026: nur AAA (56.00); BBB fällt heraus, DDD (eröffnet
05.03.) ebenfalls.
"""

from decimal import Decimal

from test_api_filter import klient  # noqa: F401  (Fixture)


def test_scorecard(klient):  # noqa: F811
    d = klient.get("/strategien").json()
    assert [z["strategie"] for z in d["zeilen"]] == ["IC1", None]
    ic1, ohne = d["zeilen"]
    assert (ic1["anzahl"], Decimal(ic1["summe_eur"]), ic1["trefferquote"]) == (
        2, Decimal("108.00"), "1.0000")
    assert ic1["profit_faktor"] is None and Decimal(ic1["max_drawdown_eur"]) == 0
    assert (ohne["anzahl"], ohne["offen"], Decimal(ohne["summe_eur"])) == (1, 1, Decimal("-14.00"))
    assert (ohne["trefferquote"], ohne["profit_faktor"]) == ("0.0000", "0.0000")
    assert Decimal(ohne["max_drawdown_eur"]) == Decimal("-14.00")


def test_zeitraum(klient):  # noqa: F811
    d = klient.get("/strategien", params={"bis": "2026-01-31"}).json()
    assert [(z["strategie"], z["anzahl"], z["offen"]) for z in d["zeilen"]] == [("IC1", 1, 0)]
    assert Decimal(d["zeilen"][0]["summe_eur"]) == Decimal("56.00")


def test_von_nach_bis_ist_422(klient):  # noqa: F811
    assert klient.get("/strategien", params={"von": "2026-02-01", "bis": "2026-01-01"}
                      ).status_code == 422


def test_ueberleitung(klient):  # noqa: F811
    d = klient.get("/strategien").json()
    assert Decimal(d["summe_strategien_eur"]) == Decimal("94.00")
    assert Decimal(d["realisiert_gesamt_eur"]) == Decimal("94.00")
    assert Decimal(d["ohne_position_eur"]) == 0
    assert Decimal(d["abgrenzung_eur"]) == 0
