"""Abnahmetests für AP-06e (Analytik IV: Equity-Kurve und Drawdown).

Vertrag: auftraege/AP-06e.md. Diese Datei ist unveränderlich; jeder
Erwartungswert ist von Hand gerechnet und am jeweiligen Test begründet.

Startzustand: ROT, weil analytics.equity noch nicht existiert —
ModuleNotFoundError ist der einzige erlaubte Fehler.

Testwelt (reine Funktion, Kontosicht — Regel: Kontosicht ist für Geld
maßgeblich, Plan §5). Fünf Einzel-Leg-Strukturen (eine Kette je Struktur,
keine Rolls), EUR, Kurs 1, Multiplikator 10, Kommission -4.00 je Struktur
(zwei Ausführungen à -2.00, wie bei der Roll-Degradation):

  K1  2026-01-02  SELL 10 / BUY  0   netto  100 - 4 =  96.00
  K2  2026-01-03  SELL  9 / BUY  4   netto   50 - 4 =  46.00
  K3  2026-01-05  SELL  2 / BUY 10   netto  -80 - 4 = -84.00
  K4  2026-01-06  SELL  5 / BUY  9   netto  -40 - 4 = -44.00
  K5  2026-02-10  SELL 24 / BUY  4   netto  200 - 4 = 196.00
  K6  2026-01-04  Kursmangel (Schlusskurs fehlt) — zählt nur als kurs_fehlt
  K7  offen (nicht abgeschlossen) — geht nirgends ein

Kumuliert (netto, EUR): Tag1 96.00 | Tag2 142.00 (Hoch 142.00) |
Tag3 58.00 (DD -84.00) | Tag4 14.00 (DD -128.00, das Minimum) |
Tag5 (Feb) 210.00 (neues Hoch, DD 0.00).

Januar: 4 Strukturen, Summe 96+46-84-44 = 14.00, Durchschnitt 3.50,
Trefferquote 2/4 = 0.5000 (K1, K2 positiv). Februar: 1 Struktur,
Summe 196.00, Durchschnitt 196.00, Trefferquote 1/1 = 1.0000.
"""

from datetime import date, timedelta
from datetime import datetime as dt
from decimal import Decimal as D

import pytest

from analytics.equity import (
    EquityErgebnis,
    EquityMonat,
    EquityTag,
    als_csv,
    equity_auswertung,
)

# (chain_id, eroeffnet, preis_open, preis_close, abgeschlossen, kursmangel)
# geschlossen_am = eroeffnet + 1 Tag (wie test_degradation.py) — die
# Eröffnung steht hier also einen Tag vor dem Datum, das in der Equity-Kurve
# erscheinen soll (siehe Modulkopf: K1 schließt am 2026-01-02 usw.).
_STRUKTUREN = [
    (1, dt(2026, 1, 1, 10, 0), "10", "0", True, False),
    (2, dt(2026, 1, 2, 10, 0), "9", "4", True, False),
    (3, dt(2026, 1, 4, 10, 0), "2", "10", True, False),
    (4, dt(2026, 1, 5, 10, 0), "5", "9", True, False),
    (5, dt(2026, 2, 9, 10, 0), "24", "4", True, False),
    (6, dt(2026, 1, 3, 10, 0), "10", "9", True, True),
    (7, dt(2026, 1, 6, 10, 0), "10", "10", False, False),
]


def _ausf(exec_id, conid, side, preis, zeit, kurs):
    return dict(
        exec_id=exec_id, conid=conid, side=side, preis=D(preis), menge=1,
        waehrung="EUR", kommission=D("-2.00"), kommission_waehrung="EUR",
        buchungskurs=kurs, handelszeit=zeit, qualitaetsstufe="A",
    )


def _welt():
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = [], [], [], [], [], []
    for chain_id, beginn, po, pc, abgeschlossen, kursmangel in _STRUKTUREN:
        structure_id, conid = chain_id * 10, chain_id * 100
        offen_id, schluss_id = f"O{structure_id}", f"C{structure_id}"
        ausfuehrungen.append(_ausf(offen_id, conid, "SELL", po, beginn, D("1")))
        if abgeschlossen:
            ende = beginn + timedelta(days=1)
            kurs = None if kursmangel else D("1")
            ausfuehrungen.append(_ausf(schluss_id, conid, "BUY", pc, ende, kurs))
            brutto = (D(po) - D(pc)) * 10
            struktur = dict(brutto_pnl=brutto, kommission=D("-4.00"),
                            netto_pnl=brutto - 4, geschlossen_am=ende)
        else:
            ende = None
            struktur = dict(brutto_pnl=None, kommission=D("-2.00"),
                            netto_pnl=None, geschlossen_am=None)
        strukturen.append(dict(structure_id=structure_id, chain_id=chain_id, typ="Single",
                               waehrung="EUR", **struktur))
        glieder.append(dict(
            structure_id=structure_id, chain_id=chain_id, sicht="konto",
            sequenz=1, verknuepfungstyp="open", erkennung="auto",
        ))
        legs.append(dict(
            leg_id=structure_id, structure_id=structure_id, conid=conid,
            open_exec_id=offen_id, close_exec_id=schluss_id if abgeschlossen else None,
            menge=1, offen_ja_nein=not abgeschlossen,
        ))
        instrumente.append(dict(conid=conid, multiplikator=D("10")))
        ketten.append(dict(
            chain_id=chain_id, sicht="konto", underlying="SPX", asset_class="OPT",
            anzahl_rolls=0, beendet_am=ende,
        ))
    return ketten, strukturen, glieder, legs, ausfuehrungen, instrumente


