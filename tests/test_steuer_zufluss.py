# ruff: noqa: E501
"""AP-10b: Abnahmebasis der Steuer nach Zufluss je Zahlungsstrom (Regeln R1–R16, OF-92/OF-93).

Alles frei erfunden und von Hand gerechnet (CLAUDE.md Regel 8). Arbeitsstand des Steuerberaters, vor Abnahme zu
bestätigen — die Tests halten die Regeln fest, sie beweisen nicht ihre Richtigkeit. Keine Verlustverrechnung.

Konventionen der Testwelt: EUR-Kurs `buchungskurs` = EUR je 1 Einheit der Handelswährung (IB `fxRateToBase`);
Kommission negativ (wie gespeichert); Optionsmultiplikator 100; Ausführungsmenge wie bei IB Flex mit Vorzeichen
(SELL negativ) — die Rechnung nimmt den Betrag.

Fälle (Nummern wie in auftraege/AP-10b.md):
 1 Short Put 29.12.2025 eröffnet, 05.01.2026 zurückgekauft
      Prämie 5,00 × 100 = 500 USD, Kommission −1, Kurs 0,90  → (500 − 1) × 0,90 = 449,10 EUR im Jahr 2025
      Rückkauf 2,00 × 100 = 200 USD, Kommission −1, Kurs 0,85 → (−200 − 1) × 0,85 = −170,85 EUR im Jahr 2026
 2 Prämie 4,00 × 100 = 400 USD, Kurs 0,90 = 360,00 EUR, Handel 31.12.2025, Abrechnung 02.01.2026
      Regel „settle“ → 2026, Regel „trade“ → 2025; betroffen = 1; IB-Kurs gehört zum Handelstag
 3 Spread: Short Put Prämie 300 (Stillhalter), Long Put 100 EUR Kosten, beide verfallen: Termingeschäft −100
 4 Short Put zugeteilt: Prämie 200 bleibt Stillhalter; Aktie 100 × 50 + Erwerbskosten 1 = 5.001; Verkauf
      100 × 47 − Veräußerungskosten 1 = 4.699 → Aktien −302
 5 Long Call ausgeübt (Kosten 300): Aktie 100 × 40 + 300 = 4.300, Verkauf 4.500 → +200, kein Termingeschäft
   Long Put ausgeübt (Kosten 200): Aktie 100 × 50 = 5.000, Erlös 100 × 45 − 200 = 4.300 → −700, kein Termingeschäft
 6 Barausgleich: Prämie 10 × 100 × 0,9 = 900 Stillhalter; Zahlung 12 × 100 × 0,9 = −1.080 Termingeschäft
 7 Kauf 100 USD × 0,90 = 90 EUR, Verkauf 100 USD × 0,80 = 80 EUR → −10 EUR (altes Netto-Verfahren: 0)
 8 Aktien −1.000, Termingeschäfte +500, Dividende +50: nichts verrechnet, Gewinne und Verluste getrennt
 9 Dividende 100 USD, einbehalten 16,67: anrechenbar 15,00 (15 %), erstattungsfähig 1,67; Land ohne Satz: ungeklärt
10 Ersatzzahlung 22 USD, Steuer 3,30: nicht anrechenbar, „Einordnung offen“, kein „steuerfrei“
11 KAP-Zeilen 2025 laut Antwort (19, 20, 22, 23, 41), 2026 „ungeprueft“
12 Offene Short-Position (2 Kontrakte à 4,00, Kommission −2): Prämie (800 − 2) = 798 im Zuflussjahr
13 4 Kontrakte à 5,00 verkauft (Kommission −4), 3 zurückgekauft (Kommission −3), 1 offen: Σ Kommission −7 genau einmal
14 Rückkauf ohne Kurs: Prämie bleibt, Rückkauf steht in den Datenlücken
15 ETF-Anteil: nicht im Aktien-Topf, „ungeklärt (InvStG)“; Option auf den ETF bleibt Stillhalter
16 Dividende ohne Kurs: Datenlücke, nicht in der Summe
17 Ungeklärte Basis: ohne Anfangsbestand „offen“, mit Anfangsbestand (100 × 40) und Verkauf 100 × 45: +500
18 Ausgabe nennt Methode: Kursquelle, Datumsregeln, Prüfstatus; Warnung bei leerem Anfangsbestand
"""
from datetime import date, datetime
from decimal import Decimal as D

