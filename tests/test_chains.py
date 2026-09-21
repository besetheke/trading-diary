"""Abnahmetests für AP-04, Teil 2: Structures → Chains (`engine/chains.py`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das günstige
Modell unveränderlich, wie `tests/test_structures.py`. Maßgeblich ist die
Erkennungsreihenfolge in `plan/trading-journal-projektplan.md`, § 6,
Abschnitt AP-04, Schritte 2a–4; der Modul-Docstring von `engine/chains.py`
trägt die Kurzfassung samt der dokumentierten Annahmen (OF-35).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from engine.chains import bilde_chains
from engine.structures import bilde_structures

KONTO = "U7777777"


def _exec(
    exec_id,
    *,
    conid,
    side,
    menge="1",
    handelszeit,
    ereignistyp="trade",
    exec_batch=None,
    oa_trade=None,
    oa_order=None,
) -> dict:
    return {
        "exec_id": exec_id,
        "konto": KONTO,
        "conid": conid,
        "side": side,
        "menge": Decimal(menge),
        "handelszeit": handelszeit,
        "ereignistyp": ereignistyp,
        "exec_batch": exec_batch,
        "oa_trade": oa_trade,
        "oa_order": oa_order,
    }


def _leg(
    open_exec_id,
    close_exec_id,
    *,
    conid,
    menge="1",
    offen_ja_nein=True,
    brutto_pnl=None,
    kommission_gesamt="0",
) -> dict:
    return {
        "conid": conid,
        "open_exec_id": open_exec_id,
        "close_exec_id": close_exec_id,
        "menge": Decimal(menge),
        "offen_ja_nein": offen_ja_nein,
        "brutto_pnl": Decimal(brutto_pnl) if brutto_pnl is not None else None,
        "kommission_gesamt": Decimal(kommission_gesamt),
    }


def _instrument(conid, *, asset_class, underlying, expiry=None, strike=None, right=None) -> dict:
    return {
        "conid": conid,
        "asset_class": asset_class,
        "underlying": underlying,
        "expiry": expiry,
        "strike": Decimal(strike) if strike is not None else None,
        "right": right,
    }


def _bilde(legs, executions, instrumente):
    struktur = bilde_structures(legs, executions, instrumente)
    return bilde_chains(struktur, legs, executions, instrumente)


# ---------------------------------------------------------------------------
# OA-Trade als Kettenidentität über oa_order-Grenzen hinweg (Roll)
# ---------------------------------------------------------------------------


def test_gleicher_oa_trade_unterschiedliche_oa_order_bildet_eine_kette_mit_roll():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4950", right="P"),
        701: _instrument(701, asset_class="OPT", underlying="SPX", expiry=date(2026, 10, 16),
                          strike="5000", right="P"),
        702: _instrument(702, asset_class="OPT", underlying="SPX", expiry=date(2026, 10, 16),
                          strike="4950", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
        _exec("E3", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
        _exec("E4", conid=602, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
        _exec("E5", conid=701, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
        _exec("E6", conid=702, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert chain.anzahl_rolls == 1
    assert chain.underlying == "SPX"
    assert chain.seite == "Put"
    assert [g.verknuepfungstyp for g in chain.glieder] == ["open", "roll"]
    assert chain.endzustand == "Offen"


def test_gleiche_ordernummer_unter_verschiedenen_oa_trades_bleibt_getrennte_kette():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        701: _instrument(701, asset_class="OPT", underlying="RUT", expiry=date(2026, 9, 18),
                          strike="2000", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
        _exec("E2", conid=701, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="20", oa_order="1"),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=701)]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 2
    assert {c.underlying for c in ergebnis.chains} == {"SPX", "RUT"}
    assert all(c.anzahl_rolls == 0 for c in ergebnis.chains)


# ---------------------------------------------------------------------------
# Zuteilungsübergang (Schritt 2a) — Pflichttest
# ---------------------------------------------------------------------------


def test_zugeteilte_option_und_aktienposition_liegen_in_derselben_kette():
    """Pflichttest (§6): eine zugeteilte Option und die daraus entstandene
    Aktienposition liegen in derselben Kette."""
    zeit_zuteilung = datetime(2026, 8, 21, 21, 0, 0)
    instrumente = {
        500: _instrument(500, asset_class="OPT", underlying="IDX5", expiry=date(2026, 8, 21),
                          strike="50", right="P"),
        501: _instrument(501, asset_class="STK", underlying="IDX5"),
    }
    executions = [
        _exec("O1", conid=500, side="SELL", handelszeit=datetime(2026, 8, 1, 10, 0, 0)),
        _exec("O2", conid=500, side="BUY", handelszeit=zeit_zuteilung,
              ereignistyp="assignment"),
        _exec("S1", conid=501, side="BUY", handelszeit=zeit_zuteilung,
              ereignistyp="assignment"),
        _exec("S2", conid=501, side="SELL", handelszeit=datetime(2026, 9, 5, 15, 0, 0)),
    ]
    legs = [
        _leg("O1", "O2", conid=500, offen_ja_nein=False, brutto_pnl="-500.00"),
        _leg("S1", "S2", conid=501, menge="100", offen_ja_nein=False, brutto_pnl="300.00"),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert chain.underlying == "IDX5"
    assert len(chain.glieder) == 2
    typen = {g.structure.typ for g in chain.glieder}
    assert typen == {"Single", "Stock"}
    assert chain.endzustand == "Geschlossen"
    assert chain.beendet_am == datetime(2026, 9, 5, 15, 0, 0)


def test_zuteilung_ohne_aktiengegenbuchung_bleibt_eigene_kette_mit_endzustand_assigned():
    """Barausgleich (kein Aktienbein) — die Kette endet an der Option selbst,
    endzustand `Assigned`."""
    instrumente = {
        500: _instrument(500, asset_class="OPT", underlying="SPX", expiry=date(2026, 8, 21),
                          strike="5000", right="P"),
    }
    executions = [
        _exec("O1", conid=500, side="SELL", handelszeit=datetime(2026, 8, 1, 10, 0, 0)),
        _exec("O2", conid=500, side="BUY", handelszeit=datetime(2026, 8, 21, 21, 0, 0),
              ereignistyp="assignment"),
    ]
    legs = [_leg("O1", "O2", conid=500, offen_ja_nein=False, brutto_pnl="-500.00")]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert len(chain.glieder) == 1
    assert chain.endzustand == "Assigned"


# ---------------------------------------------------------------------------
# Verfall — Pflichttest
# ---------------------------------------------------------------------------


def test_verfall_schliesst_ohne_folgeposition():
    """Pflichttest (§6): ein Verfall schließt die betroffenen Legs zu null,
    ohne eine Folgeposition zu erzeugen."""
    instrumente = {
        500: _instrument(500, asset_class="OPT", underlying="SPX", expiry=date(2026, 8, 21),
                          strike="5000", right="P"),
    }
    executions = [
        _exec("O1", conid=500, side="SELL", handelszeit=datetime(2026, 8, 1, 10, 0, 0)),
        _exec("O2", conid=500, side="BUY", menge="1", handelszeit=datetime(2026, 8, 21, 21, 0, 0),
              ereignistyp="expiry"),
    ]
    legs = [_leg("O1", "O2", conid=500, offen_ja_nein=False, brutto_pnl="0.00")]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert len(chain.glieder) == 1
    assert chain.endzustand == "Verfall"
    assert chain.anzahl_rolls == 0


# ---------------------------------------------------------------------------
# Futures-Rolls (Schritt 3)
# ---------------------------------------------------------------------------


def test_futures_roll_in_einer_order_ueber_gemeinsamen_exec_batch():
    """Futures verketten sich automatisch nur über Schritt 1 (derselbe
    exec_batch, Nutzer 19.09.2026) — Front-Monat-Schließung und
    Back-Monat-Eröffnung in derselben Combo-Ausführung."""
    instrumente = {
        900: _instrument(900, asset_class="FUT", underlying="ES", expiry=date(2026, 9, 19)),
        901: _instrument(901, asset_class="FUT", underlying="ES", expiry=date(2026, 12, 19)),
    }
    executions = [
        _exec("F1", conid=900, side="BUY", handelszeit=datetime(2026, 8, 1, 10, 0, 0)),
        _exec("F2", conid=900, side="SELL", handelszeit=datetime(2026, 9, 15, 14, 0, 0),
              exec_batch="5.20"),
        _exec("F3", conid=901, side="BUY", handelszeit=datetime(2026, 9, 15, 14, 0, 0),
              exec_batch="5.20"),
    ]
    legs = [
        _leg("F1", "F2", conid=900, offen_ja_nein=False, brutto_pnl="1000.00"),
        _leg("F3", None, conid=901),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert chain.anzahl_rolls == 1
    assert [g.structure.typ for g in chain.glieder] == ["Future", "Future"]


def test_futures_ohne_gemeinsamen_exec_batch_bleibt_getrennt_trotz_naher_zeit():
    """Kein Zeitfenster-Fallback für Futures (Schritt 3, Nutzer 19.09.2026):
    Front-Monat-Schließung und Back-Monat-Eröffnung am selben Handelstag,
    aber ohne gemeinsamen exec_batch, verketten sich nicht automatisch —
    das wäre höchstens ein manuell zu bestätigender Kandidat."""
    instrumente = {
        900: _instrument(900, asset_class="FUT", underlying="ES", expiry=date(2026, 9, 19)),
        901: _instrument(901, asset_class="FUT", underlying="ES", expiry=date(2026, 12, 19)),
    }
    executions = [
        _exec("F1", conid=900, side="BUY", handelszeit=datetime(2026, 8, 1, 10, 0, 0)),
        _exec("F2", conid=900, side="SELL", handelszeit=datetime(2026, 9, 15, 14, 0, 0)),
        _exec("F3", conid=901, side="BUY", handelszeit=datetime(2026, 9, 15, 14, 0, 30)),
    ]
    legs = [
        _leg("F1", "F2", conid=900, offen_ja_nein=False, brutto_pnl="1000.00"),
        _leg("F3", None, conid=901),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 2
    assert all(c.anzahl_rolls == 0 for c in ergebnis.chains)


# ---------------------------------------------------------------------------
# Options-Roll ohne OA-Referenz (Schritte 1 und 2)
# ---------------------------------------------------------------------------


def test_options_roll_in_einer_order_ueber_gemeinsamen_exec_batch():
    """Regelfall für Rolls ohne OA-Referenz (Nutzer 19.09.2026): eine
    Combo-Ausführung schließt die alte und eröffnet die neue Structure."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="DAX", expiry=date(2026, 9, 18),
                          strike="19000", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="DAX", expiry=date(2026, 9, 18),
                          strike="18900", right="P"),
        701: _instrument(701, asset_class="OPT", underlying="DAX", expiry=date(2026, 10, 16),
                          strike="18800", right="P"),
        702: _instrument(702, asset_class="OPT", underlying="DAX", expiry=date(2026, 10, 16),
                          strike="18700", right="P"),
    }
    zeit_roll = datetime(2026, 9, 15, 15, 0, 0)
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="3.1"),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="3.1"),
        _exec("E3", conid=601, side="BUY", handelszeit=zeit_roll, exec_batch="3.9"),
        _exec("E4", conid=602, side="SELL", handelszeit=zeit_roll, exec_batch="3.9"),
        _exec("E5", conid=701, side="SELL", handelszeit=zeit_roll, exec_batch="3.9"),
        _exec("E6", conid=702, side="BUY", handelszeit=zeit_roll, exec_batch="3.9"),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert chain.anzahl_rolls == 1
    assert chain.underlying == "DAX"
    # Regel 7: Der gemeinsame exec_batch belegt den Roll über die
    # Order-Nummer — das ist kein Schluss aus zeitlicher Nähe.
    assert chain.glieder[0].erkennung == "auto"
    assert chain.glieder[1].erkennung == "auto"


