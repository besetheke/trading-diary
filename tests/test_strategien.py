"""Abnahmetests für AP-06sc: Strategie-Scorecard (`analytics/strategien.py`).
Vertrag: auftraege/AP-06sc.md. Geschrieben durch das starke Modell — für die
Umsetzung unveränderlich. Alle Erwartungen von Hand gerechnet (Regel 8).

Je Strategie über die **geschlossenen** Positionen (Kontosicht, netto EUR
wirtschaftlich, wie Equity und Positionsliste):

Strategie A — drei Positionen, geschlossen 03.01., 05.01., 08.01.2026:
  +100.00 (1 Tag gehalten), −40.00 (2 Tage, mit Zuteilung), +60.00 (3 Tage)
  Anzahl 3, Gewinner 2, Verlierer 1, Trefferquote 2/3 = 0.6667
  Summe 120.00, Ø je Position 40.00, Ø Gewinn 80.00, Ø Verlust −40.00
  Profit-Faktor 160/40 = 4.0000, größter Gewinn 100.00, größter Verlust −40.00
  Kurve nach Schließung: 100, 60, 120 → max. Drawdown −40.00
  Zuteilungsquote 1/3 = 0.3333, Ø Haltedauer (1+2+3)/3 = 2.0 Tage
Strategie B — eine Position −10.00 (12 Stunden = 0.5 Tage):
  Trefferquote 0.0000, Profit-Faktor 0.0000 (keine Gewinne), Drawdown −10.00
Ohne Strategie — +5.00 und eine Position ohne Wechselkurs (netto_eur None):
  gezählt 1, kurs_fehlt 1, Profit-Faktor None (keine Verluste)
Offene Positionen zählen nur in `offen` (A: 1).
Sortierung: nach Summe absteigend — A (120), ohne (5), B (−10).
"""

from datetime import datetime
from decimal import Decimal as D

from analytics.strategien import strategie_auswertung


def _p(strategie, auf, zu, netto, zuteilung=False, chain_id=0):
    return dict(chain_id=chain_id, strategie=strategie, eroeffnet_am=auf, beendet_am=zu,
                netto_eur=None if netto is None else D(netto), zuteilung=zuteilung)


POSITIONEN = [
    _p("A", datetime(2026, 1, 2, 10), datetime(2026, 1, 3, 10), "100.00", chain_id=1),
    _p("A", datetime(2026, 1, 3, 10), datetime(2026, 1, 5, 10), "-40.00", True, chain_id=2),
    _p("A", datetime(2026, 1, 5, 10), datetime(2026, 1, 8, 10), "60.00", chain_id=3),
    _p("A", datetime(2026, 1, 9, 10), None, None, chain_id=4),
    _p("B", datetime(2026, 1, 4, 10), datetime(2026, 1, 4, 22), "-10.00", chain_id=5),
    _p(None, datetime(2026, 1, 2, 10), datetime(2026, 1, 6, 10), "5.00", chain_id=6),
    _p(None, datetime(2026, 1, 2, 10), datetime(2026, 1, 7, 10), None, chain_id=7),
]


def _je_name(ergebnis):
    return {z.strategie: z for z in ergebnis}


def test_reihenfolge_nach_summe():
    assert [z.strategie for z in strategie_auswertung(POSITIONEN)] == ["A", None, "B"]


def test_strategie_a():
    a = _je_name(strategie_auswertung(POSITIONEN))["A"]
    assert (a.anzahl, a.offen, a.gewinner, a.verlierer, a.kurs_fehlt) == (3, 1, 2, 1, 0)
    assert a.trefferquote == D("0.6667")
    assert (a.summe_eur, a.durchschnitt_eur) == (D("120.00"), D("40.00"))
    assert (a.durchschnitt_gewinn_eur, a.durchschnitt_verlust_eur) == (D("80.00"), D("-40.00"))
    assert a.profit_faktor == D("4.0000")
    assert (a.groesster_gewinn_eur, a.groesster_verlust_eur) == (D("100.00"), D("-40.00"))
    assert a.max_drawdown_eur == D("-40.00")
    assert a.zuteilungsquote == D("0.3333")
    assert a.haltedauer_tage == D("2.0")
    assert (a.erste_schliessung, a.letzte_schliessung) == (
        datetime(2026, 1, 3, 10), datetime(2026, 1, 8, 10))


def test_strategie_b():
    b = _je_name(strategie_auswertung(POSITIONEN))["B"]
    assert (b.anzahl, b.trefferquote, b.profit_faktor) == (1, D("0.0000"), D("0.0000"))
    assert b.max_drawdown_eur == D("-10.00")
    assert b.haltedauer_tage == D("0.5")


def test_ohne_strategie():
    o = _je_name(strategie_auswertung(POSITIONEN))[None]
    assert (o.anzahl, o.kurs_fehlt, o.summe_eur) == (1, 1, D("5.00"))
    assert o.profit_faktor is None
    assert o.max_drawdown_eur == D("0")


def test_leer():
    assert strategie_auswertung([]) == []
