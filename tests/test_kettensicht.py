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


def _vorkommen(legs) -> dict[str, int]:
    zaehler: dict[str, int] = {}
    for leg in legs:
        zaehler[leg.open_exec_id] = zaehler.get(leg.open_exec_id, 0) + 1
        if leg.close_exec_id:
            zaehler[leg.close_exec_id] = zaehler.get(leg.close_exec_id, 0) + 1
    return zaehler


def _offene_menge(legs, executions, conid) -> Decimal:
    """Vorzeichenbehaftete offene Menge je Kontrakt (BUY plus, SELL minus)."""
    summe = Decimal("0")
    for leg in legs:
        if leg.conid == conid and leg.close_exec_id is None:
            vorzeichen = 1 if executions[leg.open_exec_id]["side"] == "BUY" else -1
            summe += vorzeichen * leg.menge
    return summe


# ---------------------------------------------------------------------------
# AP-04sx (OF-68, Option A): Die umgeleitete Ausführung eröffnet ausschließlich
# ihren eigenen Vorgang und schließt den alten NICHT. Der alte Vorgang bleibt
# offen, bis seine eigene Schließung kommt. Jede Ausführung kommt genau einmal
# vor — damit stimmen die Summen mit der Kontosicht überein (Plan §5).
# ---------------------------------------------------------------------------


def test_umgeleitete_ausfuehrung_eroeffnet_nur_den_eigenen_vorgang_und_laesst_den_alten_offen():
    # Datenende 10.09. liegt vor dem Verfall (18.09.): nichts wird rechnerisch
    # zusammengeführt.
    executions = {e["exec_id"]: e for e in [A1, B1, B2, B3]}
    konto = _konto(executions.values())
    # Kontosicht: A1(Sell 12.00)->B1(Buy 3.00) = (12.00-3.00)*1*100 = 900.00;
    # B3 und B2 offen.
    assert any(
        leg.open_exec_id == "A1" and leg.close_exec_id == "B1"
        and leg.brutto_pnl == Decimal("900.00")
        for leg in konto
    )

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    # A1->B1 gibt es in der Kettensicht nicht mehr; A1 bleibt offen.
    assert not any(
        leg.open_exec_id == "A1" and leg.close_exec_id == "B1" for leg in kette
    )
    a1 = next(leg for leg in kette if leg.open_exec_id == "A1")
    assert a1.close_exec_id is None
    assert a1.offen_ja_nein is True
    assert a1.brutto_pnl is None
    assert a1.menge == Decimal("1")
    assert a1.kommission_gesamt == Decimal("-1.00")  # nur die eigene Kommission von A1
    # B1 eröffnet den eigenen Vorgang und wird von B3 geschlossen:
    # (2.00-3.00)*1*100 = -100.00; Kommission B1 + B3 = -2.00.
    b1 = next(leg for leg in kette if leg.open_exec_id == "B1")
    assert b1.close_exec_id == "B3"
    assert b1.brutto_pnl == Decimal("-100.00")
    assert b1.kommission_gesamt == Decimal("-2.00")
    # B2 unberührt offen; B3 hat keine eigene Zeile mehr.
    b2 = next(leg for leg in kette if leg.open_exec_id == "B2")
    assert b2.close_exec_id is None
    assert not any(leg.open_exec_id == "B3" for leg in kette)
    assert len(kette) == 3


def test_nachfolgende_schliessung_wird_dem_alten_vorgang_zugeordnet():
    # A1 offen (kurz), B1 eröffnet lang (umgeleitet). B3 (Sell) schließt B1,
    # B5 (Buy, 20.09., nach dem Verfall von 601 am 18.09.) schließt A1.
    executions = {e["exec_id"]: e for e in [A1, B1, B3, B5]}
    konto = _konto(executions.values())
    # Kontosicht: A1->B1 = 900.00; B3(Sell 2.00)->B5(Buy 1.50) = 50.00.
    assert sorted(leg.brutto_pnl for leg in konto) == [Decimal("50.00"), Decimal("900.00")]

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    assert len(kette) == 2
    b1 = next(leg for leg in kette if leg.open_exec_id == "B1")
    # B1 (Buy 3.00) -> B3 (Sell 2.00): (2.00-3.00)*1*100 = -100.00
    assert b1.close_exec_id == "B3"
    assert b1.brutto_pnl == Decimal("-100.00")
    a1 = next(leg for leg in kette if leg.open_exec_id == "A1")
    # A1 (Sell 12.00) -> B5 (Buy 1.50): (1.50-12.00)*1*100*(-1) = 1050.00
    assert a1.close_exec_id == "B5"
    assert a1.brutto_pnl == Decimal("1050.00")


