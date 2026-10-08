"""Abnahmetests für AP-06d (Analytik III: Roll-Degradation).

Vertrag: auftraege/AP-06d.md. Diese Datei ist unveränderlich; jeder
Erwartungswert ist von Hand gerechnet und am jeweiligen Test begründet.

Startzustand (AP-06d): ROT, weil analytics.degradation noch nicht existiert —
ModuleNotFoundError ist der einzige erlaubte Fehler.

Testwelt (reine Funktion, Kettensicht; alle in EUR mit Kurs 1, Multiplikator
10, Menge je Leg 1, Kommission je Ausführung -2.00). Eine Struktur ist ein
Leg: eröffnet mit SELL @po, geschlossen mit BUY @pc; Ergebnis netto =
(po - pc) * 10 - 4.00. Eine Kette ist eine Reihe solcher Strukturen; die
Rollverknüpfung zwischen zwei Strukturen trägt die in Klammern genannte
Erkennung.

  K1  0 Rolls  (10 -> 4)                           netto  56.00
  K2  0 Rolls  (8 -> 9)                            netto -14.00
  K3  0 Rolls  (5 -> 1)                            netto  36.00
  K4  1 Roll   [auto]  (10->8)(6->5)               netto  16 + 6   =  22.00
  K5  1 Roll   [auto]  (7->9)(4->3)                netto -24 + 6   = -18.00
  K6  1 Roll   [manuell]  (12->6)(3->1)            netto  56 + 16  =  72.00
  K7  2 Rolls  [auto, auto]  (9->8)(8->7)(7->5)    netto  6 + 6 + 16 = 28.00
  K8  3 Rolls  [auto x3]  4 x (10 -> 9)            netto  4 * 6    =  24.00
  K9  4 Rolls  [auto x4]  5 x (10 -> 10)           netto  5 * -4   = -20.00
  K10 2 Rolls  [auto, heuristik]  3 x (10 -> 9)    netto  18.00 (nie belegt)
  K11 offen, 0 Rolls                               (nicht abgeschlossen)
  K12 0 Rolls, Kursmangel (Kurs der Schließung fehlt)
  K13 0 Rolls  (10 -> 9), Qualitätsstufe B         netto   6.00

Regeln (siehe Vertrag): nur Kettensicht; nur abgeschlossene Ketten; Gruppen
'0', '1', '2', '3+' je Modus; Modus 'belegt' lässt nur Ketten zu, deren Rolls
alle Erkennung 'auto' tragen, Modus 'belegt_bestaetigt' zusätzlich 'manuell';
'heuristik' geht nie ein. Kursmangelketten zählen nur als kurs_fehlt.
"""

from datetime import datetime as dt
from datetime import timedelta
from decimal import Decimal as D

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

from analytics.degradation import (
    DegradationsAbdeckung,
    DegradationsErgebnis,
    DegradationsGruppe,
    als_csv,
    degradations_auswertung,
    degradations_bericht,
)
from journal.cli import main
from journal.db import create_db_engine
from journal.rebuild import offene_rollkandidaten, rebuild
from journal.schema import chain_overrides, chains, structures

# (chain_id, [(po, pc), ...], [Erkennung je Rollverknüpfung], Stufe,
#  abgeschlossen, Kursmangel)
_KETTEN = [
    (1, [("10.00", "4.00")], [], "A", True, False),
    (2, [("8.00", "9.00")], [], "A", True, False),
    (3, [("5.00", "1.00")], [], "A", True, False),
    (4, [("10.00", "8.00"), ("6.00", "5.00")], ["auto"], "A", True, False),
    (5, [("7.00", "9.00"), ("4.00", "3.00")], ["auto"], "A", True, False),
    (6, [("12.00", "6.00"), ("3.00", "1.00")], ["manuell"], "A", True, False),
    (7, [("9.00", "8.00"), ("8.00", "7.00"), ("7.00", "5.00")],
     ["auto", "auto"], "A", True, False),
    (8, [("10.00", "9.00")] * 4, ["auto"] * 3, "A", True, False),
    (9, [("10.00", "10.00")] * 5, ["auto"] * 4, "A", True, False),
    (10, [("10.00", "9.00")] * 3, ["auto", "heuristik"], "A", True, False),
    (11, [("10.00", "10.00")], [], "A", False, False),
    (12, [("10.00", "9.00")], [], "A", True, True),
    (13, [("10.00", "9.00")], [], "B", True, False),
]


