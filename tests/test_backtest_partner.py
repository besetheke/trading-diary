# ruff: noqa: E501
"""M07 Rest (AP-17g): Partner eines Backtest-Trades korrigieren und Fillpreis-Analyse des Einstiegs, von Hand gerechnet.

Reine Auswertung (Welt aus test_backtest_ursachen, Backtest „BT“ gegen Bot „BOT“, USD je Kontrakt):
  o1 2.3. 9:32 Prämie 200, Bot l1 2.3. 9:32 Fills 180 → Einstiegsabweichung 180 - 200 = -20
  o2 3.3. 9:32 Prämie 150, Bot l2 3.3. 9:32 Fills 155 → +5          Summe -15 über 2 Paare
Korrektur: zusätzlicher Bot-Trade l1b 2.3. 9:40 (Fills 190, Gewinn 40). Ohne Korrektur gehört l1 zu o1 (näher). Mit Korrektur o1 → l1b:
  Paar o1/l1b: Backtest 100, Bot 40 → Δ -60; Einstieg 190 - 200 = -10; l1 bleibt als „nur_live“ stehen.
  Korrektur o1 → kein Partner: o1 „nur_backtest“, l1 und l1b „nur_live“.

Mit API-Welt (test_api_backtests): R3 hat 208 Minuten Abstand zu 7003 (außerhalb der Paarung). Korrigiert R3 → 7003: Paar Backtest 200, Bot 100.
  Summe Backtest 224 - 500 + 200 = -76, Bot 210 - 550 + 100 = -240 → Δ -164 (zuvor -64, nur_backtest 1 und nur_live 1 entfallen).
"""
from dataclasses import replace
from decimal import Decimal
from decimal import Decimal as D

from test_api_backtests import IC, klient  # noqa: F401
from test_backtest_ursachen import _live, _oo

from analytics.backtest import backtest_auswertung

ENTSCHEIDUNG = {("BT", "BOT"): "bestaetigt"}


def welt():
    oo = [replace(_oo(1, 2, (9, 32), "100"), praemie=D(200)), replace(_oo(2, 3, (9, 32), "100"), praemie=D(150))]
    live = [
        replace(_live(1, 2, (9, 32), "80"), einstiegspraemie=D(180)),
        replace(_live(2, 3, (9, 32), "100"), einstiegspraemie=D(155)),
        replace(_live("1b", 2, (9, 40), "40"), einstiegspraemie=D(190)),
    ]
    return oo, live


def detail(z):
    return {(d.art, d.oa_trade): d for d in z.details}


def test_fillpreise_des_einstiegs_werden_je_paar_und_in_summe_gezeigt():
    oo, live = welt()
    (z,) = backtest_auswertung(oo, live, ENTSCHEIDUNG).vergleich
    d = detail(z)
    assert d[("paar", "l1")].einstieg_abweichung == D(-20) and d[("paar", "l2")].einstieg_abweichung == D(5)
    assert (d[("paar", "l1")].praemie_backtest, d[("paar", "l1")].praemie_live) == (D(200), D(180))
    assert (z.summe_einstieg_abweichung, z.anzahl_einstieg) == (D(-15), 2)


def test_ohne_praemie_auf_einer_seite_keine_abweichung():
    oo, live = welt()
    live[0] = replace(live[0], einstiegspraemie=None)
    (z,) = backtest_auswertung(oo, live, ENTSCHEIDUNG).vergleich
    assert detail(z)[("paar", "l1")].einstieg_abweichung is None
    assert (z.summe_einstieg_abweichung, z.anzahl_einstieg) == (D(5), 1)


def test_korrigierter_partner_ersetzt_die_zeitfensterpaarung():
    oo, live = welt()
    (z,) = backtest_auswertung(oo, live, ENTSCHEIDUNG, {"o1": "l1b"}).vergleich
    d = detail(z)
    paar = d[("paar", "l1b")]
    assert (paar.pl_backtest, paar.pl_live, paar.differenz) == (D(100), D(40), D(-60))
    assert paar.partner_herkunft == "manuell" and paar.einstieg_abweichung == D(-10) and paar.oo_trade == "o1"
    assert d[("paar", "l2")].partner_herkunft == "zeitfenster"
    assert ("nur_live", "l1") in d and ("paar", "l1") not in d
    assert z.anzahl_korrigiert == 1 and z.paare == 2


