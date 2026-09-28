"""Abnahmetests für die Campaign-Kandidaten (AP-05v).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das günstige
Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-05v.md`, fachlich Plan §6, AP-05, „Kandidatenregeln".

Das Modul springt still ab, solange `engine/campaigns.py` fehlt.

Alle Daten sind frei erfunden. `fixtures/golden/` wird hier nicht gelesen.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

pytest.importorskip("engine.campaigns")

from engine.campaigns import campaign_kandidaten  # noqa: E402
from engine.chains import bilde_chains  # noqa: E402
from engine.structures import bilde_structures  # noqa: E402

KONTO = "U9999999"


def _instrument(conid, *, asset_class="OPT", underlying, expiry=None, strike=None, right=None):
    return {
        "conid": conid,
        "asset_class": asset_class,
        "underlying": underlying,
        "expiry": expiry,
        "strike": Decimal(strike) if strike is not None else None,
        "right": right,
    }


def _exec(exec_id, *, conid, side, handelszeit, exec_batch=None):
    return {
        "exec_id": exec_id,
        "konto": KONTO,
        "conid": conid,
        "side": side,
        "menge": Decimal("1"),
        "handelszeit": handelszeit,
        "ereignistyp": "trade",
        "exec_batch": exec_batch,
        "oa_trade": None,
        "oa_order": None,
    }


def _leg(open_exec_id, close_exec_id, *, conid):
    return {
        "conid": conid,
        "open_exec_id": open_exec_id,
        "close_exec_id": close_exec_id,
        "menge": Decimal("1"),
        "offen_ja_nein": close_exec_id is None,
        "brutto_pnl": None,
        "kommission_gesamt": Decimal("0"),
    }


def _bilde(legs, executions, instrumente):
    struktur = bilde_structures(legs, executions, instrumente)
    return bilde_chains(struktur, legs, executions, instrumente).chains


def _vertikale_kette(prefix, *, underlying, right, expiry, conid_short, conid_long,
                      eroeffnet, beendet=None):
    """Eine einfache Zwei-Bein-Vertikale, eine Kette, kein Roll."""
    instrumente = {
        conid_short: _instrument(conid_short, underlying=underlying, expiry=expiry,
                                  strike="100", right=right),
        conid_long: _instrument(conid_long, underlying=underlying, expiry=expiry,
                                 strike="90" if right == "P" else "110", right=right),
    }
    executions = [
        _exec(f"{prefix}1", conid=conid_short, side="SELL", handelszeit=eroeffnet),
        _exec(f"{prefix}2", conid=conid_long, side="BUY", handelszeit=eroeffnet),
    ]
    legs = [
        _leg(f"{prefix}1", f"{prefix}3" if beendet else None, conid=conid_short),
        _leg(f"{prefix}2", f"{prefix}4" if beendet else None, conid=conid_long),
    ]
    if beendet:
        executions += [
            _exec(f"{prefix}3", conid=conid_short, side="BUY", handelszeit=beendet),
            _exec(f"{prefix}4", conid=conid_long, side="SELL", handelszeit=beendet),
        ]
    return _bilde(legs, executions, instrumente)[0]


def _gerollte_kette(prefix, *, underlying, right, eroeffnet, roll_zeit,
                     conid_alt_a, conid_alt_b, conid_neu_a, conid_neu_b):
    """Eine Vertikale, in einer Order gerollt (Block B, Regel 1) — eine
    Kette mit zwei Gliedern, das zweite mit `verknuepfungstyp == 'roll'`."""
    instrumente = {
        conid_alt_a: _instrument(conid_alt_a, underlying=underlying,
                                  expiry=date(2026, 9, 18), strike="100", right=right),
        conid_alt_b: _instrument(conid_alt_b, underlying=underlying,
                                  expiry=date(2026, 9, 18), strike="90", right=right),
        conid_neu_a: _instrument(conid_neu_a, underlying=underlying,
                                  expiry=date(2026, 10, 16), strike="95", right=right),
        conid_neu_b: _instrument(conid_neu_b, underlying=underlying,
                                  expiry=date(2026, 10, 16), strike="85", right=right),
    }
    executions = [
        _exec(f"{prefix}1", conid=conid_alt_a, side="SELL", handelszeit=eroeffnet,
              exec_batch=f"{prefix}.1"),
        _exec(f"{prefix}2", conid=conid_alt_b, side="BUY", handelszeit=eroeffnet,
              exec_batch=f"{prefix}.1"),
        _exec(f"{prefix}3", conid=conid_alt_a, side="BUY", handelszeit=roll_zeit,
              exec_batch=f"{prefix}.9"),
        _exec(f"{prefix}4", conid=conid_alt_b, side="SELL", handelszeit=roll_zeit,
              exec_batch=f"{prefix}.9"),
        _exec(f"{prefix}5", conid=conid_neu_a, side="SELL", handelszeit=roll_zeit,
              exec_batch=f"{prefix}.9"),
        _exec(f"{prefix}6", conid=conid_neu_b, side="BUY", handelszeit=roll_zeit,
              exec_batch=f"{prefix}.9"),
    ]
    legs = [
        _leg(f"{prefix}1", f"{prefix}3", conid=conid_alt_a),
        _leg(f"{prefix}2", f"{prefix}4", conid=conid_alt_b),
        _leg(f"{prefix}5", None, conid=conid_neu_a),
        _leg(f"{prefix}6", None, conid=conid_neu_b),
    ]
    return _bilde(legs, executions, instrumente)[0]


# ---------------------------------------------------------------------------
# IC-Kandidat
# ---------------------------------------------------------------------------


def test_ic_kandidat_erkannt():
    """Vertrag 4: gleicher Basiswert, gegenläufige Seite, gleiche Expiry am
    letzten Glied, überlappende Laufzeit — der Lehrbuchfall eines Iron
    Condor aus zwei unabhängig geführten Ketten."""
    expiry = date(2026, 10, 16)
    t0 = datetime(2026, 9, 1, 10, 0, 0)
    put = _vertikale_kette("P", underlying="RUT", right="P", expiry=expiry,
                            conid_short=601, conid_long=602, eroeffnet=t0)
    call = _vertikale_kette("C", underlying="RUT", right="C", expiry=expiry,
                             conid_short=611, conid_long=612, eroeffnet=t0)

    kandidaten = campaign_kandidaten([put, call])

    assert len(kandidaten) == 1
    assert kandidaten[0].typ == "ic"
    assert {kandidaten[0].kette_a.seite, kandidaten[0].kette_b.seite} == {"Call", "Put"}


def test_ic_kandidat_verschiedene_expiry_kein_kandidat():
    """Vertrag 4: unterschiedliche Expiry am letzten Glied — kein IC."""
    t0 = datetime(2026, 9, 1, 10, 0, 0)
    put = _vertikale_kette("P", underlying="RUT", right="P", expiry=date(2026, 10, 16),
                            conid_short=601, conid_long=602, eroeffnet=t0)
    call = _vertikale_kette("C", underlying="RUT", right="C", expiry=date(2026, 11, 20),
                             conid_short=611, conid_long=612, eroeffnet=t0)

    assert campaign_kandidaten([put, call]) == ()


def test_ic_kandidat_gleiche_seite_kein_kandidat():
    """Vertrag 4: zwei Put-Ketten sind kein IC, auch bei sonst gleichen
    Merkmalen — „gegenläufige Seiten" ist keine Formalität."""
    expiry = date(2026, 10, 16)
    t0 = datetime(2026, 9, 1, 10, 0, 0)
    a = _vertikale_kette("A", underlying="RUT", right="P", expiry=expiry,
                          conid_short=601, conid_long=602, eroeffnet=t0)
    b = _vertikale_kette("B", underlying="RUT", right="P", expiry=expiry,
                          conid_short=621, conid_long=622, eroeffnet=t0)

    assert campaign_kandidaten([a, b]) == ()


