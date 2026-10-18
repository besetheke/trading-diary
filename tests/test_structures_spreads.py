# ruff: noqa: E501
"""AP-17b (Review R05): Typ von Zwei-Bein-Spreads, alle vier Richtungen, von Hand bestimmt.

Credit-Spreads (Short-Prämie > Long-Prämie, Short näher am Geld):
  Put-Credit  (BPS): Short Put 100, Long Put 90   → Long niedriger als Short
  Call-Credit (BCS): Short Call 105, Long Call 115 → Long höher als Short
Debit-Spreads bleiben Vertical:
  Put-Debit : Long Put 100, Short Put 90   (Long höher als Short)
  Call-Debit: Long Call 105, Short Call 115 (Long niedriger als Short)
Strikes, Breite (Betrag der Differenz = 10) und die Zuordnung Short/Long müssen in allen Fällen stimmen.
"""
from datetime import date, datetime
from decimal import Decimal as D

import pytest
from test_structures import _exec, _instrument, _leg

from engine.structures import bilde_structures


def spread(recht, short_strike, long_strike):
    instrumente = {
        701: _instrument(701, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18), strike=long_strike, right=recht),
        702: _instrument(702, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18), strike=short_strike, right=recht),
    }
    zeit = datetime(2026, 9, 1, 10, 0, 0)
    executions = [
        _exec("L", conid=701, side="BUY", handelszeit=zeit, oa_trade="20", oa_order="1"),
        _exec("S", conid=702, side="SELL", handelszeit=zeit, oa_trade="20", oa_order="1"),
    ]
    legs = [_leg("L", None, conid=701), _leg("S", None, conid=702)]
    ergebnis = bilde_structures(legs, executions, instrumente)
    assert len(ergebnis.structures) == 1
    return ergebnis.structures[0]


@pytest.mark.parametrize(
    ("recht", "short_strike", "long_strike", "erwartet"),
    [
        ("P", "100", "90", "BPS"),         # Put-Credit
        ("C", "105", "115", "BCS"),        # Call-Credit (vorher fälschlich „Vertical“)
        ("P", "90", "100", "Vertical"),    # Put-Debit
        ("C", "115", "105", "Vertical"),   # Call-Debit (vorher fälschlich „BCS“)
    ],
)
def test_typ_je_richtung(recht, short_strike, long_strike, erwartet):
    s = spread(recht, short_strike, long_strike)
    assert s.typ == erwartet
    assert s.short_strike == D(short_strike) and s.long_strike == D(long_strike)
    assert s.breite == D("10")
