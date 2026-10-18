"""Abnahmetests für AP-04, Teil 1: Legs → Structures (`engine/structures.py`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das günstige
Modell unveränderlich, wie `tests/test_matching.py`. Maßgeblich ist die
Erkennungsreihenfolge in `plan/trading-journal-projektplan.md`, § 6,
Abschnitt AP-04; der Modul-Docstring von `engine/structures.py` trägt die
Kurzfassung samt der dokumentierten Annahme zu Schritt 2 (OF-34).

Jede Fixture ist von Hand konstruiert: Legs und Ausführungen direkt als
Dicts, wie `engine.matching.bilde_legs()` sie ausgäbe beziehungsweise wie
`ingest/flex.py` Ausführungen liefert — kein Rückgriff auf das echte Matching,
damit dieses Modul isoliert geprüft wird.
"""

from datetime import date, datetime
from decimal import Decimal

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


# ---------------------------------------------------------------------------
# Schritt 0a — OptionApp-Referenz, höchste Priorität
# ---------------------------------------------------------------------------


def test_oa_referenz_gruppiert_zwei_legs_zu_einer_structure():
    """Trade+Order-Paar identisch → eine Structure, Vertical (Bull Call Debit: long
    niedriger, short höherer Strike, beide Calls; BCS ist der Call-Credit-Spread, AP-17b)."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="10", oa_order="1"),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    structure = ergebnis.structures[0]
    assert structure.methode == "oa"
    assert structure.typ == "Vertical"
    assert structure.underlying == "SPX"
    assert structure.short_strike == Decimal("5050")
    assert structure.long_strike == Decimal("5000")
    assert structure.breite == Decimal("50")
    assert len(structure.leg_schluessel) == 2


def test_gleiche_ordernummer_unter_verschiedenen_oa_trades_bleibt_getrennt():
    """Pflichttest (§6): Order-Nummern sind nicht global eindeutig — Schlüssel
    ist das Paar (OA-Trade, OA-Order), niemals die Nummer allein."""
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

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 2
    underlyings = {s.underlying for s in ergebnis.structures}
    assert underlyings == {"SPX", "RUT"}


def test_generische_referenz_ohne_oa_felder_erzwingt_keine_gemeinsame_structure():
    """Eine generische orderReference (z. B. `ActivityMonitor`) liefert laut
    `ingest/flex.py` kein `oa_trade`/`oa_order` (§6.1) — dieses Modul sieht nur
    die geparsten Felder, nie den Rohtext, und darf daraus keine Kette
    erfinden. Zwei Legs ohne OA-Felder, ohne gemeinsamen exec_batch und
    außerhalb des Zeitfensters bleiben getrennt."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 30, 0)),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 2


# ---------------------------------------------------------------------------
# Schritt 1 — exec_batch, primäre Ausführungsidentität
# ---------------------------------------------------------------------------


def test_exec_batch_gruppiert_legs_ohne_oa_referenz():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4950", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.42"),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.42"),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    structure = ergebnis.structures[0]
    assert structure.methode == "exec_batch"
    # BPS: short (5000) höherer Strike, long (4950) niedrigerer, beide Puts.
    assert structure.typ == "BPS"
    assert structure.short_strike == Decimal("5000")
    assert structure.long_strike == Decimal("4950")


def test_drei_bein_structure_wird_nicht_auf_zwei_legs_zurechtgestutzt():
    """Pflichttest (§6): eine Struktur mit drei Legs bleibt eine
    Drei-Bein-Struktur (`Custom`), keine Vertical-Vereinfachung."""
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

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    structure = ergebnis.structures[0]
    assert structure.typ == "Custom"
    assert len(structure.leg_schluessel) == 3


