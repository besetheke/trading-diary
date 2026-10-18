# ruff: noqa: E501
"""Anlage SO (AP-10e, OF-99), von Hand gerechnet, Kurs je Zeile angegeben.

Welt 2025:
  PIL +100 USD × 0,9 = +90; Storno −10 USD × 0,9 = −9 (REVERSAL, mindert die empfangene PIL)   → netto 81
  PIL-Belastung −20 USD × 0,9 = −18 (kein Storno: Kompensation aus Leerverkauf)                 → nicht saldiert
  SYEP-Vergütung +5 EUR (Beschreibung „(SYEP) INTEREST“), normale Habenzinsen +3 EUR            → 5 bzw. 3
  Steuer auf PIL: −15 USD × 0,9 = −13,50 einbehalten, Erstattung +4 USD × 0,9 = +3,60          → netto 9,90
Erwartung: Ersatzzahlungen 81, SYEP 5, Summe 86 (< 256 → Freigrenze nicht überschritten), Belastung −18,
PIL-Quellensteuer 9,90 (nicht in Zeile 41), Zeile 19 enthält nur die Habenzinsen 3.
"""
from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from test_steuer_zufluss import cash, lauf  # noqa: E402

PIL = "GPK(US2) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)"
STORNO = "GPK(US2) PAYMENT IN LIEU OF DIVIDEND - REVERSAL (Ordinary Dividend)"
STEUER = "GPK(US2) PAYMENT IN LIEU OF DIVIDEND - US TAX"
SYEP = "IBKR MANAGED SECURITIES (SYEP) INTEREST FOR FEB-2025"


def welt(pil_eur_extra=None):
    c = [
        cash("Payment In Lieu Of Dividends", "100", "0.9", date(2025, 3, 3), symbol="GPK", beschr=PIL),
        cash("Payment In Lieu Of Dividends", "-10", "0.9", date(2025, 3, 3), symbol="GPK", beschr=STORNO),
        cash("Payment In Lieu Of Dividends", "-20", "0.9", date(2025, 9, 23), symbol="UNH", beschr="UNH(US3) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)"),
        cash("Broker Interest Received", "5", "1", date(2025, 3, 5), symbol=None, beschr=SYEP, waehrung="EUR"),
        cash("Broker Interest Received", "3", "1", date(2025, 4, 5), symbol=None, beschr="EUR CREDIT INT FOR MAR-2025", waehrung="EUR"),
        cash("Withholding Tax", "-15", "0.9", date(2025, 3, 3), symbol="GPK", beschr=STEUER),
        cash("Withholding Tax", "4", "0.9", date(2025, 6, 3), symbol="ABC", beschr="ABC(US4) PAYMENT IN LIEU OF DIVIDEND - US TAX"),
    ]
    if pil_eur_extra:
        c.append(cash("Payment In Lieu Of Dividends", pil_eur_extra, "1", date(2025, 5, 5), symbol="XYZ", beschr="XYZ(US5) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)", waehrung="EUR"))
    return lauf([], [], [], c)


def test_ersatzzahlungen_syep_und_belastung_werden_getrennt_ausgewiesen():
    j = welt().jahre()[2025]
    so = j["so"]
    assert so["ersatzzahlungen_netto"] == D("81")                    # 90 − 9
    assert so["syep_verguetung"] == D("5") and so["summe"] == D("86")
    assert so["freigrenze_ueberschritten"] is False
    assert so["belastung_nicht_saldiert"] == D("-18")               # nicht gegen die 81 gerechnet
    assert so["pil_quellensteuer"] == D("9.90")                      # 13,50 − 3,60 Erstattung
    assert j["quellensteuer"]["vorlaeufig_anrechenbar"] == 0         # nie in Zeile 41


def test_so_posten_sind_nicht_in_den_kap_zeilen():
    kap = welt().jahre()[2025]["kap"]
    assert kap["posten"]["ausl_kapitalertraege_saldo"]["betrag"] == D("3")      # nur die normalen Habenzinsen
    assert kap["posten"]["anrechenbare_quellensteuer"]["betrag"] == 0


def test_freigrenze_ab_256_euro_ist_ueberschritten():
    assert welt("170")  .jahre()[2025]["so"]["freigrenze_ueberschritten"] is True     # 81 + 5 + 170 = 256
    assert welt("169.99").jahre()[2025]["so"]["freigrenze_ueberschritten"] is False   # 255,99
