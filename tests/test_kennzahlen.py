"""Abnahmetests für AP-06v (Analytik I: EUR-Fundament und Kennzahlen).

Vertrag: auftraege/AP-06v.md — Datenklassen, Regeln 1–13, CSV-Format.
Diese Datei ist unveränderlich; jeder Erwartungswert ist von Hand gerechnet
und am jeweiligen Test begründet.

Startzustand (AP-06v): Diese Datei ist ROT, weil analytics.kennzahlen noch
nicht existiert — ModuleNotFoundError ist der einzige erlaubte Fehler.

Testwelt (reine Funktion, Kettensicht; alle Mengen je Leg 1,
Multiplikator USX 10, DAX 5, Kommission je Ausführung -2 in
Ausführungswährung):

  K1 USX (USD, Stufe A), vertikal geschlossen:
     U1 SELL 2001 @120 Kurs 0.90   05.01. 15:00
     U2 BUY  2002 @ 80 Kurs 0.90   05.01. 15:00
     U3 BUY  2001 @ 60 Kurs 0.95   20.01. 15:00
     U4 SELL 2002 @ 30 Kurs 0.95   20.01. 15:00
     brutto = ((120-60)+(30-80))*10 = 100.00, Kommission -8 -> netto 92.00
     wirtschaftlich = (1200*.90 -800*.90 -600*.95 +300*.95) - 7.40 = 67.60
     IB = 92*0.95 = 87.40, Effekt = -19.80

  K2 DAX (EUR, Stufe A), analog Preise 100/60 -> 40/20:
     netto 92.00, EUR-Faktor 1 -> wirtschaftlich = IB = 92.00, Effekt 0.00

  K3 USX offen: O1 SELL 2001 @130 Kurs 0.92, 02.02. 11:00
     -> netto None, offen, nicht in Quoten/Summen, kein Fehler

  K4 USX (USD, Stufe A): V1 SELL 2201 @50 / V2 BUY 2202 @30 Kurs 0.91,
     V3 BUY 2201 @70 Kurs 0.91, V4 SELL 2202 @45 Kurs None
     brutto -50.00, netto -58.00; EUR-Felder None, eur_kurs_fehlt 1,
     Fehler (Kette, buchungskurs_fehlt), nicht in summe_netto_eur

  K5 USX (USD, komplett Stufe B): W1..W4 wie K1, Kurse konstant 0.90
     netto 92.00, wirtschaftlich = (100*10)*0.90 - 7.20 = 82.80,
     IB = 82.80, Effekt 0.00, qualitaetsstufe B

Aggregate ohne Filter: Trefferquote Kette 3/4 = 0.7500 (K1,K2,K5 positiv,
K4 negativ; K3 offen), Struktur ebenso 0.7500;
summe_netto_eur = 67.60 + 92.00 + 82.80 = 242.40 (K4 fehlt Kurs).
Mit --nur-stufe-a fällt K5 weg: Quoten 2/3 = 0.6667, Summe 159.60.

Freigabe-Nachträge (E1-E6): Eine Kette mit netto exakt 0.00 zaehlt in den
Nenner und nicht in den Zaehler - kein Treffer (E5; eigener Test unten mit
Handwerten). fx_rates.quelle ist 'abgeleitet_letzte_ausfuehrung' (E3). Die
Ketten-EUR-Werte stehen in metrics_by_chain (netto_eur_wirtschaftlich,
netto_eur_ib), chains.netto_pnl_eur bleibt leer (E2).
"""

from datetime import date
from datetime import datetime as dt
from decimal import Decimal as D

from fixtures_rebuild import befuelle
from sqlalchemy import select

from analytics.kennzahlen import (
    KennzahlErgebnis,
    als_csv,
    fx_tageskurse,
    kennzahlen_auswertung,
    kennzahlen_bericht,
)
from journal.cli import main
from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import chains, fx_rates, metrics_by_chain


def _ausf(exec_id, conid, side, preis, handelszeit, kurs, stufe="A", waehrung="USD"):
    return dict(
        exec_id=exec_id,
        conid=conid,
        side=side,
        preis=D(preis),
        menge=1,
        waehrung=waehrung,
        kommission=D("-2.00"),
        kommission_waehrung=waehrung,
        buchungskurs=kurs,
        handelszeit=handelszeit,
        qualitaetsstufe=stufe,
    )


INSTRUMENTE_Z = [
    dict(conid=c, multiplikator=D("10"))
    for c in (2001, 2002, 2201, 2202, 2301, 2302)
] + [dict(conid=c, multiplikator=D("5")) for c in (2101, 2102)]