def test_teilfills_desselben_beins_verdichten_sich_zu_einer_menge():
    """Schritt 1a: zwei Fills desselben Orderbeins (gleicher conid, gleiche
    Richtung, gemeinsamer exec_batch) verdichten sich über die Menge — 3 + 2
    Kontrakte zählen als ein 5er-Bein, nicht als eigene Positionen."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1a", conid=601, side="BUY", menge="3",
              handelszeit=datetime(2026, 9, 1, 10, 0, 0), exec_batch="7.10"),
        _exec("E1b", conid=601, side="BUY", menge="2",
              handelszeit=datetime(2026, 9, 1, 10, 0, 1), exec_batch="7.10"),
        _exec("E2", conid=602, side="SELL", menge="5",
              handelszeit=datetime(2026, 9, 1, 10, 0, 0), exec_batch="7.10"),
    ]
    legs = [
        _leg("E1a", None, conid=601, menge="3"),
        _leg("E1b", None, conid=601, menge="2"),
        _leg("E2", None, conid=602, menge="5"),
    ]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    structure = ergebnis.structures[0]
    assert len(structure.leg_schluessel) == 3
    assert structure.menge == Decimal("5")


# ---------------------------------------------------------------------------
# Schritt 2 — Zeitfenster (Fallback)
# ---------------------------------------------------------------------------


def test_zeitfenster_gruppiert_legs_ohne_oa_und_exec_batch():
    """Zwei getrennt ausgeführte Beine EINER Struktur — gegenläufige
    Richtungen, deshalb ein Long- und ein Short-Bein (Plan, 19.09.2026:
    Schritt 2 führt zwei Beine einer Struktur zusammen, keine unabhängigen
    gleichgerichteten Eröffnungen)."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 2, 30)),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    assert ergebnis.structures[0].methode == "zeitfenster"


