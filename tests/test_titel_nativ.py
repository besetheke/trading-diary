"""Titel in der Währung der Geschäfte und ohne Kommission (17.10.2026).

Von Hand gerechnet, alles USD, Buchungskurs 0,9, Kommission je Ausführung −1,00:
  Lose Aktie ABC: BUY 100 @ 100 = −10.000 − 1 ; SELL 100 @ 110 = +11.000 − 1
    nativ: netto 998,00; Kommission −2,00; ohne Kommission 1.000,00
    EUR:   netto 998 × 0,9 = 898,20; Kommission −2 × 0,9 = −1,80
  Offene Aktie OFF: BUY 100 @ 50 (Kommission −1); IBs Marktwert 4.800 USD, Kurs 0,9
    nativ unrealisiert: 4.800 − (5.000 + 1) = −201,00 (Einstand samt Kommission)
"""
from datetime import date, datetime
from decimal import Decimal

from analytics.titel import titel_auswertung

D = Decimal
T0 = datetime(2026, 9, 1, 10, 0)
T1 = datetime(2026, 9, 10, 10, 0)


def _ex(exec_id, conid, side, menge, preis):
    return {"exec_id": exec_id, "conid": conid, "side": side, "menge": D(menge), "preis": D(preis),
            "waehrung": "USD", "kommission": D("-1"), "kommission_waehrung": "USD",
            "buchungskurs": D("0.9"), "handelszeit": T0 if side == "BUY" else T1,
            "qualitaetsstufe": "A", "ereignistyp": "trade", "schlusskurs": None}


def _leg(conid, offen, zu, menge):
    return {"structure_id": None, "conid": conid, "open_exec_id": offen, "close_exec_id": zu,
            "menge": D(menge), "open_faktor": D(1), "close_faktor": D(1), "brutto_pnl": None,
            "kommission_gesamt": D("-1") if zu is None else None}


def _instr(conid, underlying):
    return {"conid": conid, "multiplikator": D(1), "abwicklungsart": None, "underlying": underlying,
            "asset_class": "STK", "symbol": underlying}


def _lauf():
    ausf = [_ex("B1", 1, "BUY", 100, "100"), _ex("S1", 1, "SELL", 100, "110"),
            _ex("O1", 2, "BUY", 100, "50")]
    beine = [_leg(1, "B1", "S1", "100"), _leg(2, "O1", None, "100")]
    bestand = {2: {"menge": D(100), "wert": D("4800"), "kurs": D("0.9")}}
    zeilen = titel_auswertung([], [], [], beine, ausf, [_instr(1, "ABC"), _instr(2, "OFF")],
                              bestand, date(2026, 10, 12))
    return {z.basiswert: z for z in zeilen}


def test_original_waehrung_und_kommission():
    n = _lauf()["ABC"].nativ["USD"]
    assert n.realisiert == D("998")
    assert n.kommission == D("-2")
    assert n.realisiert - n.kommission == D("1000")                 # „ohne Kommission“
    assert n.je_klasse["STK"] == [D("998"), D("-2")]


def test_eur_stimmt_mit_der_nativen_rechnung_ueberein():
    z = _lauf()["ABC"]
    assert z.realisiert_eur == D("898.20")
    assert z.kommission_eur == D("-1.80")
    assert z.kommission_je_klasse == {"STK": D("-1.80")}


def test_unrealisiert_in_originalwaehrung():
    z = _lauf()["OFF"]
    assert z.nativ["USD"].unrealisiert == D("-201")
    assert z.unrealisiert_eur == D("-180.90")                      # −201 × 0,9