AUSFUEHRUNGEN_Z = [
    _ausf("U1", 2001, "SELL", "120.00", dt(2026, 1, 5, 15, 0), D("0.90")),
    _ausf("U2", 2002, "BUY", "80.00", dt(2026, 1, 5, 15, 0), D("0.90")),
    _ausf("U3", 2001, "BUY", "60.00", dt(2026, 1, 20, 15, 0), D("0.95")),
    _ausf("U4", 2002, "SELL", "30.00", dt(2026, 1, 20, 15, 0), D("0.95")),
    _ausf("D1", 2101, "SELL", "100.00", dt(2026, 1, 6, 15, 0), D("1"), waehrung="EUR"),
    _ausf("D2", 2102, "BUY", "60.00", dt(2026, 1, 6, 15, 0), D("1"), waehrung="EUR"),
    _ausf("D3", 2101, "BUY", "40.00", dt(2026, 1, 22, 15, 0), D("1"), waehrung="EUR"),
    _ausf("D4", 2102, "SELL", "20.00", dt(2026, 1, 22, 15, 0), D("1"), waehrung="EUR"),
    _ausf("O1", 2001, "SELL", "130.00", dt(2026, 2, 2, 11, 0), D("0.92")),
    _ausf("V1", 2201, "SELL", "50.00", dt(2026, 1, 7, 15, 0), D("0.91")),
    _ausf("V2", 2202, "BUY", "30.00", dt(2026, 1, 7, 15, 0), D("0.91")),
    _ausf("V3", 2201, "BUY", "70.00", dt(2026, 1, 23, 15, 0), D("0.91")),
    _ausf("V4", 2202, "SELL", "45.00", dt(2026, 1, 23, 15, 0), None),
    _ausf("W1", 2301, "SELL", "120.00", dt(2026, 3, 2, 15, 0), D("0.90"), stufe="B"),
    _ausf("W2", 2302, "BUY", "80.00", dt(2026, 3, 2, 15, 0), D("0.90"), stufe="B"),
    _ausf("W3", 2301, "BUY", "60.00", dt(2026, 3, 16, 15, 0), D("0.90"), stufe="B"),
    _ausf("W4", 2302, "SELL", "30.00", dt(2026, 3, 16, 15, 0), D("0.90"), stufe="B"),
]

def _kette(chain_id, underlying, beendet_am, sicht):
    return dict(
        chain_id=chain_id,
        sicht=sicht,
        underlying=underlying,
        asset_class="OPT",
        anzahl_rolls=0,
        beendet_am=beendet_am,
    )


def _struktur(structure_id, chain_id, waehrung, brutto, netto, geschlossen_am, typ="Vertical"):
    return dict(
        structure_id=structure_id,
        chain_id=chain_id,
        typ=typ,
        waehrung=waehrung,
        brutto_pnl=brutto,
        kommission=D("-8.00") if netto is not None else D("-2.00"),
        netto_pnl=netto,
        geschlossen_am=geschlossen_am,
    )


def _leg(leg_id, structure_id, conid, open_exec_id, close_exec_id, offen):
    return dict(
        leg_id=leg_id,
        structure_id=structure_id,
        conid=conid,
        open_exec_id=open_exec_id,
        close_exec_id=close_exec_id,
        menge=1,
        offen_ja_nein=offen,
    )


def _welt(sicht="kette"):
    """Liefert (ketten, strukturen, glieder, legs) in Vertragsreihenfolge."""
    ketten = [
        _kette(1, "USX", dt(2026, 1, 20, 15, 0), sicht),
        _kette(2, "DAX", dt(2026, 1, 22, 15, 0), sicht),
        _kette(3, "USX", None, sicht),
        _kette(4, "USX", dt(2026, 1, 23, 15, 0), sicht),
        _kette(5, "USX", dt(2026, 3, 16, 15, 0), sicht),
    ]
    strukturen = [
        _struktur(11, 1, "USD", D("100.00"), D("92.00"), dt(2026, 1, 20, 15, 0)),
        _struktur(12, 2, "EUR", D("100.00"), D("92.00"), dt(2026, 1, 22, 15, 0)),
        _struktur(13, 3, "USD", None, None, None, typ="Single"),
        _struktur(14, 4, "USD", D("-50.00"), D("-58.00"), dt(2026, 1, 23, 15, 0)),
        _struktur(15, 5, "USD", D("100.00"), D("92.00"), dt(2026, 3, 16, 15, 0)),
    ]
    glieder = [
        dict(structure_id=sid, chain_id=cid, sicht=sicht)
        for sid, cid in ((11, 1), (12, 2), (13, 3), (14, 4), (15, 5))
    ]
    legs = [
        _leg(101, 11, 2001, "U1", "U3", False),
        _leg(102, 11, 2002, "U2", "U4", False),
        _leg(103, 12, 2101, "D1", "D3", False),
        _leg(104, 12, 2102, "D2", "D4", False),
        _leg(105, 13, 2001, "O1", None, True),
        _leg(106, 14, 2201, "V1", "V3", False),
        _leg(107, 14, 2202, "V2", "V4", False),
        _leg(108, 15, 2301, "W1", "W3", False),
        _leg(109, 15, 2302, "W2", "W4", False),
    ]
    return ketten, strukturen, glieder, legs


