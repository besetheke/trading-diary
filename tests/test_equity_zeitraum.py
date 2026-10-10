"""Abnahmetests für AP-08f2 (Zeitraum an der Equity-Kurve, Z2/Z4 aus
auftraege/AP-08f.md). Unveränderlich; Erwartungswerte von Hand gerechnet.

Testwelt wie tests/test_equity.py (Kontosicht, EUR, Kurs 1, Multiplikator 10,
Kommission -4.00 je Struktur), geschlossen am:

  2026-01-02  K1   96.00
  2026-01-03  K2   46.00
  2026-01-04  K6   Kursmangel
  2026-01-05  K3  -84.00
  2026-01-06  K4  -44.00
  2026-02-10  K5  196.00

Z2: Eine Struktur gehört zum Zeitraum, wenn ihr Schließungsdatum darin liegt
(beide Enden einschließlich). Z4: Die Equity im Zeitraum beginnt bei 0, das
laufende Hoch ebenfalls — Drawdown nur innerhalb des Zeitraums.

Zeitraum 2026-01-03 bis 2026-01-06:
  01-03  +46  kumuliert  46  (Hoch 46)  DD    0
  01-04    0  kumuliert  46  (Kursmangel)  DD 0
  01-05  -84  kumuliert -38             DD  -84
  01-06  -44  kumuliert -82             DD -128   <- Minimum
  Januar: 3 Strukturen, Summe 46-84-44 = -82.00, Durchschnitt -82/3 =
  -27.333.. -> -27.33, Trefferquote 1/3 = 0.3333, Kursmangel 1.
"""

from datetime import date, timedelta
from datetime import datetime as dt
from decimal import Decimal as D

import pytest

from analytics.equity import EquityMonat, EquityTag, equity_auswertung

# (chain_id, geschlossen_am, preis_open, preis_close, kursmangel)
_STRUKTUREN = [
    (1, date(2026, 1, 2), "10", "0", False),
    (2, date(2026, 1, 3), "9", "4", False),
    (3, date(2026, 1, 5), "2", "10", False),
    (4, date(2026, 1, 6), "5", "9", False),
    (5, date(2026, 2, 10), "24", "4", False),
    (6, date(2026, 1, 4), "10", "9", True),
]


def _ausf(exec_id, conid, side, preis, zeit, kurs):
    return dict(
        exec_id=exec_id, conid=conid, side=side, preis=D(preis), menge=1,
        waehrung="EUR", kommission=D("-2.00"), kommission_waehrung="EUR",
        buchungskurs=kurs, handelszeit=zeit, qualitaetsstufe="A",
    )


def _welt():
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = [], [], [], [], [], []
    for chain_id, schluss, po, pc, kursmangel in _STRUKTUREN:
        structure_id, conid = chain_id * 10, chain_id * 100
        ende = dt(schluss.year, schluss.month, schluss.day, 10, 0)
        beginn = ende - timedelta(days=1)
        ausfuehrungen.append(_ausf(f"O{structure_id}", conid, "SELL", po, beginn, D("1")))
        ausfuehrungen.append(_ausf(f"C{structure_id}", conid, "BUY", pc, ende,
                                   None if kursmangel else D("1")))
        brutto = (D(po) - D(pc)) * 10
        strukturen.append(dict(structure_id=structure_id, chain_id=chain_id, typ="Single",
                               waehrung="EUR", brutto_pnl=brutto, kommission=D("-4.00"),
                               netto_pnl=brutto - 4, geschlossen_am=ende))
        glieder.append(dict(structure_id=structure_id, chain_id=chain_id, sicht="konto",
                            sequenz=1, verknuepfungstyp="open", erkennung="auto"))
        legs.append(dict(leg_id=structure_id, structure_id=structure_id, conid=conid,
                         open_exec_id=f"O{structure_id}", close_exec_id=f"C{structure_id}",
                         menge=1, offen_ja_nein=False))
        instrumente.append(dict(conid=conid, multiplikator=D("10")))
        ketten.append(dict(chain_id=chain_id, sicht="konto", underlying="SPX",
                           asset_class="OPT", anzahl_rolls=0, beendet_am=ende))
    return ketten, strukturen, glieder, legs, ausfuehrungen, instrumente


def _auswertung(von=None, bis=None):
    return equity_auswertung(*_welt(), sicht="konto", von=von, bis=bis)


def test_ohne_zeitraum_wie_bisher():
    """Ohne von/bis ändert sich nichts gegenüber AP-06e: sechs Tage, Stand
    210.00, maximaler Drawdown -128.00."""
    e = _auswertung()
    assert len(e.tage) == 6
    assert e.tage[-1].kumuliert_eur == D("210.00")
    assert e.max_drawdown_eur == D("-128.00")


def test_zeitraum_beginnt_bei_null():
    e = _auswertung(von=date(2026, 1, 3), bis=date(2026, 1, 6))
    assert e.tage == (
        EquityTag(datum=date(2026, 1, 3), netto_eur=D("46.00"), kumuliert_eur=D("46.00"),
                  drawdown_eur=D("0.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0),
        EquityTag(datum=date(2026, 1, 4), netto_eur=D("0.00"), kumuliert_eur=D("46.00"),
                  drawdown_eur=D("0.00"), anzahl_strukturen=0, anzahl_strukturen_kurs_fehlt=1),
        EquityTag(datum=date(2026, 1, 5), netto_eur=D("-84.00"), kumuliert_eur=D("-38.00"),
                  drawdown_eur=D("-84.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0),
        EquityTag(datum=date(2026, 1, 6), netto_eur=D("-44.00"), kumuliert_eur=D("-82.00"),
                  drawdown_eur=D("-128.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0),
    )
    assert e.max_drawdown_eur == D("-128.00")
    assert e.max_drawdown_datum == date(2026, 1, 6)
    assert e.monate == (
        EquityMonat(monat="2026-01", anzahl_strukturen=3, summe_netto_eur=D("-82.00"),
                    durchschnitt_netto_eur=D("-27.33"), trefferquote=D("0.3333"),
                    anzahl_strukturen_kurs_fehlt=1),
    )


def test_nur_von():
    e = _auswertung(von=date(2026, 2, 1))
    assert [(t.datum, t.kumuliert_eur) for t in e.tage] == [(date(2026, 2, 10), D("196.00"))]
    assert e.max_drawdown_eur == D("0.00")
    assert e.max_drawdown_datum is None


def test_nur_bis_einschliesslich():
    e = _auswertung(bis=date(2026, 1, 2))
    assert [(t.datum, t.kumuliert_eur) for t in e.tage] == [(date(2026, 1, 2), D("96.00"))]


def test_leerer_zeitraum():
    e = _auswertung(von=date(2026, 3, 1), bis=date(2026, 3, 31))
    assert e.tage == ()
    assert e.monate == ()
    assert e.max_drawdown_eur == D("0.00")
    assert e.max_drawdown_datum is None


def test_von_nach_bis_ist_fehler():
    with pytest.raises(ValueError, match="von"):
        _auswertung(von=date(2026, 2, 1), bis=date(2026, 1, 1))
