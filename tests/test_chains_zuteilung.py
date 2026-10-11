"""Abnahmetests für AP-04z: Zuteilungen und Wheels gehören zur Kette der Option
(OF-81, Entscheidung des Nutzers vom 11.10.2026: 1 ja, 2 ja, 3 ja).

Vertrag (auftraege/AP-04z.md). Geschrieben durch das starke Modell — für die
Umsetzung unveränderlich. Alle Szenarien frei erfunden, Beträge von Hand.

1. Ein Options-Leg, das per Zuteilung oder Ausübung schließt, setzt seine Kette
   in der dabei gelieferten Aktie fort — unabhängig davon, wie die übrige
   Struktur schließt (Fall #5213: Put zugeteilt, Call verfällt später).
2. Alle Legs der gelieferten Aktie (Teilverkäufe, FIFO-Lots) gehören zur Kette;
   je Leg eine Struktur. Lots anderer Herkunft bleiben, wo sie sind.
3. Zuordnung Aktie ↔ Option über Zeitpunkt und Basiswert; bei mehreren
   gleichzeitigen Zuteilungen entscheidet Preis = Strike.
4. Wheel: Ein Short Call auf denselben Basiswert, eröffnet während die
   zugeteilten Aktien gehalten werden, gehört zur Kette (Erkennung
   `heuristik`), wenn Kontrakte × Multiplikator die gehaltenen Stücke nicht
   übersteigen.
5. Verknüpfungstypen: Aktie `zuteilung` (Erkennung `auto`), Covered Call
   `covered_call`. Beides zählt nicht als Roll.
6. Die Kette endet mit der letzten Schließung (`beendet_am` = späteste
   Schließung, Endzustand nach dieser).
"""

from datetime import date, datetime
from decimal import Decimal

from engine.chains import bilde_chains
from engine.structures import bilde_structures

KONTO = "U7777777"


def _exec(exec_id, *, conid, side, handelszeit, menge="1", preis="0",
          ereignistyp="trade", exec_batch=None):
    return {"exec_id": exec_id, "konto": KONTO, "conid": conid, "side": side,
            "menge": Decimal(menge), "preis": Decimal(preis), "handelszeit": handelszeit,
            "ereignistyp": ereignistyp, "exec_batch": exec_batch, "oa_trade": None,
            "oa_order": None}


def _leg(open_exec_id, close_exec_id, *, conid, menge="1", brutto_pnl=None):
    return {"conid": conid, "open_exec_id": open_exec_id, "close_exec_id": close_exec_id,
            "menge": Decimal(menge), "offen_ja_nein": close_exec_id is None,
            "brutto_pnl": Decimal(brutto_pnl) if brutto_pnl is not None else None,
            "kommission_gesamt": Decimal("0")}


def _opt(conid, underlying, strike, right, expiry):
    return {"conid": conid, "asset_class": "OPT", "underlying": underlying,
            "symbol": f"{underlying} {strike}{right}", "expiry": expiry,
            "strike": Decimal(strike), "right": right, "multiplikator": Decimal("100")}


def _stk(conid, underlying):
    return {"conid": conid, "asset_class": "STK", "underlying": None, "symbol": underlying,
            "expiry": None, "strike": None, "right": None, "multiplikator": Decimal("1")}


def _bilde(legs, executions, instrumente):
    return bilde_chains(bilde_structures(legs, executions, instrumente), legs, executions,
                        instrumente)


def _kette_mit(ergebnis, exec_id):
    treffer = [c for c in ergebnis.chains
               if any(exec_id == k.open_exec_id for g in c.glieder
                      for k in g.structure.leg_schluessel)]
    assert len(treffer) == 1, exec_id
    return treffer[0]


ZUTEILUNG = datetime(2026, 8, 28, 16, 20)