def _auswertung(sicht="kette", nur_qualitaetsstufe_a=False):
    ketten, strukturen, glieder, legs = _welt(sicht)
    return kennzahlen_auswertung(
        ketten,
        strukturen,
        glieder,
        legs,
        AUSFUEHRUNGEN_Z,
        INSTRUMENTE_Z,
        sicht=sicht,
        nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )


# ---------------------------------------------------------------- reine Funktion


def test_k1_beide_eur_sichten_und_waehrungseffekt():
    """K1: wirtschaftlich 67.60, IB 87.40, Effekt -19.80 (Modul-Docstring)."""
    k1 = _auswertung().ketten[0]
    assert k1.sicht == "kette"
    assert k1.netto == D("92.00")
    assert k1.netto_eur_wirtschaftlich == D("67.60")
    assert k1.netto_eur_ib == D("87.40")
    assert k1.waehrungseffekt_eur == D("-19.80")
    assert k1.eur_kurs_fehlt == 0
    assert k1.abgeschlossen is True


def test_eur_instrument_braucht_keinen_fx_eintrag():
    """K2: Faktor 1 je Ausführung -> wirtschaftlich = IB = 92.00, Effekt 0.00."""
    k2 = _auswertung().ketten[1]
    assert k2.waehrung == "EUR"
    assert k2.netto_eur_wirtschaftlich == D("92.00")
    assert k2.netto_eur_ib == D("92.00")
    assert k2.waehrungseffekt_eur == D("0.00")


def test_fehlender_buchungskurs_ist_gezaehlter_mangel():
    """K4: nur V4 ohne Kurs -> eur_kurs_fehlt 1, EUR-Felder None,
    Fehler (Kette 4, buchungskurs_fehlt), Kette bleibt in Trefferquote."""
    ergebnis = _auswertung()
    k4 = ergebnis.ketten[3]
    assert k4.netto == D("-58.00")
    assert k4.netto_eur_wirtschaftlich is None
    assert k4.netto_eur_ib is None
    assert k4.waehrungseffekt_eur is None
    assert k4.eur_kurs_fehlt == 1
    assert ergebnis.fehler == (("4", "buchungskurs_fehlt"),)
    assert ergebnis.trefferquote_kette == D("0.7500")  # -58 zaehlt als Fehltreffer
    assert ergebnis.summe_netto_eur == D("242.40")  # ohne K4


def test_offene_kette_bleibt_draussen():
    """K3: netto None, offen, keine Fehlerzeile, nicht in Quoten/Summen."""
    ergebnis = _auswertung()
    k3 = ergebnis.ketten[2]
    assert k3.abgeschlossen is False
    assert k3.netto is None
    assert k3.netto_eur_wirtschaftlich is None
    assert ergebnis.anzahl_ketten_abgeschlossen == 4
    assert all(f[0] != "3" for f in ergebnis.fehler)


def test_trefferquoten_beider_ebenen():
    """3 von 4 abgeschlossenen Ketten positiv -> 0.7500, ebenso Strukturen.
    3/4 exakt in Decimal: 0.75 bleibt 0.7500 nach Vier-Stellen-Rundung."""
    ergebnis = _auswertung()
    assert ergebnis.trefferquote_kette == D("0.7500")
    assert ergebnis.trefferquote_struktur == D("0.7500")
    assert ergebnis.anzahl_strukturen_abgeschlossen == 4


