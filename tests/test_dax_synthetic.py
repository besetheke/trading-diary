# ruff: noqa: E501
"""DAX Synthetic erkennen (Nutzernotiz 19.10.2026), von Hand gerechnet.

Welt (alles DAX, EUR):
  F1  Long-Future 2.10.2025 → 15.12.2025,  brutto +1.000, Kommission −5
  F2  Long-Future 15.12.2025, offen
  P1  Schutz-Put gekauft 2.10.2025, Verfall 18.9.2026 (351 Tage ≥ 180), geschlossen 20.12.2025, brutto −300, Kommission −3
  C1  Short-Call verkauft 6.10.2025, Verfall 10.10.2025 (4 Tage), geschlossen 10.10.2025, brutto +120, Kommission −2
  C2  Short-Call verkauft 13.10.2025, Verfall 17.10.2025, geschlossen 17.10.2025, brutto −40, Kommission −2
  C3  Short-Call verkauft 5.1.2026, Verfall 9.1.2026, geschlossen 9.1.2026, brutto +60, Kommission −2   (nach Ende von P1)
  X1  Verkaufter Put 100 Tage (kein Baustein), X2 gekaufter Call (kein Baustein)
Erwartung je Baustein (Netto = brutto + Kommission):
  future:      F1 995, F2 0 (offen)           → Summe brutto 1.000, Kommission −5, Anzahl 2, offen 1
  schutz_put:  −303                            → Anzahl 1, offen 0
  short_call:  C1 118, C2 −42, C3 58           → brutto 140, Kommission −6, Anzahl 3
Einheit P1 (2.10.2025 – 20.12.2025): F1 geschlossen 15.12. (995), C1 10.10. (118), C2 17.10. (−42), C3 liegt nach dem 20.12. → nicht dabei,
  Put selbst geschlossen am 20.12. (−303): Ergebnis future 995, short_call 76, schutz_put −303.
Aktiv: Future und Schutz-Put gleichzeitig ab 2.10.2025; Ende: F2 offen, aber P1 geschlossen und kein weiterer Put offen → bis 20.12.2025.
"""
from datetime import date, datetime
from decimal import Decimal as D

from analytics.dax_synthetic import dax_synthetic_auswertung, klassifiziere


def leg(i, ac, right, side, auf, bis, expiry=None, strike=None, brutto=None, komm=None):
    return dict(leg_id=i, asset_class=ac, right=right, side=side, eroeffnet=auf, beendet=bis, expiry=expiry,
                strike=D(strike) if strike else None, brutto=D(brutto) if brutto is not None else None,
                kommission=D(komm) if komm is not None else None)


T = datetime
LEGS = [
    leg(1, "FUT", None, "BUY", T(2025, 10, 2, 10), T(2025, 12, 15, 10), date(2025, 12, 19), None, "1000", "-5"),
    leg(2, "FUT", None, "BUY", T(2025, 12, 15, 10), None, date(2026, 3, 20)),
    leg(3, "OPT", "P", "BUY", T(2025, 10, 2, 10), T(2025, 12, 20, 10), date(2026, 9, 18), "24400", "-300", "-3"),
    leg(4, "OPT", "C", "SELL", T(2025, 10, 6, 10), T(2025, 10, 10, 10), date(2025, 10, 10), "24500", "120", "-2"),
    leg(5, "OPT", "C", "SELL", T(2025, 10, 13, 10), T(2025, 10, 17, 10), date(2025, 10, 17), "24500", "-40", "-2"),
    leg(6, "OPT", "C", "SELL", T(2026, 1, 5, 10), T(2026, 1, 9, 10), date(2026, 1, 9), "25000", "60", "-2"),
    leg(7, "OPT", "P", "SELL", T(2025, 10, 6, 10), T(2025, 10, 7, 10), date(2026, 1, 16), "24000", "10", "-1"),
    leg(8, "OPT", "C", "BUY", T(2025, 10, 6, 10), T(2025, 10, 7, 10), date(2025, 10, 10), "25000", "5", "-1"),
]
STICHTAG = T(2026, 10, 19, 12)


def test_bausteine_und_summen():
    erg = dax_synthetic_auswertung(LEGS, STICHTAG)
    b = {x.art: x for x in erg.bausteine}
    assert (b["future"].anzahl, b["future"].offen, b["future"].brutto, b["future"].kommission) == (2, 1, D("1000"), D("-5"))
    assert (b["schutz_put"].anzahl, b["schutz_put"].netto) == (1, D("-303"))
    assert (b["short_call"].anzahl, b["short_call"].brutto, b["short_call"].kommission) == (3, D("140"), D("-6"))
    assert erg.sonstige == 2


def test_einheit_des_schutzputs():
    (e,) = dax_synthetic_auswertung(LEGS, STICHTAG).einheiten
    assert (e.put_leg_id, e.strike, e.beendet) == (3, D("24400"), T(2025, 12, 20, 10))
    assert e.ergebnis == {"future": D("995"), "schutz_put": D("-303"), "short_call": D("76")}


def test_aktiver_zeitraum():
    erg = dax_synthetic_auswertung(LEGS, STICHTAG)
    assert erg.aktiv_von == T(2025, 10, 2, 10)
    assert erg.aktiv_bis == T(2025, 12, 20, 10)       # F2 offen, aber kein Schutz-Put mehr offen


def test_offen_wenn_future_und_put_offen():
    legs = LEGS + [leg(9, "OPT", "P", "BUY", T(2026, 8, 13, 10), None, date(2027, 12, 17), "24400")]
    erg = dax_synthetic_auswertung(legs, STICHTAG)
    assert erg.aktiv_bis is None


def test_klassifizierung_grenzen():
    # genau 180 Tage zählt als Schutz-Put, 179 nicht; Short-Call bis 14 Tage, 15 nicht
    assert klassifiziere(leg(1, "OPT", "P", "BUY", T(2026, 1, 1), None, date(2026, 6, 30))) == "schutz_put"       # 180
    assert klassifiziere(leg(1, "OPT", "P", "BUY", T(2026, 1, 1), None, date(2026, 6, 29))) is None               # 179
    assert klassifiziere(leg(1, "OPT", "C", "SELL", T(2026, 1, 1), None, date(2026, 1, 15))) == "short_call"      # 14
    assert klassifiziere(leg(1, "OPT", "C", "SELL", T(2026, 1, 1), None, date(2026, 1, 16))) is None              # 15
    assert klassifiziere(leg(1, "FUT", None, "SELL", T(2026, 1, 1), None, date(2026, 3, 20))) is None            # Short-Future


def test_api_liefert_die_auswertung(migrated_db):
    import pytest
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from fixtures_rebuild import befuelle

    from api.app import erzeuge_app
    from journal.rebuild import rebuild
    befuelle(migrated_db)
    rebuild(migrated_db)
    d = TestClient(erzeuge_app(migrated_db, mit_journal=True)).get("/dax-synthetic-auswertung").json()
    assert d["erkennung"] == "heuristik" and [b["art"] for b in d["bausteine"]] == ["future", "schutz_put", "short_call"]
    assert d["regeln"] == {"schutz_put_min_dte": 180, "short_call_max_dte": 14}
