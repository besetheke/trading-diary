"""Regressionstests für die Echtlauf-Korrekturen AP-06vk (Regel 3).

Auftrag: auftraege/AP-06vr.md; Hintergrund OF-62 und auftraege/AP-06vk.md.
Diese Datei ergänzt die eingefrorene Abnahmebasis (tests/test_kennzahlen.py,
alle Mengen je Leg 1) um die zwei Echtdaten-Defekte vom 03.10.2026 — sie
ändert keine bestehende Prüfung. Alle Erwartungswerte sind von Hand gerechnet
und je Test begründet (Regel 8).

Gemessene Konvention im Echtbestand (journal.db, 03.10.2026), hier festgehalten
damit sie niemand „vereinheitlicht" und dabei Regel 3 kippt:

- ``legs.menge`` ist vorzeichenlos (21.000 von 21.000 Zeilen positiv;
  engine/matching.py speichert ``abs(menge)`` beim Lot-Bau).
- ``executions.menge`` trägt das IB-Flex-Vorzeichen: SELL negativ (16.244
  Zeilen), BUY positiv (16.231).

Testwelt (reine Funktion, Kettensicht, alle Ausführungen Stufe A):

  K1 USX (USD, mult 10) — 7184-Muster, Vorzeichen: die K1-Welt der
     Abnahmebasis, aber SELL-Ausführungen mit menge −1 wie IB Flex.
     Hand: (1200−2)·0.90 + (−800−2)·0.90 + (−600−2)·0.95 + (300−2)·0.95
     = 1078.20 − 721.80 − 571.90 + 283.10 = 67.60;
     IB = 92.00·0.95 = 87.40, Effekt −19.80. Der alte Code kippte jeden
     Verkaufscashflow: −2662.40 statt 67.60.

  K2 DAX (EUR, mult 5, Kurs 1) — 9533-Muster, Teilablösung: EINE Ausführung
     T1 (SELL 262.30, menge −40, Kommission −4.00) eröffnet zwei Strukturen
     je Leg-Anteil 10 (Roll); T3/T4 schließen je Anteil 10 (Kommission −1).
     Hand je Struktur: (262.30·10·5 − 4·10/40) + (−250·10·5 − 1) = 613.00
     bzw. (…− 249·10·5 − 1) = 663.00; Kette 1276.00 = IB, Effekt 0.00.
     Der alte Code wertete je Leg die GANZE Ausführung: +104.904 statt
     1276.00 — genau der Doppeltzählungsdefekt.

  K3 MELI (USD, mult 1, Kurs 0.86) — 9215-Muster, Assignment: Ein Leg mit
     menge 5 gegen die Ausführung M1 (SELL 172.895, menge −100, Kommission
     −2.00); M2 (BUY 0.00, Assignment-Ablösung) schließt.
     Hand: (172.895·5·1 − 2·5/100)·0.86 + 0 = 864.375·0.86 = 743.3625;
     IB = 864.375·0.86 = 743.3625, Effekt 0.00. Der alte Code nahm die
     ganze Ausführung: 14866.97.

Aggregate: summe_netto_eur = 67.60 + 1276.00 + 743.3625 = 2086.9625,
Trefferquote 3/3 = 1.0000, keine Fehler, keine Kursmängel.
"""

from datetime import datetime as dt
from decimal import Decimal as D

from analytics.kennzahlen import kennzahlen_auswertung


def _ausf(exec_id, conid, side, preis, menge, kurs, kommission, handelszeit,
          waehrung="USD"):
    return dict(
        exec_id=exec_id,
        conid=conid,
        side=side,
        preis=D(preis),
        menge=D(menge),
        waehrung=waehrung,
        kommission=D(kommission),
        kommission_waehrung=waehrung,
        buchungskurs=kurs,
        handelszeit=handelszeit,
        qualitaetsstufe="A",
    )


def _kette(chain_id, underlying, asset_class="OPT"):
    return dict(
        chain_id=chain_id,
        sicht="kette",
        underlying=underlying,
        asset_class=asset_class,
        anzahl_rolls=0,
        beendet_am=dt(2026, 1, 20, 15, 0),
    )


