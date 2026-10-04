"""Abnahmetests für AP-06w (Analytik Tranche II: Kommissionsattribution).

Vertrag: auftraege/AP-06w.md (E1-E7 freigegeben 04.10.2026). Diese Datei ist
unveränderlich; jeder Erwartungswert ist von Hand gerechnet und am Test
begründet (Regel 8).

Startzustand (AP-06w): ROT, weil analytics.kommission noch nicht existiert —
ModuleNotFoundError ist der einzige erlaubte Fehler.

Testwelt: die K-Welt aus tests/test_kennzahlen.py (K1 USX geschlossen Stufe A,
K2 DAX EUR, K3 USX offen, K4 USX Kursmangel, K5 USX Stufe B) plus

  K6 NDX, 1 Roll, 2 Strukturen, oa_strategie 'NDX: IC-Test': jede Struktur
     wie K1 (Preise 120/80/60/30, Multiplikator 10, Kommission -2 je
     Ausführung, Kurse 0.90/0.95).

Handwerte je Kette (wirtschaftliche Sicht, EUR je Ausführung mit ihrem Kurs):

  K1: brutto 1200*.90 - 800*.90 - 600*.95 + 300*.95 = 75.00;
      Kommission -2*(.90+.90+.95+.95) = -7.40; netto 67.60.
  K2: EUR, Faktor 1: brutto 100.00, Kommission -8.00, netto 92.00.
  K4: Kurs fehlt (V4) -> kein EUR-Wert, zählt als kurs_fehlt.
  K5: brutto 90.00, Kommission -7.20, netto 82.80.
  K6: zwei Strukturen wie K1 -> brutto 150.00, Kommission -14.80,
      netto 135.20.

Die reinen Tests laufen auf K1-K6; die beiden CLI-Tests am Ende laufen über die
echte Engine auf der E2E-Welt K1-K5 (ohne K6, weil ein Roll dort von der
Kettenerkennung abhinge, nicht von der Attribution).
"""

from datetime import datetime as dt
from decimal import Decimal as D

import pytest
from fixtures_rebuild import befuelle
from test_kennzahlen import (
    AUSFUEHRUNGEN_Z,
    E2E_AUSFUEHRUNGEN,
    E2E_INSTRUMENTE,
    INSTRUMENTE_Z,
    _ausf,
    _kette,
    _leg,
    _struktur,
    _welt,
)

from analytics.kommission import KommissionsErgebnis, kommissions_attribution
from journal.cli import main
from journal.rebuild import rebuild

INSTRUMENTE_K = INSTRUMENTE_Z + [
    dict(conid=c, multiplikator=D("10")) for c in (2401, 2402, 2403, 2404)
]

AUSFUEHRUNGEN_K = AUSFUEHRUNGEN_Z + [
    # K6, Struktur 16 (eröffnet 06.04., geschlossen 20.04.)
    _ausf("N1", 2401, "SELL", "120.00", dt(2026, 4, 6, 15, 0), D("0.90")),
    _ausf("N2", 2402, "BUY", "80.00", dt(2026, 4, 6, 15, 0), D("0.90")),
    _ausf("N3", 2401, "BUY", "60.00", dt(2026, 4, 20, 15, 0), D("0.95")),
    _ausf("N4", 2402, "SELL", "30.00", dt(2026, 4, 20, 15, 0), D("0.95")),
    # K6, Struktur 17 (Roll: eröffnet 20.04., geschlossen 04.05.)
    _ausf("M1", 2403, "SELL", "120.00", dt(2026, 4, 20, 15, 1), D("0.90")),
    _ausf("M2", 2404, "BUY", "80.00", dt(2026, 4, 20, 15, 1), D("0.90")),
    _ausf("M3", 2403, "BUY", "60.00", dt(2026, 5, 4, 15, 0), D("0.95")),
    _ausf("M4", 2404, "SELL", "30.00", dt(2026, 5, 4, 15, 0), D("0.95")),
]


def _welt_k(sicht="kette"):
    ketten, strukturen, glieder, legs = _welt(sicht)
    for kette in ketten:
        kette["oa_strategie"] = None
    k6 = _kette(6, "NDX", dt(2026, 5, 4, 15, 0), sicht)
    k6["anzahl_rolls"] = 1
    k6["oa_strategie"] = "NDX: IC-Test"
    ketten.append(k6)
    strukturen += [
        _struktur(16, 6, "USD", D("100.00"), D("92.00"), dt(2026, 4, 20, 15, 0)),
        _struktur(17, 6, "USD", D("100.00"), D("92.00"), dt(2026, 5, 4, 15, 0)),
    ]
    glieder += [dict(structure_id=16, chain_id=6, sicht=sicht),
                dict(structure_id=17, chain_id=6, sicht=sicht)]
    legs += [
        _leg(110, 16, 2401, "N1", "N3", False),
        _leg(111, 16, 2402, "N2", "N4", False),
        _leg(112, 17, 2403, "M1", "M3", False),
        _leg(113, 17, 2404, "M2", "M4", False),
    ]
    return ketten, strukturen, glieder, legs


