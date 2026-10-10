"""Abnahmetests für AP-06g (Kapitalentwicklung, realisiert). Vertrag:
auftraege/AP-06g.md. Unveränderlich; Erwartungswerte von Hand gerechnet.

Kapital = Ein-/Auszahlungen + realisiertes Ergebnis + Cash-Posten
(Dividenden, Quellensteuer, Zinsen, Gebühren, Kommissionsanpassungen,
Sonstiges). Kommissionen und Barausgleich stecken im realisierten Ergebnis
und zählen nicht ein zweites Mal (AP-06f, C3).

Realisiertes Ergebnis (Equity-Tage, netto EUR): 01-02 +100, 01-05 -40,
02-03 +60.
Cash-Buchungen: 01-01 Einzahlung 1000 EUR; 01-05 Dividende 10 USD × 0.90 =
9; 01-20 Gebühr -5 EUR; 02-01 Auszahlung -200 EUR; 02-03 Zinsen gezahlt
-3 EUR; 02-04 Dividende 1 USD ohne Kurs (zählt nur als kurs_fehlt).

Tag    Einzahl.  Ergebnis  Cash  Kapital
01-01    1000        0       0    1000
01-02    1000      100       0    1100
01-05    1000       60       9    1069
01-20    1000       60       4    1064
02-01     800       60       4     864
02-03     800      120       1     921

Zeitraum 01-05 bis 02-01: Anfangskapital = Kapital am Ende des Vortags des
ersten Tages im Zeitraum (01-02) = 1100; Ende 864; im Zeitraum Einzahlungen
-200, Ergebnis -40, Cash 9 - 5 = 4. Probe: 1100 - 200 - 40 + 4 = 864.
"""

from datetime import date
from datetime import datetime as dt
from decimal import Decimal as D

import pytest

from analytics.equity import EquityTag
from analytics.kapital import KapitalTag, kapital_auswertung


def _eq(tag, netto):
    return EquityTag(datum=tag, netto_eur=D(netto), kumuliert_eur=D("0"), drawdown_eur=D("0"),
                     anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0)


_EQUITY_TAGE = (
    _eq(date(2026, 1, 2), "100"),
    _eq(date(2026, 1, 5), "-40"),
    _eq(date(2026, 2, 3), "60"),
)


def _cash(datum, typ, betrag, kurs):
    return dict(datum=datum, typ=typ, betrag=D(betrag), waehrung="EUR",
                kurs=None if kurs is None else D(kurs))


_CASH = [
    _cash(dt(2026, 1, 1), "Deposits/Withdrawals", "1000", "1"),
    _cash(dt(2026, 1, 5, 20), "Dividends", "10", "0.90"),
    _cash(dt(2026, 1, 20), "Other Fees", "-5", "1"),
    _cash(dt(2026, 2, 1), "Deposits/Withdrawals", "-200", "1"),
    _cash(dt(2026, 2, 3), "Broker Interest Paid", "-3", "1"),
    _cash(dt(2026, 2, 4), "Dividends", "1", None),
]


def _k(datum, einz, erg, cash, kapital):
    return KapitalTag(datum=datum, einzahlungen_kumuliert=D(einz), ergebnis_kumuliert=D(erg),
                      cash_kumuliert=D(cash), kapital=D(kapital))


def test_tagesreihe_gesamt():
    e = kapital_auswertung(_EQUITY_TAGE, _CASH)
    assert e.tage == (
        _k(date(2026, 1, 1), "1000", "0", "0", "1000"),
        _k(date(2026, 1, 2), "1000", "100", "0", "1100"),
        _k(date(2026, 1, 5), "1000", "60", "9", "1069"),
        _k(date(2026, 1, 20), "1000", "60", "4", "1064"),
        _k(date(2026, 2, 1), "800", "60", "4", "864"),
        _k(date(2026, 2, 3), "800", "120", "1", "921"),
    )
    assert (e.anfangskapital, e.endkapital) == (D("0"), D("921"))
    assert (e.einzahlungen_im_zeitraum, e.ergebnis_im_zeitraum, e.cash_im_zeitraum) == (
        D("800"), D("120"), D("1"))
    assert e.anzahl_kurs_fehlt == 1


def test_zeitraum_zeigt_bestand_nicht_null():
    e = kapital_auswertung(_EQUITY_TAGE, _CASH, von=date(2026, 1, 5), bis=date(2026, 2, 1))
    assert [(t.datum, t.kapital) for t in e.tage] == [
        (date(2026, 1, 5), D("1069")),
        (date(2026, 1, 20), D("1064")),
        (date(2026, 2, 1), D("864")),
    ]
    assert e.anfangskapital == D("1100")
    assert e.endkapital == D("864")
    assert (e.einzahlungen_im_zeitraum, e.ergebnis_im_zeitraum, e.cash_im_zeitraum) == (
        D("-200"), D("-40"), D("4"))
    assert e.anfangskapital + e.einzahlungen_im_zeitraum + e.ergebnis_im_zeitraum \
        + e.cash_im_zeitraum == e.endkapital
    assert e.anzahl_kurs_fehlt == 0


def test_zeitraum_ohne_ereignis_haelt_den_bestand():
    """Ein Zeitraum ohne Ereignis hat keine Tage; Anfang und Ende sind der
    Bestand davor."""
    e = kapital_auswertung(_EQUITY_TAGE, _CASH, von=date(2026, 1, 21), bis=date(2026, 1, 31))
    assert e.tage == ()
    assert (e.anfangskapital, e.endkapital) == (D("1064"), D("1064"))


def test_von_nach_bis_ist_fehler():
    with pytest.raises(ValueError, match="von"):
        kapital_auswertung(_EQUITY_TAGE, _CASH, von=date(2026, 2, 1), bis=date(2026, 1, 1))
