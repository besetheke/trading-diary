# ruff: noqa: E501
"""Überleitung IB → Station (Nachtrag zu AP-10c), von Hand gerechnet, alles EUR, Kurs 1.

Fall A  Short Put (Prämie 200) zugeteilt, Aktie 100 × 50 gekauft, 100 × 47 verkauft:
        Station: Aktien 4.700 − 5.000 = −300; Stillhalter +200.
        IB: die Option bucht 0, die Prämie liegt im Einstand der Aktie → Aktien −300 + 200 = −100, Optionen 0.
        Überleitung: verschobene Prämie = (−100) − (−300) = 200; beide Reste 0.
Fall B  Offene Short-Position (Prämie 400): nur die Station zählt sie (offene Prämie 400), Rest 0.
Fall C  Zeitpunkt: Prämie 500 im Dezember 2025, Rückkauf 200 im Januar 2026. IB meldet den Gewinn 300 im Jahr 2026;
        die Station 2025 +500 und 2026 −200. Rest 2025 = +500, 2026 = −200 − 300 = −500.
"""
from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from test_steuer_zufluss import PUT100, ex, inst, lauf, leg  # noqa: E402

from analytics.steuer_ueberleitung import ib_ueberleitung  # noqa: E402


def ib(exec_id, jahr, klasse, eur):
    return {"exec_id": exec_id, "jahr": jahr, "klasse": klasse, "eur": D(eur)}


def test_fall_a_zugeteilte_praemie_verschiebt_zwischen_aktien_und_optionen():
    put = inst(4, "OPT", mult="100", abw="lieferung", right="P", symbol="AAA P50", underlying="AAA", waehrung="EUR")
    aktie = inst(5, "STK", symbol="AAA", underlying=None, waehrung="EUR")
    execs = [ex("P1", 4, "SELL", 1, "2.00", "1", date(2025, 5, 1), waehrung="EUR"),
             ex("P2", 4, "BUY", 1, "0", "1", date(2025, 6, 20), ereignis="assignment", waehrung="EUR", zeit=(16, 20)),
             ex("S1", 5, "BUY", 100, "50", "1", date(2025, 6, 20), ereignis="assignment", waehrung="EUR", zeit=(16, 20)),
             ex("S2", 5, "SELL", 100, "47", "1", date(2025, 8, 1), waehrung="EUR")]
    erg = lauf([leg(1, 4, "P1", "P2", "-1"), leg(2, 5, "S1", "S2", "100")], execs, [put, aktie])
    u = ib_ueberleitung(erg, [ib("S2", 2025, "STK", "-100"), ib("P2", 2025, "OPT", "0")], frozenset({"S2"}), frozenset())[2025]
    assert u["ib_aktien"] == D("-100") and u["station_aktien"] == D("-300")
    assert u["verschobene_praemien"] == D("200")
    assert u["rest_aktien"] == 0 and u["rest_optionen"] == 0
    assert u["ib_optionen_futures"] == 0 and u["station_optionen"] == D("200")


def test_fall_b_offene_praemie_zaehlt_nur_in_der_station():
    e = ex("O", 1, "SELL", 1, "4.00", "1", date(2025, 12, 15), waehrung="EUR")
    erg = lauf([leg(7, 1, "O", None, "-1")], [e], [PUT100])
    u = ib_ueberleitung(erg, [], frozenset(), frozenset({7}))[2025]
    assert u["offene_praemien"] == D("400") and u["station_optionen"] == D("400") and u["rest_optionen"] == 0


def test_fall_c_zeitpunkt_landet_im_rest():
    e1 = ex("O", 1, "SELL", 1, "5.00", "1", date(2025, 12, 15), waehrung="EUR")
    e2 = ex("C", 1, "BUY", 1, "2.00", "1", date(2026, 1, 8), waehrung="EUR")
    erg = lauf([leg(1, 1, "O", "C", "-1")], [e1, e2], [PUT100])
    u = ib_ueberleitung(erg, [ib("C", 2026, "OPT", "300")], frozenset(), frozenset())
    assert u[2025]["rest_optionen"] == D("500") and u[2025]["station_optionen"] == D("500")
    assert u[2026]["rest_optionen"] == D("-500") and u[2026]["station_optionen"] == D("-200")