def test_options_roll_in_zwei_orders_wird_kandidat_statt_kette():
    """Ohne gemeinsamen exec_batch entsteht **keine** Kette mehr, sondern ein
    Vorschlag (Plan §6, Block B, Regel 2; geändert durch AP-04k nach OF-41).

    Früher verkettete ein 3-Minuten-Fenster diese Paare automatisch. Die
    Durchsicht der Stichprobe zeigte, dass das in zehn von 25 Fällen falsch
    war: Ein Wiedereinstieg nach einem Profit Target sieht im Brokerbeleg
    genauso aus wie ein Roll. Geprüft wird deshalb jetzt, dass dasselbe
    Fixture zwei eigenständige Ketten und **einen Kandidaten** ergibt.
    """
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 9, 18),
                          strike="4900", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 9, 18),
                          strike="4850", right="P"),
        701: _instrument(701, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 10, 16),
                          strike="4800", right="P"),
        702: _instrument(702, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 10, 16),
                          strike="4750", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E3", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0)),
        _exec("E4", conid=602, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 0, 0)),
        _exec("E5", conid=701, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 2, 0)),
        _exec("E6", conid=702, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 2, 0)),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 2
    assert all(chain.anzahl_rolls == 0 for chain in ergebnis.chains)

    assert len(ergebnis.kandidaten) == 1
    kandidat = ergebnis.kandidaten[0]
    assert kandidat.rang == 1
    assert kandidat.abstand == timedelta(minutes=2)
    assert kandidat.mengenverhaeltnis == Decimal("1")
    assert {k.open_exec_id for k in kandidat.schliessende.leg_schluessel} == {"E1", "E2"}
    assert {k.open_exec_id for k in kandidat.eroeffnende.leg_schluessel} == {"E5", "E6"}


