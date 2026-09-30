"""Abnahmetests für AP-04s (Kettensicht-Zuordnung, engine-seitiger erster
Ausschnitt): `engine/kettensicht.py`.

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-04s.md`; die Grundsatzentscheidung („Ausführung zählt
doppelt") steht in `OFFENE_FRAGEN.md`, OF-52.

**Jeder Erwartungswert ist von Hand nachgerechnet** (Regel 8) — die
Rechnung steht als Kommentar am Wert.
"""

from datetime import date, datetime
from decimal import Decimal

from engine.kettensicht import kettensicht_legs
from engine.matching import bilde_legs
from engine.structures import bilde_structures

KONTO = "U7777777"


def _exec(
    exec_id, *, conid, side, preis, handelszeit, menge="1", kommission="-1.00",
    ereignistyp="trade", oa_trade=None, oa_order=None, oa_rolle=None,
) -> dict:
    return {
        "exec_id": exec_id,
        "konto": KONTO,
        "conid": conid,
        "side": side,
        "menge": Decimal(menge),
        "preis": Decimal(preis),
        "kommission": Decimal(kommission),
        "waehrung": "USD",
        "handelszeit": handelszeit,
        "ereignistyp": ereignistyp,
        "oa_trade": oa_trade,
        "oa_order": oa_order,
        "oa_rolle": oa_rolle,
    }


def _instrument(conid) -> dict:
    return {
        "conid": conid, "asset_class": "OPT", "underlying": "SPX",
        "expiry": date(2026, 9, 18), "strike": Decimal("5000"), "right": "P",
        "multiplikator": Decimal("100"),
    }


INSTRUMENTE = {601: _instrument(601), 701: _instrument(701)}

# ---------------------------------------------------------------------------
# Das OF-36-Muster: A1 eröffnet (oa_trade 100), B1 ist als eigene Eröffnung
# für oa_trade 200 gedacht (oa_rolle 'Open Order'), landet aber per
# Kontosicht-FIFO als Schließung von A1 — gegenläufige Richtung, gleicher
# Kontrakt, A1 zeitlich früher.
# ---------------------------------------------------------------------------

A1 = _exec("A1", conid=601, side="SELL", preis="12.00", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
            oa_trade="100", oa_order="1", oa_rolle="Open Order")
B1 = _exec("B1", conid=601, side="BUY", preis="3.00", handelszeit=datetime(2026, 9, 5, 10, 0, 0),
            oa_trade="200", oa_order="1", oa_rolle="Open Order")
B2 = _exec("B2", conid=701, side="SELL", preis="5.00", handelszeit=datetime(2026, 9, 5, 10, 0, 0),
            oa_trade="200", oa_order="1", oa_rolle="Open Order")
B3 = _exec("B3", conid=601, side="SELL", preis="2.00", handelszeit=datetime(2026, 9, 10, 10, 0, 0),
            oa_trade="200", oa_order="2", oa_rolle="Close Order")
B4 = _exec("B4", conid=701, side="BUY", preis="4.00", handelszeit=datetime(2026, 9, 10, 10, 0, 0),
            oa_trade="200", oa_order="2", oa_rolle="Close Order")
B5 = _exec("B5", conid=601, side="BUY", preis="1.50", handelszeit=datetime(2026, 9, 20, 10, 0, 0),
            oa_trade="300", oa_order="1", oa_rolle="Close Order")


def _konto(executions) -> tuple:
    return bilde_legs(executions, INSTRUMENTE, ()).legs


def _als_dict(legs) -> list[dict]:
    return [
        dict(conid=leg.conid, open_exec_id=leg.open_exec_id, close_exec_id=leg.close_exec_id,
             menge=leg.menge, offen_ja_nein=leg.offen_ja_nein, brutto_pnl=leg.brutto_pnl,
             kommission_gesamt=leg.kommission_gesamt)
        for leg in legs
    ]


