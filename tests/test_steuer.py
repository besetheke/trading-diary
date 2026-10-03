"""Abnahmetests für AP-10v: Steuerliche Auswertung (Töpfe, Jahresabgrenzung, CSV).

Nach §11.2 des Plans vom starken Modell geschrieben; für das günstige Modell
(AP-10k) unveränderlich. Rot bis AP-10k umsetzt — der Importfehler von
``analytics.steuer`` bzw. ``journal.steuer`` ist der erwartete Zustand, kein
Defekt dieser Tests. Maßgeblich ist der Vertrag in auftraege/AP-10v.md;
jede erwartete Zahl ist per Hand gerechnet und am Ort begründet
(CLAUDE.md, Regel 8).
"""

from datetime import date, datetime
from decimal import Decimal as D

from sqlalchemy import insert

from analytics.steuer import (
    ErtragsZeile,
    SteuerErgebnis,
    SteuerFehler,
    SteuerLegZeile,
    TopfZeile,
    als_csv,
    steuer_auswertung,
)
from journal.cli import main
from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import (
    corporate_actions,
    executions,
    flex_cash_transactions,
    import_runs,
    instruments,
)
from journal.steuer import steuer_bericht

# ---------------------------------------------------------------------------
# Szenario A (reine Funktion): Instrumente, Schließungen, Legs, Cash.
# ---------------------------------------------------------------------------

CONID_OPT = 1001  # SPXW-Option, USD — Termingeschäft
CONID_STK_ALT = 2001  # IDX9, USD — Aktie
CONID_STK_NEU = 2002  # IDX9N, USD — Aktie unter neuer conid (nach Split)
CONID_FUT = 3001  # FDAX, EUR — Termingeschäft in EUR

INSTRUMENTE = {
    satz["conid"]: satz
    for satz in (
        {"conid": CONID_OPT, "symbol": "SPXW 270117C6000", "asset_class": "OPT",
         "waehrung": "USD"},
        {"conid": CONID_STK_ALT, "symbol": "IDX9", "asset_class": "STK",
         "waehrung": "USD"},
        {"conid": CONID_STK_NEU, "symbol": "IDX9N", "asset_class": "STK",
         "waehrung": "USD"},
        {"conid": CONID_FUT, "symbol": "FDAX", "asset_class": "FUT",
         "waehrung": "EUR"},
        {"conid": 9800, "symbol": "ETF9", "asset_class": "FUND", "waehrung": "USD"},
        {"conid": 7777, "symbol": "EUR.USD", "asset_class": "CASH", "waehrung": "USD"},
    )
}


def _ausf(exec_id, handelszeit, buchungskurs=None):
    return {"exec_id": exec_id, "handelszeit": handelszeit, "buchungskurs": buchungskurs}


EXEC_JE_ID = {
    satz["exec_id"]: satz
    for satz in (
        _ausf("X-1", datetime(2025, 1, 15, 15, 30), D("0.92")),
        _ausf("X-2", datetime(2024, 12, 20, 22, 0), D("1")),
        _ausf("X-3", datetime(2025, 2, 3, 16, 0), D("0.95")),
        _ausf("X-4", datetime(2024, 8, 30, 15, 0), D("0.90")),
        _ausf("X-6", datetime(2025, 3, 10, 16, 0), D("0.93")),
        _ausf("X-7", datetime(2025, 4, 1, 15, 0), D("0.90")),
        _ausf("X-8", datetime(2025, 4, 2, 15, 0), D("0.90")),
        _ausf("X-9", datetime(2025, 4, 3, 15, 0), D("0.90")),
        _ausf("X-10", datetime(2025, 1, 20, 15, 0)),  # kein Buchungskurs
        _ausf("X-13", datetime(2025, 5, 5, 15, 0), D("0.90")),
        _ausf("X-14", datetime(2025, 5, 6, 15, 0), D("0.90")),
    )
}


def _leg(conid, close_exec_id, offen, menge, brutto, kommission, **abweichungen):
    satz = {
        "leg_id": None,
        "sicht": "konto",
        "conid": conid,
        "close_exec_id": close_exec_id,
        "offen_ja_nein": offen,
        "basis_ungeklaert": False,
        "menge": menge,
        "brutto_pnl": brutto,
        "kommission_gesamt": kommission,
        "matching_methode": "fifo",
    }
    satz.update(abweichungen)
    return satz


