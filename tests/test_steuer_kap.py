# ruff: noqa: E501
"""KAP-Vorschau in zwei Varianten (A: Zufluss, Prämie separat; B: IB-Methode), von Hand gerechnet, EUR, Kurs 1.

Testwelt 2025:
  Short Put: Prämie 500, Rückkauf 200 → Stillhaltersaldo +300 (der Rückkauf ist KEIN Verlust für Zeile 22)
  Long Call gehandelt: Kauf 3,00, Verkauf 2,00 → Termingeschäft −100
  Aktie X: +50 (Kauf 100, Verkauf 150); Aktie Y: −20 (Kauf 120, Verkauf 100)
  Dividende +10
Variante A: Z19 = 300 − 100 + (50 − 20) + 10 = 240; Z20 = 50; Z22 = 100; Z23 = 20
Variante B (IB: Aktien +50 und −20, Optionen +40 und −90, Dividende wie A):
  Z19 = (50 − 20) + (40 − 90) + 10 = −10; Z20 = 50; Z22 = 90; Z23 = 20
"""
from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from test_steuer_zufluss import PUT100, cash, ex, inst, lauf, leg  # noqa: E402

from analytics.steuer_ueberleitung import kap_ib_varianten  # noqa: E402


def welt():
    call = inst(2, "OPT", mult="100", abw="lieferung", right="C", waehrung="EUR")
    x, y = inst(3, "STK", symbol="X", waehrung="EUR"), inst(4, "STK", symbol="Y", waehrung="EUR")
    execs = [
        ex("P1", 1, "SELL", 1, "5.00", "1", date(2025, 3, 3), waehrung="EUR"),
        ex("P2", 1, "BUY", 1, "2.00", "1", date(2025, 4, 3), waehrung="EUR"),
        ex("C1", 2, "BUY", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR"),
        ex("C2", 2, "SELL", 1, "2.00", "1", date(2025, 4, 3), waehrung="EUR"),
        ex("X1", 3, "BUY", 1, "100", "1", date(2025, 3, 3), waehrung="EUR"),
        ex("X2", 3, "SELL", 1, "150", "1", date(2025, 4, 3), waehrung="EUR"),
        ex("Y1", 4, "BUY", 1, "120", "1", date(2025, 3, 3), waehrung="EUR"),
        ex("Y2", 4, "SELL", 1, "100", "1", date(2025, 4, 3), waehrung="EUR"),
    ]
    legs = [leg(1, 1, "P1", "P2", "-1"), leg(2, 2, "C1", "C2", "1"), leg(3, 3, "X1", "X2", "1"), leg(4, 4, "Y1", "Y2", "1")]
    c = [cash("Dividends", "10", "1", date(2025, 5, 5), symbol="X", waehrung="EUR", beschr="X(US1) CASH DIVIDEND EUR 0.10 PER SHARE (Ordinary Dividend)")]
    return lauf(legs, execs, [PUT100, call, x, y], c)


def betrag(kap, name):
    return kap["posten"][name]["betrag"]


def test_variante_a_rueckkauf_ist_im_saldo_und_als_verlust_in_zeile_22():
    # AP-10e (BMF 14.05.2025, Rn. 25): der Rückkauf 200 steht im Saldo (Zeile 19) UND als enthaltener Verlust (Zeile 22).
    kap = welt().jahre()[2025]["kap"]
    assert kap["variante"] == "zufluss"
    assert betrag(kap, "ausl_kapitalertraege_saldo") == D("240")
    assert betrag(kap, "aktiengewinne") == D("50")
    assert betrag(kap, "verluste_ohne_aktien") == D("300")          # Termingeschäft 100 + Rückkauf 200
    assert kap["alternativen"][0]["betrag"] == D("100")             # Vergleichsrechnung ohne Rückkäufe
    assert betrag(kap, "aktienverluste") == D("20")
    assert kap["posten"]["aktienverluste"]["zeile"] == 23 and kap["status"] == "amtlich_belegt"
    assert kap["zusammensetzung"]["Stillhalter (Prämien abzüglich Rückkäufe)"] == D("300")


def test_variante_b_ib_methode_aus_den_ib_zahlen():
    erg = welt()
    ib = [{"exec_id": "a", "jahr": 2025, "klasse": "STK", "eur": D("50")},
          {"exec_id": "b", "jahr": 2025, "klasse": "STK", "eur": D("-20")},
          {"exec_id": "c", "jahr": 2025, "klasse": "OPT", "eur": D("40")},
          {"exec_id": "d", "jahr": 2025, "klasse": "OPT", "eur": D("-90")},
          {"exec_id": "e", "jahr": 2025, "klasse": "CASH", "eur": D("999")}]   # Devisen zählen nicht
    kap = kap_ib_varianten(ib, erg.jahre())[2025]
    assert kap["variante"] == "ib"
    assert betrag(kap, "ausl_kapitalertraege_saldo") == D("-10")
    assert betrag(kap, "aktiengewinne") == D("50")
    assert betrag(kap, "verluste_ohne_aktien") == D("90")
    assert betrag(kap, "aktienverluste") == D("20")
    assert kap["zusammensetzung"]["Dividenden"] == D("10")


def test_negativer_stillhaltersaldo_ist_im_saldo_und_die_rueckkaeufe_stehen_in_zeile_22():
    e1 = ex("O", 1, "SELL", 1, "1.00", "1", date(2025, 3, 3), waehrung="EUR")
    e2 = ex("C", 1, "BUY", 1, "4.00", "1", date(2025, 4, 3), waehrung="EUR")
    kap = lauf([leg(1, 1, "O", "C", "-1")], [e1, e2], [PUT100]).jahre()[2025]["kap"]
    assert betrag(kap, "ausl_kapitalertraege_saldo") == D("-300")     # 100 − 400
    assert betrag(kap, "verluste_ohne_aktien") == D("400")            # der Rückkauf 400 als enthaltener Verlust
    assert kap["alternativen"][0]["betrag"] == D("300")               # nur der negative Saldo