def test_ic_kandidat_keine_ueberlappung_kein_kandidat():
    """Entscheidung 1: Schließt die Put-Kette, bevor die Call-Kette
    eröffnet, gab es keinen gemeinsamen Zeitraum — kein IC, obwohl
    Basiswert, Expiry und Seiten passen."""
    expiry = date(2026, 10, 16)
    put = _vertikale_kette("P", underlying="RUT", right="P", expiry=expiry,
                            conid_short=601, conid_long=602,
                            eroeffnet=datetime(2026, 9, 1, 10, 0, 0),
                            beendet=datetime(2026, 9, 5, 10, 0, 0))
    call = _vertikale_kette("C", underlying="RUT", right="C", expiry=expiry,
                             conid_short=611, conid_long=612,
                             eroeffnet=datetime(2026, 9, 6, 10, 0, 0))

    assert campaign_kandidaten([put, call]) == ()


# ---------------------------------------------------------------------------
# Financing-Kandidat
# ---------------------------------------------------------------------------


def test_financing_kandidat_erkannt():
    """Vertrag 5: Eine gerollte Put-Kette und eine neue Call-Kette, deren
    Eröffnung 2 Stunden nach dem Roll liegt — innerhalb der 24-Stunden-Annahme
    (Entscheidung 3).

    Die Call-Kette trägt bewusst eine andere Expiry als das Roll-Ziel der
    Put-Kette (2026-10-16) — sonst wäre das Paar zugleich ein
    IC-Kandidat (Vertrag 4) und der Test prüfte nicht mehr isoliert die
    Financing-Regel (AP-05vk, OF-51)."""
    roll_zeit = datetime(2026, 9, 15, 15, 0, 0)
    put = _gerollte_kette("P", underlying="DAX", right="P",
                           eroeffnet=datetime(2026, 9, 1, 10, 0, 0), roll_zeit=roll_zeit,
                           conid_alt_a=601, conid_alt_b=602, conid_neu_a=605, conid_neu_b=606)
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 11, 20),
                             conid_short=611, conid_long=612,
                             eroeffnet=roll_zeit + timedelta(hours=2))

    kandidaten = campaign_kandidaten([put, call])

    assert len(kandidaten) == 1
    assert kandidaten[0].typ == "financing"
    assert kandidaten[0].kette_a.seite == "Put"
    assert kandidaten[0].kette_b.seite == "Call"