def _struktur(structure_id, chain_id, waehrung, brutto, kommission, netto):
    return dict(
        structure_id=structure_id,
        chain_id=chain_id,
        typ="Single",
        waehrung=waehrung,
        brutto_pnl=brutto,
        kommission=kommission,
        netto_pnl=netto,
        geschlossen_am=dt(2026, 1, 20, 15, 0),
    )


def _leg(leg_id, structure_id, conid, open_exec_id, close_exec_id, menge):
    return dict(
        leg_id=leg_id,
        structure_id=structure_id,
        conid=conid,
        open_exec_id=open_exec_id,
        close_exec_id=close_exec_id,
        menge=D(menge),
        offen_ja_nein=False,
    )


INSTRUMENTE_R = [
    dict(conid=2001, multiplikator=D("10")),
    dict(conid=2002, multiplikator=D("10")),
    dict(conid=2101, multiplikator=D("5")),
    dict(conid=2501, multiplikator=D("1")),
]

AUSFUEHRUNGEN_R = [
    # K1 — wie die Abnahmebasis K1, aber menge mit IB-Flex-Vorzeichen.
    _ausf("U1", 2001, "SELL", "120.00", "-1", D("0.90"), "-2.00",
          dt(2026, 1, 5, 15, 0)),
    _ausf("U2", 2002, "BUY", "80.00", "1", D("0.90"), "-2.00",
          dt(2026, 1, 5, 15, 0)),
    _ausf("U3", 2001, "BUY", "60.00", "1", D("0.95"), "-2.00",
          dt(2026, 1, 20, 15, 0)),
    _ausf("U4", 2002, "SELL", "30.00", "-1", D("0.95"), "-2.00",
          dt(2026, 1, 20, 15, 0)),
    # K2 — eine Ausführung (T1) auf zwei Legs verteilt (Teilablösung/Roll).
    _ausf("T1", 2101, "SELL", "262.30", "-40", D("1"), "-4.00",
          dt(2026, 1, 5, 15, 0), waehrung="EUR"),
    _ausf("T3", 2101, "BUY", "250.00", "10", D("1"), "-1.00",
          dt(2026, 1, 20, 15, 0), waehrung="EUR"),
    _ausf("T4", 2101, "BUY", "249.00", "10", D("1"), "-1.00",
          dt(2026, 1, 20, 15, 0), waehrung="EUR"),
    # K3 — Assignment: leg.menge 5 von exec.menge −100.
    _ausf("M1", 2501, "SELL", "172.895", "-100", D("0.86"), "-2.00",
          dt(2026, 2, 10, 15, 0)),
    _ausf("M2", 2501, "BUY", "0.00", "5", D("0.86"), "0.00",
          dt(2026, 2, 10, 15, 0)),
]


def _welt():
    """Liefert (ketten, strukturen, glieder, legs) in Vertragsreihenfolge."""
    ketten = [
        _kette(1, "USX"),
        _kette(2, "DAX"),
        _kette(3, "MELI", asset_class="STK"),
    ]
    strukturen = [
        # K1: brutto (120-60)*10 + (30-80)*10 = 100.00, Kommission -8.00.
        _struktur(11, 1, "USD", D("100.00"), D("-8.00"), D("92.00")),
        # K2: Anteil 10 je Struktur; brutto (262.30-250.00)*10*5 = 615.00
        # bzw. (262.30-249.00)*10*5 = 665.00, Kommission je -2.00.
        _struktur(21, 2, "EUR", D("615.00"), D("-2.00"), D("613.00")),
        _struktur(22, 2, "EUR", D("665.00"), D("-2.00"), D("663.00")),
        # K3: brutto 172.895*5 = 864.475, Kommission -2.00*5/100 = -0.10.
        _struktur(23, 3, "USD", D("864.475"), D("-0.10"), D("864.375")),
    ]
    glieder = [
        dict(structure_id=sid, chain_id=cid, sicht="kette")
        for sid, cid in ((11, 1), (21, 2), (22, 2), (23, 3))
    ]
    legs = [
        _leg(101, 11, 2001, "U1", "U3", "1"),
        _leg(102, 11, 2002, "U2", "U4", "1"),
        # Beide Strukturen teilen sich T1 (Anteil je 10 von 40).
        _leg(121, 21, 2101, "T1", "T3", "10"),
        _leg(122, 22, 2101, "T1", "T4", "10"),
        _leg(131, 23, 2501, "M1", "M2", "5"),
    ]
    return ketten, strukturen, glieder, legs


