# ruff: noqa: E501
"""Nachtrag zu AP-10b (Echtbestand: 6 ausgeübte gekaufte Optionen ohne Lieferung, jetzt 0):

- Aktien tragen im Journal oft kein ``underlying`` (nur das Symbol); die Zuordnung zur Lieferung muss trotzdem greifen
  (z. B. SMH Call 230, 27.01.2023).
- Ein gekaufter Put, ausgeübt ohne Aktienbestand, eröffnet einen Leerverkauf (z. B. STZ Put 145, 30.12.2025): Das Bein
  ist offen, nimmt die Optionskosten aber auf; sie gelten nicht als „ohne Lieferung“.
"""
from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from test_steuer_zufluss import ex, inst, lauf, leg, saldo  # noqa: E402


def test_aktie_ohne_underlying_wird_ueber_das_symbol_der_option_zugeordnet():
    call = inst(6, "OPT", mult="100", abw="lieferung", right="C", symbol="SMH C230", underlying="SMH", waehrung="EUR")
    aktie = inst(7, "STK", symbol="SMH", underlying=None, waehrung="EUR")            # wie im Echtbestand
    execs = [
        ex("C1", 6, "BUY", 1, "3.00", "1", date(2023, 1, 20), waehrung="EUR"),
        ex("C2", 6, "SELL", 1, "0", "1", date(2023, 1, 27), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
        ex("B1", 7, "BUY", 100, "230", "1", date(2023, 1, 27), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
        ex("B2", 7, "SELL", 100, "238", "1", date(2023, 3, 10), waehrung="EUR"),
    ]
    erg = lauf([leg(1, 6, "C1", "C2", "1"), leg(2, 7, "B1", "B2", "100")], execs, [call, aktie])
    assert saldo(erg, 2023, "aktien") == D("500")        # 23.800 − (23.000 + 300 Optionskosten)
    assert not erg.regeln_offen


def test_put_ohne_aktienbestand_eroeffnet_einen_leerverkauf_und_nimmt_die_kosten_auf():
    put = inst(8, "OPT", mult="100", abw="lieferung", right="P", symbol="STZ P145", underlying="STZ", waehrung="EUR")
    aktie = inst(9, "STK", symbol="STZ", underlying=None, waehrung="EUR")
    execs = [
        ex("P1", 8, "BUY", 1, "2.00", "1", date(2025, 12, 1), waehrung="EUR"),
        ex("P2", 8, "SELL", 1, "0", "1", date(2025, 12, 30), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
        ex("S1", 9, "SELL", 100, "145", "1", date(2025, 12, 30), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
    ]
    erg = lauf([leg(1, 8, "P1", "P2", "1"), leg(2, 9, "S1", None, "-100")], execs, [put, aktie])
    assert not erg.regeln_offen                               # Optionskosten sind der offenen Lieferung zugeordnet
    assert 2025 not in erg.jahre() or "termingeschaefte" not in erg.jahre()[2025]["toepfe"]
