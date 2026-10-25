# ruff: noqa: E501
"""M07 (AP-17g): Abweichungen als Indizien, nicht als bewiesene Ursache.

Welt wie in test_backtest_ursachen (Backtest „BT“ gegen Bot „BOT“, je Paar ein Tag, Werte USD je Kontrakt):
  A 2.3.  Bot steigt 10 Min später ein UND der Backtest steigt per Stop Loss aus, der Bot per Verfall; 100 / 50
          → erste Ursache „einstiegszeit“; beobachtet sind beide: einstiegszeit und exit_art
  B 3.3.  alles gleich, nur 100 / 70                      → kein Unterschied gefunden: ungeklärter Rest
  C 4.3.  2 gegen 1 Kontrakt UND andere Strikes (105/95)  → erste Ursache „kontrakte“, beobachtet kontrakte und strikeauswahl
  D 5.3.  Backtest Stop Loss 10:30, Bot Rückkauf 10:45, 100 / 95 (Δ −5, in Toleranz) → Ursache „toleranz“, beobachtet exit_zeit
Mehrfach abweichend (mindestens zwei beobachtete Unterschiede): A und C = 2 Paare.
"""
from test_api_backtests import IC, klient  # noqa: F401
from test_backtest_ursachen import _live, _oo

from analytics.backtest import backtest_auswertung

OO = [
    _oo(1, 2, (9, 32), "100", ende=(10, 30), grund="Stop Loss"),
    _oo(2, 3, (9, 32), "100"),
    _oo(3, 4, (9, 32), "100", kontrakte=2),
    _oo(4, 5, (9, 32), "100", ende=(10, 30), grund="Stop Loss"),
]
LIVE = [
    _live(1, 2, (9, 42), "50"),
    _live(2, 3, (9, 32), "70"),
    _live(3, 4, (9, 32), "30", kurz=105, lang=95),
    _live(4, 5, (9, 32), "95", ende=(10, 45), ausgelaufen=False),
]
ENTSCHEIDUNG = {("BT", "BOT"): "bestaetigt"}


def paare():
    (z,) = backtest_auswertung(OO, LIVE, ENTSCHEIDUNG).vergleich
    return z, {d.oa_trade: d for d in z.details if d.art == "paar"}


def test_einstieg_und_exit_zeigen_beide_tatsachen():
    z, d = paare()
    a = d["l1"]
    assert a.ursache == "einstiegszeit"                                   # die erste erkannte Abweichung
    assert a.abweichungen == ("einstiegszeit", "exit_art") and a.rest_unerklaert is False
    assert (a.ausstieg_backtest, a.ausstieg_live) == ("vorzeitig", "verfall")
    assert a.partner_herkunft == "zeitfenster"


def test_ohne_gefundenen_unterschied_bleibt_der_rest_ungeklaert():
    _, d = paare()
    b = d["l2"]
    assert b.ursache == "slippage" and b.abweichungen == () and b.rest_unerklaert is True
    assert (b.ausstieg_backtest, b.ausstieg_live) == ("verfall", "verfall")


def test_kontraktzahl_und_strikes_gleichzeitig():
    _, d = paare()
    c = d["l3"]
    assert c.ursache == "kontrakte" and c.abweichungen == ("kontrakte", "strikeauswahl")


def test_kleine_differenz_mit_beobachtetem_ausstiegsunterschied():
    _, d = paare()
    x = d["l4"]
    assert x.ursache == "toleranz" and x.abweichungen == ("exit_zeit",) and x.rest_unerklaert is False
    assert (x.ausstieg_backtest, x.ausstieg_live) == ("vorzeitig", "rueckkauf")


def test_mehrfach_abweichende_paare_werden_gezaehlt_und_die_summe_bleibt():
    z, d = paare()
    assert z.mehrfach_abweichend == 2
    # die bisherige Eigenschaft bleibt: je Paar genau eine (erste) Ursache, Summe der Ursachen = Differenz
    assert sum(u.summe for u in z.ursachen.values()) == z.differenz
    assert set(z.ursachen) == {"einstiegszeit", "slippage", "kontrakte", "toleranz"}


def test_api_liefert_die_indizien_felder(klient):  # noqa: F811
    paare_antwort = klient.get("/backtests/paare", params={"oo_strategie": IC, "oa_strategie": "SPX: IC +Vo/n"}).json()
    paare_zeilen = [p for p in paare_antwort if p["art"] == "paar"]
    assert paare_zeilen
    for p in paare_zeilen:
        assert {"abweichungen", "rest_unerklaert", "ausstieg_backtest", "ausstieg_live", "partner_herkunft"} <= set(p)
        assert p["partner_herkunft"] == "zeitfenster" and isinstance(p["abweichungen"], list)