def test_fall_5213_put_zugeteilt_call_verfaellt_spaeter():
    """Short Put 895 + Short Call 807 in einer Order; der Put wird am selben Tag
    zugeteilt (100 Aktien zu 895), der Call verfällt am 30.09., die Aktien werden
    am 01.10. zu 766,89 verkauft.
    Brutto: Put +12.329,00, Call +78,00, Aktie (766,89 − 895)·100 = −12.811,00
    → Kette −404,00."""
    inst = {1: _opt(1, "SPY", "895", "P", date(2026, 9, 30)),
            2: _opt(2, "SPY", "807", "C", date(2026, 9, 30)),
            3: _stk(3, "SPY")}
    ex = [
        _exec("P1", conid=1, side="SELL", preis="123.29", exec_batch="9.1",
              handelszeit=datetime(2026, 8, 28, 11, 52)),
        _exec("C1", conid=2, side="SELL", preis="0.78", exec_batch="9.1",
              handelszeit=datetime(2026, 8, 28, 11, 52)),
        _exec("P2", conid=1, side="BUY", handelszeit=ZUTEILUNG, ereignistyp="assignment"),
        _exec("S1", conid=3, side="BUY", menge="100", preis="895", handelszeit=ZUTEILUNG,
              ereignistyp="assignment"),
        _exec("C2", conid=2, side="BUY", handelszeit=datetime(2026, 9, 30, 16, 20),
              ereignistyp="expiry"),
        _exec("S2", conid=3, side="SELL", menge="100", preis="766.89",
              handelszeit=datetime(2026, 10, 1, 15, 0)),
    ]
    legs = [_leg("P1", "P2", conid=1, brutto_pnl="12329.00"),
            _leg("C1", "C2", conid=2, brutto_pnl="78.00"),
            _leg("S1", "S2", conid=3, menge="100", brutto_pnl="-12811.00")]
    e = _bilde(legs, ex, inst)
    assert len(e.chains) == 1
    k = e.chains[0]
    assert k.brutto_pnl == Decimal("-404.00")
    assert k.endzustand == "Geschlossen"
    assert k.beendet_am == datetime(2026, 10, 1, 15, 0)
    assert k.anzahl_rolls == 0
    aktie = [g for g in k.glieder if g.structure.typ == "Stock"]
    assert [(g.verknuepfungstyp, g.erkennung) for g in aktie] == [("zuteilung", "auto")]


def test_teilverkaeufe_gehoeren_alle_zur_kette():
    """200 Aktien zugeteilt, verkauft in zwei Teilen zu je 100 (10.09., 20.09.)."""
    inst = {1: _opt(1, "ABC", "50", "P", date(2026, 8, 21)), 3: _stk(3, "ABC")}
    z = datetime(2026, 8, 21, 16, 20)
    ex = [
        _exec("P1", conid=1, side="SELL", menge="2", preis="1.00",
              handelszeit=datetime(2026, 8, 1, 10, 0)),
        _exec("P2", conid=1, side="BUY", menge="2", handelszeit=z, ereignistyp="assignment"),
        _exec("S1", conid=3, side="BUY", menge="200", preis="50", handelszeit=z,
              ereignistyp="assignment"),
        _exec("S2", conid=3, side="SELL", menge="100", preis="52",
              handelszeit=datetime(2026, 9, 10, 15, 0)),
        _exec("S3", conid=3, side="SELL", menge="100", preis="48",
              handelszeit=datetime(2026, 9, 20, 15, 0)),
    ]
    legs = [_leg("P1", "P2", conid=1, menge="2", brutto_pnl="200.00"),
            _leg("S1", "S2", conid=3, menge="100", brutto_pnl="200.00"),
            _leg("S1", "S3", conid=3, menge="100", brutto_pnl="-200.00")]
    e = _bilde(legs, ex, inst)
    assert len(e.chains) == 1
    k = e.chains[0]
    assert len([g for g in k.glieder if g.verknuepfungstyp == "zuteilung"]) == 2
    assert k.brutto_pnl == Decimal("200.00")
    assert k.beendet_am == datetime(2026, 9, 20, 15, 0)
    assert k.anzahl_rolls == 0


def test_offene_aktie_haelt_die_kette_offen():
    inst = {1: _opt(1, "ABC", "50", "P", date(2026, 8, 21)), 3: _stk(3, "ABC")}
    z = datetime(2026, 8, 21, 16, 20)
    ex = [_exec("P1", conid=1, side="SELL", preis="1.00", handelszeit=datetime(2026, 8, 1, 10)),
          _exec("P2", conid=1, side="BUY", handelszeit=z, ereignistyp="assignment"),
          _exec("S1", conid=3, side="BUY", menge="100", preis="50", handelszeit=z,
                ereignistyp="assignment")]
    legs = [_leg("P1", "P2", conid=1, brutto_pnl="100.00"),
            _leg("S1", None, conid=3, menge="100")]
    k = _bilde(legs, ex, inst).chains[0]
    assert k.endzustand == "Offen" and k.beendet_am is None and k.brutto_pnl is None


