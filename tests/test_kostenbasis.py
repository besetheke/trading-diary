# ruff: noqa: E501
"""Kostenbasis einer Kette (AP-19, Entscheidung 30.10.2026: Put-Prämie beim Wheel zählt, anteilig bei geänderter
Stückzahl, netto nach Kommission). Alle Erwartungen von Hand gerechnet.

1. Wheel: Put zugeteilt, realisiert +174,94 (Prämie netto). Aktie offen: 100 Stück zu 25,00 → Zufluss −2.500,00.
   Covered Call offen: 0,35 × 100 − 1,50 Kommission = +33,50.
   realisiert 174,94 · offene Prämien 33,50 · netto 208,44 · Einstand 2.500,00 · Kostenbasis 2.500,00 − 208,44 = 2.291,56
   · je Aktie 2.291,56 ÷ 100 = 22,9156.
2. Teilverkauf: zusätzlich 50 Stück verkauft, realisiert +100,00; offen 50 Stück zu 25,00 → Zufluss −1.250,00.
   realisiert 274,94 · netto 308,44 · Einstand 1.250,00 · Kostenbasis 941,56 · je Aktie 941,56 ÷ 50 = 18,8312.
3. DAX-BPS-Kette mit Rolls (Multiplikator 5, 10 Kontrakte, Short 25.900, Long 25.600, Breite 300):
   abgeschlossen 99 − 2.527 − 3.207 − 4.222 − 1.912 + 2.468 − 567 = −9.868; offen 170,20 × 10 − 36 = +1.666.
   netto −8.202 · je Einheit −8.202 ÷ 50 = −164,04 Punkte · Breakeven 25.900 + 164,04 = 26.064,04
   · höchster Verlust (300 + 164,04) × 50 = 23.202,00.
4. Short Call naked, Credit: offen +420 (4,20 × 100), 1 Kontrakt, Short 250 → Breakeven 254,20; kein höchster Verlust.
5. Ein fehlender Betrag macht das Ergebnis leer.
"""
from decimal import Decimal as D

from analytics.kostenbasis import Glied, kostenbasis


def test_wheel_mit_put_praemie():
    g = [Glied(1, "open", "Single", False, D("174.94")),
         Glied(2, "zuteilung", "Stock", True, D("-2500.00"), D("100")),
         Glied(3, "covered_call", "Single", True, D("33.50"))]
    k = kostenbasis(g)
    assert (k.realisiert, k.praemien_offen, k.netto) == (D("174.94"), D("33.50"), D("208.44"))
    assert (k.aktien_einstand, k.aktien_stueck, k.kostenbasis) == (D("2500.00"), D("100"), D("2291.56"))
    assert k.je_aktie == D("22.9156") and k.breakeven == D("22.9156")


def test_teilverkauf_verteilt_die_basis_auf_die_restlichen_stueck():
    g = [Glied(1, "open", "Single", False, D("174.94")),
         Glied(2, "zuteilung", "Stock", False, D("100.00")),
         Glied(3, "zuteilung", "Stock", True, D("-1250.00"), D("50")),
         Glied(4, "covered_call", "Single", True, D("33.50"))]
    k = kostenbasis(g)
    assert (k.realisiert, k.netto, k.aktien_einstand, k.kostenbasis) == (D("274.94"), D("308.44"), D("1250.00"), D("941.56"))
    assert k.je_aktie == D("18.8312")


def test_spread_kette_mit_rolls():
    abgeschlossen = ["99", "-2527", "-3207", "-4222", "-1912", "2468", "-567"]
    g = [Glied(i + 1, "roll", "BPS", False, D(b)) for i, b in enumerate(abgeschlossen)]
    g.append(Glied(8, "roll", "BPS", True, D("1666")))
    k = kostenbasis(g, recht="P", short=D("25900"), long=D("25600"), kontrakte=D("10"), multiplikator=D("5"))
    assert (k.realisiert, k.praemien_offen, k.netto) == (D("-9868"), D("1666"), D("-8202"))
    assert k.je_einheit == D("-164.04") and k.breakeven == D("26064.04")
    assert k.max_verlust == D("23202.00")
    assert k.kostenbasis is None and k.je_aktie is None


def test_naked_call():
    k = kostenbasis([Glied(1, "open", "Single", True, D("420"))], recht="C", short=D("250"), kontrakte=D("1"), multiplikator=D("100"))
    assert (k.netto, k.breakeven, k.max_verlust) == (D("420"), D("254.20"), None)


def test_fehlender_betrag_bleibt_leer():
    k = kostenbasis([Glied(1, "open", "BPS", False, None), Glied(2, "roll", "BPS", True, D("100"))],
                    recht="P", short=D("100"), long=D("90"), kontrakte=D("1"), multiplikator=D("100"))
    assert (k.realisiert, k.netto, k.breakeven) == (None, None, None)