def test_financing_kandidat_ausserhalb_fenster_kein_kandidat():
    """Entscheidung 3: 30 Stunden nach dem Roll liegt außerhalb der
    24-Stunden-Annahme — kein Kandidat.

    Andere Expiry als das Roll-Ziel, aus demselben Grund wie in
    `test_financing_kandidat_erkannt` (AP-05vk, OF-51): sonst würde die
    Intervallüberlappung der offenen Ketten unabhängig vom Zeitfenster
    einen IC-Kandidaten erzeugen, und `== ()` wäre nie erfüllbar."""
    roll_zeit = datetime(2026, 9, 15, 15, 0, 0)
    put = _gerollte_kette("P", underlying="DAX", right="P",
                           eroeffnet=datetime(2026, 9, 1, 10, 0, 0), roll_zeit=roll_zeit,
                           conid_alt_a=601, conid_alt_b=602, conid_neu_a=605, conid_neu_b=606)
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 11, 20),
                             conid_short=611, conid_long=612,
                             eroeffnet=roll_zeit + timedelta(hours=30))

    assert campaign_kandidaten([put, call]) == ()


def test_financing_kandidat_ohne_roll_kein_kandidat():
    """Vertrag 5: Ohne Roll in der Bestandskette gibt es keinen
    Rollzeitpunkt, an dem sich eine Gegenfinanzierung festmachen ließe —
    zwei ungerollte Ketten sind nie ein Financing-Kandidat, auch wenn sie
    zeitlich nah beieinander liegen.

    Unterschiedliche Expiry zwischen `put` und `call` (AP-05vk, OF-51):
    mit gleicher Expiry wären zwei offene, gegenläufige, zeitlich
    überlappende Ketten genau der IC-Kandidat aus Entscheidung 1, und
    `== ()` widerspräche dem eigenen Vertrag."""
    t0 = datetime(2026, 9, 1, 10, 0, 0)
    put = _vertikale_kette("P", underlying="DAX", right="P", expiry=date(2026, 9, 18),
                            conid_short=601, conid_long=602, eroeffnet=t0)
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 11, 20),
                             conid_short=611, conid_long=612,
                             eroeffnet=t0 + timedelta(hours=1))

    assert campaign_kandidaten([put, call]) == ()


def test_financing_kandidat_gleiche_seite_kein_kandidat():
    """Vertrag 5: Eine zweite Put-Kette nach dem Roll ist keine
    Gegenfinanzierung — „Gegenseite" ist Bedingung, nicht nur Nähe in
    der Zeit."""
    roll_zeit = datetime(2026, 9, 15, 15, 0, 0)
    put = _gerollte_kette("P", underlying="DAX", right="P",
                           eroeffnet=datetime(2026, 9, 1, 10, 0, 0), roll_zeit=roll_zeit,
                           conid_alt_a=601, conid_alt_b=602, conid_neu_a=605, conid_neu_b=606)
    zweite_put = _vertikale_kette("Q", underlying="DAX", right="P", expiry=date(2026, 10, 16),
                                   conid_short=621, conid_long=622,
                                   eroeffnet=roll_zeit + timedelta(hours=1))

    assert campaign_kandidaten([put, zweite_put]) == ()


# ---------------------------------------------------------------------------
# Determinismus
# ---------------------------------------------------------------------------


def test_determinismus_unabhaengig_von_eingabereihenfolge():
    """Vertrag 6 und 7: Ergebnis und Reihenfolge hängen nicht davon ab, in
    welcher Reihenfolge die Ketten übergeben werden."""
    expiry = date(2026, 10, 16)
    t0 = datetime(2026, 9, 1, 10, 0, 0)
    put = _vertikale_kette("P", underlying="RUT", right="P", expiry=expiry,
                            conid_short=601, conid_long=602, eroeffnet=t0)
    call = _vertikale_kette("C", underlying="RUT", right="C", expiry=expiry,
                             conid_short=611, conid_long=612, eroeffnet=t0)

    vorwaerts = campaign_kandidaten([put, call])
    rueckwaerts = campaign_kandidaten([call, put])

    assert vorwaerts == rueckwaerts
    assert len(vorwaerts) == 1