def test_netto_gleich_null_zaehlt_als_kein_treffer():
    """E5 (Freigabe): netto exakt 0.00 ist ein WERT (kein None) und kein
    Treffer. Hand fuer Kette 2: brutto (50-49.20)*10 + (30-30)*10 = 8.00,
    Kommission -8.00 -> netto 0.00; wirtschaftlich
    (450.00 - 442.80 + 270.00 - 270.00) - 7.20 = 0.00,
    IB = 0.00 * 0.90 = 0.00. Quote 1/2 = 0.5000 (nur Kette 1 positiv),
    Summe 67.60 + 0.00 = 67.60, kein Fehler."""
    ketten = [
        _kette(1, "USX", dt(2026, 1, 20, 15, 0), "kette"),
        _kette(2, "USX", dt(2026, 2, 20, 15, 0), "kette"),
    ]
    strukturen = [
        _struktur(11, 1, "USD", D("100.00"), D("92.00"), dt(2026, 1, 20, 15, 0)),
        _struktur(12, 2, "USD", D("8.00"), D("0.00"), dt(2026, 2, 20, 15, 0)),
    ]
    glieder = [
        dict(structure_id=sid, chain_id=cid, sicht="kette")
        for sid, cid in ((11, 1), (12, 2))
    ]
    legs = [
        _leg(101, 11, 2001, "U1", "U3", False),
        _leg(102, 11, 2002, "U2", "U4", False),
        _leg(103, 12, 2001, "Z1", "Z2", False),
        _leg(104, 12, 2002, "Z3", "Z4", False),
    ]
    ausfuehrungen = AUSFUEHRUNGEN_Z[:4] + [
        _ausf("Z1", 2001, "SELL", "50.00", dt(2026, 2, 20, 15, 0), D("0.90")),
        _ausf("Z2", 2001, "BUY", "49.20", dt(2026, 2, 20, 15, 0), D("0.90")),
        _ausf("Z3", 2002, "SELL", "30.00", dt(2026, 2, 20, 15, 0), D("0.90")),
        _ausf("Z4", 2002, "BUY", "30.00", dt(2026, 2, 20, 15, 0), D("0.90")),
    ]
    ergebnis = kennzahlen_auswertung(
        ketten, strukturen, glieder, legs, ausfuehrungen, INSTRUMENTE_Z
    )
    k2 = ergebnis.ketten[1]
    assert k2.netto == D("0.00")
    assert k2.netto_eur_wirtschaftlich == D("0.00")
    assert k2.netto_eur_ib == D("0.00")
    assert k2.waehrungseffekt_eur == D("0.00")
    assert k2.eur_kurs_fehlt == 0
    assert ergebnis.trefferquote_kette == D("0.5000")
    assert ergebnis.trefferquote_struktur == D("0.5000")
    assert ergebnis.summe_netto_eur == D("67.60")
    assert ergebnis.anzahl_ketten_abgeschlossen == 2
    assert ergebnis.fehler == ()


def test_qualitaetsstufe_ist_minimum_ueber_ausfuehrungen():
    """K5: alle vier Ausfuehrungen Stufe B -> Kettenminimum B (E6)."""
    assert _auswertung().ketten[4].qualitaetsstufe == "B"

def test_filter_nur_stufe_a_entfernt_k5_komplett():
    """Filter entfernt K5 (B) aus Ketten, Strukturen, Summen, Quoten, Anzahlen;
    K4 bleibt (ist Stufe A) samt Fehler und ohne Summenbeitrag:
    Quoten 2/3 = 0.6667 (HALF_UP), Summe 67.60 + 92.00 = 159.60."""
    ergebnis = _auswertung(nur_qualitaetsstufe_a=True)
    assert [k.chain_id for k in ergebnis.ketten] == [1, 2, 4]
    assert [s.structure_id for s in ergebnis.strukturen] == [11, 12, 14]
    assert ergebnis.trefferquote_kette == D("0.6667")
    assert ergebnis.trefferquote_struktur == D("0.6667")
    assert ergebnis.summe_netto_eur == D("159.60")
    assert ergebnis.anzahl_ketten_abgeschlossen == 3
    assert ergebnis.fehler == (("4", "buchungskurs_fehlt"),)


def test_konstanter_kurs_macht_waehrungseffekt_null():
    """K5: alle Kurse 0.90 -> wirtschaftlich = IB = 82.80, Effekt 0.00.
    Hand: (1200-800-600+300)*0.90 = 90.00 minus Kommission 7.20."""
    k5 = _auswertung().ketten[4]
    assert k5.netto_eur_wirtschaftlich == D("82.80")
    assert k5.netto_eur_ib == D("82.80")
    assert k5.waehrungseffekt_eur == D("0.00")


def test_strukturzeilen_inhalt_und_sortierung():
    """S11 .. S15 nach (chain_id, structure_id); offene Struktur S13 ohne netto;
    S14 behaelt netto -58.00 ohne EUR (Regel 6 gilt je Ebene)."""
    strukturen = _auswertung().strukturen
    assert [s.structure_id for s in strukturen] == [11, 12, 13, 14, 15]
    s11 = strukturen[0]
    assert (s11.chain_id, s11.typ, s11.waehrung) == (1, "Vertical", "USD")
    assert s11.brutto == D("100.00")
    assert s11.kommission == D("-8.00")
    assert s11.netto == D("92.00")
    assert s11.netto_eur_wirtschaftlich == D("67.60")
    assert strukturen[2].netto is None
    assert strukturen[3].netto == D("-58.00")
    assert strukturen[3].netto_eur_wirtschaftlich is None