# ---------------------------------------------------------------------------
# Szenario A: Legs. Jede erwartete Zahl unten ist hier per Hand begründet.
# ---------------------------------------------------------------------------

_SZENARIO_LEGS = [
    # L1: Option, Schließung 2025-01-15. netto 250 − 3 = 247.00 USD;
    # × Buchungskurs 0.92 = 227.24 EUR.
    _leg(CONID_OPT, "X-1", False, D("1"), D("250.00"), D("-3.00")),
    # L2: Future in EUR, Schließung 2024-12-20. netto −500 − 10 = −510.00;
    # Kurs 1 → −510.00 EUR.
    _leg(CONID_FUT, "X-2", False, D("1"), D("-500.00"), D("-10.00")),
    # L3: Aktie 2024-06-10 gekauft, 2025-02-03 verkauft — Zuflussjahr 2025.
    # netto 1200 − 2 = 1198.00; × 0.95 = 1138.10 EUR.
    _leg(CONID_STK_ALT, "X-3", False, D("100"), D("1200.00"), D("-2.00")),
    # L4: Aktie unter der neuen conid nach Split, verkauft 2024-08-30.
    # netto 400 − 1 = 399.00; × 0.90 = 359.10 EUR.
    _leg(CONID_STK_NEU, "X-4", False, D("200"), D("400.00"), D("-1.00")),
    # L5: offen — kein Zufluss, kein Fehler, keine Zeile.
    _leg(CONID_OPT, None, True, D("1"), None, D("-2.00")),
    # L6: Basis ungeklärt, verkauft 2025-03-10. netto 800 − 1 = 799.00;
    # × 0.93 = 743.07 EUR — aber außerhalb aller Topfsummen.
    _leg(CONID_STK_NEU, "X-6", False, D("50"), D("800.00"), D("-1.00"),
         basis_ungeklaert=True),
    # L7: Kettensicht — wird zurückgewiesen (sicht_vermischung).
    _leg(CONID_OPT, "X-7", False, D("1"), D("10.00"), D("-1.00"), sicht="kette"),
    # L8: Instrument fehlt in der Stammdatei.
    _leg(9900, "X-8", False, D("1"), D("5.00"), D("-1.00")),
    # L9: geschlossen, aber ohne Ergebnis (brutto_pnl None).
    _leg(CONID_OPT, "X-9", False, D("1"), None, D("-1.00")),
    # L10: geschlossen, Schließung ohne Buchungskurs — zählt in USD, EUR fehlt.
    # netto 100 − 1 = 99.00 USD.
    _leg(CONID_OPT, "X-10", False, D("1"), D("100.00"), D("-1.00")),
    # L13: asset_class FUND — unbekannt, kein Topf, Fehler.
    _leg(9800, "X-13", False, D("1"), D("7.00"), D("-1.00")),
    # L14: CASH — Kostenrechnung, kein Termingeschäft.
    _leg(7777, "X-14", False, D("1"), D("3.00"), D("-1.00")),
]

_CASH = [
    {"datum": datetime(2024, 12, 31, 0, 0), "typ": "Zinsen",
     "betrag": D("-25.50"), "waehrung": "EUR"},
    {"datum": datetime(2025, 6, 30, 0, 0), "typ": "Zinsen",
     "betrag": D("3.75"), "waehrung": "EUR"},
    {"datum": datetime(2025, 6, 14, 0, 0), "typ": "Quellensteuer",
     "betrag": D("-12.00"), "waehrung": "USD"},
]


def _auswertung(legs=None, cash=None):
    return steuer_auswertung(
        _SZENARIO_LEGS if legs is None else legs,
        EXEC_JE_ID,
        INSTRUMENTE,
        cash_transaktionen=_CASH if cash is None else cash,
    )


