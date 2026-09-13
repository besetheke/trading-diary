"""Abnahmetests für AP-03 (Leg-Matching), geschrieben nach §11.2 des Plans
durch das starke Modell in AP-03v — für das günstige Modell unveränderlich.

Das Modul springt still ab, solange ``engine/matching.py`` nicht existiert;
sobald es existiert, laufen alle Tests scharf. Der verbindliche Vertrag steht
in ``auftraege/AP-03.md`` unter „Vertrag an die Umsetzung"; hier steht nur,
was daraus prüfbar folgt.

**Jeder Erwartungswert ist von Hand nachgerechnet** (CLAUDE.md, Regel 8). Die
Rechnung steht als Kommentar am Wert — Stückzahl, Multiplikator, Preis,
Kommission, Zwischensumme. Kein Wert stammt aus einer Implementierung; zum
Zeitpunkt, als diese Datei entstand, gab es keine.

Die Fixtures unter ``fixtures/synthetisch/`` sind frei erfunden.
``fixtures/golden/`` wird hier nicht gelesen.

**Nachtrag AP-03vb (OF-25).** Der Golden-Lauf zeigte: Bei Barausgleich bucht
IB die Zuteilung/Ausübung mit Ereigniszeilenpreis 0.00, der tatsächliche
Abrechnungskurs steht in ``schlusskurs`` (AP-02, Regel 6). Der Vertrag
(Regel 7) verlangt seitdem: bei ``abwicklungsart='barausgleich'`` schließt
die Ereigniszeile zum ``schlusskurs``, bei ``'lieferung'`` bleibt es beim
Ereigniszeilenpreis; fehlt die Abwicklungsart, bricht der Lauf ab. Dafür ist
``ereigniszeile_kein_trade.json`` um ``abwicklungsart='lieferung'`` an conid
500011 ergänzt — sonst bräche die bestehende Ausübung jetzt am neuen Check
ab, ohne dass sich an ihrem Ergebnis etwas ändert.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

pytest.importorskip("engine.matching")

from engine.matching import bilde_legs  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "synthetisch"

# Felder, die im Fixture als Zeichenkette stehen und als Decimal gebraucht
# werden — Geldbeträge und Mengen niemals über float (CLAUDE.md, Regel 5).
DEZIMALFELDER = frozenset(
    {
        "menge",
        "preis",
        "kommission",
        "strike",
        "multiplikator",
        "tickwert",
        "faktor",
        # Kapitalmaßnahmen als Transfer (AP-03vm, OF-23): Menge auf der
        # abgebenden und der empfangenden Seite, IBs Kostenangabe für einen
        # reinen Zugang.
        "alte_menge",
        "neue_menge",
        "kosten_neu",
        "fifo_pnl_unrealisiert",
        "realisiert_brutto",
        "unrealisiert",
        "gesamt",
        # Abrechnungskurs einer Zuteilung/Ausübung bei Barausgleich (AP-03vb,
        # OF-25) — nur an dieser Sorte Ereigniszeile gefüllt.
        "schlusskurs",
    }
)
DATUMSFELDER = frozenset({"expiry", "stichtag"})
ZEITFELDER = frozenset({"handelszeit"})


def _wandeln(satz: dict) -> dict:
    """JSON-Zeichenketten in Decimal, date und datetime."""
    ergebnis = {}
    for feld, wert in satz.items():
        if wert is None:
            ergebnis[feld] = None
        elif feld in DEZIMALFELDER:
            ergebnis[feld] = Decimal(wert)
        elif feld in ZEITFELDER:
            ergebnis[feld] = datetime.strptime(wert, "%Y-%m-%d %H:%M:%S")
        elif feld in DATUMSFELDER:
            ergebnis[feld] = date.fromisoformat(wert)
        else:
            ergebnis[feld] = wert
    return ergebnis


@dataclass(frozen=True)
class Fall:
    """Ein geladenes Fixture in der Form, die ``bilde_legs`` erwartet."""

    executions: list
    instruments: dict
    kapitalmassnahmen: list
    offene_positionen: list
    broker_summe: dict


def lade(name: str) -> Fall:
    roh = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    instrumente = [_wandeln(satz) for satz in roh["instruments"]]
    return Fall(
        executions=[_wandeln(satz) for satz in roh["executions"]],
        instruments={satz["conid"]: satz for satz in instrumente},
        kapitalmassnahmen=[_wandeln(satz) for satz in roh.get("kapitalmassnahmen", [])],
        offene_positionen=[_wandeln(satz) for satz in roh.get("offene_positionen", [])],
        broker_summe={
            klasse: _wandeln(werte) for klasse, werte in roh.get("broker_summe", {}).items()
        },
    )


def bilde(name: str):
    fall = lade(name)
    return bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)


def legs_von(ergebnis, conid=None):
    if conid is None:
        return list(ergebnis.legs)
    return [leg for leg in ergebnis.legs if leg.conid == conid]


def geschlossene(legs):
    return [leg for leg in legs if not leg.offen_ja_nein]


def offene(legs):
    return [leg for leg in legs if leg.offen_ja_nein]


def leg_von(ergebnis, open_exec_id, close_exec_id=None):
    """Genau das Leg zu diesem Paar aus Eröffnung und Schließung."""
    treffer = [
        leg
        for leg in ergebnis.legs
        if leg.open_exec_id == open_exec_id and leg.close_exec_id == close_exec_id
    ]
    assert len(treffer) == 1, (
        f"erwartet genau ein Leg {open_exec_id}->{close_exec_id}, gefunden: {len(treffer)}"
    )
    return treffer[0]


def summe(werte):
    return sum(werte, Decimal("0"))


# ---------------------------------------------------------------------------
# Vertrag und Grundform
# ---------------------------------------------------------------------------


def test_ergebnis_traegt_legs_und_nicht_gematchte():
    ergebnis = bilde("teilschliessung_restmenge")
    assert hasattr(ergebnis, "legs")
    assert hasattr(ergebnis, "nicht_gematcht")
    assert list(ergebnis.nicht_gematcht) == []


def test_leere_eingabe_liefert_leeres_ergebnis():
    ergebnis = bilde_legs([], {}, [])
    assert list(ergebnis.legs) == []
    assert list(ergebnis.nicht_gematcht) == []


def test_matching_methode_steht_auf_jedem_leg():
    ergebnis = bilde("teilschliessung_restmenge")
    assert {leg.matching_methode for leg in ergebnis.legs} == {"fifo"}


def test_ergebnis_ist_unabhaengig_von_der_eingabereihenfolge():
    """P2: gleiche Eingabe, bitgleiche Ausgabe — auch wenn die Ausführungen
    in anderer Reihenfolge hereinkommen. Maßgeblich ist die Handelszeit."""
    fall = lade("teilschliessung_restmenge")
    vorwaerts = bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)
    rueckwaerts = bilde_legs(
        list(reversed(fall.executions)), fall.instruments, fall.kapitalmassnahmen
    )
    assert list(vorwaerts.legs) == list(rueckwaerts.legs)


def test_zweiter_aufruf_liefert_dasselbe_ergebnis():
    """P2: deterministisch, kein Zustand zwischen den Aufrufen."""
    assert list(bilde("summenprobe").legs) == list(bilde("summenprobe").legs)


def test_alle_geldbetraege_sind_decimal():
    """CLAUDE.md, Regel 5: niemals float."""
    for leg in bilde("summenprobe").legs:
        assert isinstance(leg.menge, Decimal)
        assert isinstance(leg.kommission_gesamt, Decimal)
        if leg.brutto_pnl is not None:
            assert isinstance(leg.brutto_pnl, Decimal)


def test_offen_und_close_exec_id_bleiben_konsistent():
    """AP-03.md: ``offen_ja_nein`` und ``close_exec_id`` müssen zueinander
    passen — ein offenes Leg hat keine Schließung und kein realisiertes
    Ergebnis, ein geschlossenes hat beides."""
    for name in ("teilschliessung_restmenge", "positionsumkehr", "summenprobe"):
        for leg in bilde(name).legs:
            if leg.offen_ja_nein:
                assert leg.close_exec_id is None, name
                assert leg.brutto_pnl is None, name
            else:
                assert leg.close_exec_id is not None, name
                assert leg.brutto_pnl is not None, name


def test_jedes_leg_traegt_eine_positive_menge():
    for name in ("teilschliessung_restmenge", "positionsumkehr", "aktiensplit"):
        for leg in bilde(name).legs:
            assert leg.menge > 0, f"{name}: {leg}"


# ---------------------------------------------------------------------------
# Teilschließung mit Restmenge (Pflichtfall)
#
# T1 BUY 10 @ 2.00, Kommission -10.00
# T2 SELL 4 @ 3.00, Kommission  -4.00
# T3 SELL 3 @ 2.50, Kommission  -3.00      Multiplikator 100
# ---------------------------------------------------------------------------


def test_teilschliessung_erzeugt_drei_legs():
    legs = legs_von(bilde("teilschliessung_restmenge"))
    assert len(legs) == 3
    assert len(geschlossene(legs)) == 2
    assert len(offene(legs)) == 1


def test_teilschliessung_erste_schliessung_brutto():
    # (3.00 - 2.00) * 4 Kontrakte * 100 = 1.00 * 400 = 400.00
    leg = leg_von(bilde("teilschliessung_restmenge"), "T1", "T2")
    assert leg.menge == Decimal("4")
    assert leg.brutto_pnl == Decimal("400.00")


def test_teilschliessung_zweite_schliessung_brutto():
    # (2.50 - 2.00) * 3 Kontrakte * 100 = 0.50 * 300 = 150.00
    leg = leg_von(bilde("teilschliessung_restmenge"), "T1", "T3")
    assert leg.menge == Decimal("3")
    assert leg.brutto_pnl == Decimal("150.00")


def test_teilschliessung_restmenge_bleibt_offen():
    # 10 eröffnet - 4 - 3 geschlossen = 3 offen
    leg = leg_von(bilde("teilschliessung_restmenge"), "T1", None)
    assert leg.menge == Decimal("3")
    assert leg.offen_ja_nein is True
    assert leg.brutto_pnl is None


def test_teilschliessung_kommission_erstes_leg():
    # Eröffnung: -10.00 * 4/10 = -4.00
    # Schließung: -4.00 * 4/4  = -4.00
    # zusammen                 = -8.00
    assert leg_von(bilde("teilschliessung_restmenge"), "T1", "T2").kommission_gesamt == Decimal(
        "-8.00"
    )


def test_teilschliessung_kommission_zweites_leg():
    # Eröffnung: -10.00 * 3/10 = -3.00
    # Schließung: -3.00 * 3/3  = -3.00
    # zusammen                 = -6.00
    assert leg_von(bilde("teilschliessung_restmenge"), "T1", "T3").kommission_gesamt == Decimal(
        "-6.00"
    )


def test_teilschliessung_kommission_offenes_leg():
    # Rest der Eröffnungskommission: -10.00 - (-4.00) - (-3.00) = -3.00
    assert leg_von(bilde("teilschliessung_restmenge"), "T1", None).kommission_gesamt == Decimal(
        "-3.00"
    )


def test_teilschliessung_kommissionssumme_bleibt_erhalten():
    # -10.00 + -4.00 + -3.00 = -17.00; keine Kommission darf verschwinden
    # oder doppelt gezählt werden.
    legs = legs_von(bilde("teilschliessung_restmenge"))
    assert summe(leg.kommission_gesamt for leg in legs) == Decimal("-17.00")


# ---------------------------------------------------------------------------
# Kommissionsaufteilung über drei Teilschließungen (Pflichtfall)
#
# K1 BUY 3 @ 1.00, Kommission -1.00   -> -1.00 / 3 = -0.3333... je Kontrakt
# K2 SELL 1 @ 1.50, Kommission -0.35
# K3 SELL 1 @ 1.60, Kommission -0.35
# K4 SELL 1 @ 1.70, Kommission -0.35        Multiplikator 100
# ---------------------------------------------------------------------------


def test_kommissionsaufteilung_erzeugt_drei_geschlossene_legs():
    legs = legs_von(bilde("kommission_drei_teilschliessungen"))
    assert len(legs) == 3
    assert offene(legs) == []


def test_kommissionsaufteilung_brutto_je_leg():
    ergebnis = bilde("kommission_drei_teilschliessungen")
    # (1.50 - 1.00) * 1 * 100 = 50.00
    assert leg_von(ergebnis, "K1", "K2").brutto_pnl == Decimal("50.00")
    # (1.60 - 1.00) * 1 * 100 = 60.00
    assert leg_von(ergebnis, "K1", "K3").brutto_pnl == Decimal("60.00")
    # (1.70 - 1.00) * 1 * 100 = 70.00
    assert leg_von(ergebnis, "K1", "K4").brutto_pnl == Decimal("70.00")


def test_kommissionsaufteilung_erste_beiden_anteile_abgerundet():
    # -1.00 * 1/3 = -0.333... -> auf den Cent -0.33, dazu je -0.35 der
    # Schließung: -0.33 + -0.35 = -0.68
    ergebnis = bilde("kommission_drei_teilschliessungen")
    assert leg_von(ergebnis, "K1", "K2").kommission_gesamt == Decimal("-0.68")
    assert leg_von(ergebnis, "K1", "K3").kommission_gesamt == Decimal("-0.68")


def test_kommissionsaufteilung_rundungsrest_faellt_auf_die_letzte_teilmenge():
    # Rest der Eröffnung: -1.00 - (-0.33) - (-0.33) = -0.34
    # dazu die Schließung -0.35 -> -0.69
    leg = leg_von(bilde("kommission_drei_teilschliessungen"), "K1", "K4")
    assert leg.kommission_gesamt == Decimal("-0.69")


def test_kommissionsaufteilung_summe_ist_zentgenau():
    # -1.00 + 3 * -0.35 = -1.00 + -1.05 = -2.05
    legs = legs_von(bilde("kommission_drei_teilschliessungen"))
    assert summe(leg.kommission_gesamt for leg in legs) == Decimal("-2.05")


def test_kommissionsaufteilung_bruttosumme():
    # 50.00 + 60.00 + 70.00 = 180.00
    legs = legs_von(bilde("kommission_drei_teilschliessungen"))
    assert summe(leg.brutto_pnl for leg in legs) == Decimal("180.00")


# ---------------------------------------------------------------------------
# Aktiensplit vor dem Matching (Pflichtfall, Semantik korrigiert in AP-03vm,
# OF-23: eine Kapitalmaßnahme ist ein Transfer auf eine neue conid, kein
# Faktor auf derselben — gemessen an allen 10 Maßnahmen der Golden-Exporte,
# ausnahmslos).
#
# AKT1 (500003 -> 500030, 2 neue je 1 altes Stück): S1 BUY 100 @ 40.00
#      (-1.00) am 01.02. auf 500003, vor dem Stichtag (10.03.) — wird beim
#      Transfer zu 200 Stück @ 20.00 auf 500030. S2 SELL 150 @ 21.00 (-1.50)
#      am 15.03. liegt schon auf der neuen conid 500030, wie im echten
#      Export: nach der Maßnahme wird die neue conid gehandelt.
# AKT2 (500009 -> 500032): S3 BUY 10 @ 50.00 GENAU am Stichtag — eine
#      Ausführung am Stichtag selbst gilt bereits zu neuen Konditionen und
#      wird deshalb NICHT verschoben; S3/S4 bleiben auf 500009.
# ---------------------------------------------------------------------------


def test_split_passt_die_eroeffnung_auf_menge_und_preis_an():
    # Ohne Preisanpassung wäre das Ergebnis (21.00 - 40.00) * 150 = -2850.00,
    # ohne Mengenanpassung ließen sich nur 100 der 150 Stück schließen.
    # Richtig: (21.00 - 20.00) * 150 Stück * 1 = 150.00 — auf der neuen conid.
    leg = leg_von(bilde("aktiensplit"), "S1", "S2")
    assert leg.conid == 500030
    assert leg.menge == Decimal("150")
    assert leg.brutto_pnl == Decimal("150.00")


def test_split_erhoeht_die_offene_restmenge():
    # 200 transferierte Stück - 150 verkauft = 50 offen, auf 500030.
    leg = leg_von(bilde("aktiensplit"), "S1", None)
    assert leg.conid == 500030
    assert leg.menge == Decimal("50")
    assert leg.offen_ja_nein is True


def test_split_kommission_folgt_der_angepassten_menge():
    # Eröffnung: -1.00 * 150/200 = -0.75, Schließung -1.50 -> -2.25
    assert leg_von(bilde("aktiensplit"), "S1", "S2").kommission_gesamt == Decimal("-2.25")
    # Rest der Eröffnung: -1.00 - (-0.75) = -0.25
    assert leg_von(bilde("aktiensplit"), "S1", None).kommission_gesamt == Decimal("-0.25")


def test_split_wirkt_nicht_auf_ausfuehrungen_ab_dem_stichtag():
    # S3 liegt genau auf dem Stichtag von AKT2 und gilt bereits zu neuen
    # Konditionen — kein Transfer nach 500032, S3/S4 bleiben auf 500009.
    # Richtig: (55.00 - 50.00) * 10 * 1 = 50.00, nichts bleibt offen.
    # Fälschlich verschoben wären es 20 Stück zu 25.00 auf 500032, also
    # (55.00 - 25.00) * 10 = 300.00 und 10 Stück offen dort.
    legs_alt = legs_von(bilde("aktiensplit"), conid=500009)
    legs_neu = legs_von(bilde("aktiensplit"), conid=500032)
    assert len(legs_alt) == 1
    assert legs_neu == []
    assert legs_alt[0].brutto_pnl == Decimal("50.00")
    assert legs_alt[0].kommission_gesamt == Decimal("-2.00")


def test_split_laesst_die_kommissionssumme_unveraendert():
    # 500030 (Ziel des Transfers): -1.00 + -1.50 = -2.50
    # 500009 (unverschoben): -1.00 + -1.00 = -2.00
    ergebnis = bilde("aktiensplit")
    assert summe(
        leg.kommission_gesamt for leg in legs_von(ergebnis, conid=500030)
    ) == Decimal("-2.50")
    assert summe(
        leg.kommission_gesamt for leg in legs_von(ergebnis, conid=500009)
    ) == Decimal("-2.00")


# ---------------------------------------------------------------------------
# Futures mit Tickwert (Pflichtfall)
#
# conid 500004: Multiplikator 5, Tickwert 25 — beide gesetzt und verschieden.
#               Preisfaktor ist der Multiplikator; der Tickwert geht nicht in
#               den P&L ein (Vertrag Regel 3, OF-14, korrigiert in AP-03vk).
# conid 500005: Multiplikator 20, kein Tickwert.
# ---------------------------------------------------------------------------


def test_futures_tickwert_geht_nicht_in_den_pnl_ein():
    # Preisfaktor ist der Multiplikator, der gesetzte Tickwert 25 bleibt außen vor:
    # (18010.0 - 18000.0) * 2 Kontrakte * 5 = 10 * 10 = 100.00
    leg = leg_von(bilde("futures_tickwert"), "F1", "F2")
    assert leg.brutto_pnl == Decimal("100.00")


def test_futures_tickwert_als_faktor_waere_das_falsche_ergebnis():
    # Gegenprobe: mit dem Tickwert 25 als Faktor wären es (10.0 * 2 * 25) = 500.00.
    leg = leg_von(bilde("futures_tickwert"), "F1", "F2")
    assert leg.brutto_pnl != Decimal("500.00")


def test_futures_ohne_tickwert_gilt_der_multiplikator():
    # (100.5 - 100.0) * 1 Kontrakt * 20 = 0.5 * 20 = 10.00
    leg = leg_von(bilde("futures_tickwert"), "F3", "F4")
    assert leg.brutto_pnl == Decimal("10.00")


def test_futures_kommission_wird_voll_zugeordnet():
    ergebnis = bilde("futures_tickwert")
    # -4.00 Eröffnung + -4.00 Schließung
    assert leg_von(ergebnis, "F1", "F2").kommission_gesamt == Decimal("-8.00")
    # -2.00 Eröffnung + -2.00 Schließung
    assert leg_von(ergebnis, "F3", "F4").kommission_gesamt == Decimal("-4.00")


def test_futures_beide_positionen_sind_geschlossen():
    assert offene(legs_von(bilde("futures_tickwert"))) == []


def test_fehlender_multiplikator_bricht_ab():
    """Vertrag Regel 3: ohne Multiplikator kein Preisfaktor — der Lauf endet mit
    ValueError unter Nennung des conid. Der gesetzte Tickwert 25 darf nicht
    einspringen, denn er geht nicht in den P&L ein (OF-14)."""
    fall = lade("futures_tickwert")
    instrumente = {conid: dict(satz) for conid, satz in fall.instruments.items()}
    instrumente[500004]["multiplikator"] = None
    with pytest.raises(ValueError) as fehler:
        bilde_legs(fall.executions, instrumente, fall.kapitalmassnahmen)
    assert "500004" in str(fehler.value)


# ---------------------------------------------------------------------------
# Offene Position am Periodenende und Short-Rechnung (Pflichtfall)
#
# conid 500006: O1 SELL 5 @ 3.00 (-5.00), O2 BUY 2 @ 1.00 (-2.00)
# conid 500010: O3 SELL 1 @ 2.00 (-1.00), O4 BUY 1 @ 3.50 (-1.00)
# ---------------------------------------------------------------------------


def test_short_teilschliessung_brutto():
    # Short verdient bei fallendem Preis:
    # (3.00 Verkauf - 1.00 Rückkauf) * 2 Kontrakte * 100 = 2.00 * 200 = 400.00
    leg = leg_von(bilde("offene_position_periodenende"), "O1", "O2")
    assert leg.menge == Decimal("2")
    assert leg.brutto_pnl == Decimal("400.00")


def test_short_restmenge_bleibt_offen():
    # 5 verkauft - 2 zurückgekauft = 3 offen
    leg = leg_von(bilde("offene_position_periodenende"), "O1", None)
    assert leg.menge == Decimal("3")
    assert leg.offen_ja_nein is True
    assert leg.brutto_pnl is None


def test_short_kommission_teilt_sich_nach_menge():
    ergebnis = bilde("offene_position_periodenende")
    # geschlossen: -5.00 * 2/5 = -2.00, dazu -2.00 der Schließung = -4.00
    assert leg_von(ergebnis, "O1", "O2").kommission_gesamt == Decimal("-4.00")
    # offen: Rest -5.00 - (-2.00) = -3.00
    assert leg_von(ergebnis, "O1", None).kommission_gesamt == Decimal("-3.00")


def test_short_bei_steigendem_preis_ist_ein_verlust():
    # (2.00 Verkauf - 3.50 Rückkauf) * 1 * 100 = -1.50 * 100 = -150.00
    leg = leg_von(bilde("offene_position_periodenende"), "O3", "O4")
    assert leg.brutto_pnl == Decimal("-150.00")


def test_offene_legs_tragen_kein_realisiertes_ergebnis():
    for leg in offene(legs_von(bilde("offene_position_periodenende"))):
        assert leg.brutto_pnl is None
        assert leg.close_exec_id is None


# ---------------------------------------------------------------------------
# Ereigniszeilen (Fehlerpfad, Plan §1.4 und P7)
# ---------------------------------------------------------------------------


def test_verfall_schliesst_das_leg_zu_null():
    # Short zu 2.00 verfällt wertlos: (2.00 - 0.00) * 1 * 100 = 200.00
    leg = leg_von(bilde("ereigniszeile_kein_trade"), "E1", "E2")
    assert leg.brutto_pnl == Decimal("200.00")
    assert leg.offen_ja_nein is False


def test_verfall_traegt_nur_die_kommission_der_eroeffnung():
    # -1.00 Eröffnung + 0.00 Verfall = -1.00
    assert leg_von(bilde("ereigniszeile_kein_trade"), "E1", "E2").kommission_gesamt == Decimal(
        "-1.00"
    )


def test_ausuebung_schliesst_das_leg():
    # Long zu 4.00, Ausübung zu 6.00: (6.00 - 4.00) * 1 * 100 = 200.00
    leg = leg_von(bilde("ereigniszeile_kein_trade"), "E5", "E6")
    assert leg.brutto_pnl == Decimal("200.00")
    assert leg.offen_ja_nein is False


def test_unbekannter_ereignistyp_wird_nicht_gematcht():
    """OF-07: Der Ereigniscode P ist fachlich nicht klassifiziert. Er darf
    weder still als Schließung gebucht noch still verworfen werden."""
    ergebnis = bilde("ereigniszeile_kein_trade")
    nicht_gematcht = {eintrag.exec_id for eintrag in ergebnis.nicht_gematcht}
    assert nicht_gematcht == {"E4"}


def test_nicht_gematchte_zeile_nennt_einen_grund():
    ergebnis = bilde("ereigniszeile_kein_trade")
    eintrag = next(e for e in ergebnis.nicht_gematcht if e.exec_id == "E4")
    assert eintrag.grund, "der Grund muss benannt sein, nicht bloß die Zeile"
    assert "unbekannt" in eintrag.grund


def test_position_hinter_einer_nicht_gematchten_zeile_bleibt_offen():
    # E3 kauft 1 Kontrakt; E4 ist nicht zuordenbar und schließt daher nichts.
    legs = legs_von(bilde("ereigniszeile_kein_trade"), conid=500008)
    assert len(legs) == 1
    assert legs[0].open_exec_id == "E3"
    assert legs[0].offen_ja_nein is True
    assert legs[0].menge == Decimal("1")
    assert legs[0].kommission_gesamt == Decimal("-1.00")


# ---------------------------------------------------------------------------
# FIFO-Reihenfolge und Positionsumkehr
# ---------------------------------------------------------------------------


def test_fifo_schliesst_das_aelteste_los_zuerst():
    # G1 BUY 10 @ 10.00, G2 BUY 10 @ 20.00, G3 SELL 10 @ 30.00
    # FIFO: (30.00 - 10.00) * 10 * 1 = 200.00
    # LIFO wäre (30.00 - 20.00) * 10 = 100.00 und damit falsch.
    leg = leg_von(bilde("fifo_reihenfolge"), "G1", "G3")
    assert leg.brutto_pnl == Decimal("200.00")


def test_fifo_laesst_das_juengere_los_offen():
    leg = leg_von(bilde("fifo_reihenfolge"), "G2", None)
    assert leg.menge == Decimal("10")
    assert leg.offen_ja_nein is True


def test_positionsumkehr_schliesst_und_eroeffnet_zugleich():
    # P1 BUY 10 @ 10.00, P2 SELL 15 @ 12.00:
    # 10 Stück schließen, 5 Stück eröffnen eine Short-Position.
    ergebnis = bilde("positionsumkehr")
    assert len(legs_von(ergebnis)) == 2
    geschlossen = leg_von(ergebnis, "P1", "P2")
    # (12.00 - 10.00) * 10 * 1 = 20.00
    assert geschlossen.brutto_pnl == Decimal("20.00")
    assert geschlossen.menge == Decimal("10")


def test_positionsumkehr_ueberhang_wird_zur_neuen_offenen_position():
    leg = leg_von(bilde("positionsumkehr"), "P2", None)
    assert leg.menge == Decimal("5")
    assert leg.offen_ja_nein is True


def test_positionsumkehr_teilt_die_kommission_der_umkehrenden_ausfuehrung():
    ergebnis = bilde("positionsumkehr")
    # schließender Anteil: -1.50 * 10/15 = -1.00, dazu -1.00 der Eröffnung P1
    assert leg_von(ergebnis, "P1", "P2").kommission_gesamt == Decimal("-2.00")
    # eröffnender Anteil: Rest -1.50 - (-1.00) = -0.50
    assert leg_von(ergebnis, "P2", None).kommission_gesamt == Decimal("-0.50")


# ---------------------------------------------------------------------------
# Fehlerpfad: fehlende Instrumentenzeile
# ---------------------------------------------------------------------------


def test_fehlende_instrumentenzeile_bricht_ab():
    fall = lade("fehlende_instrumentenzeile")
    with pytest.raises(ValueError):
        bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)


def test_fehlende_instrumentenzeile_nennt_den_conid():
    fall = lade("fehlende_instrumentenzeile")
    with pytest.raises(ValueError) as fehler:
        bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)
    assert "599999" in str(fehler.value)


def test_fehlende_instrumentenzeile_erfindet_keinen_multiplikator():
    """Kein stiller Standardwert 1 — der Lauf endet, statt zu raten."""
    fall = lade("fehlende_instrumentenzeile")
    with pytest.raises(ValueError):
        bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)


# ---------------------------------------------------------------------------
# Summenprobe (Abnahmekriterium AP-03)
#
# OPT 510001: A1 BUY 2 @ 1.00 (-2.00), A2 SELL 2 @ 1.75 (-2.00), Mult. 100
# FUT 510002: B1 BUY 1 @ 200.00 (-3.00), B2 SELL 1 @ 198.00 (-3.00), Mult. 50
# STK 510003: C1 BUY 100 @ 10.00 (-1.00), C2 SELL 40 @ 12.00 (-1.00), Mult. 1
#             60 Stück bleiben offen, unrealisiert +30.00 laut Broker
# ---------------------------------------------------------------------------


def _je_anlageklasse(ergebnis, fall, klasse):
    conids = {
        conid for conid, satz in fall.instruments.items() if satz["asset_class"] == klasse
    }
    return [leg for leg in ergebnis.legs if leg.conid in conids]


def test_summenprobe_optionen_auf_den_cent():
    fall = lade("summenprobe")
    ergebnis = bilde("summenprobe")
    legs = _je_anlageklasse(ergebnis, fall, "OPT")
    erwartet = fall.broker_summe["OPT"]
    # (1.75 - 1.00) * 2 * 100 = 0.75 * 200 = 150.00
    assert summe(leg.brutto_pnl for leg in geschlossene(legs)) == erwartet["realisiert_brutto"]
    # -2.00 + -2.00 = -4.00
    assert summe(leg.kommission_gesamt for leg in legs) == erwartet["kommission"]


def test_summenprobe_futures_auf_den_cent():
    fall = lade("summenprobe")
    ergebnis = bilde("summenprobe")
    legs = _je_anlageklasse(ergebnis, fall, "FUT")
    erwartet = fall.broker_summe["FUT"]
    # (198.00 - 200.00) * 1 * 50 = -2.00 * 50 = -100.00
    assert summe(leg.brutto_pnl for leg in geschlossene(legs)) == erwartet["realisiert_brutto"]
    # -3.00 + -3.00 = -6.00
    assert summe(leg.kommission_gesamt for leg in legs) == erwartet["kommission"]


def test_summenprobe_aktien_auf_den_cent():
    fall = lade("summenprobe")
    ergebnis = bilde("summenprobe")
    legs = _je_anlageklasse(ergebnis, fall, "STK")
    erwartet = fall.broker_summe["STK"]
    # (12.00 - 10.00) * 40 * 1 = 80.00
    assert summe(leg.brutto_pnl for leg in geschlossene(legs)) == erwartet["realisiert_brutto"]
    # geschlossen: -1.00 * 40/100 = -0.40 plus -1.00; offen: Rest -0.60
    # zusammen -2.00 — jede gebuchte Kommission genau einmal.
    assert summe(leg.kommission_gesamt for leg in legs) == erwartet["kommission"]


def test_summenprobe_offene_aktienposition_traegt_die_restmenge():
    # 100 gekauft - 40 verkauft = 60 offen, wie vom Broker ausgewiesen
    leg = leg_von(bilde("summenprobe"), "C1", None)
    assert leg.menge == lade("summenprobe").offene_positionen[0]["menge"]


def test_summenprobe_gesamtrechnung_je_anlageklasse():
    """Realisiert brutto + Kommission + unrealisiert = ausgewiesene Summe.
    OPT: 150.00 - 4.00 + 0.00 = 146.00
    FUT: -100.00 - 6.00 + 0.00 = -106.00
    STK: 80.00 - 2.00 + 30.00 = 108.00
    """
    fall = lade("summenprobe")
    ergebnis = bilde("summenprobe")
    for klasse in ("OPT", "FUT", "STK"):
        legs = _je_anlageklasse(ergebnis, fall, klasse)
        erwartet = fall.broker_summe[klasse]
        gerechnet = (
            summe(leg.brutto_pnl for leg in geschlossene(legs))
            + summe(leg.kommission_gesamt for leg in legs)
            + erwartet["unrealisiert"]
        )
        assert gerechnet == erwartet["gesamt"], klasse


def test_summenprobe_anlageklassen_werden_nicht_vermischt():
    """Getrennt geprüft heißt getrennt gerechnet: die drei Klassen dürfen
    sich nicht gegenseitig ausgleichen."""
    fall = lade("summenprobe")
    ergebnis = bilde("summenprobe")
    conids = {
        klasse: {c for c, s in fall.instruments.items() if s["asset_class"] == klasse}
        for klasse in ("OPT", "FUT", "STK")
    }
    assert conids["OPT"] & conids["FUT"] == set()
    verteilt = [len(_je_anlageklasse(ergebnis, fall, k)) for k in ("OPT", "FUT", "STK")]
    assert verteilt == [1, 1, 2]


# ---------------------------------------------------------------------------
# Kommissionen mit mehr als zwei Nachkommastellen (Nachtrag AP-03vn, OF-18)
#
# IB bucht Kommissionen meist mit mehr als zwei Nachkommastellen (gemessen:
# 61 bis 78 % der Ausführungen). Die gebuchte Kommission wird nie gerundet: nur
# die Anteile vor der letzten Teilmenge gehen auf den Cent, die letzte trägt
# den exakten Rest (Vertrag Regel 5).
#
# conid 520001: N1 BUY 1 @ 2.00 (-1.0472), N2 SELL 1 @ 2.50 (-1.0472)
# conid 520002: M1 BUY 3 @ 10.00 (-2.3456), M2 SELL 1 @ 11.00 (-0.35),
#               M3 SELL 2 @ 12.00 (-0.35)
# conid 520003: R1 SELL 5 @ 4.00 (-1.2345), R2 BUY 2 @ 3.00 (-0.5555)
# ---------------------------------------------------------------------------


def test_ungeteilte_gebrochene_kommission_bleibt_exakt():
    # Beide Ausführungen ungeteilt, also keine Rundung:
    # -1.0472 + -1.0472 = -2.0944 (gerundet wären es -1.05 + -1.05 = -2.10)
    leg = leg_von(bilde("kommission_nachkommastellen"), "N1", "N2")
    assert leg.kommission_gesamt == Decimal("-2.0944")


def test_gebrochene_kommission_letzte_teilmenge_traegt_den_exakten_rest():
    ergebnis = bilde("kommission_nachkommastellen")
    # M1: -2.3456 * 1/3 = -0.781866... -> -0.78; dazu M2 ungeteilt -0.35 = -1.13
    assert leg_von(ergebnis, "M1", "M2").kommission_gesamt == Decimal("-1.13")
    # Rest von M1: -2.3456 - (-0.78) = -1.5656 (nicht -1.57); dazu M3 -0.35 = -1.9156
    assert leg_von(ergebnis, "M1", "M3").kommission_gesamt == Decimal("-1.9156")
    # R1: -1.2345 * 2/5 = -0.4938 -> -0.49; dazu R2 ungeteilt -0.5555 = -1.0455
    assert leg_von(ergebnis, "R1", "R2").kommission_gesamt == Decimal("-1.0455")
    # offener Rest von R1: -1.2345 - (-0.49) = -0.7445 (nicht -0.74)
    assert leg_von(ergebnis, "R1", None).kommission_gesamt == Decimal("-0.7445")


def test_gebrochene_kommission_summe_je_conid_ist_exakt():
    """Die Summe allein genügt nicht als Beleg: bei conid 520003 ergäben die
    gerundeten Anteile -1.05 + -0.74 zufällig ebenfalls -1.79. Deshalb prüft
    der Test davor jedes Leg einzeln."""
    ergebnis = bilde("kommission_nachkommastellen")
    erwartet = {
        520001: Decimal("-2.0944"),  # -1.0472 + -1.0472
        520002: Decimal("-3.0456"),  # -2.3456 + -0.35 + -0.35
        520003: Decimal("-1.7900"),  # -1.2345 + -0.5555
    }
    for conid, wert in erwartet.items():
        gerechnet = summe(leg.kommission_gesamt for leg in legs_von(ergebnis, conid=conid))
        assert gerechnet == wert, conid


# ---------------------------------------------------------------------------
# Barausgleich bei Zuteilung und Ausübung (Nachtrag AP-03vb, OF-25)
#
# IB bucht eine Zuteilung oder Ausübung, die in bar abgerechnet wird
# (abwicklungsart='barausgleich'), mit dem Ereigniszeilenpreis 0.00 — der
# tatsächliche Abrechnungskurs steht in schlusskurs (AP-02, Regel 6). Bei
# physischer Lieferung (abwicklungsart='lieferung') bleibt es beim
# Ereigniszeilenpreis; die Prämie steht dort in der Aktienbasis, nicht an
# der Option (OF-24) — ein gesetzter schlusskurs muss ignoriert werden.
#
# conid 500020 (barausgleich): BA1 BUY 1 @ 5.00 (-1.00), BA2 assignment
#               preis 0.00, schlusskurs 8.50
# conid 500021 (lieferung, Kontrollgruppe): BA3 SELL 1 @ 6.00 (-1.00), BA4
#               assignment preis 0.00, schlusskurs 9.75 (muss ignoriert werden)
# Multiplikator 100 in beiden Fällen.
# ---------------------------------------------------------------------------


def test_barausgleich_schliesst_zum_schlusskurs():
    # (8.50 - 5.00) * 1 * 100 * Richtung Eröffnung (+1, long) = 350.00
    leg = leg_von(bilde("barausgleich"), "BA1", "BA2")
    assert leg.brutto_pnl == Decimal("350.00")


def test_barausgleich_ereigniszeilenpreis_waere_das_falsche_ergebnis():
    # Gegenprobe: mit dem Ereigniszeilenpreis 0.00 statt schlusskurs wären es
    # (0.00 - 5.00) * 1 * 100 = -500.00.
    leg = leg_von(bilde("barausgleich"), "BA1", "BA2")
    assert leg.brutto_pnl != Decimal("-500.00")


def test_lieferung_ignoriert_gesetzten_schlusskurs():
    # abwicklungsart='lieferung': maßgeblich bleibt der Ereigniszeilenpreis
    # 0.00, obwohl schlusskurs 9.75 gesetzt ist.
    # (0.00 - 6.00) * 1 * 100 * Richtung Eröffnung (-1, short) = 600.00
    leg = leg_von(bilde("barausgleich"), "BA3", "BA4")
    assert leg.brutto_pnl == Decimal("600.00")
    # Gegenprobe: mit schlusskurs 9.75 statt 0.00 wären es
    # (9.75 - 6.00) * 1 * 100 * -1 = -375.00 — anderes Vorzeichen, anderer Betrag.
    assert leg.brutto_pnl != Decimal("-375.00")


def test_fehlende_abwicklungsart_bei_ausuebung_bricht_ab():
    """OF-25: Ohne abwicklungsart ist Barausgleich gegen Lieferung nicht
    entscheidbar — kein Standardwert, der Lauf bricht ab."""
    fall = lade("barausgleich_fehlende_abwicklungsart")
    with pytest.raises(ValueError) as fehler:
        bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)
    assert "500022" in str(fehler.value)


def test_barausgleich_ohne_schlusskurs_bricht_ab():
    """OF-25: abwicklungsart='barausgleich', aber kein schlusskurs an der
    Ausübungszeile — kein Ausweichen auf den Ereigniszeilenpreis 0.00."""
    fall = lade("barausgleich_fehlender_schlusskurs")
    with pytest.raises(ValueError) as fehler:
        bilde_legs(fall.executions, fall.instruments, fall.kapitalmassnahmen)
    assert "BS2" in str(fehler.value) or "500023" in str(fehler.value)


# ---------------------------------------------------------------------------
# Kapitalmaßnahmen als Transfer (Nachtrag AP-03vm, OF-23)
#
# IB bucht eine Kapitalmaßnahme nicht als Faktor auf derselben conid, sondern
# als Abgang auf der alten und Zugang auf einer neuen — gemessen an allen 10
# Maßnahmen der Golden-Exporte, ausnahmslos. „Aktiensplit vor dem Matching"
# weiter oben deckt den Regelfall (Transfer, Stichtagsgrenze) ab; hier zwei
# weitere Pflichtfälle: ein Mengenverhältnis, das vom glatten Split abweicht,
# und der reine Zugang ohne abgebende Seite.
#
# conid 500033 -> 500034 (5 neue je 4 alte Stück): O1 BUY 4 @ 10.00 (-2.00)
#                 vor dem Stichtag, O2 SELL 5 @ 9.00 (-2.50) auf der neuen
#                 conid. Multiplikator 100.
# conid 500035 (reiner Zugang, IBs Kosten 250.00 für 10 Stück): Z1 SELL 10
#                 @ 30.00 (-1.00).
# conid 500036 (reiner Zugang ohne Kostenangabe, 5 Stück): Z2 SELL 5 @ 12.00
#                 (-1.00).
# ---------------------------------------------------------------------------


def test_optionsanpassung_uebertraegt_menge_nach_verhaeltnis_der_massnahme():
    # Faktor 5/4 = 1.25, nicht 2 — aus alte_menge/neue_menge, nicht fest
    # verdrahtet. Menge: 4 * 1.25 = 5, Preis: 10.00 / 1.25 = 8.00.
    # Brutto: (9.00 - 8.00) * 5 * 100 = 500.00
    leg = leg_von(bilde("kapitalmassnahme_optionsanpassung"), "O1", "O2")
    assert leg.conid == 500034
    assert leg.menge == Decimal("5")
    assert leg.brutto_pnl == Decimal("500.00")
    assert leg.kommission_gesamt == Decimal("-4.50")  # -2.00 + -2.50


def test_optionsanpassung_glattes_verhaeltnis_waere_das_falsche_ergebnis():
    # Gegenprobe: mit dem (falschen) glatten Faktor 2 wären es 8 Stück zu
    # 5.00, also (9.00 - 5.00) * 8 * 100 = 3200.00 — deutlich daneben.
    leg = leg_von(bilde("kapitalmassnahme_optionsanpassung"), "O1", "O2")
    assert leg.menge != Decimal("8")
    assert leg.brutto_pnl != Decimal("3200.00")


def test_reiner_zugang_mit_kostenangabe_eroeffnet_zu_deren_stueckpreis():
    # Synthetische Eröffnung: 250.00 / 10 Stück = 25.00 je Stück.
    # Brutto: (30.00 - 25.00) * 10 * 1 = 50.00
    ergebnis = bilde("kapitalmassnahme_reiner_zugang")
    leg = leg_von(ergebnis, "KM:AKT4", "Z1")
    assert leg.brutto_pnl == Decimal("50.00")
    assert leg.kommission_gesamt == Decimal("-1.00")  # 0.00 (Zugang) + -1.00
    assert leg.basis_ungeklaert is False


def test_reiner_zugang_ohne_kostenangabe_ist_basis_ungeklaert():
    # Ohne kosten_neu öffnet das Lot zu 0.00 — aber markiert, keine stille
    # Nullbasis. Brutto: (12.00 - 0.00) * 5 * 1 = 60.00
    ergebnis = bilde("kapitalmassnahme_reiner_zugang")
    leg = leg_von(ergebnis, "KM:AKT5", "Z2")
    assert leg.brutto_pnl == Decimal("60.00")
    assert leg.basis_ungeklaert is True