import pytest

pytest.importorskip("analytics.steuer_zufluss")

from analytics.steuer_konfig import STANDARD_KONFIG, kap_zeilen  # noqa: E402
from analytics.steuer_zufluss import Anfangsbestand, steuer_zufluss  # noqa: E402


def ex(exec_id, conid, side, menge, preis, kurs, tag, *, komm="0", ereignis="trade", waehrung="USD",
       settle=None, schluss=None, unterkat=None, zeit=(10, 0)):
    return {
        "exec_id": exec_id, "conid": conid, "side": side,
        "menge": -D(menge) if side == "SELL" else D(menge),
        "preis": D(preis), "waehrung": waehrung, "kommission": D(komm), "kommission_waehrung": waehrung,
        "buchungskurs": None if kurs is None else D(kurs),
        "handelszeit": datetime(tag.year, tag.month, tag.day, *zeit), "ereignistyp": ereignis,
        "schlusskurs": None if schluss is None else D(schluss),
        "trade_date": tag, "settle_date": settle or tag, "unterkategorie": unterkat,
    }


def inst(conid, klasse, *, mult="1", abw=None, symbol="X", underlying="X", waehrung="USD", right=None, land="US"):
    return {"conid": conid, "asset_class": klasse, "multiplikator": D(mult), "abwicklungsart": abw,
            "symbol": symbol, "underlying": underlying, "waehrung": waehrung, "right": right, "land": land}


def leg(leg_id, conid, offen, zu, menge, *, basis_ungeklaert=False):
    return {"leg_id": leg_id, "conid": conid, "open_exec_id": offen, "close_exec_id": zu, "menge": D(menge),
            "open_faktor": D(1), "close_faktor": D(1), "offen_ja_nein": zu is None,
            "basis_ungeklaert": basis_ungeklaert}


def cash(typ, betrag, kurs, tag, *, symbol="WDC", beschr, land="US", waehrung="USD"):
    return {"datum": datetime(tag.year, tag.month, tag.day), "typ": typ, "betrag": D(betrag),
            "kurs": None if kurs is None else D(kurs), "waehrung": waehrung, "symbol": symbol,
            "beschreibung": beschr, "settle_date": tag, "land": land}


def lauf(legs, execs, instrumente, cash_zeilen=(), konfig=STANDARD_KONFIG, ab=()):
    return steuer_zufluss(legs, execs, instrumente, cash_zeilen, konfig=konfig, anfangsbestaende=ab)


def saldo(erg, jahr, topf):
    return erg.jahre()[jahr]["toepfe"].get(topf, {}).get("saldo", D(0))


PUT100 = inst(1, "OPT", mult="100", abw="lieferung", right="P")


def test_1_short_put_praemie_und_rueckkauf_in_verschiedenen_jahren():
    e1 = ex("O", 1, "SELL", 1, "5.00", "0.90", date(2025, 12, 29), komm="-1", settle=date(2025, 12, 30))
    e2 = ex("C", 1, "BUY", 1, "2.00", "0.85", date(2026, 1, 5), komm="-1", settle=date(2026, 1, 6))
    erg = lauf([leg(1, 1, "O", "C", "-1")], [e1, e2], [PUT100])
    assert saldo(erg, 2025, "stillhalter") == D("449.10")
    assert saldo(erg, 2026, "stillhalter") == D("-170.85")


def test_2_datumsregel_betroffenheit_und_kursdatum():
    e1 = ex("O", 1, "SELL", 1, "4.00", "0.90", date(2025, 12, 31), settle=date(2026, 1, 2))
    welt = ([leg(1, 1, "O", None, "-1")], [e1], [PUT100])
    standard = lauf(*welt)                                     # Prämie nach Abrechnungstag → 2026
    assert saldo(standard, 2026, "stillhalter") == D("360.00") and 2025 not in standard.jahre()
    s = standard.stroeme[0]
    assert s.steuerdatum == date(2026, 1, 2) and s.fx_datum == date(2025, 12, 31)      # IB-Kurs gehört zum Handelstag
    assert s.pruefstatus == "kursdatum_abweichend"                                     # nicht still verbunden
    assert standard.jahre()[2026]["betroffen"] == 1                                    # bei Regelwechsel anderes Jahr
    trade = STANDARD_KONFIG.mit_regel("stillhalterpraemie", steuerdatum="tradeDate", fx="tradeDate")
    erg = lauf(*welt, konfig=trade)
    assert saldo(erg, 2025, "stillhalter") == D("360.00") and erg.stroeme[0].pruefstatus == "ok"