def _ausf(exec_id, conid, side, preis, zeit, kurs, stufe):
    return dict(
        exec_id=exec_id, conid=conid, side=side, preis=D(preis), menge=1,
        waehrung="EUR", kommission=D("-2.00"), kommission_waehrung="EUR",
        buchungskurs=kurs, handelszeit=zeit, qualitaetsstufe=stufe,
    )


def _welt(sicht="kette"):
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = [], [], [], [], [], []
    structure_id, leg_id, conid = 100, 1000, 5000
    for chain_id, preise, erkennungen, stufe, abgeschlossen, kursmangel in _KETTEN:
        ende = None
        for position, (po, pc) in enumerate(preise):
            structure_id += 1
            leg_id += 1
            conid += 1
            offen_id, schluss_id = f"O{structure_id}", f"C{structure_id}"
            beginn = dt(2026, 1, 1, 10, 0) + timedelta(days=structure_id)
            ausfuehrungen.append(_ausf(offen_id, conid, "SELL", po, beginn, D("1"), stufe))
            if abgeschlossen:
                ende = beginn + timedelta(days=1)
                kurs = None if kursmangel else D("1")
                ausfuehrungen.append(_ausf(schluss_id, conid, "BUY", pc, ende, kurs, stufe))
                brutto = (D(po) - D(pc)) * 10
                struktur = dict(brutto_pnl=brutto, kommission=D("-4.00"),
                                netto_pnl=brutto - 4, geschlossen_am=ende)
            else:
                struktur = dict(brutto_pnl=None, kommission=D("-2.00"),
                                netto_pnl=None, geschlossen_am=None)
            strukturen.append(dict(structure_id=structure_id, chain_id=chain_id, typ="Single",
                                   waehrung="EUR", **struktur))
            glieder.append(dict(
                structure_id=structure_id, chain_id=chain_id, sicht=sicht,
                sequenz=position + 1,
                verknuepfungstyp="open" if position == 0 else "roll",
                erkennung="auto" if position == 0 else erkennungen[position - 1],
            ))
            legs.append(dict(
                leg_id=leg_id, structure_id=structure_id, conid=conid,
                open_exec_id=offen_id, close_exec_id=schluss_id if abgeschlossen else None,
                menge=1, offen_ja_nein=not abgeschlossen,
            ))
            instrumente.append(dict(conid=conid, multiplikator=D("10")))
        ketten.append(dict(
            chain_id=chain_id, sicht=sicht, underlying="SPX", asset_class="OPT",
            anzahl_rolls=len(preise) - 1, beendet_am=ende,
        ))
    return ketten, strukturen, glieder, legs, ausfuehrungen, instrumente


def _auswertung(sicht="kette", offene_kandidaten=4, nur_qualitaetsstufe_a=False):
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = _welt(sicht)
    return degradations_auswertung(
        ketten, strukturen, glieder, legs, ausfuehrungen, instrumente,
        sicht=sicht, offene_kandidaten=offene_kandidaten,
        nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )


def _gruppe(ergebnis, modus, roll_gruppe):
    treffer = [g for g in ergebnis.gruppen if g.modus == modus and g.roll_gruppe == roll_gruppe]
    assert len(treffer) == 1, (modus, roll_gruppe, ergebnis.gruppen)
    return treffer[0]


def _werte(g):
    return (g.anzahl_ketten, g.summe_netto_eur, g.durchschnitt_netto_eur,
            g.trefferquote, g.anzahl_ketten_kurs_fehlt)


def _abdeckung(ergebnis, modus):
    treffer = [a for a in ergebnis.abdeckung if a.modus == modus]
    assert len(treffer) == 1, (modus, ergebnis.abdeckung)
    return treffer[0]


# ---------------------------------------------------------------- reine Funktion


