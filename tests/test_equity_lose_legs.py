"""Abnahmetests für AP-06i: Ergebnis loser Legs in der Equity-Kurve (OF-78).

Vertrag: auftraege/AP-06i.md. Geschrieben durch das starke Modell —
für die Umsetzung unveränderlich. Jeder Erwartungswert ist von Hand
gerechnet (Regel 8).

Lose Legs sind abgeschlossene Legs der Kontosicht ohne Struktur
(``structure_id`` None), etwa Aktien aus einer Zuteilung, die die
Kettenbildung nicht fortsetzen konnte. Ihr Ergebnis gehört ins Geld
(Plan §5: Kontosicht ist für Geld maßgeblich) — bisher fehlte es.

Testwelt (reine Funktion):

  S1  Struktur, EUR, Mult 10: SELL 10.00 am 2026-01-02, BUY 4.00 am
      2026-01-03, Kommission -2.00 je Ausführung
      → (10 - 4) × 10 - 4 = 56.00, Tag 2026-01-03.
  L1  loses Aktien-Leg, Mult 1, Kurs 0.9: BUY 100 zu 50.00 am 2026-01-03,
      SELL 100 zu 45.00 am 2026-01-05, Kommission -1.00 je Ausführung
      → ((45 - 50) × 100 - 2) × 0.9 = -502 × 0.9 = -451.80, Tag 2026-01-05.
  L2  loses Leg, Schließung ohne buchungskurs am 2026-01-06
      → kein Betrag, aber als Mangel sichtbar.
  L3  loses Leg, offen → geht nirgends ein.
  L4  loses Leg, Stufe B, Mult 1, Kurs 1: BUY 10 zu 20.00 am 2026-02-01,
      SELL 10 zu 23.00 am 2026-02-02, Kommission -1.00 je Ausführung
      → 30 - 2 = 28.00, Tag 2026-02-02.

Kurve: 01-03 +56.00 (kum 56.00) | 01-05 -451.80 (kum -395.80, DD -451.80) |
01-06 0.00 (kum -395.80, DD -451.80, ein Mangel) | 02-02 +28.00
(kum -367.80, DD -423.80). Max. Drawdown -451.80 am 2026-01-05.
"""

from datetime import date
from datetime import datetime as dt
from decimal import Decimal as D

from analytics.equity import EquityMonat, EquityTag, equity_auswertung


def _ausf(exec_id, conid, side, preis, menge, zeit, kurs, kommission, stufe="A"):
    return dict(
        exec_id=exec_id, conid=conid, side=side, preis=D(preis), menge=D(menge),
        waehrung="EUR", kommission=D(kommission), kommission_waehrung="EUR",
        buchungskurs=kurs, handelszeit=zeit, qualitaetsstufe=stufe,
    )


def _welt():
    ketten = [dict(chain_id=1, sicht="konto", underlying="SPX", asset_class="OPT",
                   anzahl_rolls=0, beendet_am=dt(2026, 1, 3, 10, 0))]
    strukturen = [dict(structure_id=10, chain_id=1, typ="Single", waehrung="EUR",
                       brutto_pnl=D("60.00"), kommission=D("-4.00"),
                       netto_pnl=D("56.00"), geschlossen_am=dt(2026, 1, 3, 10, 0))]
    glieder = [dict(structure_id=10, chain_id=1, sicht="konto", sequenz=1,
                    verknuepfungstyp="open", erkennung="auto")]
    instrumente = [
        dict(conid=100, multiplikator=D("10")),
        dict(conid=200, multiplikator=D("1")),
        dict(conid=300, multiplikator=D("1")),
        dict(conid=400, multiplikator=D("1")),
        dict(conid=500, multiplikator=D("1")),
    ]
    ausfuehrungen = [
        _ausf("S1o", 100, "SELL", "10.00", "1", dt(2026, 1, 2, 10, 0), D("1"), "-2.00"),
        _ausf("S1c", 100, "BUY", "4.00", "1", dt(2026, 1, 3, 10, 0), D("1"), "-2.00"),
        _ausf("L1o", 200, "BUY", "50.00", "100", dt(2026, 1, 3, 10, 0), D("0.9"), "-1.00"),
        _ausf("L1c", 200, "SELL", "45.00", "100", dt(2026, 1, 5, 15, 0), D("0.9"), "-1.00"),
        _ausf("L2o", 300, "BUY", "30.00", "10", dt(2026, 1, 4, 10, 0), D("1"), "-1.00"),
        _ausf("L2c", 300, "SELL", "31.00", "10", dt(2026, 1, 6, 10, 0), None, "-1.00"),
        _ausf("L3o", 400, "BUY", "70.00", "10", dt(2026, 1, 4, 10, 0), D("1"), "-1.00"),
        _ausf("L4o", 500, "BUY", "20.00", "10", dt(2026, 2, 1, 10, 0), D("1"), "-1.00", "B"),
        _ausf("L4c", 500, "SELL", "23.00", "10", dt(2026, 2, 2, 10, 0), D("1"), "-1.00", "B"),
    ]
    legs = [
        dict(structure_id=10, conid=100, open_exec_id="S1o", close_exec_id="S1c", menge=D("1")),
        dict(structure_id=None, conid=200, open_exec_id="L1o", close_exec_id="L1c",
             menge=D("100")),
        dict(structure_id=None, conid=300, open_exec_id="L2o", close_exec_id="L2c",
             menge=D("10")),
        dict(structure_id=None, conid=400, open_exec_id="L3o", close_exec_id=None,
             menge=D("10")),
        dict(structure_id=None, conid=500, open_exec_id="L4o", close_exec_id="L4c",
             menge=D("10")),
    ]
    return ketten, strukturen, glieder, legs, ausfuehrungen, instrumente