def test_ohne_umleitung_bleibt_die_kettensicht_identisch_zur_kontosicht():
    executions = {e["exec_id"]: e for e in [A1]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    assert kette == konto


def test_nicht_trade_ereignis_wird_nicht_als_umgeleitet_behandelt():
    # A1 offen, keine Schließung -> kein Kandidat für eine Umleitung, ganz
    # unabhängig vom oa_rolle-Wert (P7-Vorfilter gilt sinngemäß auch hier).
    a1_verfall = dict(A1, ereignistyp="expiry")
    executions = {e["exec_id"]: e for e in [a1_verfall]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    assert kette == konto


def test_umgeleitete_ausfuehrung_oeffnet_ihre_eigene_struktur_wenn_ein_freier_closer_existiert():
    # B3 ist in der Kontosicht frei (offene Eröffnung, niemand schließt sie)
    # -> sie darf B1s eigene Position in der Kettensicht schließen.
    executions = {e["exec_id"]: e for e in [A1, B1, B2, B3]}
    konto = _konto(executions.values())
    # Kontosicht-Handrechnung: A1(Sell 12.00)->B1(Buy 3.00) schließt,
    # brutto = (12.00-3.00)*1*100 = 900.00. B3 (Sell 2.00) bleibt offen,
    # niemand schließt sie auf conid 601. B2 (Sell 5.00) bleibt offen.
    assert len(konto) == 3
    a1_b1 = next(leg for leg in konto if leg.open_exec_id == "A1")
    assert a1_b1.close_exec_id == "B1"
    assert a1_b1.brutto_pnl == Decimal("900.00")
    b3_leg = next(leg for leg in konto if leg.open_exec_id == "B3")
    assert b3_leg.close_exec_id is None

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    # A1->B1 bleibt unverändert (Regel „Ausführung zählt doppelt", OF-52).
    assert a1_b1 in kette
    # B3s eigene Kontosicht-Zeile (offen) entfällt - sie schließt jetzt B1.
    assert b3_leg not in kette
    b1_b3 = next(leg for leg in kette if leg.open_exec_id == "B1")
    assert b1_b3.close_exec_id == "B3"
    # Handrechnung: B1 (Buy 3.00) -> B3 (Sell 2.00), brutto =
    # (2.00-3.00)*1*100 = -100.00 (ein verlustreicher Long Put).
    assert b1_b3.brutto_pnl == Decimal("-100.00")
    # B2 bleibt unberührt (anderer Kontrakt, nicht Teil der Umleitung).
    b2_leg = next(leg for leg in kette if leg.open_exec_id == "B2")
    assert b2_leg.close_exec_id is None
    assert len(kette) == 3


def test_umgeleitete_ausfuehrung_bleibt_offen_wenn_kein_freier_closer_existiert():
    # B5 schließt B3 bereits in der Kontosicht (B3 ist dort NICHT mehr
    # frei) - die Kettensicht darf B3 dann nicht zusätzlich B1 zuschlagen,
    # sonst zählte B3 zweimal innerhalb DERSELBEN Sicht. B1 bleibt offen,
    # statt eine mehrstufige Neuzuordnung zu versuchen (Vertrag, Grenzen).
    executions = {e["exec_id"]: e for e in [A1, B1, B3, B5]}
    konto = _konto(executions.values())
    # Handrechnung: A1->B1 (900.00, wie oben), B3(Sell 2.00)->B5(Buy 1.50)
    # schließt: brutto = (2.00-1.50)*1*100 = 50.00. Alles geschlossen.
    assert all(leg.close_exec_id is not None for leg in konto)

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    # Alle Kontosicht-Legs bleiben erhalten (nichts wird verbraucht).
    for leg in konto:
        assert leg in kette
    b1_leg = next(leg for leg in kette if leg.open_exec_id == "B1" and leg.close_exec_id is None)
    assert b1_leg.brutto_pnl is None
    assert len(kette) == len(konto) + 1


def test_keine_mehrfachverwendung_in_der_kettensicht_ausser_der_umgeleiteten_ausfuehrung():
    # Die Kettensicht darf innerhalb sich selbst keine Ausführung zweimal
    # verwenden - außer der einen, bei der genau das Absicht ist: der
    # umgeleiteten Eröffnung, die ihren alten Vorgang schließt UND ihren
    # eigenen eröffnet (OF-52, „zählt doppelt"). B1 ist dieser einzige
    # Sonderfall; A1/B2/B3 dürfen je nur einmal auftauchen.
    executions = {e["exec_id"]: e for e in [A1, B1, B2, B3]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    vorkommen: dict[str, int] = {}
    for leg in kette:
        vorkommen[leg.open_exec_id] = vorkommen.get(leg.open_exec_id, 0) + 1
        if leg.close_exec_id:
            vorkommen[leg.close_exec_id] = vorkommen.get(leg.close_exec_id, 0) + 1

    assert vorkommen["B1"] == 2  # schließt A1 UND eröffnet die eigene Struktur
    assert vorkommen["A1"] == 1
    assert vorkommen["B2"] == 1
    assert vorkommen["B3"] == 1


def test_vorgang_b_wird_erst_in_der_kettensicht_zur_vollstaendigen_struktur():
    # Der eigentliche Zweck von AP-04s: In der Kontosicht bildet B2 allein
    # eine einbeinige Struktur (B1 fehlt - wurde zum Schließen von A1
    # verbraucht). In der Kettensicht gruppiert dieselbe (oa_trade,
    # oa_order)-Regel (engine.structures, Schritt 0a) B1 und B2 zur
    # vollständigen Zwei-Beine-Struktur, weil B1 dort seine eigene
    # Eröffnung ist.
    executions = {e["exec_id"]: e for e in [A1, B1, B2, B3]}
    konto = _konto(executions.values())

    konto_ergebnis = bilde_structures(_als_dict(konto), executions.values(), INSTRUMENTE)
    b_struktur_konto = next(
        s for s in konto_ergebnis.structures
        if any(sch.open_exec_id == "B2" for sch in s.leg_schluessel)
    )
    assert len(b_struktur_konto.leg_schluessel) == 1

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)
    kette_ergebnis = bilde_structures(_als_dict(kette), executions.values(), INSTRUMENTE)
    b_struktur_kette = next(
        s for s in kette_ergebnis.structures
        if any(sch.open_exec_id == "B2" for sch in s.leg_schluessel)
    )
    assert len(b_struktur_kette.leg_schluessel) == 2
    assert {sch.open_exec_id for sch in b_struktur_kette.leg_schluessel} == {"B1", "B2"}