_ERWARTETE_TOEPFE = (
    # 2024 aktien USD: nur L4 — netto 399.00, 399 × 0.90 = 359.10.
    TopfZeile(jahr=2024, topf="aktien", waehrung="USD", brutto=D("400.00"),
              kommission=D("-1.00"), netto=D("399.00"), netto_eur_ib=D("359.10"),
              eur_kurs_fehlt=0, anzahl_legs=1, basis_ungeklaert=0),
    # 2024 Termingeschäfte EUR: nur L2.
    TopfZeile(jahr=2024, topf="termingeschaefte", waehrung="EUR",
              brutto=D("-500.00"), kommission=D("-10.00"), netto=D("-510.00"),
              netto_eur_ib=D("-510.00"), eur_kurs_fehlt=0, anzahl_legs=1,
              basis_ungeklaert=0),
    # 2025 aktien USD: nur L3 — Eröffnung war 2024, Zufluss ist 2025.
    TopfZeile(jahr=2025, topf="aktien", waehrung="USD", brutto=D("1200.00"),
              kommission=D("-2.00"), netto=D("1198.00"), netto_eur_ib=D("1138.10"),
              eur_kurs_fehlt=0, anzahl_legs=1, basis_ungeklaert=0),
    # 2025 Termingeschäfte USD: L1 + L10 — brutto 250 + 100 = 350,
    # Kommission −3 − 1 = −4, netto 346. EUR nur aus L1 (L10 ohne Kurs):
    # 227.24, eur_kurs_fehlt = 1.
    TopfZeile(jahr=2025, topf="termingeschaefte", waehrung="USD",
              brutto=D("350.00"), kommission=D("-4.00"), netto=D("346.00"),
              netto_eur_ib=D("227.24"), eur_kurs_fehlt=1, anzahl_legs=2,
              basis_ungeklaert=0),
)


def test_toepfe_je_jahr_topf_und_waehrung():
    ergebnis = _auswertung()
    assert ergebnis.toepfe == _ERWARTETE_TOEPFE


def test_zufluss_im_jahr_der_schliessung():
    # L3: gekauft 2024-06-10, verkauft 2025-02-03 → Zuflussjahr 2025.
    # Und 2024/aktien enthält ausschließlich L4 (Brutto 400.00, nicht 1600.00).
    ergebnis = _auswertung()
    detail_x3 = [z for z in ergebnis.details if z.close_exec_id == "X-3"]
    assert [z.jahr for z in detail_x3] == [2025]
    topf_2024_aktien = [z for z in ergebnis.toepfe
                        if z.jahr == 2024 and z.topf == "aktien"]
    assert [z.brutto for z in topf_2024_aktien] == [D("400.00")]


def test_details_drilldown_und_reihenfolge():
    # Reihenfolge nach (handelszeit, close_exec_id): X-4 (2024-08-30) vor
    # X-2 (2024-12-20) vor X-1 (2025-01-15) vor X-10 (2025-01-20) vor
    # X-3 (2025-02-03).
    ergebnis = _auswertung()
    assert [z.close_exec_id for z in ergebnis.details] == [
        "X-4", "X-2", "X-1", "X-10", "X-3",
    ]
    # Drilldown deckelt die Topfzeile (§5): 2025/termingeschaefte/USD.
    summe = sum(
        (z.brutto, z.kommission, z.netto) for z in ergebnis.details
        if z.jahr == 2025 and z.topf == "termingeschaefte"
    )
    assert summe == (D("350.00"), D("-4.00"), D("346.00"))


def test_detailzeile_vollstaendig():
    ergebnis = _auswertung()
    x4 = [z for z in ergebnis.details if z.close_exec_id == "X-4"][0]
    assert x4 == SteuerLegZeile(
        leg_id=None, close_exec_id="X-4", conid=CONID_STK_NEU, symbol="IDX9N",
        handelszeit=datetime(2024, 8, 30, 15, 0), jahr=2024, topf="aktien",
        waehrung="USD", menge=D("200"), brutto=D("400.00"),
        kommission=D("-1.00"), netto=D("399.00"), buchungskurs=D("0.90"),
        netto_eur_ib=D("359.10"), basis_ungeklaert=False,
    )


