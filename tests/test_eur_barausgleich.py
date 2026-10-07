"""Abnahmetests für AP-06x: Barausgleich-Zuteilung und -Ausübung in der
wirtschaftlichen EUR-Rechnung (Kennzahlen und Kommissionsattribution).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-06x.md`.

Der Fehler (Echtlauf 07.10.2026): Bei Zuteilung/Ausübung einer Option mit
Barausgleich trägt die Ereigniszeile den Preis 0, der Abrechnungskurs steht
in `schlusskurs` (OF-25). `engine.matching` rechnet deshalb mit dem
`schlusskurs`; die EUR-Rechnung rechnete mit dem Preis 0 und zeigte nur die
Prämie. Folge: wirtschaftliches Netto in EUR zu hoch, „Währungseffekt"
verfälscht, Kommissionsanteile je Strategie verzerrt.

Regel: Eine Ausführung mit `ereignistyp` `assignment` oder `exercise`,
deren Instrument die `abwicklungsart` `barausgleich` trägt, wird mit ihrem
`schlusskurs` bewertet statt mit ihrem `preis`. Alles andere bleibt beim
`preis` (Handel, Lieferung, auch ein gesetzter `schlusskurs` bei Lieferung
oder bei einem normalen Handel). Fehlt der `schlusskurs` bei Barausgleich,
endet die Rechnung mit `ValueError`, der die Ausführung nennt (kein Raten).

Testwelt (eine Kette, ein Short-Put-Leg, Multiplikator 100, Menge 1,
Kommission je Ausführung -2.00 in USD):

  S1 SELL @ 4.00   Kurs 0.80   (Eröffnung)
  Z1 BUY  @ 0.00   Kurs 0.90   (Zuteilung, schlusskurs 10.00)

  brutto USD = -(10.00 - 4.00) * 1 * 100 = -600.00; Kommission -4.00;
  netto USD = -604.00.
  wirtschaftlich = (+400 - 2.00) * 0.80 + (-1000 - 2.00) * 0.90
                 = 318.40 - 901.80 = -583.40
  IB = -604.00 * 0.90 (Kurs der letzten Schließung) = -543.60
  Währungseffekt = -583.40 - (-543.60) = -39.80
  EUR-Brutto = 400 * 0.80 - 1000 * 0.90 = 320.00 - 900.00 = -580.00
  EUR-Kommission = -2.00 * 0.80 - 2.00 * 0.90 = -3.40
"""

from datetime import date
from datetime import datetime as dt
from decimal import Decimal as D

import pytest
from fixtures_rebuild import befuelle

from analytics.kennzahlen import kennzahlen_auswertung, kennzahlen_bericht
from analytics.kommission import kommissions_attribution, kommissions_bericht
from journal.rebuild import rebuild


def _ausf(exec_id, side, preis, kurs, handelszeit, ereignistyp="trade", schlusskurs=None):
    return dict(
        exec_id=exec_id,
        conid=3001,
        side=side,
        preis=D(preis),
        menge=1,
        waehrung="USD",
        kommission=D("-2.00"),
        kommission_waehrung="USD",
        buchungskurs=kurs,
        handelszeit=handelszeit,
        qualitaetsstufe="A",
        ereignistyp=ereignistyp,
        schlusskurs=None if schlusskurs is None else D(schlusskurs),
    )


def _welt(ausfuehrungen, abwicklungsart, brutto, netto, kommission):
    """(ketten, strukturen, glieder, legs, ausfuehrungen, instrumente)."""
    ende = ausfuehrungen[-1]["handelszeit"]
    kette = dict(chain_id=1, sicht="konto", underlying="SPX", asset_class="OPT",
                 anzahl_rolls=0, beendet_am=ende, oa_strategie=None)
    struktur = dict(structure_id=11, chain_id=1, typ="Single", waehrung="USD",
                    brutto_pnl=D(brutto), kommission=D(kommission), netto_pnl=D(netto),
                    geschlossen_am=ende)
    glied = dict(structure_id=11, chain_id=1, sicht="konto")
    leg = dict(leg_id=101, structure_id=11, conid=3001,
               open_exec_id=ausfuehrungen[0]["exec_id"],
               close_exec_id=ausfuehrungen[1]["exec_id"], menge=1, offen_ja_nein=False)
    instrument = dict(conid=3001, multiplikator=D("100"), abwicklungsart=abwicklungsart)
    return [kette], [struktur], [glied], [leg], ausfuehrungen, [instrument]