def _auswertung(sicht="konto", nur_qualitaetsstufe_a=False):
    ketten, strukturen, glieder, legs, ausfuehrungen, instrumente = _welt()
    return equity_auswertung(
        ketten, strukturen, glieder, legs, ausfuehrungen, instrumente,
        sicht=sicht, nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )


def _tag(ergebnis, datum):
    treffer = [t for t in ergebnis.tage if t.datum == datum]
    assert len(treffer) == 1, (datum, ergebnis.tage)
    return treffer[0]


def _monat(ergebnis, monat):
    treffer = [m for m in ergebnis.monate if m.monat == monat]
    assert len(treffer) == 1, (monat, ergebnis.monate)
    return treffer[0]


# ---------------------------------------------------------------- reine Funktion


def test_nur_kontosicht_erlaubt():
    """Geld ist Kontosicht-Sache (Plan §5) — anders als die Roll-
    Degradation (AP-06d, E1), die bewusst nur Kettensicht zulässt."""
    with pytest.raises(ValueError, match="Kontosicht"):
        _auswertung(sicht="kette")


def test_tagesreihe_und_kumulierter_wert():
    e = _auswertung()
    assert _tag(e, date(2026, 1, 2)) == EquityTag(
        datum=date(2026, 1, 2), netto_eur=D("96.00"), kumuliert_eur=D("96.00"),
        drawdown_eur=D("0.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0)
    assert _tag(e, date(2026, 1, 3)) == EquityTag(
        datum=date(2026, 1, 3), netto_eur=D("46.00"), kumuliert_eur=D("142.00"),
        drawdown_eur=D("0.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0)
    # Tag 2026-01-04 hat nur K6 (Kursmangel) -> kein Beitrag zur Summe,
    # aber als eigener Tag mit kurs_fehlt=1 sichtbar (kein stilles Fehlen).
    assert _tag(e, date(2026, 1, 4)) == EquityTag(
        datum=date(2026, 1, 4), netto_eur=D("0.00"), kumuliert_eur=D("142.00"),
        drawdown_eur=D("0.00"), anzahl_strukturen=0, anzahl_strukturen_kurs_fehlt=1)
    assert _tag(e, date(2026, 1, 5)) == EquityTag(
        datum=date(2026, 1, 5), netto_eur=D("-84.00"), kumuliert_eur=D("58.00"),
        drawdown_eur=D("-84.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0)
    assert _tag(e, date(2026, 1, 6)) == EquityTag(
        datum=date(2026, 1, 6), netto_eur=D("-44.00"), kumuliert_eur=D("14.00"),
        drawdown_eur=D("-128.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0)
    assert _tag(e, date(2026, 2, 10)) == EquityTag(
        datum=date(2026, 2, 10), netto_eur=D("196.00"), kumuliert_eur=D("210.00"),
        drawdown_eur=D("0.00"), anzahl_strukturen=1, anzahl_strukturen_kurs_fehlt=0)
    # K7 (offen) erzeugt keinen Tag, kein 2026-01-07 in der Reihe.
    assert date(2026, 1, 7) not in {t.datum for t in e.tage}
    assert len(e.tage) == 6


def test_max_drawdown():
    """Minimum über die Tagesreihe: -128.00 am 2026-01-06 (Hoch 142.00 am
    2026-01-03, Tiefpunkt 14.00 am 2026-01-06)."""
    e = _auswertung()
    assert e.max_drawdown_eur == D("-128.00")
    assert e.max_drawdown_datum == date(2026, 1, 6)


def test_monatsuebersicht():
    e = _auswertung()
    assert _monat(e, "2026-01") == EquityMonat(
        monat="2026-01", anzahl_strukturen=4, summe_netto_eur=D("14.00"),
        durchschnitt_netto_eur=D("3.50"), trefferquote=D("0.5000"),
        anzahl_strukturen_kurs_fehlt=1)
    assert _monat(e, "2026-02") == EquityMonat(
        monat="2026-02", anzahl_strukturen=1, summe_netto_eur=D("196.00"),
        durchschnitt_netto_eur=D("196.00"), trefferquote=D("1.0000"),
        anzahl_strukturen_kurs_fehlt=0)
    assert len(e.monate) == 2


def test_leerer_bestand():
    leer = equity_auswertung([], [], [], [], [], [], sicht="konto")
    assert leer == EquityErgebnis(
        sicht="konto", tage=(), monate=(), max_drawdown_eur=D("0.00"), max_drawdown_datum=None)


def test_als_csv_hat_tage_und_monate_abschnitt():
    """E8-Stil (wie Degradation/Kommission): eine CSV, Kopf plus
    `tag`-Zeilen und `monat`-Zeilen, erkennbar am ersten Feld."""
    text = als_csv(_auswertung())
    zeilen = text.split("\n")
    assert zeilen[0].startswith("abschnitt;")
    tag_zeilen = [z for z in zeilen[1:] if z.startswith("tag;")]
    monat_zeilen = [z for z in zeilen[1:] if z.startswith("monat;")]
    assert len(tag_zeilen) == 6
    assert len(monat_zeilen) == 2
    # Handgerechnet: die 2026-01-06-Zeile trägt den Drawdown -128.00.
    assert any("2026-01-06" in z and "-128.00" in z for z in tag_zeilen)