def _auswertung(**kwargs):
    return equity_auswertung(*_welt(), sicht="konto", **kwargs)


def test_tagesreihe_mit_losen_legs():
    e = _auswertung()
    assert e.tage == (
        EquityTag(datum=date(2026, 1, 3), netto_eur=D("56.00"), kumuliert_eur=D("56.00"),
                  drawdown_eur=D("0.00"), anzahl_strukturen=1,
                  anzahl_strukturen_kurs_fehlt=0, anzahl_lose_legs=0,
                  anzahl_lose_legs_kurs_fehlt=0),
        EquityTag(datum=date(2026, 1, 5), netto_eur=D("-451.80"),
                  kumuliert_eur=D("-395.80"), drawdown_eur=D("-451.80"),
                  anzahl_strukturen=0, anzahl_strukturen_kurs_fehlt=0,
                  anzahl_lose_legs=1, anzahl_lose_legs_kurs_fehlt=0),
        EquityTag(datum=date(2026, 1, 6), netto_eur=D("0.00"), kumuliert_eur=D("-395.80"),
                  drawdown_eur=D("-451.80"), anzahl_strukturen=0,
                  anzahl_strukturen_kurs_fehlt=0, anzahl_lose_legs=0,
                  anzahl_lose_legs_kurs_fehlt=1),
        EquityTag(datum=date(2026, 2, 2), netto_eur=D("28.00"), kumuliert_eur=D("-367.80"),
                  drawdown_eur=D("-423.80"), anzahl_strukturen=0,
                  anzahl_strukturen_kurs_fehlt=0, anzahl_lose_legs=1,
                  anzahl_lose_legs_kurs_fehlt=0),
    )


def test_max_drawdown_mit_losen_legs():
    e = _auswertung()
    assert e.max_drawdown_eur == D("-451.80")
    assert e.max_drawdown_datum == date(2026, 1, 5)


def test_monate_mit_losen_legs():
    """Summe enthält die losen Legs; Durchschnitt und Trefferquote bleiben
    Kennzahlen über Strukturen (I3)."""
    e = _auswertung()
    assert e.monate == (
        EquityMonat(monat="2026-01", anzahl_strukturen=1, summe_netto_eur=D("-395.80"),
                    durchschnitt_netto_eur=D("56.00"), trefferquote=D("1.0000"),
                    anzahl_strukturen_kurs_fehlt=0, lose_legs_eur=D("-451.80"),
                    anzahl_lose_legs=1, anzahl_lose_legs_kurs_fehlt=1),
        EquityMonat(monat="2026-02", anzahl_strukturen=0, summe_netto_eur=D("28.00"),
                    durchschnitt_netto_eur=None, trefferquote=None,
                    anzahl_strukturen_kurs_fehlt=0, lose_legs_eur=D("28.00"),
                    anzahl_lose_legs=1, anzahl_lose_legs_kurs_fehlt=0),
    )


def test_nur_stufe_a_laesst_lose_legs_schlechterer_stufe_weg():
    """L4 trägt Stufe B: fehlt mit dem Filter ganz, auch der Tag 02-02."""
    e = _auswertung(nur_qualitaetsstufe_a=True)
    assert [t.datum for t in e.tage] == [date(2026, 1, 3), date(2026, 1, 5), date(2026, 1, 6)]
    assert [m.monat for m in e.monate] == ["2026-01"]


def test_zeitraum_gilt_fuer_lose_legs():
    """Ab 2026-01-04: S1 (01-03) fällt heraus, die Kurve beginnt bei 0."""
    e = _auswertung(von=date(2026, 1, 4))
    assert [(t.datum, t.netto_eur, t.kumuliert_eur) for t in e.tage] == [
        (date(2026, 1, 5), D("-451.80"), D("-451.80")),
        (date(2026, 1, 6), D("0.00"), D("-451.80")),
        (date(2026, 2, 2), D("28.00"), D("-423.80")),
    ]
    assert e.max_drawdown_eur == D("-451.80")


def test_ohne_lose_legs_bleiben_die_neuen_felder_null():
    """Nur S1: die neuen Felder stehen auf 0 (Rückwärtsverträglichkeit)."""
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = _welt()
    legs = [leg for leg in legs if leg["structure_id"] is not None]
    e = equity_auswertung(ketten, strukturen, glieder, legs, ausfuehrungen, instrumente,
                          sicht="konto")
    assert len(e.tage) == 1
    assert e.tage[0].anzahl_lose_legs == 0
    assert e.monate[0].lose_legs_eur == D("0.00")