def test_offene_legs_kein_zufluss_kein_fehler():
    # L5 ist offen: keine Zeile, kein Fehler. Von den 12 Szenario-Legs
    # fließen genau 5 in die Töpfe (L6 separat ungeklärt, L7/L8/L9/L13/L14
    # fehlerhaft verworfen).
    ergebnis = _auswertung()
    assert sum(z.anzahl_legs for z in ergebnis.toepfe) == 5
    assert len(ergebnis.details) == 5
    assert all(f.schluessel != "X-5" for f in ergebnis.fehler)


def test_kettensicht_wird_zurueckgewiesen():
    # L7 trägt sicht='kette' — die Steuer wertet die Kontosicht; die Zeile
    # wird benannt und fließt in keine Summe (Plan §5).
    ergebnis = _auswertung()
    assert (SteuerFehler(schluessel="X-7", grund="sicht_vermischung")
            in ergebnis.fehler)
    assert all(z.close_exec_id != "X-7" for z in ergebnis.details)
    assert all(z.jahr != 2025 or z.topf != "aktien" for z in ergebnis.toepfe)


def test_basis_ungeklaert_direkt_und_nicht_in_summen():
    # L6: verkauft mit Ergebnis, aber Basis ungeklärt — volle Zeile in
    # `ungeklaert`, nichts in den Töpfen (Scheingewinn-Problem, schema.py).
    ergebnis = _auswertung()
    assert len(ergebnis.ungeklaert) == 1
    z6 = ergebnis.ungeklaert[0]
    assert (z6.close_exec_id, z6.netto, z6.netto_eur_ib, z6.basis_ungeklaert) == (
        "X-6", D("799.00"), D("743.07"), True,
    )
    assert all(z.anzahl_legs == 0 or z.brutto != D("800.00") for z in ergebnis.toepfe)
    assert ergebnis.toepfe == _ERWARTETE_TOEPFE


def test_fehlerliste_komplett_und_sortiert():
    # Sechs Benennungen, sortiert nach (schluessel, grund). X-10 ist
    # gleichzeitig bewertet (Topfbeitrag) und benannt (EUR unvollständig).
    ergebnis = _auswertung()
    assert [(f.schluessel, f.grund) for f in ergebnis.fehler] == [
        ("X-10", "buchungskurs_fehlt"),
        ("X-13", "asset_class_unbekannt"),
        ("X-14", "cash_ausgeschlossen"),
        ("X-7", "sicht_vermischung"),
        ("X-8", "instrument_fehlt"),
        ("X-9", "ergebnis_fehlt"),
    ]


# ---------------------------------------------------------------------------
# Zuteilung (Entscheidung (b)): die Option realisiert am Zuteilungstag, die
# synthetische Aktien-Leg bleibt offen — kein Zufluss vor dem Verkauf.
# ---------------------------------------------------------------------------

def test_zuteilung_realisiert_an_der_option():
    legs = [
        # Options-Leg, geschlossen durch Zuteilung 2025-06-20:
        # netto −150 − 1 = −151.00 USD; × 0.95 = −143.45 EUR.
        _leg(CONID_OPT, "X-11", False, D("1"), D("-150.00"), D("-1.00")),
        # Synthetische Aktien-Leg aus der Zuteilung: offen, kein Zufluss.
        _leg(CONID_STK_ALT, None, True, D("100"), None, D("0")),
    ]
    ergebnis = steuer_auswertung(
        legs,
        {"X-11": _ausf("X-11", datetime(2025, 6, 20, 15, 0), D("0.95"))},
        INSTRUMENTE,
    )
    assert ergebnis.toepfe == (
        TopfZeile(jahr=2025, topf="termingeschaefte", waehrung="USD",
                  brutto=D("-150.00"), kommission=D("-1.00"),
                  netto=D("-151.00"), netto_eur_ib=D("-143.45"),
                  eur_kurs_fehlt=0, anzahl_legs=1, basis_ungeklaert=0),
    )
    assert len(ergebnis.details) == 1
    assert not ergebnis.fehler
    assert not ergebnis.ungeklaert


def test_ertraege_getrennt_und_gruppiert():
    # Drei Buchungen → drei Zeilen (Zinsen tauchen in zwei Jahren getrennt
    # auf), sortiert nach (jahr, typ, waehrung); kein Betrag in den Töpfen.
    ergebnis = _auswertung()
    assert ergebnis.ertraege == (
        ErtragsZeile(jahr=2024, typ="Zinsen", waehrung="EUR", betrag=D("-25.50")),
        ErtragsZeile(jahr=2025, typ="Quellensteuer", waehrung="USD",
                     betrag=D("-12.00")),
        ErtragsZeile(jahr=2025, typ="Zinsen", waehrung="EUR", betrag=D("3.75")),
    )