def test_options_roll_andere_seite_verkettet_nicht():
    """Eine Put-Struktur, die schließt, verkettet sich nicht mit einer neu
    eröffneten Call-Struktur, selbst wenn Zeitfenster und Menge passen."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 9, 18),
                          strike="4900", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 9, 18),
                          strike="4850", right="P"),
        701: _instrument(701, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 10, 16),
                          strike="5200", right="C"),
        702: _instrument(702, asset_class="OPT", underlying="ESTX50", expiry=date(2026, 10, 16),
                          strike="5250", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E3", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0)),
        _exec("E4", conid=602, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 0, 0)),
        _exec("E5", conid=701, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 2, 0)),
        _exec("E6", conid=702, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 2, 0)),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 2
    assert all(c.anzahl_rolls == 0 for c in ergebnis.chains)


# ---------------------------------------------------------------------------
# Aktien — keine automatische Kettenbildung (Schritt 4)
# ---------------------------------------------------------------------------


def test_zwei_unabhaengige_aktientranchen_bleiben_getrennte_ketten():
    instrumente = {501: _instrument(501, asset_class="STK", underlying="IDX9")}
    executions = [
        _exec("S1", conid=501, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("S2", conid=501, side="BUY", handelszeit=datetime(2026, 9, 5, 10, 0, 0)),
    ]
    legs = [_leg("S1", None, conid=501), _leg("S2", None, conid=501)]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 2
    assert all(c.anzahl_rolls == 0 for c in ergebnis.chains)


# ---------------------------------------------------------------------------
# Grundform
# ---------------------------------------------------------------------------


def test_leere_eingabe_liefert_leeres_ergebnis():
    from engine.structures import StrukturErgebnis

    ergebnis = bilde_chains(StrukturErgebnis(structures=(), nicht_strukturiert=()), [], [], {})
    assert ergebnis.chains == ()


def test_einzelne_structure_ohne_referenz_ist_eigene_kette_ohne_rolls():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
    }
    executions = [_exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0))]
    legs = [_leg("E1", None, conid=601)]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    chain = ergebnis.chains[0]
    assert chain.anzahl_rolls == 0
    assert chain.seite == "Call"
    assert chain.endzustand == "Offen"


def test_custom_structure_ohne_einheitliches_recht_hat_seite_n_a():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
        603: _instrument(603, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4900", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="9.10"),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="9.10"),
        _exec("E3", conid=603, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="9.10"),
    ]
    legs = [
        _leg("E1", None, conid=601),
        _leg("E2", None, conid=602),
        _leg("E3", None, conid=603),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    assert ergebnis.chains[0].seite == "n.a."


def test_ergebnis_ist_unabhaengig_von_der_eingabereihenfolge():
    """P2: gleiche Eingabe, bitgleiche Ausgabe, auch bei anderer Reihenfolge."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4950", right="P"),
        701: _instrument(701, asset_class="OPT", underlying="SPX", expiry=date(2026, 10, 16),
                          strike="5000", right="P"),
        702: _instrument(702, asset_class="OPT", underlying="SPX", expiry=date(2026, 10, 16),
                          strike="4950", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
        _exec("E3", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
        _exec("E4", conid=602, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
        _exec("E5", conid=701, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
        _exec("E6", conid=702, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="10", oa_order="2"),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
    ]

    vorwaerts = _bilde(legs, executions, instrumente)
    rueckwaerts = _bilde(
        list(reversed(legs)), list(reversed(executions)), instrumente
    )

    assert vorwaerts.chains == rueckwaerts.chains


# ---------------------------------------------------------------------------
# Rollkandidaten (AP-04k, Plan §6, Block B, Regel 2)
# ---------------------------------------------------------------------------


def _estx(conid, strike, expiry, right="P"):
    return _instrument(conid, asset_class="OPT", underlying="ESTX50", expiry=expiry,
                       strike=strike, right=right)


def test_belegte_fortsetzung_erzeugt_keinen_kandidaten():
    """Was die Order-Nummer belegt, wird nicht zur Rückfrage (Vertrag 5).

    Dasselbe Bild wie beim Zeitfenster-Fall, nur mit gemeinsamem
    `exec_batch`: eine Kette, kein Kandidat.
    """
    instrumente = {
        601: _estx(601, "4900", date(2026, 9, 18)),
        602: _estx(602, "4850", date(2026, 9, 18)),
        701: _estx(701, "4800", date(2026, 10, 16)),
        702: _estx(702, "4750", date(2026, 10, 16)),
    }
    zeit = datetime(2026, 9, 15, 15, 0, 0)
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.1"),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.1"),
        _exec("E3", conid=601, side="BUY", handelszeit=zeit, exec_batch="7.9"),
        _exec("E4", conid=602, side="SELL", handelszeit=zeit, exec_batch="7.9"),
        _exec("E5", conid=701, side="SELL", handelszeit=zeit, exec_batch="7.9"),
        _exec("E6", conid=702, side="BUY", handelszeit=zeit, exec_batch="7.9"),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 1
    assert ergebnis.kandidaten == ()


def test_zwei_moegliche_fortsetzungen_werden_beide_angeboten():
    """Mehrdeutigkeit wird angeboten, nicht aufgelöst (Vertrag 6).

    Die alte Logik nahm den ersten passenden Kandidaten und verbaute damit
    den richtigen — gemessen in der Gegenprobe der Stichprobe (OF-41). Hier
    schließt eine Position, und zwei kommen als Fortsetzung in Frage: eine
    nach 2, eine nach 20 Minuten. Beide erscheinen, die nähere zuerst.
    """
    instrumente = {
        601: _estx(601, "4900", date(2026, 9, 18)),
        602: _estx(602, "4850", date(2026, 9, 18)),
        701: _estx(701, "4800", date(2026, 10, 16)),
        702: _estx(702, "4750", date(2026, 10, 16)),
        801: _estx(801, "4700", date(2026, 11, 20)),
        802: _estx(802, "4650", date(2026, 11, 20)),
    }
    schluss = datetime(2026, 9, 15, 15, 0, 0)
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E3", conid=601, side="BUY", handelszeit=schluss),
        _exec("E4", conid=602, side="SELL", handelszeit=schluss),
        _exec("E5", conid=701, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 2, 0)),
        _exec("E6", conid=702, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 2, 0)),
        _exec("E7", conid=801, side="SELL", handelszeit=datetime(2026, 9, 15, 15, 20, 0)),
        _exec("E8", conid=802, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 20, 0)),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=702),
        _leg("E7", None, conid=801),
        _leg("E8", None, conid=802),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert len(ergebnis.chains) == 3
    assert [k.rang for k in ergebnis.kandidaten] == [1, 2]
    assert [k.abstand for k in ergebnis.kandidaten] == [
        timedelta(minutes=2), timedelta(minutes=20),
    ]