def test_ketten_sortiert_und_sicht_feld_ist_konto():
    """Sicht konto: gleiche Zahlen, jede Zeile traegt sicht='konto' (E1)."""
    ergebnis = _auswertung(sicht="konto")
    assert [k.chain_id for k in ergebnis.ketten] == [1, 2, 3, 4, 5]
    assert all(k.sicht == "konto" for k in ergebnis.ketten)
    assert ergebnis.sicht == "konto"
    assert ergebnis.summe_netto_eur == D("242.40")


def test_leere_eingabe_liefert_leeres_ergebnis():
    ergebnis = kennzahlen_auswertung([], [], [], [], [], [])
    assert isinstance(ergebnis, KennzahlErgebnis)
    assert ergebnis.ketten == ()
    assert ergebnis.strukturen == ()
    assert ergebnis.fehler == ()
    assert ergebnis.summe_netto_eur is None
    assert ergebnis.trefferquote_kette is None
    assert ergebnis.trefferquote_struktur is None
    assert ergebnis.anzahl_ketten_abgeschlossen == 0
    assert ergebnis.anzahl_strukturen_abgeschlossen == 0


def test_waehrung_gemischt_ist_fehler_nie_geraten():
    """Defensiv (Regel 10): Kette aus USD- und EUR-Struktur -> netto None
    und Fehler (waehrung_gemischt) statt einer gemischte Summe."""
    ketten = [_kette(9, "USX", dt(2026, 1, 20, 15, 0), "kette")]
    strukturen = [
        _struktur(91, 9, "USD", D("10.00"), D("8.00"), dt(2026, 1, 20, 15, 0)),
        _struktur(92, 9, "EUR", D("5.00"), D("3.00"), dt(2026, 1, 20, 15, 0)),
    ]
    glieder = [dict(structure_id=91, chain_id=9, sicht="kette"),
               dict(structure_id=92, chain_id=9, sicht="kette")]
    legs = [_leg(191, 91, 2001, "U1", "U3", False),
            _leg(192, 92, 2101, "D1", "D3", False)]
    ergebnis = kennzahlen_auswertung(
        ketten, strukturen, glieder, legs, AUSFUEHRUNGEN_Z, INSTRUMENTE_Z
    )
    k9 = ergebnis.ketten[0]
    assert k9.netto is None
    assert k9.netto_eur_wirtschaftlich is None
    assert ("9", "waehrung_gemischt") in ergebnis.fehler
    assert ergebnis.summe_netto_eur is None


# ---------------------------------------------------------------- fx_tageskurse


def test_fx_tageskurse_nach_vertrag():
    """Je (Tag, Waehrung != EUR) der Kurs der LETZTEN Ausführung des Tages,
    sortiert nach (datum, waehrung); V4 (Kurs None) traegt nichts bei;
    die EUR-Tage 06.01./22.01. fehlen (Regel 11)."""
    quelle = "abgeleitet_letzte_ausfuehrung"
    kurse = fx_tageskurse(AUSFUEHRUNGEN_Z)
    assert kurse == [
        dict(datum=date(2026, 1, 5), waehrung="USD", kurs_eur=D("0.90"), quelle=quelle),
        dict(datum=date(2026, 1, 7), waehrung="USD", kurs_eur=D("0.91"), quelle=quelle),
        dict(datum=date(2026, 1, 20), waehrung="USD", kurs_eur=D("0.95"), quelle=quelle),
        dict(datum=date(2026, 2, 2), waehrung="USD", kurs_eur=D("0.92"), quelle=quelle),
        dict(datum=date(2026, 3, 2), waehrung="USD", kurs_eur=D("0.90"), quelle=quelle),
        dict(datum=date(2026, 3, 16), waehrung="USD", kurs_eur=D("0.90"), quelle=quelle),
    ]


def test_fx_tageskurs_bei_mehreren_kursen_am_tag():
    """09:00 Kurs 0.88, 16:00 Kurs 0.89 -> 0.89 gewinnt;
    Gleichstand der handelszeit -> groesste exec_id gewinnt (Regel 11)."""
    frueh = _ausf("F1", 2001, "SELL", "100.00", dt(2026, 4, 1, 9, 0), D("0.88"))
    spaet = _ausf("F2", 2001, "BUY", "100.00", dt(2026, 4, 1, 16, 0), D("0.89"))
    gleich1 = _ausf("G1", 2002, "SELL", "100.00", dt(2026, 4, 2, 10, 0), D("0.90"))
    gleich2 = _ausf("G2", 2002, "SELL", "100.00", dt(2026, 4, 2, 10, 0), D("0.91"))
    kurse = fx_tageskurse([frueh, spaet, gleich1, gleich2])
    assert [(k["datum"], k["kurs_eur"]) for k in kurse] == [
        (date(2026, 4, 1), D("0.89")),
        (date(2026, 4, 2), D("0.91")),
    ]