def test_gleiche_richtung_verschmilzt_nicht_im_zeitfenster():
    """Gegenprobe: zwei gleichgerichtete Eröffnungen sind keine gemeinsame
    Struktur, auch innerhalb des Zeitfensters — Schritt 2 führt zwei Beine
    EINER Struktur zusammen, nicht mehrere unabhängige Eröffnungen."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 2, 30)),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 2


def test_zeitfenster_ueberschritten_bleibt_getrennt():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 3, 1)),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 2


def test_unterschiedliches_underlying_verschmilzt_nicht_trotz_gleichem_zeitstempel():
    """Pflichttest (§6): acht sekundengleiche Legs aus zwei getrennten Orders
    auf SPY und XSP — Sekundengleichheit belegt keine gemeinsame Order.
    Verkürzt auf je zwei Legs je Basiswert, derselbe Effekt."""
    instrumente = {
        801: _instrument(801, asset_class="OPT", underlying="SPY", expiry=date(2026, 9, 18),
                          strike="500", right="P"),
        802: _instrument(802, asset_class="OPT", underlying="SPY", expiry=date(2026, 9, 18),
                          strike="495", right="P"),
        803: _instrument(803, asset_class="OPT", underlying="XSP", expiry=date(2026, 9, 18),
                          strike="500", right="P"),
        804: _instrument(804, asset_class="OPT", underlying="XSP", expiry=date(2026, 9, 18),
                          strike="495", right="P"),
    }
    zeit = datetime(2026, 9, 3, 17, 20, 42)
    executions = [
        _exec("E1", conid=801, side="SELL", handelszeit=zeit),
        _exec("E2", conid=802, side="BUY", handelszeit=zeit),
        _exec("E3", conid=803, side="SELL", handelszeit=zeit),
        _exec("E4", conid=804, side="BUY", handelszeit=zeit),
    ]
    legs = [
        _leg("E1", None, conid=801),
        _leg("E2", None, conid=802),
        _leg("E3", None, conid=803),
        _leg("E4", None, conid=804),
    ]

    ergebnis = bilde_structures(legs, executions, instrumente)

    for structure in ergebnis.structures:
        assert structure.underlying in ("SPY", "XSP")
    spy_legs = sum(
        len(s.leg_schluessel) for s in ergebnis.structures if s.underlying == "SPY"
    )
    xsp_legs = sum(
        len(s.leg_schluessel) for s in ergebnis.structures if s.underlying == "XSP"
    )
    assert spy_legs == 2
    assert xsp_legs == 2


def test_mengenabweichung_ueber_20_prozent_bleibt_getrennt():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", menge="10",
              handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=602, side="SELL", menge="7",
              handelszeit=datetime(2026, 9, 1, 10, 0, 30)),
    ]
    legs = [
        _leg("E1", None, conid=601, menge="10"),
        _leg("E2", None, conid=602, menge="7"),
    ]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 2


# ---------------------------------------------------------------------------
# Schritt 0 — P7-Vorfilter
# ---------------------------------------------------------------------------


def test_zuteilung_als_eroeffnung_bildet_keine_structure():
    """Eine durch Zuteilung entstandene Aktienposition (ereignistyp
    'assignment' an der Eröffnung) nimmt nicht an der Strukturbildung teil —
    ihre Einordnung ist Sache der Kettenbildung (AP-04, Teil 2)."""
    instrumente = {901: _instrument(901, asset_class="STK", underlying="IDX9")}
    executions = [
        _exec("E1", conid=901, side="BUY", handelszeit=datetime(2026, 9, 1, 21, 0, 0),
              ereignistyp="assignment"),
    ]
    legs = [_leg("E1", None, conid=901)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert ergebnis.structures == ()
    assert len(ergebnis.nicht_strukturiert) == 1
    grund = ergebnis.nicht_strukturiert[0].grund
    assert "assignment" in grund


def test_mehr_als_zwanzig_ereigniszeilen_am_stichtag_erzeugen_keine_structure():
    """Pflichttest (§6): ein Zeitstempel mit mehr als 20 Ereigniszeilen über
    mehrere Basiswerte erzeugt null Strukturen — sie schließen bestehende
    Legs (als close_exec_id, hier nicht simuliert), eröffnen aber nie neue."""
    zeit = datetime(2026, 9, 18, 21, 0, 0)
    instrumente = {
        1000 + i: _instrument(1000 + i, asset_class="OPT", underlying=f"U{i}",
                               expiry=date(2026, 9, 18), strike="100", right="C")
        for i in range(25)
    }
    executions = [
        _exec(f"E{i}", conid=1000 + i, side="SELL", handelszeit=zeit, ereignistyp="expiry")
        for i in range(25)
    ]
    # In der Praxis sind das close_exec_id auf bereits offenen Legs; hier zur
    # Isolation als (nie vorkommende) Eröffnung durch Verfall modelliert —
    # entscheidend ist, dass ereignistyp != 'trade' greift.
    legs = [_leg(f"E{i}", None, conid=1000 + i) for i in range(25)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert ergebnis.structures == ()
    assert len(ergebnis.nicht_strukturiert) == 25


# ---------------------------------------------------------------------------
# Schließung — nur vollständig, wenn jedes Leg der Structure zu ist
# ---------------------------------------------------------------------------


def test_vollstaendig_geschlossene_structure_traegt_schluss_und_ergebnis():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E3", conid=601, side="SELL", handelszeit=datetime(2026, 9, 10, 15, 0, 0)),
        _exec("E4", conid=602, side="BUY", handelszeit=datetime(2026, 9, 10, 15, 0, 0)),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="150.00",
             kommission_gesamt="-1.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="-80.00",
             kommission_gesamt="-1.00"),
    ]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    structure = ergebnis.structures[0]
    assert structure.status == "geschlossen"
    assert structure.geschlossen_am == datetime(2026, 9, 10, 15, 0, 0)
    assert structure.schluss_ereignistyp == "trade"
    assert structure.brutto_pnl == Decimal("70.00")
    assert structure.kommission_gesamt == Decimal("-2.00")


def test_teilweise_geschlossene_structure_bleibt_offen():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E3", conid=601, side="SELL", handelszeit=datetime(2026, 9, 10, 15, 0, 0)),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="150.00",
             kommission_gesamt="-1.00"),
        _leg("E2", None, conid=602, offen_ja_nein=True, kommission_gesamt="-1.00"),
    ]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    structure = ergebnis.structures[0]
    assert structure.status == "offen"
    assert structure.geschlossen_am is None
    assert structure.brutto_pnl is None


def test_verfall_setzt_schluss_ereignistyp_expiry():
    instrumente = {601: _instrument(601, asset_class="OPT", underlying="SPX",
                                     expiry=date(2026, 9, 18), strike="5000", right="C")}
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=601, side="SELL", handelszeit=datetime(2026, 9, 18, 21, 0, 0),
              ereignistyp="expiry"),
    ]
    legs = [_leg("E1", "E2", conid=601, offen_ja_nein=False, brutto_pnl="-150.00",
                 kommission_gesamt="-1.00")]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert ergebnis.structures[0].schluss_ereignistyp == "expiry"
    assert ergebnis.structures[0].status == "geschlossen"


def test_zuteilung_hat_vorrang_vor_verfall_bei_gemischtem_schluss():
    """Ein Spread, dessen kurzes Bein zugeteilt wird, während das lange
    verfällt: Zuteilung ist die folgenreichere Ereignisart und gewinnt."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4950", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E3", conid=601, side="BUY", handelszeit=datetime(2026, 9, 18, 21, 0, 0),
              ereignistyp="assignment"),
        _exec("E4", conid=602, side="SELL", handelszeit=datetime(2026, 9, 18, 21, 0, 0),
              ereignistyp="expiry"),
    ]
    legs = [
        _leg("E1", "E3", conid=601, offen_ja_nein=False, brutto_pnl="-500.00",
             kommission_gesamt="-1.00"),
        _leg("E2", "E4", conid=602, offen_ja_nein=False, brutto_pnl="0.00",
             kommission_gesamt="-1.00"),
    ]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert ergebnis.structures[0].schluss_ereignistyp == "assignment"


