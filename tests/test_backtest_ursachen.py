"""Abnahmetest für AP-12c: Ursache der Abweichung je Paar Backtest ↔ Bot
(`analytics.backtest.backtest_auswertung`, rein). Vorlage ist die Pipeline aus
dem früheren Chat (Nutzer 12.10.2026): jedes Paar bekommt GENAU EINE Ursache, in
dieser Prüfreihenfolge — offen, Kontraktzahl, Toleranz, Einstiegszeit,
Strikeauswahl, Exit-Logik, Slippage. Den Effekt abweichender Kontraktzahlen
rechnet die Auswertung zusätzlich heraus.

Schwellen (Annahmen, OF-84): Toleranz 10 USD je Kontrakt; Einstieg „später/
früher" ab mehr als 3 Minuten; Ausstieg „anders" bei verschiedener Art (Verfall
gegen vorzeitig) oder mehr als 5 Minuten Unterschied; Paarung bis 90 Minuten,
eins zu eins.

Welt: Put-Vertikale 100/90 (verkauft/gekauft), je Paar ein eigener Tag 2.3.–9.3.
2026, Backtest „BT" gegen Bot „BOT". Alle Werte USD je Kontrakt:

  P1 2.3.  gleich in allem, Backtest 100, Bot 95        Δ  −5   → toleranz
  P2 3.3.  gleich in allem, Backtest 100, Bot 70        Δ −30   → slippage
  P3 4.3.  Bot steigt 10 Minuten später ein, 100 / 50   Δ −50   → einstiegszeit
  P4 5.3.  Bot mit Strikes 105/95, 100 / 140             Δ +40   → strikeauswahl
  P5 6.3.  Backtest Stop Loss 10:30, Bot Verfall, 100/−100  Δ −200 → exit
  P6 9.3.  Backtest 2 Kontrakte, P/L 100 (50 je Kontrakt);
           Bot 1 Kontrakt, P/L 30                        Δ −20   → kontrakte
  P7 10.3. Backtest offen (Backtest Completed)           → offen (nicht in Δ)
Summe Δ = −5 −30 −50 +40 −200 −20 = −265 = Bot 345 − Backtest 610 (je Kontrakt:
100+100+100+100+100+50 = 550; 95+70+50+140−100+30 = 285 → Δ −265, Gegenprobe
285 − 550 = −265).
Kontrakteffekt P6 = (Kontrakte Bot − Kontrakte Backtest) · Ergebnis Bot je
Kontrakt = (1 − 2) · 30 = −30 USD.
"""

from datetime import date, datetime
from decimal import Decimal as D

from analytics.backtest import LiveZeile, OoZeile, backtest_auswertung
from engine.oo_zuordnung import Eroeffnung, Leg


def _legs(kurz, lang, tag, menge=1):
    return (Leg(menge, "S", "P", D(kurz), tag), Leg(menge, "B", "P", D(lang), tag))


def _oo(nr, tag, uhr, pl, kontrakte=1, kurz=100, lang=90, offen=False, ende=(16, 0),
        grund="Expired"):
    t = date(2026, 3, tag)
    e = Eroeffnung(f"o{nr}", "BT", datetime(2026, 3, tag, *uhr), "SPX", _legs(kurz, lang, t,
                                                                              kontrakte))
    return OoZeile(e, kontrakte, D(pl), offen, geschlossen=datetime(2026, 3, tag, *ende),
                   grund=grund)


def _live(nr, tag, uhr, profit, kontrakte=1, kurz=100, lang=90, ende=(16, 0), ausgelaufen=True):
    t = date(2026, 3, tag)
    e = Eroeffnung(f"l{nr}", "BOT", datetime(2026, 3, tag, *uhr), "SPX", _legs(kurz, lang, t,
                                                                              kontrakte))
    return LiveZeile(e, kontrakte, D(profit), False, ende=datetime(2026, 3, tag, *ende),
                     ausgelaufen=ausgelaufen)


OO = [
    _oo(1, 2, (9, 32), "100"), _oo(2, 3, (9, 32), "100"), _oo(3, 4, (9, 32), "100"),
    _oo(4, 5, (9, 32), "100"),
    _oo(5, 6, (9, 32), "100", ende=(10, 30), grund="Stop Loss"),
    _oo(6, 9, (9, 32), "100", kontrakte=2),
    _oo(7, 10, (9, 32), "-10", offen=True, grund="Backtest Completed"),
]
LIVE = [
    _live(1, 2, (9, 32), "95"), _live(2, 3, (9, 32), "70"),
    _live(3, 4, (9, 42), "50"), _live(4, 5, (9, 32), "140", kurz=105, lang=95),
    _live(5, 6, (9, 32), "-100"), _live(6, 9, (9, 32), "30"),
]
ENTSCHEIDUNG = {("BT", "BOT"): "bestaetigt"}


def _zeile():
    (z,) = [v for v in backtest_auswertung(OO, LIVE, ENTSCHEIDUNG).vergleich]
    return z


def test_summen_und_gegenprobe():
    z = _zeile()
    assert z.paare == 6 and z.offen == 1
    assert (z.summe_backtest, z.summe_live, z.differenz) == (D("550"), D("285"), D("-265"))


def test_ursachen_je_paar_und_summe():
    z = _zeile()
    u = {k: (v.anzahl, v.summe) for k, v in z.ursachen.items()}
    assert u == {
        "toleranz": (1, D("-5")), "slippage": (1, D("-30")), "einstiegszeit": (1, D("-50")),
        "strikeauswahl": (1, D("40")), "exit": (1, D("-200")), "kontrakte": (1, D("-20")),
    }
    assert sum(v.summe for v in z.ursachen.values()) == z.differenz


def test_kontrakteffekt_getrennt():
    assert _zeile().kontrakt_effekt == D("-30")


def test_details_tragen_ursache_und_zeitversatz():
    d = {x.zeit_backtest.day: x for x in _zeile().details if x.art == "paar"}
    assert d[4].ursache == "einstiegszeit" and d[4].zeitversatz_min == 10
    assert d[3].ursache == "slippage" and d[3].zeitversatz_min == 0
    assert d[9].ursache == "kontrakte" and d[9].kontrakt_effekt == D("-30")
