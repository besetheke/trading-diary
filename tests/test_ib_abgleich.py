"""Abnahmetests für AP-08u2: Abgleich des realisierten Ergebnisses Journal ↔ IB.
Vertrag im Modulkopf von analytics/ib_abgleich.py und in auftraege/AP-08u2.md.

Welt (frei erfunden), von Hand gerechnet:

S1  Option USD, Multiplikator 100: SELL 2.00 (Kurs 0.90), BUY 1.00 (Kurs 0.80).
    Journal nativ 100.00 USD; EUR 2.00·100·0.90 − 1.00·100·0.80 = 180 − 80 = 100.00.
    IB: 100.00 USD zum Kurs 0.80 = 80.00 EUR. Währungsmethode 100 − 100·0.80 = 20.00;
    Methode (100 − 100)·0.80 = 0.

S2  Put USD, Multiplikator 100, Lieferung: SELL 3.00 (Kurs 0.90), Zuteilung BUY 0.00
    (Kurs 0.85). Journal nativ 300.00; EUR 300·0.90 = 270.00. IB bucht 0 (Prämie in
    den Aktieneinstand). Währungsmethode 270 − 300·0.85 = 15.00; Methode
    (300 − 0)·0.85 = 255.00.
    Die Aktie (100 Stück zu 50.00, Kurs 0.85) wird noch gehalten: Journal-Einstand
    5000.00, IB costBasisMoney 4700.00 (= 5000 − 300 Prämie), Bestandskurs 0.80.
    Prämie im Einstand zum Kurs der Eröffnung 300·0.85 = 255.00, zum Bestandskurs
    300·0.80 = 240.00.

S3  Option EUR, Multiplikator 10, Struktur noch **offen**: SELL 1.00, BUY 0.40,
    Kurs 1. Journal 6.00 = IB 6.00; Zeitpunkt-Teil 6.00 (ein Leg).

Summen: Journal 376.00, IB 86.00, Unterschied 290.00 = Währungsmethode 35.00 +
Methode 255.00. Gleich: 2 Zeilen (S1, S3), abweichend 1 (S2).
"""

from datetime import datetime
from decimal import Decimal as D

from analytics.ib_abgleich import ib_abgleich


def _ausf(exec_id, conid, side, menge, preis, kurs, ereignis="trade"):
    return dict(exec_id=exec_id, conid=conid, side=side, menge=D(menge), preis=D(preis),
                kommission=D("0"), buchungskurs=D(kurs), ereignistyp=ereignis,
                schlusskurs=None, handelszeit=datetime(2026, 1, 1))


def _leg(structure_id, conid, offen, schluss, menge, brutto):
    return dict(structure_id=structure_id, conid=conid, open_exec_id=offen,
                close_exec_id=schluss, menge=D(menge),
                brutto_pnl=None if brutto is None else D(brutto),
                kommission_gesamt=D("0"), open_faktor=D("1"), close_faktor=D("1"))


AUSFUEHRUNGEN = [
    _ausf("E1", 1, "SELL", "-1", "2.00", "0.90"),
    _ausf("E2", 1, "BUY", "1", "1.00", "0.80"),
    _ausf("E3", 2, "SELL", "-1", "3.00", "0.90"),
    _ausf("E4", 2, "BUY", "1", "0.00", "0.85", "assignment"),
    _ausf("E5", 3, "BUY", "100", "50.00", "0.85", "assignment"),
    _ausf("E6", 4, "SELL", "-1", "1.00", "1"),
    _ausf("E7", 4, "BUY", "1", "0.40", "1"),
]
INSTRUMENTE = [
    dict(conid=1, multiplikator=D("100"), abwicklungsart="lieferung"),
    dict(conid=2, multiplikator=D("100"), abwicklungsart="lieferung"),
    dict(conid=3, multiplikator=D("1"), abwicklungsart=None),
    dict(conid=4, multiplikator=D("10"), abwicklungsart="lieferung"),
]
LEGS = [
    _leg(10, 1, "E1", "E2", "-1", "100.00"),
    _leg(20, 2, "E3", "E4", "-1", "300.00"),
    _leg(30, 3, "E5", None, "100", None),
    _leg(40, 4, "E6", "E7", "-1", "6.00"),
]
IB = {
    "E1": (D("0"), D("0.90")),
    "E2": (D("100.00"), D("0.80")),
    "E3": (D("0"), D("0.90")),
    "E4": (D("0"), D("0.85")),
    "E5": (D("0"), D("0.85")),
    "E6": (D("0"), D("1")),
    "E7": (D("6.00"), D("1")),
}
BESTAND = [dict(conid=3, kosten=D("4700.00"), kurs=D("0.80"))]


def _ergebnis():
    return ib_abgleich(LEGS, {40, 30}, AUSFUEHRUNGEN, INSTRUMENTE, IB, BESTAND)


def test_summen():
    e = _ergebnis()
    assert e.journal_legs_eur == D("376.00")
    assert e.ib_realisiert_eur == D("86.00")


def test_waehrungsmethode_und_methode_der_einstaende():
    e = _ergebnis()
    assert e.waehrungsmethode == D("35.00")
    assert e.methode_einstand == D("255.00")