def test_gruppen_im_modus_belegt():
    """Modus 'belegt' (alle Rolls 'auto'):
    '0': K1 56 + K2 -14 + K3 36 + K13 6 = 84.00, Durchschnitt 84/4 = 21.00,
         Treffer 3 von 4 = 0.7500; K12 hat Kursmangel -> kurs_fehlt 1.
    '1': K4 22 + K5 -18 = 4.00, Durchschnitt 2.00, Treffer 1/2 = 0.5000
         (K6 ist nur bestätigt, nicht belegt).
    '2': K7 28.00, Durchschnitt 28.00, Treffer 1/1 = 1.0000.
    '3+': K8 24 + K9 -20 = 4.00, Durchschnitt 2.00, Treffer 1/2 = 0.5000."""
    e = _auswertung()
    assert _werte(_gruppe(e, "belegt", "0")) == (4, D("84.00"), D("21.00"), D("0.7500"), 1)
    assert _werte(_gruppe(e, "belegt", "1")) == (2, D("4.00"), D("2.00"), D("0.5000"), 0)
    assert _werte(_gruppe(e, "belegt", "2")) == (1, D("28.00"), D("28.00"), D("1.0000"), 0)
    assert _werte(_gruppe(e, "belegt", "3+")) == (2, D("4.00"), D("2.00"), D("0.5000"), 0)


def test_gruppen_im_modus_belegt_bestaetigt():
    """Zusätzlich K6 (Roll 'manuell') in Gruppe '1': 22 - 18 + 72 = 76.00,
    Durchschnitt 76/3 = 25.3333.. -> 25.33, Treffer 2/3 = 0.6667. Alle
    anderen Gruppen wie im Modus 'belegt'."""
    e = _auswertung()
    assert _werte(_gruppe(e, "belegt_bestaetigt", "1")) == (
        3, D("76.00"), D("25.33"), D("0.6667"), 0)
    for roll_gruppe in ("0", "2", "3+"):
        assert _werte(_gruppe(e, "belegt_bestaetigt", roll_gruppe)) == _werte(
            _gruppe(e, "belegt", roll_gruppe))


def test_heuristik_und_offene_ketten_gehen_nie_ein():
    """K10 (ein Roll 'heuristik') steht in keinem Modus, K11 (offen) nirgends.
    Summe aller Gruppen im Modus 'belegt_bestaetigt': 84 + 76 + 28 + 4 =
    192.00 (ohne K10 = 18.00 und ohne K12 = Kursmangel)."""
    e = _auswertung()
    summe = sum(g.summe_netto_eur for g in e.gruppen if g.modus == "belegt_bestaetigt")
    assert summe == D("192.00")


def test_alle_acht_gruppen_stehen_sortiert_im_ergebnis():
    e = _auswertung()
    assert isinstance(e, DegradationsErgebnis)
    assert e.sicht == "kette"
    assert [(g.modus, g.roll_gruppe) for g in e.gruppen] == [
        ("belegt", "0"), ("belegt", "1"), ("belegt", "2"), ("belegt", "3+"),
        ("belegt_bestaetigt", "0"), ("belegt_bestaetigt", "1"),
        ("belegt_bestaetigt", "2"), ("belegt_bestaetigt", "3+"),
    ]
    assert all(isinstance(g, DegradationsGruppe) for g in e.gruppen)
    assert all(isinstance(a, DegradationsAbdeckung) for a in e.abdeckung)


def test_abdeckung_modus_belegt():
    """Abgeschlossen sind K1-K10, K12, K13 = 12 Ketten (K11 offen).
    Zugelassen im Modus 'belegt': K1-K5, K7-K9, K12, K13 = 10 (ohne K6 und
    K10) -> 10/12 = 0.8333. Rollverknüpfungen dieser 10: 1 + 1 + 2 + 3 + 4 =
    11; mit 4 offenen Kandidaten: 11/(11 + 4) = 0.7333."""
    a = _abdeckung(_auswertung(), "belegt")
    assert (a.ketten_abgeschlossen, a.ketten_ausgewertet, a.abdeckung_ketten) == (
        12, 10, D("0.8333"))
    assert (a.rollverknuepfungen, a.offene_kandidaten, a.abdeckung_rollverknuepfungen) == (
        11, 4, D("0.7333"))


def test_abdeckung_modus_belegt_bestaetigt():
    """Zugelassen: zusätzlich K6 -> 11/12 = 0.9167 (0.91666..). Rollverknüpfungen
    11 + 1 = 12; 12/(12 + 4) = 0.7500."""
    a = _abdeckung(_auswertung(), "belegt_bestaetigt")
    assert (a.ketten_abgeschlossen, a.ketten_ausgewertet, a.abdeckung_ketten) == (
        12, 11, D("0.9167"))
    assert (a.rollverknuepfungen, a.offene_kandidaten, a.abdeckung_rollverknuepfungen) == (
        12, 4, D("0.7500"))