def _attribution(sicht="kette", nur_qualitaetsstufe_a=False):
    ketten, strukturen, glieder, legs = _welt_k(sicht)
    return kommissions_attribution(
        ketten, strukturen, glieder, legs, AUSFUEHRUNGEN_K, INSTRUMENTE_K,
        sicht=sicht, nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )


def _gruppe(ergebnis, dimension, schluessel):
    treffer = [g for g in ergebnis.gruppen
               if g.dimension == dimension and g.schluessel == schluessel]
    assert len(treffer) == 1, (dimension, schluessel, ergebnis.gruppen)
    return treffer[0]


def _werte(g):
    return (g.anzahl_ketten, g.kommission_eur, g.brutto_eur, g.netto_eur,
            g.kommissionsanteil, g.anzahl_ketten_kurs_fehlt,
            g.anzahl_ketten_abgeschlossen)


# ---------------------------------------------------------------- reine Funktion


def test_index_je_underlying_ohne_zusammenfassen():
    """Regel 4: SPX/SPY/XSP-Prinzip - jedes Underlying eine eigene Gruppe.
    DAX: nur K2: -8.00 / 100.00 / 92.00, Anteil 8/100 = 0.0800.
    NDX: nur K6: -14.80 / 150.00 / 135.20, Anteil 14.80/150 = 0.09866.. -> 0.0987.
    USX: K1 + K5 tragen: Kommission -7.40 - 7.20 = -14.60, brutto 75.00 + 90.00
    = 165.00, netto 67.60 + 82.80 = 150.40, Anteil 14.60/165 = 0.08848.. ->
    0.0885. K4 (abgeschlossen, Kursmangel) zählt nur als kurs_fehlt 1 -> 3
    abgeschlossene; K3 ist offen und taucht in keiner Gruppe auf."""
    ergebnis = _attribution()
    assert _werte(_gruppe(ergebnis, "index", "DAX")) == (
        1, D("-8.00"), D("100.00"), D("92.00"), D("0.0800"), 0, 1)
    assert _werte(_gruppe(ergebnis, "index", "NDX")) == (
        1, D("-14.80"), D("150.00"), D("135.20"), D("0.0987"), 0, 1)
    assert _werte(_gruppe(ergebnis, "index", "USX")) == (
        2, D("-14.60"), D("165.00"), D("150.40"), D("0.0885"), 1, 3)


def test_anlageklasse_opt_buendelt_alle_optionsketten():
    """OPT: K1, K2, K5, K6 tragen. Kommission -7.40 - 8.00 - 7.20 - 14.80 =
    -37.40; brutto 75 + 100 + 90 + 150 = 415.00; netto 377.60; Anteil
    37.40/415 = 0.09012.. -> 0.0901; kurs_fehlt 1 (K4); abgeschlossen 5
    (K1, K2, K4, K5, K6)."""
    g = _gruppe(_attribution(), "anlageklasse", "OPT")
    assert _werte(g) == (4, D("-37.40"), D("415.00"), D("377.60"),
                         D("0.0901"), 1, 5)


def test_strategie_ohne_bucket_und_oa_strategie():
    """Regel 4: chains.oa_strategie, sonst der Bucket '(ohne)'.
    '(ohne)': K1, K2, K5: -7.40 - 8.00 - 7.20 = -22.60 / 75 + 100 + 90 =
    265.00 / 242.40, Anteil 22.60/265 = 0.08528.. -> 0.0853, kurs_fehlt 1.
    'NDX: IC-Test': nur K6, wie oben 0.0987."""
    ergebnis = _attribution()
    assert _werte(_gruppe(ergebnis, "strategie", "(ohne)")) == (
        3, D("-22.60"), D("265.00"), D("242.40"), D("0.0853"), 1, 4)
    assert _werte(_gruppe(ergebnis, "strategie", "NDX: IC-Test")) == (
        1, D("-14.80"), D("150.00"), D("135.20"), D("0.0987"), 0, 1)


def test_roll_anzahl_gruppen_als_text():
    """'0': K1, K2, K5 (K4 kurs_fehlt) wie '(ohne)'; '1': K6."""
    ergebnis = _attribution()
    assert _werte(_gruppe(ergebnis, "roll_anzahl", "0")) == (
        3, D("-22.60"), D("265.00"), D("242.40"), D("0.0853"), 1, 4)
    assert _werte(_gruppe(ergebnis, "roll_anzahl", "1")) == (
        1, D("-14.80"), D("150.00"), D("135.20"), D("0.0987"), 0, 1)