# ---------------------------------------------------------------------------
# Grundform
# ---------------------------------------------------------------------------


def test_leere_eingabe_liefert_leeres_ergebnis():
    ergebnis = bilde_structures([], [], {})
    assert ergebnis.structures == ()
    assert ergebnis.nicht_strukturiert == ()


def test_einzelnes_bein_wird_als_single_erkannt():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
    }
    executions = [_exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0))]
    legs = [_leg("E1", None, conid=601)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 1
    assert ergebnis.structures[0].typ == "Single"


def test_zwei_aktienlegs_bilden_je_eine_stock_structure():
    """§6, Schritt 4: keine automatische Kettenbildung bei Aktien — Tranchen
    bleiben eigenständige Structures."""
    instrumente = {901: _instrument(901, asset_class="STK", underlying="IDX9")}
    executions = [
        _exec("E1", conid=901, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
        _exec("E2", conid=901, side="BUY", handelszeit=datetime(2026, 9, 5, 10, 0, 0)),
    ]
    legs = [_leg("E1", None, conid=901), _leg("E2", None, conid=901)]

    ergebnis = bilde_structures(legs, executions, instrumente)

    assert len(ergebnis.structures) == 2
    assert all(s.typ == "Stock" for s in ergebnis.structures)


def test_fehlende_instrumentenzeile_wird_benannt_nicht_verworfen():
    executions = [_exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0))]
    legs = [_leg("E1", None, conid=601)]

    ergebnis = bilde_structures(legs, executions, {})

    assert ergebnis.structures == ()
    assert len(ergebnis.nicht_strukturiert) == 1
    assert "601" in ergebnis.nicht_strukturiert[0].grund


def test_ergebnis_ist_unabhaengig_von_der_eingabereihenfolge():
    """P2: gleiche Eingabe, bitgleiche Ausgabe, auch bei anderer Reihenfolge."""
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="C"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5050", right="C"),
    }
    executions = [
        _exec("E1", conid=601, side="BUY", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
        _exec("E2", conid=602, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              exec_batch="7.10"),
    ]
    legs = [_leg("E1", None, conid=601), _leg("E2", None, conid=602)]

    vorwaerts = bilde_structures(legs, executions, instrumente)
    rueckwaerts = bilde_structures(
        list(reversed(legs)), list(reversed(executions)), instrumente
    )

    assert vorwaerts.structures == rueckwaerts.structures