def test_lot_anderer_herkunft_bleibt_eigene_kette():
    """100 Aktien früher gekauft (T0), 100 zugeteilt (S1), 200 in einem Verkauf
    (X): FIFO teilt in (T0→X) und (S1→X). Nur (S1→X) gehört zur Optionskette."""
    inst = {1: _opt(1, "ABC", "50", "P", date(2026, 8, 21)), 3: _stk(3, "ABC")}
    z = datetime(2026, 8, 21, 16, 20)
    ex = [_exec("T0", conid=3, side="BUY", menge="100", preis="55",
                handelszeit=datetime(2026, 7, 1, 10)),
          _exec("P1", conid=1, side="SELL", preis="1.00", handelszeit=datetime(2026, 8, 1, 10)),
          _exec("P2", conid=1, side="BUY", handelszeit=z, ereignistyp="assignment"),
          _exec("S1", conid=3, side="BUY", menge="100", preis="50", handelszeit=z,
                ereignistyp="assignment"),
          _exec("X", conid=3, side="SELL", menge="200", preis="53",
                handelszeit=datetime(2026, 9, 1, 15))]
    legs = [_leg("T0", "X", conid=3, menge="100", brutto_pnl="-200.00"),
            _leg("P1", "P2", conid=1, brutto_pnl="100.00"),
            _leg("S1", "X", conid=3, menge="100", brutto_pnl="300.00")]
    e = _bilde(legs, ex, inst)
    assert len(e.chains) == 2
    assert _kette_mit(e, "P1").brutto_pnl == Decimal("400.00")
    assert _kette_mit(e, "T0").brutto_pnl == Decimal("-200.00")


def test_gleichzeitige_zuteilungen_nach_strike():
    """Zwei Puts desselben Basiswerts (50 und 45) werden zur selben Zeit
    zugeteilt; die Aktienbuchungen stehen in umgekehrter Reihenfolge."""
    inst = {1: _opt(1, "ABC", "50", "P", date(2026, 8, 21)),
            2: _opt(2, "ABC", "45", "P", date(2026, 8, 21)), 3: _stk(3, "ABC")}
    z = datetime(2026, 8, 21, 16, 20)
    ex = [_exec("A1", conid=1, side="SELL", preis="2.00", handelszeit=datetime(2026, 8, 1, 10)),
          _exec("B1", conid=2, side="SELL", preis="1.00", handelszeit=datetime(2026, 8, 2, 10)),
          _exec("A2", conid=1, side="BUY", handelszeit=z, ereignistyp="assignment"),
          _exec("B2", conid=2, side="BUY", handelszeit=z, ereignistyp="assignment"),
          _exec("SB", conid=3, side="BUY", menge="100", preis="45", handelszeit=z,
                ereignistyp="assignment"),
          _exec("SA", conid=3, side="BUY", menge="100", preis="50", handelszeit=z,
                ereignistyp="assignment")]
    legs = [_leg("A1", "A2", conid=1, brutto_pnl="200.00"),
            _leg("B1", "B2", conid=2, brutto_pnl="100.00"),
            _leg("SA", None, conid=3, menge="100"),
            _leg("SB", None, conid=3, menge="100")]
    e = _bilde(legs, ex, inst)
    assert len(e.chains) == 2
    a = _kette_mit(e, "A1")
    assert any(k.open_exec_id == "SA" for g in a.glieder for k in g.structure.leg_schluessel)
    b = _kette_mit(e, "B1")
    assert any(k.open_exec_id == "SB" for g in b.glieder for k in g.structure.leg_schluessel)


