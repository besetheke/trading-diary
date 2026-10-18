# ruff: noqa: E501
"""Härtung nach der Prüfung durch Codex (17.10.2026), von Hand gerechnet, EUR, Kurs 1.

 1 Fehlende Schließung: die zugeflossene Prämie 300 bleibt, die Lücke wird gemeldet.
 2 Fehlendes Abrechnungsdatum: Datenlücke, Status „abrechnungsdatum_fehlt“ (kein stilles Ersetzen), auch bei Cash.
 3 Unbekannte Abwicklungsart bei Zuteilung: Datenlücke, nichts bewertet (keine stille Annahme „Lieferung“).
 4 assignment_links entscheiden: zwei Calls auf BBB zur selben Zeit ausgeübt. Call 1 (Kosten 300) → Aktie B1
   (40, verkauft 50): 5.000 − (4.000 + 300) = 700. Call 2 (Kosten 500) → Aktie B2 (45, verkauft 50): 5.000 − (4.500 + 500) = 0.
   Ohne Links würden die 800 je zur Hälfte verteilt: 600 und 100 (heuristisch, Warnung).
 5 ETF-Kategorie je Instrument, auch wenn die einzelne Ausführung sie nicht trägt.
 6 Deklarationsstatus nennt die Gründe.
 7 Zeile 22 mit und ohne Rückkäufe: Prämie 500, Rückkauf 200 → Saldo Stillhalter 300; Zeile 22 = 0 (nur Saldo) oder 200
   (Rückkauf als enthaltener Verlust); Zeile 19 bleibt 300.
 8 Aktien deutscher Emittenten (+50): Hinweis zu Zeile 18/19, Zeile 19 enthält sie unverändert.
 9 Cash: Dividende mit Abrechnung zwei Tage nach dem Buchungsdatum → „kursdatum_abweichend“.
"""
from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from test_steuer_zufluss import PUT100, cash, ex, inst, lauf, leg, saldo  # noqa: E402

from analytics.steuer_konfig import STANDARD_KONFIG  # noqa: E402
from analytics.steuer_zufluss import steuer_zufluss  # noqa: E402

DIV = "WDC(US1) CASH DIVIDEND USD 0.10 PER SHARE (Ordinary Dividend)"


