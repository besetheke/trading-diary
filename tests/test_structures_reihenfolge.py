# ruff: noqa: E501
"""AP-17f (Review R06): die Strukturbildung hängt nicht von der Reihenfolge der Eingabe ab.

Welt: vier gleichzeitig eröffnete Put-Legs ohne Orderreferenz, gleicher Verfall:
  Long 90 (E1), Long 95 (E2), Short 100 (E3), Short 105 (E4).
Festgelegte Regel (Ersatzweg Zeitfenster): Beine werden nach (Zeit, Basiswert, Verfall, Recht, Strike, Richtung, Menge, ID)
geordnet; ein Bein bekommt unter den passenden Clustern den mit den wenigsten Beinen seiner eigenen Richtung.
Handrechnung: L90 eröffnet Cluster 1, L95 (gleiche Richtung) Cluster 2, S100 → Cluster 1 (beide ohne Short, früherer),
S105 → Cluster 2 (Cluster 1 hat schon einen Short). Ergebnis: {E1,E3} und {E2,E4}, nicht 3 + 1.
"""
from datetime import date, datetime
from itertools import permutations

from test_structures import _exec, _instrument, _leg

from engine.structures import bilde_structures

ZEIT = datetime(2026, 9, 1, 10, 0, 0)
INSTRUMENTE = {
    c: _instrument(c, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18), strike=k, right="P")
    for c, k in ((801, "90"), (802, "95"), (803, "100"), (804, "105"))
}
EXECS = [
    _exec("E1", conid=801, side="BUY", handelszeit=ZEIT),
    _exec("E2", conid=802, side="BUY", handelszeit=ZEIT),
    _exec("E3", conid=803, side="SELL", handelszeit=ZEIT),
    _exec("E4", conid=804, side="SELL", handelszeit=ZEIT),
]
LEGS = [_leg("E1", None, conid=801), _leg("E2", None, conid=802),
        _leg("E3", None, conid=803), _leg("E4", None, conid=804)]


def _ergebnis(legs, execs):
    erg = bilde_structures(legs, execs, INSTRUMENTE)
    return sorted(
        (tuple(sorted(k.open_exec_id for k in s.leg_schluessel)), s.typ, s.short_strike, s.long_strike)
        for s in erg.structures
    )


def test_alle_permutationen_der_legs_ergeben_dieselben_strukturen():
    erwartet = _ergebnis(LEGS, EXECS)
    for p in permutations(LEGS):
        assert _ergebnis(list(p), EXECS) == erwartet


def test_alle_permutationen_der_ausfuehrungen_ergeben_dieselben_strukturen():
    erwartet = _ergebnis(LEGS, EXECS)
    for p in permutations(EXECS):
        assert _ergebnis(LEGS, list(p)) == erwartet


def test_festgelegte_regel_zwei_paare_statt_drei_plus_eins():
    ergebnis = _ergebnis(LEGS, EXECS)
    assert [e[0] for e in ergebnis] == [("E1", "E3"), ("E2", "E4")]