def test_gruppen_vollstaendig_und_deterministisch_sortiert():
    """Genau 8 Gruppen (OPT, 3 Underlyings, 2 Strategien, 2 Roll-Gruppen),
    sortiert nach (dimension, schluessel) als Text. anzahl_ketten_gesamt =
    6 (K1-K6, auch die offene K3 und die kursmangelhafte K4)."""
    ergebnis = _attribution()
    assert isinstance(ergebnis, KommissionsErgebnis)
    assert ergebnis.sicht == "kette"
    assert ergebnis.anzahl_ketten_gesamt == 6
    assert [(g.dimension, g.schluessel) for g in ergebnis.gruppen] == [
        ("anlageklasse", "OPT"),
        ("index", "DAX"),
        ("index", "NDX"),
        ("index", "USX"),
        ("roll_anzahl", "0"),
        ("roll_anzahl", "1"),
        ("strategie", "(ohne)"),
        ("strategie", "NDX: IC-Test"),
    ]
    assert all(g.sicht == "kette" for g in ergebnis.gruppen)
    assert _attribution() == ergebnis  # Determinismus: gleiche Eingabe, gleiches Ergebnis


def test_filter_nur_stufe_a_entfernt_k5_ganz():
    """E6 wie Tranche I: Der Filter entfernt K5 (Stufe B) aus Summen, Anzahlen
    und anzahl_ketten_gesamt (6 -> 5). Hand:
    OPT: K1, K2, K6: -7.40 - 8.00 - 14.80 = -30.20 / 75 + 100 + 150 = 325.00 /
    294.80, Anteil 30.20/325 = 0.09292.. -> 0.0929, kurs_fehlt 1, abg. 4.
    USX: nur K1: -7.40 / 75.00 / 67.60, Anteil 7.40/75 = 0.09866.. -> 0.0987,
    kurs_fehlt 1 (K4), abgeschlossen 2.
    roll '0' / '(ohne)': K1, K2: -15.40 / 175.00 / 159.60, Anteil
    15.40/175 = 0.0880, kurs_fehlt 1, abgeschlossen 3.
    DAX und NDX bleiben unverändert."""
    ergebnis = _attribution(nur_qualitaetsstufe_a=True)
    assert ergebnis.anzahl_ketten_gesamt == 5
    assert _werte(_gruppe(ergebnis, "anlageklasse", "OPT")) == (
        3, D("-30.20"), D("325.00"), D("294.80"), D("0.0929"), 1, 4)
    assert _werte(_gruppe(ergebnis, "index", "USX")) == (
        1, D("-7.40"), D("75.00"), D("67.60"), D("0.0987"), 1, 2)
    assert _werte(_gruppe(ergebnis, "roll_anzahl", "0")) == (
        2, D("-15.40"), D("175.00"), D("159.60"), D("0.0880"), 1, 3)
    assert _werte(_gruppe(ergebnis, "strategie", "(ohne)")) == (
        2, D("-15.40"), D("175.00"), D("159.60"), D("0.0880"), 1, 3)
    assert _werte(_gruppe(ergebnis, "index", "DAX")) == (
        1, D("-8.00"), D("100.00"), D("92.00"), D("0.0800"), 0, 1)
    assert _werte(_gruppe(ergebnis, "index", "NDX")) == (
        1, D("-14.80"), D("150.00"), D("135.20"), D("0.0987"), 0, 1)


def test_kursmangel_kette_hat_keine_summe_und_keinen_kurs_eins():
    """K4 (Kurs V4 fehlt) steht nur als kurs_fehlt: Ließe die Attribution K4
    mit Kurs 1 in USX einfließen, stünde dort anzahl_ketten 3 und eine
    andere Kommission. Erwartet bleibt 2 / -14.60 / kurs_fehlt 1."""
    g = _gruppe(_attribution(), "index", "USX")
    assert g.anzahl_ketten == 2
    assert g.kommission_eur == D("-14.60")
    assert g.anzahl_ketten_kurs_fehlt == 1


