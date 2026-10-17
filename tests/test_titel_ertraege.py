"""Erträge je Titel (Dividenden, Quellensteuer) in der Titel-Auswertung (OF-89, 17.10.2026).

Von Hand gerechnet (Betrag × fxRateToBase der Buchung):
  WDC  Dividende          45,00 USD × 0,90 = 40,50
  WDC  Ersatzzahlung      10,00 USD × 0,90 =  9,00     → Dividenden 49,50
  WDC  Quellensteuer      −7,50 USD × 0,90 = −6,75     → Erträge netto 42,75
  KNSL Dividende         100,00 EUR × 1,00 = 100,00
  ohne Symbol (Zins-Quellensteuer −8,05 EUR)           → keinem Titel zugeordnet
  ABC  Dividende ohne Kurs                             → zählt nicht, steht in ertraege_kurs_fehlt
"""
from datetime import date, datetime
from decimal import Decimal

from analytics.titel import titel_auswertung

D = Decimal


def _cash(tag, typ, betrag, kurs, symbol):
    return {"datum": datetime(2026, 9, tag, 20, 20), "typ": typ, "betrag": D(betrag),
            "kurs": None if kurs is None else D(kurs), "symbol": symbol}


CASH = [
    _cash(17, "Dividends", "45", "0.9", "WDC"),
    _cash(18, "Payment In Lieu Of Dividends", "10", "0.9", "WDC"),
    _cash(17, "Withholding Tax", "-7.5", "0.9", "WDC"),
    _cash(20, "Dividends", "100", "1", "KNSL"),
    _cash(5, "Withholding Tax", "-8.05", "1", None),
    _cash(21, "Dividends", "30", None, "ABC"),
    _cash(22, "Broker Interest Received", "5", "1", "WDC"),
]


def _lauf(**kw):
    zeilen = titel_auswertung([], [], [], [], [], [], {}, None, cash_zeilen=CASH, **kw)
    return {z.basiswert: z for z in zeilen}


def test_dividenden_und_quellensteuer_je_titel():
    z = _lauf()["WDC"]
    assert z.dividenden_eur == D("49.50")
    assert z.quellensteuer_eur == D("-6.75")
    assert z.ertraege_eur == D("42.75")
    assert z.realisiert_eur == 0 and z.gesamt_eur == 0           # Handelsergebnis bleibt unberührt
    assert z.gesamt_inkl_ertraege_eur == D("42.75")


def test_titel_nur_mit_dividende_erscheint_ohne_ketten():
    z = _lauf()["KNSL"]
    assert z.ketten == 0 and z.dividenden_eur == D("100")


def test_ohne_symbol_und_andere_typen_zaehlen_nicht():
    zeilen = _lauf()
    assert set(zeilen) == {"WDC", "KNSL", "ABC"}                  # kein Titel für die Zins-Steuer
    assert sum(z.ertraege_eur for z in zeilen.values()) == D("42.75") + D("100")


def test_fehlender_kurs_zaehlt_nicht_und_wird_gemeldet():
    z = _lauf()["ABC"]
    assert z.dividenden_eur == 0 and z.ertraege_kurs_fehlt == 1


def test_zeitraum_nach_buchungsdatum_beide_enden_einschliesslich():
    z = _lauf(von=date(2026, 9, 18), bis=date(2026, 9, 18))["WDC"]
    assert z.dividenden_eur == D("9.00") and z.quellensteuer_eur == 0
    assert "KNSL" not in _lauf(von=date(2026, 9, 18), bis=date(2026, 9, 18))