def test_summen_der_kettensicht_entsprechen_der_kontosicht():
    # Plan §5. Handrechnung Brutto: Konto 900.00 + 50.00 = 950.00;
    # Kette -100.00 + 1050.00 = 950.00. Kommission: vier Ausführungen
    # zu je -1.00 = -4.00 in beiden Sichten.
    executions = {e["exec_id"]: e for e in [A1, B1, B3, B5]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    assert sum((leg.brutto_pnl for leg in konto), Decimal("0")) == Decimal("950.00")
    assert sum((leg.brutto_pnl for leg in kette), Decimal("0")) == Decimal("950.00")
    assert sum((leg.kommission_gesamt for leg in konto), Decimal("0")) == Decimal("-4.00")
    assert sum((leg.kommission_gesamt for leg in kette), Decimal("0")) == Decimal("-4.00")


def test_jede_ausfuehrung_kommt_in_der_kettensicht_genau_einmal_vor():
    # Ersetzt die frühere Mehrfachverwendungs-Erwartung (B1 zweimal).
    for namen in ([A1, B1, B2, B3], [A1, B1, B3, B5]):
        executions = {e["exec_id"]: e for e in namen}
        konto = _konto(executions.values())

        kette = kettensicht_legs(konto, executions, INSTRUMENTE)

        assert _vorkommen(kette) == {e["exec_id"]: 1 for e in namen}


def test_offene_menge_je_kontrakt_entspricht_der_kontosicht():
    executions = {e["exec_id"]: e for e in [A1, B1, B2, B3]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    # 601: Konto offen = B3 (Sell) = -1; Kette offen = A1 (Sell) = -1 (B1 ist
    # durch B3 geschlossen). 701: B2 (Sell) = -1 in beiden Sichten.
    assert _offene_menge(konto, executions, 601) == Decimal("-1")
    assert _offene_menge(kette, executions, 601) == Decimal("-1")
    assert _offene_menge(konto, executions, 701) == Decimal("-1")
    assert _offene_menge(kette, executions, 701) == Decimal("-1")


def test_ohne_eigene_schliessung_bleiben_beide_vorgaenge_vor_dem_verfall_offen():
    # Nur A1 und B1; Datenende 05.09. < Verfall 18.09.: das Konto ist flach,
    # die Kettensicht führt beide Vorgänge brutto weiter (offen, je 1).
    executions = {e["exec_id"]: e for e in [A1, B1]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    assert len(kette) == 2
    assert all(leg.close_exec_id is None and leg.brutto_pnl is None for leg in kette)
    assert {leg.open_exec_id for leg in kette} == {"A1", "B1"}
    # Nettobestand wie im (flachen) Konto: -1 + 1 = 0.
    assert _offene_menge(kette, executions, 601) == Decimal("0")
    assert _offene_menge(konto, executions, 601) == Decimal("0")


def test_nach_dem_verfall_werden_gegenlaeufige_offene_vorgaenge_zusammengefuehrt():
    # Wie oben, aber eine weitere Ausführung am 20.09. (Datenende) liegt nach
    # dem Verfall von 601 (18.09.): A1 und B1 heben sich dann wie in der
    # Kontosicht gegeneinander auf (A1->B1 = 900.00) — es gibt keine eigene
    # Schließung mehr, die sie noch trennen könnte. Kein Geld geht verloren.
    spaeter = _exec("X9", conid=701, side="SELL", preis="1.00",
                    handelszeit=datetime(2026, 9, 20, 10, 0, 0),
                    oa_trade="900", oa_order="1", oa_rolle="Open Order")
    executions = {e["exec_id"]: e for e in [A1, B1, spaeter]}
    konto = _konto(executions.values())

    kette = kettensicht_legs(konto, executions, INSTRUMENTE)

    assert kette == konto
    leg = next(leg for leg in kette if leg.conid == 601)
    assert (leg.open_exec_id, leg.close_exec_id) == ("A1", "B1")
    assert leg.brutto_pnl == Decimal("900.00")


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
