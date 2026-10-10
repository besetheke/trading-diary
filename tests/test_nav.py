"""Abnahmetests für AP-06h (Kontowert-Kurve). Vertrag: auftraege/AP-06h.md.
Unveränderlich; Erwartungswerte von Hand gerechnet.

Kontowert je Tag (IB, EUR): 01-02 1000, 01-03 1100, 01-06 1300, 01-07 1250.
Einzahlungen (Cash-Buchungen Deposits/Withdrawals × Kurs): 01-02 +1000,
01-06 +200; eine Dividende (kein Einzahlungsposten) am 01-03 ändert nichts.

Gewinn laut IB = Kontowert − kumulierte Einzahlungen bis einschließlich Tag:
  01-02  1000 − 1000 =   0
  01-03  1100 − 1000 = 100
  01-06  1300 − 1200 = 100
  01-07  1250 − 1200 =  50
Zeitraum 01-03 bis 01-06: Tage 01-03 und 01-06 mit absoluten Werten
(Bestand, wie AP-06g K3); Anfang = Kontowert am letzten Tag davor (1000).
"""

from datetime import date
from datetime import datetime as dt
from decimal import Decimal as D

import pytest

from analytics.nav import NavTag, nav_auswertung


def _nav(tag, gesamt, cash="0", aktien="0", optionen="0"):
    return dict(datum=tag, gesamt=D(gesamt), cash=D(cash), aktien=D(aktien),
                optionen=D(optionen), rohstoffe=None)


_NAV = [
    _nav(date(2026, 1, 2), "1000", cash="1000"),
    _nav(date(2026, 1, 3), "1100", cash="400", aktien="700"),
    _nav(date(2026, 1, 6), "1300", cash="600", aktien="750", optionen="-50"),
    _nav(date(2026, 1, 7), "1250", cash="600", aktien="700", optionen="-50"),
]

_CASH = [
    dict(datum=dt(2026, 1, 2), typ="Deposits/Withdrawals", betrag=D("1000"), waehrung="EUR",
         kurs=D("1")),
    dict(datum=dt(2026, 1, 3, 20), typ="Dividends", betrag=D("10"), waehrung="USD", kurs=D("0.9")),
    dict(datum=dt(2026, 1, 6), typ="Deposits/Withdrawals", betrag=D("200"), waehrung="EUR",
         kurs=D("1")),
]


def test_gewinn_laut_ib():
    e = nav_auswertung(_NAV, _CASH)
    assert [(t.datum, t.gesamt, t.einzahlungen_kumuliert, t.gewinn) for t in e.tage] == [
        (date(2026, 1, 2), D("1000"), D("1000"), D("0")),
        (date(2026, 1, 3), D("1100"), D("1000"), D("100")),
        (date(2026, 1, 6), D("1300"), D("1200"), D("100")),
        (date(2026, 1, 7), D("1250"), D("1200"), D("50")),
    ]
    assert e.tage[2] == NavTag(datum=date(2026, 1, 6), gesamt=D("1300"), cash=D("600"),
                               aktien=D("750"), optionen=D("-50"), rohstoffe=None,
                               einzahlungen_kumuliert=D("1200"), gewinn=D("100"))
    assert (e.anfangswert, e.endwert) == (None, D("1250"))


def test_zeitraum_zeigt_bestand():
    e = nav_auswertung(_NAV, _CASH, von=date(2026, 1, 3), bis=date(2026, 1, 6))
    assert [(t.datum, t.gesamt, t.gewinn) for t in e.tage] == [
        (date(2026, 1, 3), D("1100"), D("100")),
        (date(2026, 1, 6), D("1300"), D("100")),
    ]
    assert (e.anfangswert, e.endwert) == (D("1000"), D("1300"))


def test_cash_ohne_kurs_zaehlt_als_mangel():
    cash = _CASH + [dict(datum=dt(2026, 1, 7), typ="Deposits/Withdrawals", betrag=D("5"),
                         waehrung="USD", kurs=None)]
    e = nav_auswertung(_NAV, cash)
    assert e.tage[-1].einzahlungen_kumuliert == D("1200")
    assert e.anzahl_kurs_fehlt == 1


def test_von_nach_bis_ist_fehler():
    with pytest.raises(ValueError, match="von"):
        nav_auswertung(_NAV, _CASH, von=date(2026, 1, 7), bis=date(2026, 1, 2))