def test_abweichende_menge_wird_angeboten_aber_hinten_einsortiert():
    """Die Menge ordnet, sie entscheidet nicht (Vertrag 3 und 4).

    Ein Roll ist keine Eins-zu-eins-Nachfolge — Positionen werden geteilt
    und erweitert. Früher verwarf eine Abweichung über 20 % den Kandidaten;
    jetzt erscheint er, nur weiter hinten.

    Von Hand: Die schließende Position hat Menge 2. Der eine Kandidat trägt
    Menge 2 (Verhältnis 1), der andere Menge 6 (Verhältnis 3). Beide
    öffnen zur selben Zeit — bei gleichem Abstand entscheidet das
    Mengenverhältnis, also erst 1, dann 3.
    """
    instrumente = {
        601: _estx(601, "4900", date(2026, 9, 18)),
        602: _estx(602, "4850", date(2026, 9, 18)),
        701: _estx(701, "4800", date(2026, 10, 16)),
        801: _estx(801, "4700", date(2026, 11, 20)),
    }
    schluss = datetime(2026, 9, 15, 15, 0, 0)
    gleichzeitig = datetime(2026, 9, 15, 15, 5, 0)
    executions = [
        _exec("E1", conid=601, side="SELL", menge="2",
              handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", menge="2",
              handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E3", conid=601, side="BUY", menge="2", handelszeit=schluss),
        _exec("E4", conid=602, side="SELL", menge="2", handelszeit=schluss),
        _exec("E5", conid=701, side="SELL", menge="2", handelszeit=gleichzeitig),
        _exec("E6", conid=801, side="SELL", menge="6", handelszeit=gleichzeitig),
    ]
    legs = [
        _leg("E1", "E3", conid=601, menge="2", offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, menge="2", offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701, menge="2"),
        _leg("E6", None, conid=801, menge="6"),
    ]

    ergebnis = _bilde(legs, executions, instrumente)

    assert [k.mengenverhaeltnis for k in ergebnis.kandidaten] == [
        Decimal("1"), Decimal("3"),
    ]


def test_kandidatenreihenfolge_haengt_nicht_an_der_eingabereihenfolge():
    """Vertrag 4: Bei Gleichstand entscheidet der Naturschlüssel."""
    instrumente = {
        601: _estx(601, "4900", date(2026, 9, 18)),
        602: _estx(602, "4850", date(2026, 9, 18)),
        701: _estx(701, "4800", date(2026, 10, 16)),
        801: _estx(801, "4700", date(2026, 11, 20)),
    }
    schluss = datetime(2026, 9, 15, 15, 0, 0)
    gleichzeitig = datetime(2026, 9, 15, 15, 5, 0)
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E3", conid=601, side="BUY", handelszeit=schluss),
        _exec("E4", conid=602, side="SELL", handelszeit=schluss),
        _exec("E5", conid=701, side="SELL", handelszeit=gleichzeitig),
        _exec("E6", conid=801, side="SELL", handelszeit=gleichzeitig),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="50.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-20.00"),
        _leg("E5", None, conid=701),
        _leg("E6", None, conid=801),
    ]

    vorwaerts = _bilde(legs, executions, instrumente)
    rueckwaerts = _bilde(list(reversed(legs)), list(reversed(executions)), instrumente)

    def _bild(ergebnis):
        return [
            (k.rang, tuple(sorted(x.open_exec_id for x in k.eroeffnende.leg_schluessel)))
            for k in ergebnis.kandidaten
        ]

    assert _bild(vorwaerts) == _bild(rueckwaerts)