S1 = _ausf("S1", "SELL", "4.00", D("0.80"), dt(2026, 9, 1, 15, 0))
Z1 = _ausf("Z1", "BUY", "0.00", D("0.90"), dt(2026, 9, 18, 22, 0),
           ereignistyp="assignment", schlusskurs="10.00")


def _kennzahl_kette(welt):
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = welt
    return kennzahlen_auswertung(
        ketten, strukturen, glieder, legs, ausfuehrungen, instrumente, sicht="konto"
    ).ketten[0]


def _kommission_gruppe(welt):
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = welt
    ergebnis = kommissions_attribution(
        ketten, strukturen, glieder, legs, ausfuehrungen, instrumente, sicht="konto"
    )
    return next(g for g in ergebnis.gruppen if g.dimension == "anlageklasse")


# ---------------------------------------------------------------- Kennzahlen


def test_barausgleich_zuteilung_wird_zum_schlusskurs_bewertet():
    """wirtschaftlich -583.40, IB -543.60, Effekt -39.80 (Modul-Docstring);
    mit dem alten Preis 0 wären es +316.60."""
    kette = _kennzahl_kette(_welt([S1, Z1], "barausgleich", "-600.00", "-604.00", "-4.00"))

    assert kette.netto_eur_wirtschaftlich == D("-583.40")
    assert kette.netto_eur_ib == D("-543.60")
    assert kette.waehrungseffekt_eur == D("-39.80")


def test_barausgleich_ausuebung_einer_long_option():
    """Long Call: BUY @ 4.00 Kurs 0.80, Ausübung SELL @ 0.00 Kurs 0.90,
    schlusskurs 10.00. wirtschaftlich = (-400 - 2.00) * 0.80 + (+1000 - 2.00)
    * 0.90 = -321.60 + 898.20 = 576.60. netto USD = +600 - 4 = 596.00,
    IB = 596.00 * 0.90 = 536.40, Effekt = 576.60 - 536.40 = 40.20."""
    kauf = _ausf("S1", "BUY", "4.00", D("0.80"), dt(2026, 9, 1, 15, 0))
    ausuebung = _ausf("Z1", "SELL", "0.00", D("0.90"), dt(2026, 9, 18, 22, 0),
                      ereignistyp="exercise", schlusskurs="10.00")

    kette = _kennzahl_kette(
        _welt([kauf, ausuebung], "barausgleich", "600.00", "596.00", "-4.00")
    )

    assert kette.netto_eur_wirtschaftlich == D("576.60")
    assert kette.netto_eur_ib == D("536.40")
    assert kette.waehrungseffekt_eur == D("40.20")


def test_lieferung_bleibt_beim_preis_auch_mit_gesetztem_schlusskurs():
    """Bei Lieferung steht die Prämie in der Aktienbasis (OF-24); der Option
    bleibt der Ereigniszeilenpreis 0. wirtschaftlich = 318.40 + (0 - 2.00) *
    0.90 = 318.40 - 1.80 = 316.60. netto USD = 400 - 4 = 396.00, IB = 396.00
    * 0.90 = 356.40, Effekt = 316.60 - 356.40 = -39.80."""
    kette = _kennzahl_kette(_welt([S1, Z1], "lieferung", "400.00", "396.00", "-4.00"))

    assert kette.netto_eur_wirtschaftlich == D("316.60")
    assert kette.netto_eur_ib == D("356.40")
    assert kette.waehrungseffekt_eur == D("-39.80")


def test_schlusskurs_wirkt_nur_bei_zuteilung_und_ausuebung():
    """Eine normale Schließung (ereignistyp trade) mit gesetztem schlusskurs
    wird zum preis bewertet: BUY @ 10.00 Kurs 0.90 -> (-1000 - 2.00) * 0.90 =
    -901.80; zusammen mit der Eröffnung 318.40 ergibt das -583.40."""
    schliessung = _ausf("Z1", "BUY", "10.00", D("0.90"), dt(2026, 9, 18, 22, 0),
                        schlusskurs="99.00")

    kette = _kennzahl_kette(
        _welt([S1, schliessung], "barausgleich", "-600.00", "-604.00", "-4.00")
    )

    assert kette.netto_eur_wirtschaftlich == D("-583.40")


