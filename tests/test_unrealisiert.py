"""Abnahmetests für AP-07fu: unrealisiertes Ergebnis offener Legs (Journal-Einstand,
IBs letzter Marktwert). Vertrag im Modulkopf von analytics/unrealisiert.py.

Welt (frei erfunden, von Hand):
  L1  Short Put USD, Multiplikator 100: SELL 1 zu 2.00, Kommission des Legs −1.00.
      Journal-Einstand −2.00·1·100 − (−1.00) = −199.00 (Gutschrift).
      IB-Bestand der conid: Menge −1, Marktwert −50.00, Kurs 0.80.
      Wert des Legs −50.00 (ganze Position) → unrealisiert −50 − (−199) = 149.00 USD
      = 119.20 EUR.
  L2  Aktie USD, Multiplikator 1: BUY 100 zu 40.00, Kommission −1.00 → Einstand
      4001.00. IB-Bestand der conid: 200 Stück (ein zweites Leg gehört nicht zur
      Auswahl), Marktwert 9000.00, Kurs 0.80 → Anteil 100/200 = 4500.00 →
      unrealisiert 499.00 USD = 399.20 EUR.
  L3  conid ohne Bestandszeile → kein Kurs, gezählt.
Summe 518.40 EUR, 2 Legs bewertet, 1 ohne Kurs.
"""

from datetime import date
from decimal import Decimal as D

from analytics.unrealisiert import unrealisiert_auswertung

AUSF = {
    "O1": dict(exec_id="O1", conid=1, side="SELL", preis=D("2.00")),
    "O2": dict(exec_id="O2", conid=2, side="BUY", preis=D("40.00")),
    "O3": dict(exec_id="O3", conid=3, side="BUY", preis=D("10.00")),
}
MULT = {1: D("100"), 2: D("1"), 3: D("1")}
LEGS = [
    dict(conid=1, open_exec_id="O1", menge=D("-1"), kommission_gesamt=D("-1.00"),
         open_faktor=D("1")),
    dict(conid=2, open_exec_id="O2", menge=D("100"), kommission_gesamt=D("-1.00"),
         open_faktor=D("1")),
    dict(conid=3, open_exec_id="O3", menge=D("5"), kommission_gesamt=D("0"),
         open_faktor=D("1")),
]
BESTAND = {
    1: dict(menge=D("-1"), wert=D("-50.00"), kurs=D("0.80")),
    2: dict(menge=D("200"), wert=D("9000.00"), kurs=D("0.80")),
}


def test_summe_und_zaehlung():
    e = unrealisiert_auswertung(LEGS, AUSF, MULT, BESTAND, date(2026, 10, 9))
    assert e.eur == D("518.40")
    assert (e.anzahl_legs, e.ohne_kurs) == (2, 1)
    assert e.stichtag == date(2026, 10, 9)


def test_short_put_einzeln():
    e = unrealisiert_auswertung(LEGS[:1], AUSF, MULT, BESTAND, date(2026, 10, 9))
    assert e.eur == D("119.20")


def test_anteil_einer_position():
    e = unrealisiert_auswertung(LEGS[1:2], AUSF, MULT, BESTAND, date(2026, 10, 9))
    assert e.eur == D("399.20")


def test_faktor_einer_kapitalmassnahme():
    """Wie im Matching: Preis ÷ Faktor, Menge in neuen Stücken. Kauf 25 alte Stück zu
    160.00, 1 für 4 → 100 neue Stück zu 40.00 — gleiches Ergebnis wie L2."""
    ausf = {**AUSF, "O2": dict(exec_id="O2", conid=2, side="BUY", preis=D("160.00"))}
    leg = dict(LEGS[1], open_faktor=D("4"))
    e = unrealisiert_auswertung([leg], ausf, MULT, BESTAND, date(2026, 10, 9))
    assert e.eur == D("399.20")


def test_leer():
    e = unrealisiert_auswertung([], AUSF, MULT, BESTAND, None)
    assert (e.eur, e.anzahl_legs, e.ohne_kurs, e.stichtag) == (D("0"), 0, 0, None)
