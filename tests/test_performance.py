"""Abnahmetests für AP-08p: Wertentwicklung des Kontos (zeitgewichtet), Drawdown in
Prozent vom Höchststand, Wochen- und Monatswerte. Vertrag im Modulkopf von
analytics/performance.py.

Einzahlungen verfälschen einen Drawdown auf den Kontowert (eine Einzahlung
sieht aus wie ein Gewinn). Deshalb ein zeitgewichteter Index: Tagesrendite
r_t = (Kontowert_t − Einzahlungen_t) / Kontowert_{t−1}, Index = Π (1 + r).
Drawdown = Index / bisheriges Hoch − 1.

Welt (frei erfunden, von Hand gerechnet):
  Do 29.01.2026  Kontowert 1000, Einzahlungen kumuliert 1000
  Fr 30.01.2026  Kontowert 1200, Einzahlungen kumuliert 1200 (+200 an diesem Tag)
                 r = (1200 − 200) / 1000 = 1        → Index 1
  Mo 02.02.2026  Kontowert 1080                     → r = 0.9, Index 0.9, DD −0.1
  Di 03.02.2026  Kontowert 1188                     → r = 1.1, Index 0.99, DD −0.01
  Gewinn laut IB je Tag (Veränderung ohne Einzahlungen): 0, 0, −120, +108.
  Realisiert (Journal): +50.00 am 30.01., −20.00 am 03.02.

Wochen (ISO): 2026-W05 (26.01.–01.02.): Gewinn 0, realisiert 50, Rendite 0;
2026-W06 (02.02.–08.02.): Gewinn −12, realisiert −20, Rendite 0.9·1.1 − 1 = −0.01.
Monate: 2026-01 wie W05, 2026-02 wie W06.
"""

from datetime import date
from decimal import Decimal as D

from analytics.performance import performance_auswertung

NAV = [
    dict(datum=date(2026, 1, 29), gesamt=D("1000"), einzahlungen_kumuliert=D("1000")),
    dict(datum=date(2026, 1, 30), gesamt=D("1200"), einzahlungen_kumuliert=D("1200")),
    dict(datum=date(2026, 2, 2), gesamt=D("1080"), einzahlungen_kumuliert=D("1200")),
    dict(datum=date(2026, 2, 3), gesamt=D("1188"), einzahlungen_kumuliert=D("1200")),
]
EQUITY = [
    dict(datum=date(2026, 1, 30), netto_eur=D("50.00")),
    dict(datum=date(2026, 2, 3), netto_eur=D("-20.00")),
]


def test_index_und_drawdown_je_tag():
    e = performance_auswertung(NAV, EQUITY)
    assert [(t.datum, t.index, t.drawdown_quote) for t in e.tage] == [
        (date(2026, 1, 29), D("1"), D("0")),
        (date(2026, 1, 30), D("1"), D("0")),
        (date(2026, 2, 2), D("0.9"), D("-0.1")),
        (date(2026, 2, 3), D("0.99"), D("-0.01")),
    ]


def test_einzahlung_ist_kein_gewinn():
    """Der Kontowert steigt am 30.01. um 200 — alles Einzahlung, Rendite 0."""
    e = performance_auswertung(NAV, EQUITY)
    assert e.tage[1].index == e.tage[0].index


def test_maximaler_drawdown():
    e = performance_auswertung(NAV, EQUITY)
    assert e.max_drawdown_quote == D("-0.1")
    assert e.max_drawdown_datum == date(2026, 2, 2)


def test_wochen():
    e = performance_auswertung(NAV, EQUITY)
    assert [(w.schluessel, w.beginn, w.ende, w.gewinn_ib, w.realisiert, w.rendite_quote)
            for w in e.wochen] == [
        ("2026-W05", date(2026, 1, 26), date(2026, 2, 1), D("0"), D("50.00"), D("0")),
        ("2026-W06", date(2026, 2, 2), date(2026, 2, 8), D("-12"), D("-20.00"), D("-0.01")),
    ]


def test_monate():
    e = performance_auswertung(NAV, EQUITY)
    assert [(m.schluessel, m.gewinn_ib, m.realisiert, m.rendite_quote) for m in e.monate] == [
        ("2026-01", D("0"), D("50.00"), D("0")),
        ("2026-02", D("-12"), D("-20.00"), D("-0.01")),
    ]


def test_zeitraum_beginnt_beim_vortag():
    """Ab 02.02.: Basis ist der Kontowert vom 30.01. (Index 1), die Bewegung in den
    ersten Tag zählt mit — gleich wie beim Gewinn laut IB."""
    e = performance_auswertung(NAV, EQUITY, von=date(2026, 2, 2))
    assert [(t.datum, t.index, t.drawdown_quote) for t in e.tage] == [
        (date(2026, 2, 2), D("0.9"), D("-0.1")),
        (date(2026, 2, 3), D("0.99"), D("-0.01")),
    ]
    assert [(w.schluessel, w.gewinn_ib, w.realisiert) for w in e.wochen] == [
        ("2026-W06", D("-12"), D("-20.00"))]


def test_leer():
    e = performance_auswertung([], [])
    assert e.tage == () and e.wochen == () and e.monate == ()
    assert e.max_drawdown_quote == 0 and e.max_drawdown_datum is None