def test_identitaet_unterschied_gleich_waehrung_plus_methode():
    e = _ergebnis()
    assert e.journal_legs_eur - e.ib_realisiert_eur == e.waehrungsmethode + e.methode_einstand


def test_praemie_im_einstand_der_gehaltenen_aktie():
    e = _ergebnis()
    assert e.praemien_im_einstand == D("255.00")        # Kurs der Eröffnung 0.85
    assert e.praemien_im_einstand_heute == D("240.00")  # Bestandskurs 0.80


def test_zeitpunkt_legs_in_offenen_strukturen():
    e = _ergebnis()
    assert e.zeitpunkt_offene_strukturen == D("6.00")
    assert e.anzahl_legs_offene_strukturen == 1


def test_gleiche_und_abweichende_zeilen():
    e = _ergebnis()
    assert (e.zeilen_gleich, e.zeilen_abweichend) == (2, 1)


# ------------------------------------------------- AP-08u3: der Rest im Einzelnen
#
# S4  Put USD, Multiplikator 100, Lieferung: SELL 2.00 (Kurs 0.90), Zuteilung
#     (Kurs 0.90); die Aktie (100 zu 40.00, Kurs 0.90) wird später VERKAUFT zu
#     45.00 (Kurs 0.80). IB: Option 0; Aktie (45 − (40 − 2))·100 = 700.00.
#     Journal: Option 200.00, Aktie (45 − 40)·100 = 500.00.
#     Nativ gleicht sich die Verschiebung aus: (200 − 0) + (500 − 700) = 0.
#     In EUR nicht: 200·0.90 − 200·0.80 = 180 − 160 = 20.00 → Kurseffekt.
# S5  Aktie USD, Kurs 1: IB führt den Einstand 30.00 niedriger (z. B. eine
#     Kapitalrückzahlung): Journal (60 − 50)·100 = 1000.00, IB 1030.00 →
#     Einzelrest −30.00 USD = −30.00 EUR in der Gruppe „R".
# Gruppen: conids 5/6 gehören zu „P" (Option und Aktie desselben Basiswerts),
# conid 7 zu „R".

S45_AUSF = [
    _ausf("F1", 5, "SELL", "-1", "2.00", "0.90"),
    _ausf("F2", 5, "BUY", "1", "0.00", "0.90", "assignment"),
    _ausf("F3", 6, "BUY", "100", "40.00", "0.90", "assignment"),
    _ausf("F4", 6, "SELL", "-100", "45.00", "0.80"),
    _ausf("G1", 7, "BUY", "100", "50.00", "1"),
    _ausf("G2", 7, "SELL", "-100", "60.00", "1"),
]
S45_INSTR = [
    dict(conid=5, multiplikator=D("100"), abwicklungsart="lieferung"),
    dict(conid=6, multiplikator=D("1"), abwicklungsart=None),
    dict(conid=7, multiplikator=D("1"), abwicklungsart=None),
]
S45_LEGS = [
    _leg(50, 5, "F1", "F2", "-1", "200.00"),
    _leg(60, 6, "F3", "F4", "100", "500.00"),
    _leg(70, 7, "G1", "G2", "100", "1000.00"),
]
S45_IB = {
    "F2": (D("0"), D("0.90")),
    "F4": (D("700.00"), D("0.80")),
    "G2": (D("1030.00"), D("1")),
}
S45_GRUPPEN = {5: "P", 6: "P", 7: "R"}


def _s45():
    return ib_abgleich(S45_LEGS, set(), S45_AUSF, S45_INSTR, S45_IB, [],
                       gruppe_je_conid=S45_GRUPPEN)


def test_kurseffekt_auf_verschobene_praemien():
    e = _s45()
    assert e.kurseffekt_praemien == D("20.00")


def test_einzelreste_je_gruppe():
    e = _s45()
    assert [(r.gruppe, r.nativ, r.eur) for r in e.einzelreste] == [("R", D("-30.00"), D("-30.00"))]


def test_rest_ist_kurseffekt_plus_einzelreste():
    """Ohne gehaltene Aktien ist der ganze Methodenteil Rest:
    Methode = (200·0.90) + (500 − 700)·0.80 + (1000 − 1030)·1 = 180 − 160 − 30 = −10.00."""
    e = _s45()
    assert e.methode_einstand == D("-10.00")
    assert e.praemien_im_einstand == 0
    rest = e.methode_einstand - e.praemien_im_einstand
    assert rest == e.kurseffekt_praemien + sum(r.eur for r in e.einzelreste)


def test_ohne_gruppen_gilt_die_conid_als_gruppe():
    """Ohne Zuordnung bildet jede conid ihre eigene Gruppe — dann gleicht sich
    die Verschiebung zwischen Option (5) und Aktie (6) nicht aus und erscheint
    als zwei Einzelreste."""
    e = ib_abgleich(S45_LEGS, set(), S45_AUSF, S45_INSTR, S45_IB, [])
    assert e.kurseffekt_praemien == 0
    assert sorted(r.gruppe for r in e.einzelreste) == ["5", "6", "7"]