def test_ausuebung_eines_long_calls():
    inst = {1: _opt(1, "ABC", "40", "C", date(2026, 8, 21)), 3: _stk(3, "ABC")}
    z = datetime(2026, 8, 21, 16, 20)
    ex = [_exec("L1", conid=1, side="BUY", preis="3.00", handelszeit=datetime(2026, 8, 1, 10)),
          _exec("L2", conid=1, side="SELL", handelszeit=z, ereignistyp="exercise"),
          _exec("S1", conid=3, side="BUY", menge="100", preis="40", handelszeit=z,
                ereignistyp="exercise")]
    legs = [_leg("L1", "L2", conid=1, brutto_pnl="-300.00"),
            _leg("S1", None, conid=3, menge="100")]
    e = _bilde(legs, ex, inst)
    assert len(e.chains) == 1
    assert [g.verknuepfungstyp for g in e.chains[0].glieder] == ["open", "zuteilung"]


def _wheel(call_menge="1", call_offen=datetime(2026, 8, 24, 10), call_basis="ABC"):
    """Put 50 zugeteilt am 21.08. (100 Aktien), Covered Call 55 verkauft
    (verfällt 18.09.), zweiter Covered Call 55 am 21.09., zugeteilt am 16.10.:
    Aktien zu 55 geliefert.
    Brutto: Put +100, Call 1 +80, Call 2 +60, Aktie (55 − 50)·100 = +500 → +740."""
    inst = {1: _opt(1, "ABC", "50", "P", date(2026, 8, 21)),
            2: _opt(2, call_basis, "55", "C", date(2026, 9, 18)),
            4: _opt(4, "ABC", "55", "C", date(2026, 10, 16)),
            3: _stk(3, "ABC")}
    z1 = datetime(2026, 8, 21, 16, 20)
    z2 = datetime(2026, 10, 16, 16, 20)
    ex = [_exec("P1", conid=1, side="SELL", preis="1.00", handelszeit=datetime(2026, 8, 1, 10)),
          _exec("P2", conid=1, side="BUY", handelszeit=z1, ereignistyp="assignment"),
          _exec("S1", conid=3, side="BUY", menge="100", preis="50", handelszeit=z1,
                ereignistyp="assignment"),
          _exec("C1", conid=2, side="SELL", menge=call_menge, preis="0.80", handelszeit=call_offen),
          _exec("C2", conid=2, side="BUY", menge=call_menge,
                handelszeit=datetime(2026, 9, 18, 16, 20), ereignistyp="expiry"),
          _exec("D1", conid=4, side="SELL", preis="0.60", handelszeit=datetime(2026, 9, 21, 10)),
          _exec("D2", conid=4, side="BUY", handelszeit=z2, ereignistyp="assignment"),
          _exec("S2", conid=3, side="SELL", menge="100", preis="55", handelszeit=z2,
                ereignistyp="assignment")]
    legs = [_leg("P1", "P2", conid=1, brutto_pnl="100.00"),
            _leg("C1", "C2", conid=2, menge=call_menge, brutto_pnl="80.00"),
            _leg("D1", "D2", conid=4, brutto_pnl="60.00"),
            _leg("S1", "S2", conid=3, menge="100", brutto_pnl="500.00")]
    return _bilde(legs, ex, inst)


def test_wheel_ist_eine_position():
    e = _wheel()
    assert len(e.chains) == 1
    k = e.chains[0]
    assert k.brutto_pnl == Decimal("740.00")
    assert k.endzustand == "Assigned"
    assert k.beendet_am == datetime(2026, 10, 16, 16, 20)
    assert k.anzahl_rolls == 0
    calls = [(g.verknuepfungstyp, g.erkennung) for g in k.glieder
             if g.structure.rechte == frozenset({"C"})]
    assert calls == [("covered_call", "heuristik"), ("covered_call", "heuristik")]


def test_call_vor_der_zuteilung_ist_kein_covered_call():
    e = _wheel(call_offen=datetime(2026, 8, 10, 10))
    assert len(e.chains) == 2
    assert _kette_mit(e, "C1") is not _kette_mit(e, "P1")


def test_zu_viele_calls_sind_kein_covered_call():
    """Zwei Kontrakte (200 Stück) auf 100 gehaltene Aktien."""
    e = _wheel(call_menge="2")
    assert _kette_mit(e, "C1") is not _kette_mit(e, "P1")
    assert _kette_mit(e, "D1") is _kette_mit(e, "P1")


def test_call_auf_anderen_basiswert_ist_kein_covered_call():
    e = _wheel(call_basis="XYZ")
    assert _kette_mit(e, "C1") is not _kette_mit(e, "P1")