def test_ohne_angabe_der_offenen_kandidaten_bleibt_die_roll_abdeckung_leer():
    """Wird die Zahl der offenen Kandidaten nicht übergeben (None), ist die
    Abdeckung der Rollverknüpfungen unbestimmt: None, nicht 1.0000."""
    a = _abdeckung(_auswertung(offene_kandidaten=None), "belegt")
    assert a.offene_kandidaten is None
    assert a.abdeckung_rollverknuepfungen is None
    assert a.rollverknuepfungen == 11


def test_keine_offenen_kandidaten_ergibt_volle_roll_abdeckung():
    a = _abdeckung(_auswertung(offene_kandidaten=0), "belegt")
    assert a.abdeckung_rollverknuepfungen == D("1.0000")


def test_nur_stufe_a_entfernt_ketten_ganz():
    """K13 (Stufe B) fällt weg - auch aus der Abdeckung: '0' belegt: K1 56 +
    K2 -14 + K3 36 = 78.00, Durchschnitt 26.00, Treffer 2/3 = 0.6667;
    abgeschlossen 11, zugelassen 9 -> 9/11 = 0.8182 (belegt) und 10/11 =
    0.9091 (belegt_bestaetigt)."""
    e = _auswertung(nur_qualitaetsstufe_a=True)
    assert _werte(_gruppe(e, "belegt", "0")) == (3, D("78.00"), D("26.00"), D("0.6667"), 1)
    assert _abdeckung(e, "belegt").abdeckung_ketten == D("0.8182")
    assert _abdeckung(e, "belegt_bestaetigt").abdeckung_ketten == D("0.9091")
    assert _abdeckung(e, "belegt").ketten_abgeschlossen == 11


def test_leere_gruppe_hat_keine_durchschnitte():
    """Eine Gruppe ohne Ketten: Anzahl 0, Summe 0.00, Durchschnitt und
    Trefferquote None. Hier: Welt nur mit K1 -> Gruppe '3+' leer."""
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = _welt()
    k1 = [k for k in ketten if k["chain_id"] == 1]
    ids = {s["structure_id"] for s in strukturen if s["chain_id"] == 1}
    e = degradations_auswertung(
        k1, [s for s in strukturen if s["chain_id"] == 1],
        [g for g in glieder if g["chain_id"] == 1],
        [x for x in legs if x["structure_id"] in ids],
        ausfuehrungen, instrumente, sicht="kette", offene_kandidaten=0,
    )
    assert _werte(_gruppe(e, "belegt", "3+")) == (0, D("0.00"), None, None, 0)
    assert _werte(_gruppe(e, "belegt", "0")) == (1, D("56.00"), D("56.00"), D("1.0000"), 0)


def test_kontosicht_wird_zurueckgewiesen():
    """Plan §5: Die Roll-Degradation läuft auf der Kettensicht."""
    with pytest.raises(ValueError, match="Kettensicht"):
        _auswertung(sicht="konto")


def test_csv_format_und_inhalt():
    """Eine Datei, Semikolon; erst die acht Gruppen, dann die zwei
    Abdeckungszeilen; Geld mit zwei, Quoten mit vier Stellen, Leere für nicht
    zutreffende Spalten."""
    zeilen = als_csv(_auswertung()).split("\n")

    assert zeilen[0] == (
        "abschnitt;modus;roll_gruppe;anzahl_ketten;summe_netto_eur;"
        "durchschnitt_netto_eur;trefferquote;anzahl_ketten_kurs_fehlt;"
        "ketten_abgeschlossen;ketten_ausgewertet;abdeckung_ketten;"
        "rollverknuepfungen;offene_kandidaten;abdeckung_rollverknuepfungen"
    )
    assert len(zeilen) == 1 + 8 + 2
    assert zeilen[1] == ";".join(
        ["gruppe", "belegt", "0", "4", "84.00", "21.00", "0.7500", "1", "", "", "", "", "", ""])
    assert zeilen[6] == ";".join(
        ["gruppe", "belegt_bestaetigt", "1", "3", "76.00", "25.33", "0.6667", "0",
         "", "", "", "", "", ""])
    assert zeilen[9] == ";".join(
        ["abdeckung", "belegt", "", "", "", "", "", "", "12", "10", "0.8333", "11", "4", "0.7333"])
    assert zeilen[10] == ";".join(
        ["abdeckung", "belegt_bestaetigt", "", "", "", "", "", "", "12", "11", "0.9167",
         "12", "4", "0.7500"])