def test_brutto_null_ergibt_kein_anteil_statt_null():
    """E3: Brutto exakt 0 -> Anteil None (nicht 0.0000). Hand für eine eigene
    Kette 7 (USX): Z1 SELL 2001 @50.00, Z2 BUY 2001 @50.00, Kurs 0.90 ->
    brutto (50-50)*10 = 0.00; Kommission -2 - 2 = -4.00 USD * 0.90 = -3.60 EUR;
    netto -3.60; Anteil: Nenner 0 -> None."""
    ketten = [_kette(7, "USX", dt(2026, 2, 20, 15, 0), "kette")]
    ketten[0]["oa_strategie"] = None
    strukturen = [_struktur(21, 7, "USD", D("0.00"), D("-4.00"),
                            dt(2026, 2, 20, 15, 0), typ="Single")]
    strukturen[0]["kommission"] = D("-4.00")
    glieder = [dict(structure_id=21, chain_id=7, sicht="kette")]
    legs = [_leg(120, 21, 2001, "Z1", "Z2", False)]
    ausfuehrungen = [
        _ausf("Z1", 2001, "SELL", "50.00", dt(2026, 2, 20, 15, 0), D("0.90")),
        _ausf("Z2", 2001, "BUY", "50.00", dt(2026, 2, 20, 15, 0), D("0.90")),
    ]
    ergebnis = kommissions_attribution(
        ketten, strukturen, glieder, legs, ausfuehrungen, INSTRUMENTE_K)
    g = _gruppe(ergebnis, "index", "USX")
    assert (g.kommission_eur, g.brutto_eur, g.netto_eur) == (
        D("-3.60"), D("0.00"), D("-3.60"))
    assert g.kommissionsanteil is None


def test_sicht_konto_traegt_jede_gruppe_und_unbekannte_sicht_bricht_ab():
    ergebnis = _attribution(sicht="konto")
    assert ergebnis.sicht == "konto"
    assert all(g.sicht == "konto" for g in ergebnis.gruppen)
    with pytest.raises(ValueError, match="Unbekannte sicht"):
        _attribution(sicht="mischung")


# ---------------------------------------------------------------- Ende zu Ende
# Echte Engine (befuelle + rebuild) über die E2E-Welt von test_kennzahlen
# (K1-K5, ohne K6): der Bericht kommt über `journal kennzahlen --kommission`.

_KOPF = (
    "dimension;schluessel;sicht;anzahl_ketten;kommission_eur;brutto_eur;"
    "netto_eur;kommissionsanteil;anzahl_ketten_kurs_fehlt;"
    "anzahl_ketten_abgeschlossen"
)


def _bereite_db_vor(db_pfad):
    befuelle(str(db_pfad), ausfuehrungen=E2E_AUSFUEHRUNGEN, instrumente_=E2E_INSTRUMENTE)
    rebuild(str(db_pfad))


def test_cli_schreibt_kommissions_csv(migrated_db, tmp_path):
    """Ohne K6 (E2E-Welt K1-K5): OPT -22.60 / 265.00 / 242.40, 0.0853, kurs_fehlt 1,
    abgeschlossen 4; DAX wie oben; USX 2 Ketten -14.60 / 165.00 / 150.40,
    0.0885, kurs_fehlt 1, abgeschlossen 3; roll '0' und '(ohne)' wie OPT.
    Reihenfolge nach (dimension, schluessel); Beträge zwei, Anteile vier
    Nachkommastellen; UTF-8 mit BOM wie der Tranche-I-Bericht."""
    _bereite_db_vor(migrated_db)
    kennzahlen = tmp_path / "kennzahlen.csv"
    kommission = tmp_path / "kommission.csv"
    assert main(["kennzahlen", str(kennzahlen), "--kommission", str(kommission),
                 "--db", str(migrated_db)]) == 0

    assert kennzahlen.exists()  # der Tranche-I-Bericht entsteht weiter
    assert kommission.read_bytes()[:3] == b"\xef\xbb\xbf"
    zeilen = kommission.read_text(encoding="utf-8-sig").splitlines()
    assert zeilen == [
        _KOPF,
        "anlageklasse;OPT;kette;3;-22.60;265.00;242.40;0.0853;1;4",
        "index;DAX;kette;1;-8.00;100.00;92.00;0.0800;0;1",
        "index;USX;kette;2;-14.60;165.00;150.40;0.0885;1;3",
        "roll_anzahl;0;kette;3;-22.60;265.00;242.40;0.0853;1;4",
        "strategie;(ohne);kette;3;-22.60;265.00;242.40;0.0853;1;4",
    ]


def test_cli_ohne_kommissions_option_schreibt_keine_zweite_datei(migrated_db, tmp_path):
    _bereite_db_vor(migrated_db)
    kennzahlen = tmp_path / "kennzahlen.csv"
    assert main(["kennzahlen", str(kennzahlen), "--db", str(migrated_db)]) == 0
    # Nur Berichtsdateien (*.csv) zählen: die Fixture migrated_db legt die
    # SQLite-Datei selbst in tmp_path ab (AP-06wvk).
    assert sorted(p.name for p in tmp_path.glob("*.csv")) == ["kennzahlen.csv"]