def test_3_spread_beine_getrennt_langes_bein_verfaellt_als_verlust():
    kurz, lang = inst(2, "OPT", mult="100", abw="lieferung", right="P", waehrung="EUR"), \
        inst(3, "OPT", mult="100", abw="lieferung", right="P", waehrung="EUR")
    execs = [ex("K1", 2, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR"),
             ex("L1", 3, "BUY", 1, "1.00", "1", date(2025, 3, 3), waehrung="EUR"),
             ex("K2", 2, "BUY", 1, "0", "1", date(2025, 3, 21), ereignis="expiry", waehrung="EUR"),
             ex("L2", 3, "SELL", 1, "0", "1", date(2025, 3, 21), ereignis="expiry", waehrung="EUR")]
    erg = lauf([leg(1, 2, "K1", "K2", "-1"), leg(2, 3, "L1", "L2", "1")], execs, [kurz, lang])
    assert saldo(erg, 2025, "stillhalter") == D("300")         # kurzes Bein: Prämie, Verfall ohne Wirkung
    assert saldo(erg, 2025, "termingeschaefte") == D("-100")   # langes Bein: wertloser Verfall = Verlust
    t = erg.jahre()[2025]["toepfe"]["termingeschaefte"]
    assert t["gewinne"] == 0 and t["verluste"] == D("-100")


def test_4_short_put_zugeteilt_praemie_bleibt_separat_erwerbs_und_veraeusserungskosten():
    put = inst(4, "OPT", mult="100", abw="lieferung", right="P", symbol="AAA P50", underlying="AAA", waehrung="EUR")
    aktie = inst(5, "STK", symbol="AAA", underlying="AAA", waehrung="EUR")
    execs = [ex("P1", 4, "SELL", 1, "2.00", "1", date(2025, 5, 1), waehrung="EUR"),
             ex("P2", 4, "BUY", 1, "0", "1", date(2025, 6, 20), ereignis="assignment", waehrung="EUR", zeit=(16, 20)),
             ex("S1", 5, "BUY", 100, "50", "1", date(2025, 6, 20), komm="-1", ereignis="assignment", waehrung="EUR", zeit=(16, 20)),
             ex("S2", 5, "SELL", 100, "47", "1", date(2025, 8, 1), komm="-1", waehrung="EUR")]
    erg = lauf([leg(1, 4, "P1", "P2", "-1"), leg(2, 5, "S1", "S2", "100")], execs, [put, aktie])
    assert saldo(erg, 2025, "stillhalter") == D("200")         # Prämie nicht in den Anschaffungskosten
    assert saldo(erg, 2025, "aktien") == D("-302")             # 4.699 − 5.001


def test_5_gekaufte_option_mit_lieferung_geht_in_die_aktie():
    call = inst(6, "OPT", mult="100", abw="lieferung", right="C", symbol="BBB C40", underlying="BBB", waehrung="EUR")
    put = inst(8, "OPT", mult="100", abw="lieferung", right="P", symbol="CCC P45", underlying="CCC", waehrung="EUR")
    a_b = inst(7, "STK", symbol="BBB", underlying="BBB", waehrung="EUR")
    a_c = inst(9, "STK", symbol="CCC", underlying="CCC", waehrung="EUR")
    execs = [
        ex("C1", 6, "BUY", 1, "3.00", "1", date(2025, 2, 3), waehrung="EUR"),
        ex("C2", 6, "SELL", 1, "0", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
        ex("B1", 7, "BUY", 100, "40", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
        ex("B2", 7, "SELL", 100, "45", "1", date(2025, 4, 1), waehrung="EUR"),
        ex("P1", 8, "BUY", 1, "2.00", "1", date(2025, 2, 3), waehrung="EUR"),
        ex("P2", 8, "SELL", 1, "0", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
        ex("D1", 9, "BUY", 100, "50", "1", date(2025, 1, 10), waehrung="EUR"),
        ex("D2", 9, "SELL", 100, "45", "1", date(2025, 3, 21), ereignis="exercise", waehrung="EUR", zeit=(16, 20)),
    ]
    legs = [leg(1, 6, "C1", "C2", "1"), leg(2, 7, "B1", "B2", "100"), leg(3, 8, "P1", "P2", "1"), leg(4, 9, "D1", "D2", "100")]
    erg = lauf(legs, execs, [call, put, a_b, a_c])
    assert saldo(erg, 2025, "aktien") == D("200") + D("-700")  # Long Call: 4.500 − (4.000 + 300); Long Put: (4.500 − 200) − 5.000
    assert saldo(erg, 2025, "termingeschaefte") == 0           # kein Termingeschäft bei Lieferung


def test_6_barausgleich_ist_termingeschaeftsverlust():
    spx = inst(10, "OPT", mult="100", abw="barausgleich", right="C", symbol="SPX", underlying="SPX")
    execs = [ex("A", 10, "SELL", 1, "10.00", "0.90", date(2025, 6, 2)),
             ex("Z", 10, "BUY", 1, "0", "0.90", date(2025, 6, 2), ereignis="assignment", schluss="12.00")]
    erg = lauf([leg(1, 10, "A", "Z", "-1")], execs, [spx])
    assert saldo(erg, 2025, "stillhalter") == D("900.00")
    assert saldo(erg, 2025, "termingeschaefte") == D("-1080.00")


def test_7_waehrung_je_zahlungsstrom_nicht_netto_zum_schlusskurs():
    aktie = inst(11, "STK", symbol="DDD", underlying="DDD")
    execs = [ex("K", 11, "BUY", 1, "100", "0.90", date(2025, 1, 10)),
             ex("V", 11, "SELL", 1, "100", "0.80", date(2025, 2, 10))]
    erg = lauf([leg(1, 11, "K", "V", "1")], execs, [aktie])
    assert saldo(erg, 2025, "aktien") == D("-10")              # 80 − 90, nicht 0


def test_8_verlusttoepfe_werden_nicht_verrechnet_gewinne_und_verluste_getrennt():
    aktie, opt = inst(12, "STK", symbol="EEE", underlying="EEE", waehrung="EUR"), inst(13, "OPT", mult="100", abw="lieferung", right="C", waehrung="EUR")
    execs = [ex("A1", 12, "BUY", 10, "200", "1", date(2025, 1, 5), waehrung="EUR"),
             ex("A2", 12, "SELL", 10, "100", "1", date(2025, 2, 5), waehrung="EUR"),
             ex("T1", 13, "BUY", 1, "2.00", "1", date(2025, 1, 5), waehrung="EUR"),
             ex("T2", 13, "SELL", 1, "7.00", "1", date(2025, 2, 5), waehrung="EUR")]
    c = [cash("Dividends", "50", "1", date(2025, 3, 3), symbol="EEE", beschr="EEE(US1) CASH DIVIDEND EUR 0.05 PER SHARE (Ordinary Dividend)", waehrung="EUR")]
    erg = lauf([leg(1, 12, "A1", "A2", "10"), leg(2, 13, "T1", "T2", "1")], execs, [aktie, opt], c)
    j = erg.jahre()[2025]["toepfe"]
    assert j["aktien"]["saldo"] == D("-1000") and j["aktien"]["verluste"] == D("-1000") and j["aktien"]["gewinne"] == 0
    assert j["termingeschaefte"]["saldo"] == D("500") and j["termingeschaefte"]["gewinne"] == D("500")
    assert j["dividenden"]["saldo"] == D("50")
    assert "verrechnet" not in erg.jahre()[2025]                # die Seite verrechnet nichts


def test_9_quellensteuer_vorlaeufige_obergrenze_in_drei_zustaenden():
    c = [cash("Dividends", "100", "1", date(2025, 5, 5), beschr="WDC(US1) CASH DIVIDEND USD 1.00 PER SHARE (Ordinary Dividend)"),
         cash("Withholding Tax", "-16.67", "1", date(2025, 5, 5), beschr="WDC(US1) CASH DIVIDEND USD 1.00 PER SHARE - US TAX"),
         cash("Dividends", "80", "1", date(2025, 6, 6), symbol="YYY", land="XX", beschr="YYY(XX1) CASH DIVIDEND USD 1.00 PER SHARE (Ordinary Dividend)"),
         cash("Withholding Tax", "-10", "1", date(2025, 6, 6), symbol="YYY", land="XX", beschr="YYY(XX1) CASH DIVIDEND USD 1.00 PER SHARE - XX TAX")]
    q = lauf([], [], [], c).jahre()[2025]["quellensteuer"]
    assert q["vorlaeufig_anrechenbar"] == D("15.00")
    assert q["erstattungsfaehig"] == D("1.67")
    assert q["ungeklaert"] == D("10")                          # Land ohne Satz: nicht berechnet


def test_10_ersatzzahlung_nicht_automatisch_anrechenbar_und_nie_steuerfrei():
    c = [cash("Payment In Lieu Of Dividends", "22", "1", date(2025, 7, 7), symbol="GPK", beschr="GPK(US2) PAYMENT IN LIEU OF DIVIDEND (Ordinary Dividend)"),
         cash("Withholding Tax", "-3.30", "1", date(2025, 7, 7), symbol="GPK", beschr="GPK(US2) PAYMENT IN LIEU OF DIVIDEND - US TAX")]
    erg = lauf([], [], [], c)
    j = erg.jahre()[2025]
    assert j["quellensteuer"]["vorlaeufig_anrechenbar"] == 0
    assert j["quellensteuer"]["ersatzzahlung_zu_pruefen"] == D("3.30")
    assert j["toepfe"]["so_kandidat"]["saldo"] == D("22")
    offen = [r for r in erg.regeln_offen if r.art == "ersatzzahlung"]
    assert offen and "Einordnung offen" in offen[0].text and "Freigrenze nicht abschließend geprüft" in offen[0].text
    assert not any("steuerfrei" in r.text.lower() for r in erg.regeln_offen)


def test_11_kap_zeilen_je_formularjahr():
    z25 = kap_zeilen(2025)
    assert z25["status"] == "laut_berater_antwort"
    assert z25["zeilen"] == {"ausl_kapitalertraege_saldo": 19, "aktiengewinne": 20, "verluste_ohne_aktien": 22,
                             "aktienverluste": 23, "anrechenbare_quellensteuer": 41}
    assert kap_zeilen(2026)["status"] == "ungeprueft"


def test_12_offene_short_position_zaehlt_im_zuflussjahr():
    e = ex("O", 1, "SELL", 2, "4.00", "1", date(2025, 12, 15), komm="-2", waehrung="EUR")
    erg = lauf([leg(1, 1, "O", None, "-2")], [e], [inst(1, "OPT", mult="100", abw="lieferung", right="P", waehrung="EUR")])
    assert saldo(erg, 2025, "stillhalter") == D("798")


def test_13_teilglattstellung_restmenge_kommission_genau_einmal():
    opt = inst(1, "OPT", mult="100", abw="lieferung", right="P", waehrung="EUR")
    execs = [ex("E1", 1, "SELL", 4, "5.00", "1", date(2025, 1, 10), komm="-4", waehrung="EUR"),
             ex("E2", 1, "BUY", 3, "1.00", "1", date(2025, 2, 10), komm="-3", waehrung="EUR")]
    erg = lauf([leg(1, 1, "E1", "E2", "-3"), leg(2, 1, "E1", None, "-1")], execs, [opt])
    assert sum(s.kommission_eur for s in erg.stroeme) == D("-7")                       # −4 und −3, je einmal
    assert sum(s.brutto_eur for s in erg.stroeme if s.vorgang == "stillhalterpraemie") == D("2000")   # 4 × 5,00 × 100
    assert saldo(erg, 2025, "stillhalter") == D("2000") - D("300") - D("7")


def test_14_fehlender_kurs_des_rueckkaufs_laesst_die_praemie_bestehen():
    e1 = ex("O", 1, "SELL", 1, "5.00", "0.90", date(2025, 12, 20))
    e2 = ex("C", 1, "BUY", 1, "2.00", None, date(2026, 1, 10))
    erg = lauf([leg(1, 1, "O", "C", "-1")], [e1, e2], [PUT100])
    assert saldo(erg, 2025, "stillhalter") == D("450.00")
    assert 2026 not in erg.jahre() or "stillhalter" not in erg.jahre()[2026]["toepfe"]
    assert [d.grund for d in erg.datenluecken] == ["kurs_fehlt"] and erg.datenluecken[0].schluessel == "C"


def test_15_etf_anteil_ist_ungeklaert_option_auf_etf_bleibt_stillhalter():
    etf = inst(14, "STK", symbol="SPY", underlying="SPY")
    opt = inst(15, "OPT", mult="100", abw="lieferung", right="P", symbol="SPY P", underlying="SPY")
    execs = [ex("A", 14, "BUY", 10, "100", "1", date(2025, 1, 5), waehrung="EUR", unterkat="ETF"),
             ex("B", 14, "SELL", 10, "110", "1", date(2025, 2, 5), waehrung="EUR", unterkat="ETF"),
             ex("O", 15, "SELL", 1, "2.00", "1", date(2025, 3, 5), waehrung="EUR")]
    erg = lauf([leg(1, 14, "A", "B", "10"), leg(2, 15, "O", None, "-1")], execs, [etf, opt])
    assert "aktien" not in erg.jahre()[2025]["toepfe"]
    assert saldo(erg, 2025, "stillhalter") == D("200")
    offen = [r for r in erg.regeln_offen if r.art == "etf_investmentsteuer"]
    assert len(offen) == 1 and offen[0].anzahl == 1 and offen[0].betrag_eur == D("100")


def test_16_cash_buchung_ohne_kurs_ist_eine_datenluecke():
    c = [cash("Dividends", "30", None, date(2025, 4, 4), symbol="ABC", beschr="ABC(US3) CASH DIVIDEND USD 0.30 PER SHARE (Ordinary Dividend)")]
    erg = lauf([], [], [], c)
    assert [d.grund for d in erg.datenluecken] == ["kurs_fehlt"]
    assert 2025 not in erg.jahre() or erg.jahre()[2025]["toepfe"].get("dividenden", {}).get("saldo", D(0)) == 0


def test_17_ungeklaerte_basis_braucht_einen_anfangsbestand():
    aktie = inst(16, "STK", symbol="FFF", underlying="FFF", waehrung="EUR")
    execs = [ex("X1", 16, "BUY", 100, "1", "1", date(2024, 1, 2), waehrung="EUR"),
             ex("X2", 16, "SELL", 100, "45", "1", date(2025, 6, 1), waehrung="EUR")]
    legs = [leg(1, 16, "X1", "X2", "100", basis_ungeklaert=True)]
    ohne = lauf(legs, execs, [aktie])
    assert "aktien" not in ohne.jahre().get(2025, {"toepfe": {}})["toepfe"]
    assert [r.art for r in ohne.regeln_offen] == ["basis_ungeklaert"]
    ab = Anfangsbestand(conid=16, menge=D(100), ak_je_stueck=D("40"), datum=date(2024, 1, 2), waehrung="EUR", kurs=D("1"))
    mit = lauf(legs, execs, [aktie], ab=[ab])
    assert saldo(mit, 2025, "aktien") == D("500")              # 100 × 45 − 100 × 40
    assert not mit.regeln_offen


def test_18_ausgabe_nennt_methode_und_warnt_ohne_anfangsbestand():
    erg = lauf([], [], [])
    m = erg.methode
    assert m["kursquelle"] == "IB fxRateToBase je Ausführung" and m["pruefstatus"] == "ungeprueft"
    assert m["datumsregeln"]["stillhalterpraemie"]["steuerdatum"] == "settleDateTarget"
    assert m["datumsregeln"]["wertpapierverkauf"]["steuerdatum"] == "tradeDate"
    assert any("Anfangsbestand" in w for w in erg.warnungen)