def _auswertung():
    ketten, strukturen, glieder, legs = _welt()
    return kennzahlen_auswertung(
        ketten, strukturen, glieder, legs, AUSFUEHRUNGEN_R, INSTRUMENTE_R
    )


def test_sell_menge_negativ_wie_ib_flex_kippt_keinen_cashflow():
    """Defekt 1 (Kette 7184): IB Flex trägt das Seitenvorzeichen zusätzlich
    in der Menge (SELL = −1); die Richtung kommt allein aus ``side``
    (AP-03, Regel 1 / OF-13). Hand, siehe Modul-Docstring: wirtschaftlich
    67.60 (nicht −2662.40), IB 87.40, Effekt −19.80 — exakt die Werte der
    K1-Welt der Abnahmebasis mit vorzeichenloser Menge."""
    k1 = _auswertung().ketten[0]
    assert k1.netto == D("92.00")
    assert k1.netto_eur_wirtschaftlich == D("67.60")
    assert k1.netto_eur_ib == D("87.40")
    assert k1.waehrungseffekt_eur == D("-19.80")
    assert k1.eur_kurs_fehlt == 0


def test_geteilte_ausfuehrung_zaehlt_nur_die_leg_anteile():
    """Defekt 2a (Kette 9533): Bei Teilablösung speist EINE Ausführung zwei
    Legs (hier T1, menge −40, auf zwei Strukturen mit je menge 10 verteilt);
    gewertet wird der Leg-Anteil, nie die Gesamtausführung (AP-03, Regel 5).
    Hand: Struktur 21 = 613.00, Struktur 22 = 663.00, Kette 1276.00 = IB
    (Kurs 1), Effekt 0.00 — der alte Code zählte +104.904 doppelt."""
    ergebnis = _auswertung()
    k2 = ergebnis.ketten[1]
    assert k2.netto == D("1276.00")
    assert k2.netto_eur_wirtschaftlich == D("1276.00")
    assert k2.netto_eur_ib == D("1276.00")
    assert k2.waehrungseffekt_eur == D("0.00")
    s21 = next(s for s in ergebnis.strukturen if s.structure_id == 21)
    s22 = next(s for s in ergebnis.strukturen if s.structure_id == 22)
    assert s21.netto_eur_wirtschaftlich == D("613.00")
    assert s22.netto_eur_wirtschaftlich == D("663.00")


def test_assignment_wertet_den_zugeteilten_anteil():
    """Defekt 2b (Kette 9215): Bei Assignment ist ``leg.menge`` der
    zugeordnete Anteil (5), nicht die Ausführungsmenge (100). Hand:
    (172.895·5 − 2·5/100)·0.86 = 864.375·0.86 = 743.3625; IB derselbe
    Wert (Kurs konstant), Effekt 0.00. Der alte Code wertete die ganze
    Ausführung: 14866.97."""
    k3 = _auswertung().ketten[2]
    assert k3.netto == D("864.375")
    assert k3.netto_eur_wirtschaftlich == D("743.3625")
    assert k3.netto_eur_ib == D("743.3625")
    assert k3.waehrungseffekt_eur == D("0.00")
    assert k3.eur_kurs_fehlt == 0


def test_aggregate_ohne_mangel():
    """Summe und Quote über alle drei Ketten, Hand:
    67.60 + 1276.00 + 743.3625 = 2086.9625; 3 von 3 positiv = 1.0000;
    kein Fehler, kein Kursmangel (E4 greift nicht)."""
    ergebnis = _auswertung()
    assert ergebnis.summe_netto_eur == D("2086.9625")
    assert ergebnis.trefferquote_kette == D("1.0000")
    assert ergebnis.trefferquote_struktur == D("1.0000")
    assert ergebnis.anzahl_ketten_abgeschlossen == 3
    assert ergebnis.fehler == ()