def test_ertraege_mehrer_zeilen_eines_typs_summiert():
    cash = [
        {"datum": datetime(2024, 1, 31, 0, 0), "typ": "Zinsen",
         "betrag": D("-10.00"), "waehrung": "EUR"},
        {"datum": datetime(2024, 7, 31, 0, 0), "typ": "Zinsen",
         "betrag": D("-15.50"), "waehrung": "EUR"},
    ]
    ergebnis = _auswertung(cash=cash)
    assert ergebnis.ertraege == (
        ErtragsZeile(jahr=2024, typ="Zinsen", waehrung="EUR", betrag=D("-25.50")),
    )


def test_leere_eingabe_leeres_ergebnis():
    ergebnis = steuer_auswertung([], {}, {})
    assert ergebnis == SteuerErgebnis((), (), (), (), ())


def test_csv_format_und_spalten():
    # Kleinstmöglicher Bericht, vollständig per Hand geschrieben: Kopfzeile
    # (21 Spalten, Semikolon), eine Topfzeile, eine Detailzeile, eine
    # Ertragszeile, eine Fehlerzeile. 21 Spalten = 20 Semikolons je Zeile.
    ergebnis = SteuerErgebnis(
        toepfe=(
            TopfZeile(jahr=2024, topf="aktien", waehrung="USD", brutto=D("400.00"),
                      kommission=D("-1.00"), netto=D("399.00"),
                      netto_eur_ib=D("359.10"), eur_kurs_fehlt=0, anzahl_legs=1,
                      basis_ungeklaert=0),
        ),
        details=(
            SteuerLegZeile(leg_id=5, close_exec_id="X-4", conid=2002,
                           symbol="IDX9N", handelszeit=datetime(2024, 8, 30, 15, 0),
                           jahr=2024, topf="aktien", waehrung="USD",
                           menge=D("200"), brutto=D("400.00"),
                           kommission=D("-1.00"), netto=D("399.00"),
                           buchungskurs=D("0.90"), netto_eur_ib=D("359.10"),
                           basis_ungeklaert=False),
        ),
        ungeklaert=(),
        ertraege=(
            ErtragsZeile(jahr=2024, typ="Zinsen", waehrung="EUR",
                         betrag=D("-25.50")),
        ),
        fehler=(SteuerFehler(schluessel="X-9", grund="ergebnis_fehlt"),),
    )
    assert als_csv(ergebnis) == (
        "abschnitt;sicht;jahr;topf;waehrung;brutto;kommission;netto;netto_eur_ib;"
        "eur_kurs_fehlt;anzahl_legs;basis_ungeklaert;conid;symbol;close_exec_id;"
        "handelszeit;menge;typ;betrag;schluessel;grund\n"
        # topf: 12 gefüllte Felder bis 'nein', dann 9 leere Spalten.
        "topf;konto;2024;aktien;USD;400.00;-1.00;399.00;359.10;0;1;nein;;;;;;;;;\n"
        # detail: nach netto_eur_ib folgen 3 leere Spalten (eur_kurs_fehlt,
        # anzahl_legs, basis_ungeklaert), nach menge 4 (typ bis grund).
        "detail;konto;2024;aktien;USD;400.00;-1.00;399.00;359.10;;;;2002;IDX9N;"
        "X-4;2024-08-30T15:00:00;200;;;;\n"
        # ertrag: sicht/topf leer, brutto bis menge leer (12), dann typ/betrag.
        "ertrag;;2024;;EUR;;;;;;;;;;;;;Zinsen;-25.50;;\n"
        # fehler: nur schluessel und grund gefüllt — 19 leere Felder davor.
        "fehler;;;;;;;;;;;;;;;;;;;X-9;ergebnis_fehlt\n"
    )


# ---------------------------------------------------------------------------
# Szenario B (Ende zu Ende): Datenbank, Rebuild mit Split über die
# Jahresgrenze, steuer_bericht und CLI.
# ---------------------------------------------------------------------------