# ---------------------------------------------------------------- CSV


# Die drei langen Kettenzeilen als Konstanten (Ruff, Zeilenlaenge 100).
_ZEILE_K1 = "kette;kette;1;USX;OPT;abgeschlossen;0;USD;92.00;67.60;87.40;-19.80;0;A;;;;;;;;"
_ZEILE_K2 = "kette;kette;2;DAX;OPT;abgeschlossen;0;EUR;92.00;92.00;92.00;0.00;0;A;;;;;;;;"
_ZEILE_K5 = "kette;kette;5;USX;OPT;abgeschlossen;0;USD;92.00;82.80;82.80;0.00;0;B;;;;;;;;"


def test_als_csv_zeilen_exakt():
    """Regel 13: 22 Spalten, Semikolon, Kopf exakt, Reihenfolge
    Kopf - 5 kette - 4 struktur - 1 fehler - summe.
    Betrage zwei Nachkommastellen, Quoten vier (HALF_UP)."""
    csv = als_csv(_auswertung())
    zeilen = csv.splitlines()
    assert zeilen[0] == (
        "abschnitt;sicht;chain_id;underlying;asset_class;status;anzahl_rolls;waehrung;netto;"
        "netto_eur_wirtschaftlich;netto_eur_ib;waehrungseffekt_eur;eur_kurs_fehlt;"
        "qualitaetsstufe;structure_id;typ;brutto;kommission;schluessel;grund;"
        "trefferquote_kette;trefferquote_struktur"
    )
    assert len(zeilen) == 12
    assert zeilen[1] == _ZEILE_K1
    assert zeilen[2] == _ZEILE_K2
    assert zeilen[3] == "kette;kette;3;USX;OPT;offen;0;USD;;;;;0;A;;;;;;;;"
    assert zeilen[4] == "kette;kette;4;USX;OPT;abgeschlossen;0;USD;-58.00;;;;1;A;;;;;;;;"
    assert zeilen[5] == _ZEILE_K5
    assert zeilen[6] == "struktur;kette;1;;;;;USD;92.00;67.60;;;;;11;Vertical;100.00;-8.00;;;;"
    assert zeilen[10] == "fehler;kette;;;;;;;;;;;;;;;;;4;buchungskurs_fehlt;;"
    assert zeilen[11] == "summe;kette;;;;;;;;242.40;;;1;;;;;;;;0.7500;0.7500"
    assert all(len(z.split(";")) == 22 for z in zeilen)

# ---------------------------------------------------------------- Ende zu Ende
# Dieselbe Welt wie oben, aber über die echte Engine: befuelle() aus
# fixtures_rebuild schreibt Instrumente und Ausführungen (Defaults:
# Menge 1, Kommission -2.00 je Ausführung, Stufe A), exec_batch macht die
# Combo-Eröffnungen/-Schließungen; rebuild() baut Legs, Strukturen,
# Ketten in beiden Sichten. Die Engine liefert dieselben Beträge wie die
# reine Funktion (Handrechnung im Modul-Docstring).


def _opt(conid, symbol, underlying, strike, expiry, multiplikator, waehrung):
    return dict(
        conid=conid, symbol=symbol, underlying=underlying, asset_class="OPT",
        expiry=expiry, strike=D(strike), right="P",
        multiplikator=D(multiplikator), waehrung=waehrung,
    )


E2E_INSTRUMENTE = [
    _opt(2001, "USX  260220P6000", "USX", "6000", date(2026, 2, 20), "10", "USD"),
    _opt(2002, "USX  260220P5900", "USX", "5900", date(2026, 2, 20), "10", "USD"),
    _opt(2101, "DAX  260220P19000", "DAX", "19000", date(2026, 2, 20), "5", "EUR"),
    _opt(2102, "DAX  260220P18900", "DAX", "18900", date(2026, 2, 20), "5", "EUR"),
    _opt(2201, "USX  260220P5000", "USX", "5000", date(2026, 2, 20), "10", "USD"),
    _opt(2202, "USX  260220P4900", "USX", "4900", date(2026, 2, 20), "10", "USD"),
    _opt(2301, "USX  260320P7000", "USX", "7000", date(2026, 3, 20), "10", "USD"),
    _opt(2302, "USX  260320P6900", "USX", "6900", date(2026, 3, 20), "10", "USD"),
]


