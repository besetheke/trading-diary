# ruff: noqa: E501
"""Einzelfälle und Listen für den Steuerberater (AP-10d Teil 0): Einzelfälle der offenen Regeln, CSV-Listen."""
from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from test_steuer_zufluss import PUT100, cash, ex, inst, lauf, leg  # noqa: E402

from journal.steuer_zufluss import listen_schreiben  # noqa: E402


def test_regeln_offen_tragen_einzelfaelle_und_die_listen_werden_geschrieben(tmp_path):
    etf = inst(14, "STK", symbol="SPY", underlying="SPY")
    execs = [ex("A", 14, "BUY", 10, "100", "1", date(2025, 1, 5), waehrung="EUR", unterkat="ETF"),
             ex("B", 14, "SELL", 10, "110", "1", date(2025, 2, 5), waehrung="EUR", unterkat="ETF")]
    c = [cash("Payment In Lieu Of Dividends", "22", "1", date(2025, 7, 7), symbol="GPK", beschr="GPK(US2) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)"),
         cash("Withholding Tax", "-3.30", "1", date(2025, 7, 7), symbol="GPK", beschr="GPK(US2) PAYMENT IN LIEU OF DIVIDEND - US TAX")]
    erg = lauf([leg(1, 14, "A", "B", "10")], execs, [etf], c)
    etf_falle = next(r for r in erg.regeln_offen if r.art == "etf_investmentsteuer").details
    assert etf_falle == [{"leg_id": 1, "symbol": "SPY", "eroeffnet": "2025-01-05", "geschlossen": "2025-02-05", "ergebnis_eur": D("100")}]
    anzahl = listen_schreiben(erg, tmp_path / "listen")
    assert anzahl["etf_beine.csv"] == 1 and anzahl["ersatzzahlungen.csv"] == 1
    assert anzahl["quellensteuer_zu_pruefen.csv"] == 1                       # 3,30 auf die Ersatzzahlung
    zeilen = (tmp_path / "listen" / "ersatzzahlungen.csv").read_text(encoding="utf-8-sig").splitlines()
    assert zeilen[0] == "jahr;datum;symbol;betrag_eur;waehrung;beschreibung"
    assert zeilen[1].startswith("2025;2025-07-07;GPK;22.00;USD;GPK(US2) PAYMENT IN LIEU")


def test_jahreswechsel_liste_enthaelt_nur_betroffene_buchungen(tmp_path):
    e1 = ex("O", 1, "SELL", 1, "4.00", "0.90", date(2025, 12, 31), settle=date(2026, 1, 2))      # betroffen
    e2 = ex("P", 1, "SELL", 1, "4.00", "0.90", date(2025, 3, 3), settle=date(2025, 3, 4))        # nicht betroffen
    erg = lauf([leg(1, 1, "O", None, "-1"), leg(2, 1, "P", None, "-1")], [e1, e2], [PUT100])
    listen_schreiben(erg, tmp_path)
    zeilen = (tmp_path / "jahreswechsel.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(zeilen) == 2 and zeilen[1].startswith("2026;2025;2026-01-02;stillhalterpraemie")