# ---------------------------------------------------------------- offene Kandidaten


def _ablehnung(db_pfad) -> None:
    ketten = {z["natur_schluessel"]: z for z in _zeilen(db_pfad, chains)}
    strukturen = {z["natur_schluessel"]: z for z in _zeilen(db_pfad, structures)}
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        verbindung.execute(
            insert(chain_overrides).values(
                chain_id=ketten["k:Z1|Z2"]["chain_id"],
                structure_id=strukturen["Z5|Z6"]["structure_id"],
                notiz=None, erstellt_am=dt(2026, 9, 21, 18, 0, 0), urteil="abgelehnt",
            )
        )


def _zeilen(db_pfad, tabelle) -> list[dict]:
    stmt = select(tabelle).where(tabelle.c.sicht == "konto")
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return [dict(z) for z in verbindung.execute(stmt).mappings().all()]


def test_offene_rollkandidaten_zaehlt_wie_der_rebuild(migrated_db):
    """Wie `tests/test_rebuild.py`: der Fixture-Bestand hat genau einen offenen
    Kandidaten (ESTX50); nach der Ablehnung keinen. Die Funktion schreibt
    nichts."""
    befuelle(migrated_db)
    assert rebuild(migrated_db).kandidaten_offen == 1
    vorher = _zeilen(migrated_db, chains)

    assert offene_rollkandidaten(migrated_db) == 1
    assert _zeilen(migrated_db, chains) == vorher

    _ablehnung(migrated_db)
    assert rebuild(migrated_db).kandidaten_offen == 0
    assert offene_rollkandidaten(migrated_db) == 0


# ---------------------------------------------------------------- Hülle und CLI


def test_bericht_liest_die_offenen_kandidaten_selbst(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)

    e = degradations_bericht(migrated_db)

    assert e.sicht == "kette"
    assert len(e.gruppen) == 8
    assert [a.modus for a in e.abdeckung] == ["belegt", "belegt_bestaetigt"]
    assert all(a.offene_kandidaten == 1 for a in e.abdeckung)
    ausgewertet = sum(
        g.anzahl_ketten + g.anzahl_ketten_kurs_fehlt for g in e.gruppen if g.modus == "belegt"
    )
    assert ausgewertet == e.abdeckung[0].ketten_ausgewertet


def test_cli_schreibt_degradations_csv(migrated_db, tmp_path, capsys):
    befuelle(migrated_db)
    rebuild(migrated_db)
    kennzahlen = tmp_path / "kz.csv"
    degradation = tmp_path / "deg.csv"

    assert main(["kennzahlen", str(kennzahlen), "--degradation", str(degradation),
                 "--db", str(migrated_db)]) == 0

    inhalt = degradation.read_bytes()
    assert inhalt.startswith(b"\xef\xbb\xbf")  # UTF-8 mit BOM
    zeilen = inhalt.decode("utf-8-sig").split("\n")
    assert zeilen[0].startswith("abschnitt;modus;roll_gruppe;anzahl_ketten;")
    assert zeilen[-1] == ""  # Zeilenende \n, keine \r
    assert len([z for z in zeilen if z.startswith("gruppe;")]) == 8
    assert len([z for z in zeilen if z.startswith("abdeckung;")]) == 2
    assert "Degradation nach" in capsys.readouterr().out


def test_cli_weist_die_kontosicht_zurueck_ohne_etwas_zu_schreiben(migrated_db, tmp_path, capsys):
    befuelle(migrated_db)
    rebuild(migrated_db)
    kennzahlen = tmp_path / "kz.csv"
    degradation = tmp_path / "deg.csv"

    assert main(["kennzahlen", str(kennzahlen), "--sicht", "konto",
                 "--degradation", str(degradation), "--db", str(migrated_db)]) == 1

    assert not kennzahlen.exists()
    assert not degradation.exists()
    assert "Kettensicht" in capsys.readouterr().err


def test_cli_ohne_degradations_option_schreibt_keine_weitere_datei(migrated_db, tmp_path):
    befuelle(migrated_db)
    rebuild(migrated_db)
    kennzahlen = tmp_path / "kz.csv"

    assert main(["kennzahlen", str(kennzahlen), "--db", str(migrated_db)]) == 0

    assert sorted(p.name for p in tmp_path.glob("*.csv")) == ["kz.csv"]