def _e2e(exec_id, conid, side, preis, handelszeit, kurs, stufe="A", waehrung="USD", batch=None):
    satz = dict(
        exec_id=exec_id, conid=conid, side=side, preis=D(preis),
        handelszeit=handelszeit, buchungskurs=kurs, qualitaetsstufe=stufe,
        waehrung=waehrung, kommission_waehrung=waehrung,
    )
    if batch is not None:
        satz["exec_batch"] = batch
    return satz


E2E_AUSFUEHRUNGEN = [
    _e2e("U1", 2001, "SELL", "120.00", dt(2026, 1, 5, 15, 0), D("0.90"), batch="1.1"),
    _e2e("U2", 2002, "BUY", "80.00", dt(2026, 1, 5, 15, 0), D("0.90"), batch="1.1"),
    _e2e("U3", 2001, "BUY", "60.00", dt(2026, 1, 20, 15, 0), D("0.95"), batch="1.2"),
    _e2e("U4", 2002, "SELL", "30.00", dt(2026, 1, 20, 15, 0), D("0.95"), batch="1.2"),
    _e2e("D1", 2101, "SELL", "100.00", dt(2026, 1, 6, 15, 0), D("1"), waehrung="EUR", batch="2.1"),
    _e2e("D2", 2102, "BUY", "60.00", dt(2026, 1, 6, 15, 0), D("1"), waehrung="EUR", batch="2.1"),
    _e2e("D3", 2101, "BUY", "40.00", dt(2026, 1, 22, 15, 0), D("1"), waehrung="EUR", batch="2.2"),
    _e2e("D4", 2102, "SELL", "20.00", dt(2026, 1, 22, 15, 0), D("1"), waehrung="EUR", batch="2.2"),
    _e2e("O1", 2001, "SELL", "130.00", dt(2026, 2, 2, 11, 0), D("0.92")),
    _e2e("V1", 2201, "SELL", "50.00", dt(2026, 1, 7, 15, 0), D("0.91"), batch="4.1"),
    _e2e("V2", 2202, "BUY", "30.00", dt(2026, 1, 7, 15, 0), D("0.91"), batch="4.1"),
    _e2e("V3", 2201, "BUY", "70.00", dt(2026, 1, 23, 15, 0), D("0.91"), batch="4.2"),
    _e2e("V4", 2202, "SELL", "45.00", dt(2026, 1, 23, 15, 0), None, batch="4.2"),
    _e2e("W1", 2301, "SELL", "120.00", dt(2026, 3, 2, 15, 0), D("0.90"), stufe="B", batch="5.1"),
    _e2e("W2", 2302, "BUY", "80.00", dt(2026, 3, 2, 15, 0), D("0.90"), stufe="B", batch="5.1"),
    _e2e("W3", 2301, "BUY", "60.00", dt(2026, 3, 16, 15, 0), D("0.90"), stufe="B", batch="5.2"),
    _e2e("W4", 2302, "SELL", "30.00", dt(2026, 3, 16, 15, 0), D("0.90"), stufe="B", batch="5.2"),
]


def _bereite_db_vor(db_pfad):
    befuelle(str(db_pfad), ausfuehrungen=E2E_AUSFUEHRUNGEN, instrumente_=E2E_INSTRUMENTE)
    rebuild(str(db_pfad))