def test_kein_partner_ist_eine_ausdrueckliche_entscheidung():
    oo, live = welt()
    (z,) = backtest_auswertung(oo, live, ENTSCHEIDUNG, {"o1": None}).vergleich
    d = detail(z)
    assert ("nur_backtest", None) in d and d[("nur_backtest", None)].oo_trade == "o1" and d[("nur_backtest", None)].partner_herkunft == "manuell"
    assert {"l1", "l1b"} == {oa for art, oa in d if art == "nur_live"}
    assert z.paare == 1


def test_unbekannter_partner_wird_ignoriert():
    oo, live = welt()
    (z,) = backtest_auswertung(oo, live, ENTSCHEIDUNG, {"o1": "gibt-es-nicht"}).vergleich
    assert z.anzahl_korrigiert == 0 and detail(z)[("paar", "l1")].partner_herkunft == "zeitfenster"


def test_ohne_korrekturen_bleibt_alles_wie_vorher():
    oo, live = welt()
    assert backtest_auswertung(oo, live, ENTSCHEIDUNG).vergleich == backtest_auswertung(oo, live, ENTSCHEIDUNG, {}).vergleich


# ------------------------------------------------------------------------------------------------ API


def _ic(klient, **p):  # noqa: F811
    zeilen = {z["oo_strategie"]: z for z in klient.get("/backtests").json()["vergleich"]}
    return zeilen[IC]


def _details(klient):  # noqa: F811
    return klient.get("/backtests/paare", params={"oo_strategie": IC, "oa_strategie": "SPX: IC +Vo/n"}).json()


def test_api_korrigiert_den_partner_und_nimmt_ihn_zurueck(klient):  # noqa: F811
    vorher = _ic(klient)
    assert (vorher["paare"], vorher["nur_backtest"], vorher["nur_live"], Decimal(vorher["differenz"])) == (2, 1, 1, Decimal("-64"))
    r3 = next(d for d in _details(klient) if d["art"] == "nur_backtest")
    kandidaten = klient.get("/backtests/partner-kandidaten", params={"oo_trade": r3["oo_trade"], "oa_strategie": "SPX: IC +Vo/n"}).json()
    assert "7003" in {k["oa_trade"] for k in kandidaten}

    antwort = klient.post("/journal/backtests/partner", json={"oo_trade": int(r3["oo_trade"]), "oa_strategie": "SPX: IC +Vo/n", "oa_trade": "7003", "begruendung": "gleicher Trade, späterer Einstieg"})
    assert antwort.status_code == 200 and antwort.json()["erkennung"] == "manuell"
    nachher = _ic(klient)
    assert (nachher["paare"], nachher["nur_backtest"], nachher["nur_live"], nachher["anzahl_korrigiert"], Decimal(nachher["differenz"])) == (3, 0, 0, 1, Decimal("-164"))
    assert next(d for d in _details(klient) if d["oa_trade"] == "7003")["partner_herkunft"] == "manuell"

    assert klient.post("/journal/backtests/partner/zuruecknehmen", json={"oo_trade": int(r3["oo_trade"])}).status_code == 200
    zurueck = _ic(klient)
    assert (zurueck["paare"], zurueck["nur_backtest"], zurueck["nur_live"], Decimal(zurueck["differenz"])) == (2, 1, 1, Decimal("-64"))
    assert klient.post("/journal/backtests/partner/zuruecknehmen", json={"oo_trade": int(r3["oo_trade"])}).status_code == 404       # nichts mehr zurückzunehmen


def test_api_prueft_die_eingaben(klient):  # noqa: F811
    r3 = next(d for d in _details(klient) if d["art"] == "nur_backtest")
    assert klient.post("/journal/backtests/partner", json={"oo_trade": 999999, "oa_strategie": "SPX: IC +Vo/n", "oa_trade": None}).status_code == 404
    falsch = klient.post("/journal/backtests/partner", json={"oo_trade": int(r3["oo_trade"]), "oa_strategie": "SPX: IC +Vo/n", "oa_trade": "7004"})   # gehört zu XSP: IF
    assert falsch.status_code == 409
    assert klient.get("/backtests/partner-kandidaten", params={"oo_trade": 999999, "oa_strategie": "x"}).status_code == 404
