# ruff: noqa: E501
"""Titel: geschlossene Beine in noch offenen Strukturen stehen getrennt (OF-89, Punkt 3), von Hand gerechnet.

Welt (USD, Kurs 1, keine Kommission): Struktur 1 ist offen. Bein A (Aktie, geschlossen): BUY 10 @ 20, SELL 10 @ 22 = +20.
Bein B (Aktie, offen): BUY 5 @ 30. Erwartung: teilrealisiert +20, realisiert 0 (die Struktur ist nicht geschlossen),
die Summen enthalten die 20 nicht.
"""
from datetime import date, datetime
from decimal import Decimal as D

from test_titel import _ex, _instr, _leg

from analytics.titel import titel_auswertung


def test_geschlossenes_bein_in_offener_struktur_steht_getrennt():
    ausf = [_ex("E1", 1, "BUY", 10, "20"), _ex("E2", 1, "SELL", 10, "22"), _ex("O1", 2, "BUY", 5, "30")]
    instrumente = [_instr(1, "STK", "TTT"), _instr(2, "STK", "TTT")]
    ketten = [{"chain_id": 1, "underlying": "TTT", "asset_class": "STK", "anzahl_rolls": 0, "beendet_am": None}]
    strukturen = [{"structure_id": 1, "typ": "Vertical", "waehrung": "USD", "brutto_pnl": None, "kommission": None,
                   "netto_pnl": None, "geschlossen_am": None}]
    glieder = [{"chain_id": 1, "structure_id": 1, "sequenz": 0, "verknuepfungstyp": "open", "erkennung": "auto"}]
    beine = [_leg(1, 1, "E1", "E2", "10"), _leg(1, 2, "O1", None, "5")]
    z = {t.basiswert: t for t in titel_auswertung(ketten, strukturen, glieder, beine, ausf, instrumente, {},
                                                   date(2026, 10, 12))}["TTT"]
    assert z.teilrealisiert_eur == D("20")
    assert z.realisiert_eur == 0 and z.gesamt_eur == 0
    assert datetime(2026, 9, 10).year == 2026  # Testwelt: Schließung am 10.09.2026 (von test_titel)