def test_ende_zu_ende_bericht_und_befuellung(migrated_db):
    """rebuild + kennzahlen_bericht: Aggregate wie in der reinen Welt,
    fx_rates vollständig neu (E3: quelle 'abgeleitet_letzte_ausfuehrung'),
    metrics_by_chain in BEIDEN Sichten mit wirtschaftlichem und IB-Ergebnis
    (Regel 11); NULL nur fuer offen/Kursmangel. chains.netto_pnl_eur bleibt
    auch nach dem Bericht leer (E2)."""
    _bereite_db_vor(migrated_db)
    ergebnis = kennzahlen_bericht(str(migrated_db))

    assert ergebnis.sicht == "kette"
    assert ergebnis.trefferquote_kette == D("0.7500")
    assert ergebnis.trefferquote_struktur == D("0.7500")
    assert ergebnis.summe_netto_eur == D("242.40")
    assert ergebnis.anzahl_ketten_abgeschlossen == 4
    assert ergebnis.anzahl_strukturen_abgeschlossen == 4
    assert len(ergebnis.ketten) == 5

    k4 = next(k for k in ergebnis.ketten if k.netto == D("-58.00"))
    assert k4.eur_kurs_fehlt == 1
    assert ergebnis.fehler == ((str(k4.chain_id), "buchungskurs_fehlt"),)
    k1 = next(k for k in ergebnis.ketten if k.netto_eur_wirtschaftlich == D("67.60"))
    assert (k1.netto_eur_ib, k1.waehrungseffekt_eur) == (D("87.40"), D("-19.80"))
    k3 = next(k for k in ergebnis.ketten if not k.abgeschlossen)
    assert k3.netto is None and k3.netto_eur_wirtschaftlich is None
    k5 = next(k for k in ergebnis.ketten if k.qualitaetsstufe == "B")
    assert k5.netto_eur_wirtschaftlich == D("82.80")
    k2 = next(k for k in ergebnis.ketten if k.waehrung == "EUR")
    assert k2.netto_eur_wirtschaftlich == k2.netto_eur_ib == D("92.00")

    erwartete = sorted([D("67.60"), D("82.80"), D("92.00")])
    assert sorted(
        s.netto_eur_wirtschaftlich for s in ergebnis.strukturen
        if s.netto_eur_wirtschaftlich is not None
    ) == erwartete

    engine = create_db_engine(str(migrated_db))
    with engine.connect() as verbindung:
        assert verbindung.execute(
            select(chains.c.netto_pnl_eur).where(chains.c.sicht == "kette")
        ).scalars().all() == [None] * 5  # E2: bleibt auch nach dem Bericht leer
        for sicht in ("kette", "konto"):
            zeilen = verbindung.execute(
                select(
                    metrics_by_chain.c.netto_eur_wirtschaftlich,
                    metrics_by_chain.c.netto_eur_ib,
                )
                .join(chains, chains.c.chain_id == metrics_by_chain.c.chain_id)
                .where(chains.c.sicht == sicht)
            ).all()
            assert len(zeilen) == 5
            werte_w = [w for w, _ in zeilen]
            werte_ib = [ib for _, ib in zeilen]
            assert werte_w.count(None) == 2  # K3 offen, K4 Kursmangel
            assert sorted(w for w in werte_w if w is not None) == erwartete
            assert werte_ib.count(None) == 2
            assert sorted(
                ib for ib in werte_ib if ib is not None
            ) == [D("82.80"), D("87.40"), D("92.00")]
        kurse = verbindung.execute(
            select(
                fx_rates.c.datum, fx_rates.c.waehrung,
                fx_rates.c.kurs_eur, fx_rates.c.quelle,
            ).order_by(fx_rates.c.datum, fx_rates.c.waehrung)
        ).all()
    assert kurse == [
        (date(2026, 1, 5), "USD", D("0.90"), "abgeleitet_letzte_ausfuehrung"),
        (date(2026, 1, 7), "USD", D("0.91"), "abgeleitet_letzte_ausfuehrung"),
        (date(2026, 1, 20), "USD", D("0.95"), "abgeleitet_letzte_ausfuehrung"),
        (date(2026, 2, 2), "USD", D("0.92"), "abgeleitet_letzte_ausfuehrung"),
        (date(2026, 3, 2), "USD", D("0.90"), "abgeleitet_letzte_ausfuehrung"),
        (date(2026, 3, 16), "USD", D("0.90"), "abgeleitet_letzte_ausfuehrung"),
    ]


def test_bericht_sicht_konto_ohne_vermischung(migrated_db):
    """E1: --sicht konto liefert dieselben Zahlen (das Fixture vermixt
    conids nicht), jede Zeile traegt sicht='konto'."""
    _bereite_db_vor(migrated_db)
    ergebnis = kennzahlen_bericht(str(migrated_db), sicht="konto")
    assert ergebnis.sicht == "konto"
    assert all(k.sicht == "konto" for k in ergebnis.ketten)
    assert ergebnis.summe_netto_eur == D("242.40")
    assert ergebnis.trefferquote_kette == D("0.7500")


def test_cli_schreibt_csv_datei(migrated_db, tmp_path):
    _bereite_db_vor(migrated_db)
    ziel = tmp_path / "kennzahlen.csv"
    assert main(["kennzahlen", str(ziel), "--db", str(migrated_db)]) == 0
    assert ziel.read_bytes()[:3] == b"\xef\xbb\xbf"
    inhalt = ziel.read_text(encoding="utf-8-sig")
    assert inhalt.startswith(
        "abschnitt;sicht;chain_id;underlying;asset_class;status;anzahl_rolls;waehrung;netto;"
    )
    # K1-Zeile (eindeutig ueber 67.60/87.40) und die Summenzeile:
    assert ";USX;OPT;abgeschlossen;0;USD;92.00;67.60;87.40;-19.80;0;A" in inhalt
    assert "summe;kette;;;;;;;;242.40;;;1;;;;;;;;0.7500;0.7500" in inhalt





