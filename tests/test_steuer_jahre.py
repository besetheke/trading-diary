# ruff: noqa: E501
"""Jahresübersicht der Steuer-Aufbereitung: Summen je Zuflussjahr, von Hand gerechnet."""
from decimal import Decimal as D

from analytics.steuer import SteuerErgebnis, TopfZeile
from analytics.steuer_jahre import jahres_uebersicht


def _topf(jahr, topf, waehrung, eur, legs, fehlt=0):
    return TopfZeile(jahr=jahr, topf=topf, waehrung=waehrung, brutto=D(0), kommission=D(0), netto=D(0),
                     netto_eur_ib=D(eur), eur_kurs_fehlt=fehlt, anzahl_legs=legs, basis_ungeklaert=0)


def test_toepfe_aller_waehrungen_werden_je_jahr_in_eur_addiert():
    e = SteuerErgebnis(
        toepfe=(_topf(2025, "aktien", "USD", "-100.50", 3), _topf(2025, "aktien", "EUR", "20", 1),
                _topf(2025, "termingeschaefte", "USD", "1000", 10, fehlt=2),
                _topf(2026, "termingeschaefte", "EUR", "5", 1)),
        details=(), ungeklaert=(), ertraege=(), fehler=())
    j = jahres_uebersicht(e, [])
    assert j[2025]["aktien_eur"] == D("-80.50") and j[2025]["aktien_legs"] == 4
    assert j[2025]["termin_eur"] == D("1000") and j[2025]["eur_kurs_fehlt"] == 2
    assert j[2026]["termin_eur"] == D("5") and j[2026]["aktien_eur"] == 0
    assert list(j) == [2025, 2026]


def test_praemie_der_lieferungen_je_jahr():
    from datetime import datetime

    from analytics.steuer import SteuerLegZeile

    def leg(exec_id, jahr, topf, eur):
        return SteuerLegZeile(leg_id=1, close_exec_id=exec_id, conid=1, symbol="X", handelszeit=datetime(jahr, 5, 5),
                              jahr=jahr, topf=topf, waehrung="USD", menge=D(1), brutto=D(0), kommission=D(0),
                              netto=D(0), buchungskurs=D(1), netto_eur_ib=D(eur), basis_ungeklaert=False)

    e = SteuerErgebnis(
        toepfe=(), ungeklaert=(), ertraege=(), fehler=(),
        details=(leg("A", 2025, "termingeschaefte", "300"), leg("B", 2025, "termingeschaefte", "50.5"),
                 leg("C", 2025, "termingeschaefte", "7"), leg("A2", 2025, "aktien", "999")))
    j = jahres_uebersicht(e, [], frozenset({"A", "B", "A2"}))
    assert j[2025]["praemie_lieferung_eur"] == D("350.5")      # A + B; C endete ohne Lieferung, A2 ist Aktie


def test_ertraege_je_jahr_nur_steuerliche_kategorien():
    e = SteuerErgebnis(toepfe=(), details=(), ungeklaert=(), ertraege=(), fehler=())
    monate = [("2025-03", "dividenden", D("10")), ("2025-11", "dividenden", D("5.5")),
              ("2025-11", "quellensteuer", D("-2")), ("2026-01", "zinsen_gezahlt", D("-7")),
              ("2025-05", "kommissionen", D("-99")), ("2025-05", "ein_auszahlungen", D("500"))]
    j = jahres_uebersicht(e, monate)
    assert j[2025]["ertraege"]["dividenden"] == D("15.5")
    assert j[2025]["ertraege"]["quellensteuer"] == D("-2")
    assert j[2026]["ertraege"]["zinsen_gezahlt"] == D("-7")
    assert "kommissionen" not in j[2025]["ertraege"]          # steckt schon in den Töpfen