_E2E_INSTRUMENTE = (
    {"conid": 4001, "symbol": "SPXW 270119C6000", "underlying": "SPX",
     "asset_class": "OPT", "expiry": date(2027, 1, 19), "strike": D("6000"),
     "right": "C", "multiplikator": D("100"), "tickwert": None,
     "waehrung": "USD"},
    {"conid": 4501, "symbol": "CORP", "underlying": "CORP",
     "asset_class": "STK", "expiry": None, "strike": None, "right": None,
     "multiplikator": D("1"), "tickwert": None, "waehrung": "USD"},
    {"conid": 4502, "symbol": "CORP", "underlying": "CORP",
     "asset_class": "STK", "expiry": None, "strike": None, "right": None,
     "multiplikator": D("1"), "tickwert": None, "waehrung": "USD"},
    {"conid": 4601, "symbol": "FDAX", "underlying": "DAX",
     "asset_class": "FUT", "expiry": date(2024, 3, 15), "strike": None,
     "right": None, "multiplikator": D("25"), "tickwert": None,
     "waehrung": "EUR"},
)

_E2E_AUSFUEHRUNGEN = (
    # Option: 2023 eröffnet, 2024 geschlossen — Zuflussjahr 2024.
    # brutto (25 − 20) × 1 × 100 = 500.00; Kommission −1.10 − 1.10 = −2.20;
    # netto 497.80; × 0.90 = 448.02.
    {"exec_id": "E-O1", "conid": 4001, "side": "BUY", "menge": D("1"),
     "preis": D("20.00"), "kommission": D("-1.10"), "buchungskurs": D("0.92"),
     "handelszeit": datetime(2023, 12, 4, 15, 30)},
    {"exec_id": "E-O2", "conid": 4001, "side": "SELL", "menge": D("1"),
     "preis": D("25.00"), "kommission": D("-1.10"), "buchungskurs": D("0.90"),
     "handelszeit": datetime(2024, 1, 8, 15, 30)},
    # Aktie: 2023 gekauft (100 zu 40), 2-für-1-Split am 2024-01-20
    # überträgt auf conid 4502 (200 zu 20), Verkauf 2024-02-05 (200 zu 22):
    # brutto (22 − 20) × 200 = 400.00; Kommission −1.00 − 2.00 = −3.00;
    # netto 397.00; × 0.93 = 369.21. Der Stichtag selbst realisiert nichts.
    {"exec_id": "E-S1", "conid": 4501, "side": "BUY", "menge": D("100"),
     "preis": D("40.00"), "kommission": D("-1.00"), "buchungskurs": D("0.95"),
     "handelszeit": datetime(2023, 11, 6, 15, 30)},
    {"exec_id": "E-S2", "conid": 4502, "side": "SELL", "menge": D("200"),
     "preis": D("22.00"), "kommission": D("-2.00"), "buchungskurs": D("0.93"),
     "handelszeit": datetime(2024, 2, 5, 15, 30)},
    # Offener Future: kein Zufluss, kein Fehler, keine Topfzeile.
    {"exec_id": "E-F1", "conid": 4601, "side": "BUY", "menge": D("1"),
     "preis": D("20000.00"), "kommission": D("-2.00"), "buchungskurs": D("1"),
     "handelszeit": datetime(2024, 3, 1, 15, 30)},
)

_E2E_CASH = (
    {"quell_schluessel": "CT-1", "datum": datetime(2024, 12, 31, 0, 0),
     "typ": "Zinsen", "betrag": D("-25.50"), "waehrung": "EUR"},
    {"quell_schluessel": "CT-2", "datum": datetime(2024, 6, 14, 0, 0),
     "typ": "Quellensteuer", "betrag": D("-12.00"), "waehrung": "USD"},
)


