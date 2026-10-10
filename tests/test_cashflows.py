"""Abnahmetests für AP-06f (Kosten & Erträge). Vertrag: auftraege/AP-06f.md.
Unveränderlich; jeder Erwartungswert ist von Hand gerechnet.

Startzustand: ROT (ModuleNotFoundError: analytics.cashflows).

Testwelt — Instrumente: conid 1 Option, Multiplikator 100, Barausgleich;
conid 2 Aktie, Multiplikator 1.

Ausführungen (Kommission × buchungskurs = EUR):
  E1 2026-01-05 trade      SELL conid 1, Kommission -1.50 USD, Kurs 0.90 -> -1.35
  E2 2026-01-16 assignment BUY  conid 1, menge 1, schlusskurs 3.00, Kurs 0.90,
     Kommission 0 -> Barausgleich: -1 × 3.00 × 1 × 100 × 0.90 = -270.00
  E3 2026-02-03 trade      BUY  conid 2, Kommission -1.00 EUR, Kurs 1 -> -1.00
  E4 2026-02-04 trade      SELL conid 2, Kommission -2.00 EUR, Kurs fehlt
     -> zählt nur als kurs_fehlt

Cash-Buchungen (betrag × fxRateToBase = EUR):
  C1 2026-01-10 Dividends                      10.00 USD × 0.90 =    9.00
  C2 2026-01-10 Withholding Tax                -1.50 USD × 0.90 =   -1.35
  C5 2026-01-20 Other Fees                    -10.00 USD × 0.90 =   -9.00
  C3 2026-02-05 Broker Interest Received        5.00 EUR × 1    =    5.00
  C4 2026-02-05 Broker Interest Paid           -2.00 CHF × 1.05 =   -2.10
  C6 2026-02-10 Deposits/Withdrawals         1000.00 EUR × 1    = 1000.00
  C7 2026-02-11 Payment In Lieu Of Dividends    4.00 USD × 0.95 =    3.80
  C8 2026-02-12 Bond Interest (unbekannt)       1.00 EUR × 1    =    1.00

Summen je Kategorie:
  kommissionen       2 Buchungen  -2.35  (1 ohne Kurs)
  kommissionsanpassungen 0         0.00
  gebuehren          1            -9.00
  zinsen_erhalten    1             5.00
  zinsen_gezahlt     1            -2.10
  dividenden         2            12.80  (9.00 + 3.80)
  quellensteuer      1            -1.35
  barausgleich       1          -270.00
  sonstige           1             1.00
  ein_auszahlungen   1          1000.00
"""

from datetime import date
from datetime import datetime as dt
from decimal import Decimal as D

import pytest

from analytics.cashflows import (
    KATEGORIEN,
    CashflowKategorie,
    CashflowMonat,
    cashflow_auswertung,
)

_INSTRUMENTE = [
    dict(conid=1, multiplikator=D("100"), abwicklungsart="barausgleich"),
    dict(conid=2, multiplikator=D("1"), abwicklungsart=None),
]


def _ausf(exec_id, conid, side, menge, zeit, kommission, kurs, ereignistyp="trade",
          schlusskurs=None, preis="1.00", waehrung="USD"):
    return dict(
        exec_id=exec_id, conid=conid, side=side, menge=D(menge), preis=D(preis),
        waehrung=waehrung, kommission=D(kommission), kommission_waehrung=waehrung,
        buchungskurs=None if kurs is None else D(kurs), handelszeit=zeit,
        ereignistyp=ereignistyp, schlusskurs=None if schlusskurs is None else D(schlusskurs),
    )


_AUSFUEHRUNGEN = [
    _ausf("E1", 1, "SELL", "-1", dt(2026, 1, 5, 15), "-1.50", "0.90"),
    _ausf("E2", 1, "BUY", "1", dt(2026, 1, 16, 22), "0", "0.90",
          ereignistyp="assignment", schlusskurs="3.00", preis="0"),
    _ausf("E3", 2, "BUY", "10", dt(2026, 2, 3, 15), "-1.00", "1", waehrung="EUR"),
    _ausf("E4", 2, "SELL", "-10", dt(2026, 2, 4, 15), "-2.00", None, waehrung="EUR"),
]


def _cash(datum, typ, betrag, waehrung, kurs):
    return dict(datum=datum, typ=typ, betrag=D(betrag), waehrung=waehrung, kurs=D(kurs))


_CASH = [
    _cash(dt(2026, 1, 10, 20), "Dividends", "10.00", "USD", "0.90"),
    _cash(dt(2026, 1, 10, 20), "Withholding Tax", "-1.50", "USD", "0.90"),
    _cash(dt(2026, 1, 20, 18), "Other Fees", "-10.00", "USD", "0.90"),
    _cash(dt(2026, 2, 5), "Broker Interest Received", "5.00", "EUR", "1"),
    _cash(dt(2026, 2, 5), "Broker Interest Paid", "-2.00", "CHF", "1.05"),
    _cash(dt(2026, 2, 10), "Deposits/Withdrawals", "1000.00", "EUR", "1"),
    _cash(dt(2026, 2, 11, 20), "Payment In Lieu Of Dividends", "4.00", "USD", "0.95"),
    _cash(dt(2026, 2, 12), "Bond Interest", "1.00", "EUR", "1"),
]