def test_barausgleich_ohne_schlusskurs_nennt_die_ausfuehrung():
    ohne = _ausf("Z1", "BUY", "0.00", D("0.90"), dt(2026, 9, 18, 22, 0),
                 ereignistyp="assignment", schlusskurs=None)
    welt = _welt([S1, ohne], "barausgleich", "-600.00", "-604.00", "-4.00")

    with pytest.raises(ValueError, match="Z1"):
        _kennzahl_kette(welt)


# ---------------------------------------------------------------- Kommission


def test_kommission_brutto_enthaelt_den_barausgleich():
    """EUR-Brutto -580.00, Kommission -3.40, netto -583.40, Anteil
    3.40/580.00 = 0.005862.. -> 0.0059."""
    gruppe = _kommission_gruppe(
        _welt([S1, Z1], "barausgleich", "-600.00", "-604.00", "-4.00")
    )

    assert gruppe.brutto_eur == D("-580.00")
    assert gruppe.kommission_eur == D("-3.40")
    assert gruppe.netto_eur == D("-583.40")
    assert gruppe.kommissionsanteil == D("0.0059")


def test_kommission_lieferung_bleibt_beim_preis():
    """Brutto 400 * 0.80 = 320.00, Kommission -3.40, Anteil 3.40/320.00 =
    0.010625 -> 0.0106 (HALF_UP)."""
    gruppe = _kommission_gruppe(
        _welt([S1, Z1], "lieferung", "400.00", "396.00", "-4.00")
    )

    assert gruppe.brutto_eur == D("320.00")
    assert gruppe.kommissionsanteil == D("0.0106")


def test_kommission_barausgleich_ohne_schlusskurs_nennt_die_ausfuehrung():
    ohne = _ausf("Z1", "BUY", "0.00", D("0.90"), dt(2026, 9, 18, 22, 0),
                 ereignistyp="assignment", schlusskurs=None)
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = _welt(
        [S1, ohne], "barausgleich", "-600.00", "-604.00", "-4.00"
    )

    with pytest.raises(ValueError, match="Z1"):
        kommissions_attribution(
            ketten, strukturen, glieder, legs, ausfuehrungen, instrumente, sicht="konto"
        )


# ---------------------------------------------------------------- Ende zu Ende

INSTRUMENT_DB = dict(
    conid=3001, symbol="SPX   260918P5000", underlying="SPX", asset_class="OPT",
    expiry=date(2026, 9, 18), strike=D("5000"), right="P",
    multiplikator=D("100"), waehrung="USD", abwicklungsart="barausgleich",
)

AUSFUEHRUNGEN_DB = [
    dict(exec_id="S1", conid=3001, side="SELL", preis=D("4.00"), waehrung="USD",
         kommission_waehrung="USD", buchungskurs=D("0.80"),
         handelszeit=dt(2026, 9, 1, 15, 0, 0), oa_trade="10", oa_order="1"),
    dict(exec_id="Z1", conid=3001, side="BUY", preis=D("0.00"), waehrung="USD",
         kommission_waehrung="USD", buchungskurs=D("0.90"),
         handelszeit=dt(2026, 9, 18, 22, 0, 0), ereignistyp="assignment",
         schlusskurs=D("10.00")),
]


def test_ende_zu_ende_kennzahlen_lesen_schlusskurs_und_abwicklungsart(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_DB, instrumente_=[INSTRUMENT_DB])
    rebuild(migrated_db)

    ergebnis = kennzahlen_bericht(migrated_db, sicht="konto")

    assert len(ergebnis.ketten) == 1
    kette = ergebnis.ketten[0]
    assert kette.netto == D("-604.00")
    assert kette.netto_eur_wirtschaftlich == D("-583.40")
    assert kette.netto_eur_ib == D("-543.60")
    assert kette.waehrungseffekt_eur == D("-39.80")


def test_ende_zu_ende_kommission_liest_schlusskurs_und_abwicklungsart(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_DB, instrumente_=[INSTRUMENT_DB])
    rebuild(migrated_db)

    ergebnis = kommissions_bericht(migrated_db, sicht="konto")

    gruppe = next(g for g in ergebnis.gruppen if g.dimension == "anlageklasse")
    assert gruppe.brutto_eur == D("-580.00")
    assert gruppe.kommission_eur == D("-3.40")