def _befuelle_steuer_db(db_pfad):
    engine = create_db_engine(db_pfad)
    symbol_je_conid = {s["conid"]: s["symbol"] for s in _E2E_INSTRUMENTE}
    waehrung_je_conid = {s["conid"]: s["waehrung"] for s in _E2E_INSTRUMENTE}
    with engine.begin() as verbindung:
        for satz in _E2E_INSTRUMENTE:
            verbindung.execute(insert(instruments).values(**satz))
        lauf = verbindung.execute(
            insert(import_runs).values(
                quelle="flex", datei_hash="steuer-fixture",
                importiert_am=datetime(2026, 10, 3, 6, 0, 0),
                qualitaetsstufe="A", zeilen_gesamt=0, zeilen_neu=0,
            )
        ).inserted_primary_key[0]
        for satz in _E2E_AUSFUEHRUNGEN:
            verbindung.execute(
                insert(executions).values(
                    konto="U7777777",
                    symbol=symbol_je_conid[satz["conid"]],
                    waehrung=waehrung_je_conid[satz["conid"]],
                    kommission_waehrung=waehrung_je_conid[satz["conid"]],
                    ereignistyp="trade", roh_json="{}", qualitaetsstufe="A",
                    import_run_id=lauf, **satz,
                )
            )
        verbindung.execute(
            insert(corporate_actions).values(
                aktion_id="AKT-S", konto="U7777777", typ="FS",
                stichtag=date(2024, 1, 20), alter_conid=4501,
                alte_menge=D("1"), neuer_conid=4502, neue_menge=D("2"),
                kosten_neu=None, roh_json="{}",
            )
        )
        for satz in _E2E_CASH:
            verbindung.execute(
                insert(flex_cash_transactions).values(
                    konto="U7777777", beschreibung=None, roh_json="{}",
                    import_run_id=lauf, **satz,
                )
            )
    rebuild(str(db_pfad))


def test_ende_zu_ende_split_ueber_jahresgrenze(migrated_db):
    _befuelle_steuer_db(migrated_db)
    ergebnis = steuer_bericht(str(migrated_db))

    # Nur die Kontosicht zählt: eine Leg je Geschäft, die Kettensicht
    # verdoppelt nichts. Beide Zuflüsse liegen 2024 — die Option wurde
    # 2023 eröffnet, die Aktie 2023 gekauft und zwischendurch gesplittet;
    # Zufluss ist jeweils das Jahr der Schließung, der Split-Stichtag
    # selbst realisiert nichts.
    assert ergebnis.toepfe == (
        TopfZeile(jahr=2024, topf="aktien", waehrung="USD", brutto=D("400.00"),
                  kommission=D("-3.00"), netto=D("397.00"),
                  netto_eur_ib=D("369.21"), eur_kurs_fehlt=0, anzahl_legs=1,
                  basis_ungeklaert=0),
        TopfZeile(jahr=2024, topf="termingeschaefte", waehrung="USD",
                  brutto=D("500.00"), kommission=D("-2.20"), netto=D("497.80"),
                  netto_eur_ib=D("448.02"), eur_kurs_fehlt=0, anzahl_legs=1,
                  basis_ungeklaert=0),
    )
    assert [z.close_exec_id for z in ergebnis.details] == ["E-O2", "E-S2"]
    assert not ergebnis.ungeklaert
    assert not ergebnis.fehler
    assert ergebnis.ertraege == (
        ErtragsZeile(jahr=2024, typ="Quellensteuer", waehrung="USD",
                     betrag=D("-12.00")),
        ErtragsZeile(jahr=2024, typ="Zinsen", waehrung="EUR",
                     betrag=D("-25.50")),
    )


def test_cli_schreibt_csv_datei(migrated_db, tmp_path):
    _befuelle_steuer_db(migrated_db)
    ziel = tmp_path / "steuer.csv"
    assert main(["steuer", str(ziel), "--db", str(migrated_db)]) == 0
    # UTF-8 mit BOM (Excel), danach der verankerte Spaltenkopf; die
    # Aktien-Topfzeile des End-zu-Ende-Szenarios steht unverändert drin.
    inhalt = ziel.read_text(encoding="utf-8-sig")
    assert ziel.read_bytes()[:3] == b"\xef\xbb\xbf"
    assert inhalt.startswith(
        "abschnitt;sicht;jahr;topf;waehrung;brutto;kommission;netto;netto_eur_ib;"
    )
    assert ("topf;konto;2024;aktien;USD;400.00;-3.00;397.00;369.21;0;1;nein"
            in inhalt)