def _auswertung(von=None, bis=None):
    return cashflow_auswertung(_AUSFUEHRUNGEN, _INSTRUMENTE, _CASH, von=von, bis=bis)


def _kategorie(e, name):
    treffer = [k for k in e.kategorien if k.kategorie == name]
    assert len(treffer) == 1, name
    return treffer[0]


def test_alle_kategorien_in_fester_reihenfolge():
    """Jede Kategorie erscheint genau einmal, auch ohne Buchung (Anzahl 0,
    Summe 0) — die Oberfläche soll nicht raten, was fehlt."""
    e = _auswertung()
    assert tuple(k.kategorie for k in e.kategorien) == KATEGORIEN
    assert _kategorie(e, "kommissionsanpassungen") == CashflowKategorie(
        kategorie="kommissionsanpassungen", anzahl=0, summe_eur=D("0"), anzahl_kurs_fehlt=0,
        im_ergebnis_enthalten=False)


def test_summen_je_kategorie():
    e = _auswertung()
    erwartet = {
        "kommissionen": (2, D("-2.35"), 1),
        "gebuehren": (1, D("-9.00"), 0),
        "zinsen_erhalten": (1, D("5.00"), 0),
        "zinsen_gezahlt": (1, D("-2.10"), 0),
        "dividenden": (2, D("12.80"), 0),
        "quellensteuer": (1, D("-1.35"), 0),
        "barausgleich": (1, D("-270.00"), 0),
        "sonstige": (1, D("1.00"), 0),
        "ein_auszahlungen": (1, D("1000.00"), 0),
    }
    for name, (anzahl, summe, fehlt) in erwartet.items():
        k = _kategorie(e, name)
        assert (k.anzahl, k.summe_eur, k.anzahl_kurs_fehlt) == (anzahl, summe, fehlt), name


def test_im_ergebnis_enthalten_markiert_doppelzaehlung():
    """Kommissionen und Barausgleich stecken schon im realisierten Ergebnis
    (Tranche I, AP-06x) — markiert, damit niemand sie ein zweites Mal
    addiert (Kapitalentwicklung, AP-06g)."""
    e = _auswertung()
    enthalten = {k.kategorie for k in e.kategorien if k.im_ergebnis_enthalten}
    assert enthalten == {"kommissionen", "barausgleich"}


def test_monate():
    e = _auswertung()
    jan = {m.kategorie: m for m in e.monate if m.monat == "2026-01"}
    feb = {m.kategorie: m for m in e.monate if m.monat == "2026-02"}
    assert set(jan) == {"kommissionen", "gebuehren", "dividenden", "quellensteuer", "barausgleich"}
    assert jan["barausgleich"] == CashflowMonat(
        monat="2026-01", kategorie="barausgleich", anzahl=1, summe_eur=D("-270.00"),
        anzahl_kurs_fehlt=0)
    assert set(feb) == {"kommissionen", "zinsen_erhalten", "zinsen_gezahlt", "dividenden",
                        "sonstige", "ein_auszahlungen"}
    assert feb["kommissionen"] == CashflowMonat(
        monat="2026-02", kategorie="kommissionen", anzahl=1, summe_eur=D("-1.00"),
        anzahl_kurs_fehlt=1)
    # Reihenfolge: Monat aufsteigend, darin die feste Kategorienfolge.
    reihen = [(m.monat, KATEGORIEN.index(m.kategorie)) for m in e.monate]
    assert reihen == sorted(reihen)


def test_zeitraum_nach_buchungsdatum():
    """Zeitraum nach dem Datum der Buchung (beide Enden einschließlich)."""
    e = _auswertung(von=date(2026, 2, 1))
    assert _kategorie(e, "barausgleich").anzahl == 0
    assert (_kategorie(e, "kommissionen").anzahl, _kategorie(e, "kommissionen").summe_eur,
            _kategorie(e, "kommissionen").anzahl_kurs_fehlt) == (1, D("-1.00"), 1)
    assert _kategorie(e, "dividenden").summe_eur == D("3.80")
    e2 = _auswertung(bis=date(2026, 1, 10))
    assert _kategorie(e2, "dividenden").summe_eur == D("9.00")
    assert _kategorie(e2, "gebuehren").anzahl == 0


def test_von_nach_bis_ist_fehler():
    with pytest.raises(ValueError, match="von"):
        _auswertung(von=date(2026, 2, 1), bis=date(2026, 1, 1))