def test_1_fehlende_schliessung_laesst_die_praemie_bestehen():
    e = ex("O", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR")
    erg = lauf([leg(1, 1, "O", "FEHLT", "-1")], [e], [PUT100])
    assert saldo(erg, 2025, "stillhalter") == D("300")
    assert [(d.schluessel, d.grund) for d in erg.datenluecken] == [("FEHLT", "ausfuehrung_fehlt")]


def test_2_fehlendes_abrechnungsdatum_ist_eine_luecke():
    e = ex("O", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR")
    e["settle_date"] = None
    erg = lauf([leg(1, 1, "O", None, "-1")], [e], [PUT100])
    assert erg.stroeme[0].pruefstatus == "abrechnungsdatum_fehlt"
    assert [d.grund for d in erg.datenluecken] == ["abrechnungsdatum_fehlt"]
    c = cash("Dividends", "10", "1", date(2025, 3, 3), beschr=DIV)
    c["settle_date"] = None
    erg = lauf([], [], [], [c])
    assert erg.stroeme[0].pruefstatus == "abrechnungsdatum_fehlt" and erg.datenluecken[0].grund == "abrechnungsdatum_fehlt"


def test_3_unbekannte_abwicklungsart_wird_nicht_als_lieferung_angenommen():
    put = inst(1, "OPT", mult="100", abw=None, right="P", waehrung="EUR")
    execs = [ex("O", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR"),
             ex("Z", 1, "BUY", 1, "0", "1", date(2025, 4, 3), ereignis="assignment", waehrung="EUR")]
    erg = lauf([leg(1, 1, "O", "Z", "-1")], execs, [put])
    assert saldo(erg, 2025, "stillhalter") == D("300")  # die Prämie bleibt
    assert [d.grund for d in erg.datenluecken] == ["abwicklungsart_unbekannt"]


def _zwei_calls():
    c1 = inst(6, "OPT", mult="100", abw="lieferung", right="C", symbol="BBB C40", underlying="BBB", waehrung="EUR")
    c2 = inst(7, "OPT", mult="100", abw="lieferung", right="C", symbol="BBB C45", underlying="BBB", waehrung="EUR")
    akt = inst(8, "STK", symbol="BBB", underlying=None, waehrung="EUR")
    zeit = (16, 20)
    execs = [
        ex("C1a", 6, "BUY", 1, "3.00", "1", date(2025, 2, 3), waehrung="EUR"),
        ex("C1b", 6, "SELL", 1, "0", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=zeit),
        ex("C2a", 7, "BUY", 1, "5.00", "1", date(2025, 2, 3), waehrung="EUR"),
        ex("C2b", 7, "SELL", 1, "0", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=zeit),
        ex("B1a", 8, "BUY", 100, "40", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=zeit),
        ex("B2a", 8, "BUY", 100, "45", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=zeit),
        ex("B1v", 8, "SELL", 100, "50", "1", date(2025, 4, 1), waehrung="EUR"),
        ex("B2v", 8, "SELL", 100, "50", "1", date(2025, 4, 2), waehrung="EUR"),
    ]
    legs = [leg(1, 6, "C1a", "C1b", "1"), leg(2, 7, "C2a", "C2b", "1"),
            leg(3, 8, "B1a", "B1v", "100"), leg(4, 8, "B2a", "B2v", "100")]
    return legs, execs, [c1, c2, akt]


def test_4_assignment_links_entscheiden_ueber_die_zuordnung():
    legs, execs, instrumente = _zwei_calls()
    mit = steuer_zufluss(legs, execs, instrumente, assignment_links=[("C1b", "B1a"), ("C2b", "B2a")])
    je_leg = {s.leg_id: s.betrag_eur for s in mit.stroeme if s.topf == "aktien"}
    assert je_leg == {3: D("700"), 4: D("0")}
    assert not any("heuristisch" in w for w in mit.warnungen)
    ohne = steuer_zufluss(legs, execs, instrumente)
    je_leg = {s.leg_id: s.betrag_eur for s in ohne.stroeme if s.topf == "aktien"}
    assert je_leg == {3: D("600"), 4: D("100")}  # 800 je zur Hälfte
    assert any("heuristisch" in w for w in ohne.warnungen)


def test_5_etf_kategorie_je_instrument():
    etf = inst(14, "STK", symbol="SPY", underlying="SPY")
    etf["unterkategorie"] = "ETF"  # aus einer anderen Ausführung bekannt
    execs = [ex("A", 14, "BUY", 10, "100", "1", date(2025, 1, 5), waehrung="EUR"),  # Ausführung ohne Kategorie
             ex("B", 14, "SELL", 10, "110", "1", date(2025, 2, 5), waehrung="EUR")]
    erg = lauf([leg(1, 14, "A", "B", "10")], execs, [etf])
    assert 2025 not in erg.jahre()  # kein Aktien-Strom: der ETF-Anteil steht in den offenen Regeln
    assert [r.art for r in erg.regeln_offen] == ["etf_investmentsteuer"]
    ohne = inst(15, "STK", symbol="ZZZ", underlying="ZZZ")  # nirgends eine Kategorie
    e2 = [ex("C", 15, "BUY", 1, "10", "1", date(2025, 1, 5), waehrung="EUR"),
          ex("D", 15, "SELL", 1, "12", "1", date(2025, 2, 5), waehrung="EUR")]
    erg = lauf([leg(2, 15, "C", "D", "1")], e2, [ohne])
    assert saldo(erg, 2025, "aktien") == D("2")  # als Aktie behandelt …
    assert any("ohne IB-Kategorie" in w and "ZZZ" in w for w in erg.warnungen)  # … aber nicht still


def test_6_deklarationsstatus_nennt_gruende_und_hinweise():
    # AP-10e: ohne blockierenden Grund „deklarierbar mit Erläuterung“ (§ 150 Abs. 7 AO), die Hinweise bleiben sichtbar.
    e = ex("O", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), settle=date(2025, 3, 5), waehrung="EUR")
    erg = lauf([leg(1, 1, "O", None, "-1")], [e], [PUT100])
    st = erg.jahre()[2025]["deklarationsstatus"]
    assert st["status"] == "deklarierbar_mit_erlaeuterung" and st["gruende"] == []
    text = " ".join(st["hinweise"])
    assert "vorsichtige Standardbehandlung" in text and "Kursdatum" in text and "Verlustvorträge" in text
    assert "Ergänzende Angaben" in text
    # Ein blockierender Grund (Datenlücke: Rückkauf ohne Kurs) macht das Jahr „nicht deklarationsfähig“.
    e1 = ex("O2", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR")
    e2 = ex("C2", 1, "BUY", 1, "1.00", None, date(2025, 4, 3), waehrung="EUR")
    blockiert = lauf([leg(1, 1, "O2", "C2", "-1")], [e1, e2], [PUT100]).jahre()[2025]["deklarationsstatus"]
    assert blockiert["status"] == "nicht_deklarationsfaehig" and "Datenlücken" in " ".join(blockiert["gruende"])


def test_7_zeile_22_standard_mit_rueckkaeufen_vergleich_ohne():
    e1 = ex("O", 1, "SELL", 1, "5.00", "1", date(2025, 3, 3), waehrung="EUR")
    e2 = ex("C", 1, "BUY", 1, "2.00", "1", date(2025, 4, 3), waehrung="EUR")
    welt = ([leg(1, 1, "O", "C", "-1")], [e1, e2], [PUT100])
    kap = lauf(*welt).jahre()[2025]["kap"]                              # Standard: BMF-Behandlung
    assert kap["posten"]["verluste_ohne_aktien"]["betrag"] == D("200")
    assert kap["alternativen"][0]["betrag"] == 0 and kap["alternativen"][0]["zeile"] == 22
    assert "Vergleichsrechnung" in kap["alternativen"][0]["name"]
    nur_saldo = lauf(*welt, konfig=replace(STANDARD_KONFIG, rueckkauf_als_verlust=False)).jahre()[2025]["kap"]
    assert nur_saldo["posten"]["verluste_ohne_aktien"]["betrag"] == 0 and nur_saldo["alternativen"][0]["betrag"] == D("200")
    for k in (kap, nur_saldo):
        assert k["posten"]["ausl_kapitalertraege_saldo"]["betrag"] == D("300")


def test_8_aktien_deutscher_emittenten_stehen_in_zeile_18():
    de = inst(20, "STK", symbol="HNR1", underlying=None, waehrung="EUR")
    de["land"] = "DE"
    de["unterkategorie"] = "COMMON"
    execs = [ex("A", 20, "BUY", 1, "100", "1", date(2025, 1, 5), waehrung="EUR"),
             ex("B", 20, "SELL", 1, "150", "1", date(2025, 2, 5), waehrung="EUR")]
    kap = lauf([leg(1, 20, "A", "B", "1")], execs, [de]).jahre()[2025]["kap"]
    assert kap["posten"]["inl_kapitalertraege_saldo"]["betrag"] == D("50")       # Zeile 18
    assert kap["posten"]["ausl_kapitalertraege_saldo"]["betrag"] == 0           # Zeile 19 ohne HNR1
    assert kap["posten"]["aktiengewinne"]["betrag"] == D("50")                   # Zeile 20 bleibt
    assert any("Zeile 18" in h and "50.00" in h for h in kap["hinweise"])


def test_9_cash_mit_abweichendem_abrechnungsdatum_ist_kursdatum_abweichend():
    c = cash("Dividends", "10", "1", date(2025, 3, 3), beschr=DIV)
    c["settle_date"] = date(2025, 3, 5)
    assert lauf([], [], [], [c]).stroeme[0].pruefstatus == "kursdatum_abweichend"
    c["settle_date"] = date(2025, 3, 3)
    assert lauf([], [], [], [c]).stroeme[0].pruefstatus == "ok"
