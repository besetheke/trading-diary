"""Abnahmetests für AP-13v: Verknüpfung und Ergebnisabgleich OA-Export ↔
Ketten (`engine/oa_abgleich.py`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-13v.md`; die Begründung des Fingerabdruck-Musters (ohne
Entry Time) steht in `OFFENE_FRAGEN.md`, OF-53.
"""

from datetime import date, datetime
from decimal import Decimal

from engine.chains import bilde_chains
from engine.oa_abgleich import OALegSignatur, OATradeEintrag, oa_abgleich
from engine.structures import bilde_structures

KONTO = "U7777777"


def _exec(
    exec_id,
    *,
    conid,
    side,
    menge="1",
    handelszeit,
    ereignistyp="trade",
    exec_batch=None,
    oa_trade=None,
    oa_order=None,
) -> dict:
    return {
        "exec_id": exec_id,
        "konto": KONTO,
        "conid": conid,
        "side": side,
        "menge": Decimal(menge),
        "handelszeit": handelszeit,
        "ereignistyp": ereignistyp,
        "exec_batch": exec_batch,
        "oa_trade": oa_trade,
        "oa_order": oa_order,
    }


def _leg(
    open_exec_id,
    close_exec_id,
    *,
    conid,
    menge="1",
    offen_ja_nein=True,
    brutto_pnl=None,
    kommission_gesamt="0",
) -> dict:
    return {
        "conid": conid,
        "open_exec_id": open_exec_id,
        "close_exec_id": close_exec_id,
        "menge": Decimal(menge),
        "offen_ja_nein": offen_ja_nein,
        "brutto_pnl": Decimal(brutto_pnl) if brutto_pnl is not None else None,
        "kommission_gesamt": Decimal(kommission_gesamt),
    }


def _instrument(conid, *, asset_class, underlying, expiry=None, strike=None, right=None) -> dict:
    return {
        "conid": conid,
        "asset_class": asset_class,
        "underlying": underlying,
        "expiry": expiry,
        "strike": Decimal(strike) if strike is not None else None,
        "right": right,
    }


def _chains(legs, executions, instrumente):
    struktur = bilde_structures(legs, executions, instrumente)
    return bilde_chains(struktur, legs, executions, instrumente).chains


def _oa_leg(*, right, strike, expiry, richtung, menge="1") -> OALegSignatur:
    return OALegSignatur(right=right, strike=Decimal(strike), expiry=expiry, richtung=richtung,
                          menge=Decimal(menge))


def _oa_trade(oa_trade, legs, *, profit, strategie="SPX: IC", status="CLOSED") -> OATradeEintrag:
    return OATradeEintrag(
        oa_trade=oa_trade, legs=tuple(legs), profit=Decimal(profit), strategie=strategie,
        status=status,
    )


# ---------------------------------------------------------------------------
# Eine geschlossene, einbeinige SPX-Kette mit OA-Referenz "10"
# ---------------------------------------------------------------------------

INSTRUMENTE_SPX = {
    601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                      strike="5000", right="P"),
}
EXECUTIONS_SPX = [
    _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
          oa_trade="10", oa_order="1"),
    _exec("E2", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
          oa_trade="10", oa_order="1"),
]
LEGS_SPX = [
    _leg("E1", "E2", conid=601, offen_ja_nein=False, brutto_pnl="120.00"),
]


def _spx_chain():
    return _chains(LEGS_SPX, EXECUTIONS_SPX, INSTRUMENTE_SPX)


def test_treffer_mit_uebereinstimmendem_fingerabdruck_ist_auto():
    chains = _spx_chain()
    trade = _oa_trade(
        "10", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1)],
        profit="115.50",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in EXECUTIONS_SPX},
                            INSTRUMENTE_SPX)

    assert ergebnis.fehler == ()
    assert len(ergebnis.zuordnungen) == 1
    z = ergebnis.zuordnungen[0]
    assert z.oa_trade == "10"
    assert z.fingerabdruck_treffer is True
    assert z.erkennung == "auto"
    assert z.ergebnis_oa == Decimal("115.50")
    assert z.ergebnis_eigen == Decimal("120.00")
    # Handrechnung: 115.50 - 120.00 = -4.50
    assert z.abweichung == Decimal("-4.50")
    assert z.strategie == "SPX: IC"
    assert z.status == "CLOSED"
    assert ergebnis.abdeckung == Decimal("1")


def test_abweichender_fingerabdruck_bleibt_zugeordnet_aber_heuristik():
    chains = _spx_chain()
    # Falscher Strike (4950 statt 5000) — die Nummer bleibt Primärschlüssel
    # (§6.1), die Zuordnung wird nicht verworfen, nur als unsicher markiert.
    trade = _oa_trade(
        "10", [_oa_leg(right="P", strike="4950", expiry=date(2026, 9, 18), richtung=-1)],
        profit="115.50",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in EXECUTIONS_SPX},
                            INSTRUMENTE_SPX)

    assert ergebnis.fehler == ()
    assert len(ergebnis.zuordnungen) == 1
    z = ergebnis.zuordnungen[0]
    assert z.fingerabdruck_treffer is False
    assert z.erkennung == "heuristik"
    # Der Ergebnisabgleich ist vom Fingerabdruck unabhängig.
    assert z.abweichung == Decimal("-4.50")


def test_ergebnisabgleich_vergleicht_netto_nicht_brutto():
    # AP-13vk2 (OF-56): OAs profit ist bereits kommissionsbereinigt. Bei
    # brutto_pnl=120.00 und kommission_gesamt=-3.00 ist das eigene
    # Netto-Ergebnis 117.00 (Vertrag 10a: netto = brutto + kommission,
    # ADDIERT — die Kommission trägt IBs Vorzeichen). OA meldet exakt
    # 117.00 -> Handrechnung: 117.00 - 117.00 = 0.00, keine Abweichung.
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="12", oa_order="1"),
        _exec("E2", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="12", oa_order="1"),
    ]
    legs = [
        _leg("E1", "E2", conid=601, offen_ja_nein=False, brutto_pnl="120.00",
             kommission_gesamt="-3.00"),
    ]
    chains = _chains(legs, executions, instrumente)
    trade = _oa_trade(
        "12", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1)],
        profit="117.00",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in executions}, instrumente)

    z = ergebnis.zuordnungen[0]
    assert z.ergebnis_eigen == Decimal("117.00")
    assert z.abweichung == Decimal("0.00")


def test_signierte_ausfuehrungsmenge_zaehlt_trotzdem_als_treffer():
    # AP-13vk2 (OF-55): executions.menge trägt bei IB-Sell ein Vorzeichen
    # (Flex-quantity unverändert übernommen, ingest/flex.py), OA meldet in
    # Strikes nur den Betrag. Ohne abs() verfehlte das jeden echten Treffer.
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", menge="-1",
              handelszeit=datetime(2026, 9, 1, 10, 0, 0), oa_trade="10", oa_order="1"),
        _exec("E2", conid=601, side="BUY", menge="1",
              handelszeit=datetime(2026, 9, 15, 15, 0, 0), oa_trade="10", oa_order="1"),
    ]
    legs = [_leg("E1", "E2", conid=601, offen_ja_nein=False, brutto_pnl="120.00")]
    chains = _chains(legs, executions, instrumente)
    trade = _oa_trade(
        "10", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1,
                        menge="1")],
        profit="115.50",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in executions}, instrumente)

    z = ergebnis.zuordnungen[0]
    assert z.fingerabdruck_treffer is True
    assert z.erkennung == "auto"


def test_abweichende_menge_bleibt_zugeordnet_aber_heuristik():
    # AP-13vk: Die Menge gehört zur vollständigen Leg-Spezifikation (§6.1) —
    # zwei Kontrakte im Export gegen einen in der Kette darf nicht als
    # Fingerabdruck-Treffer durchgehen, auch wenn Right/Strike/Expiry/
    # Richtung übereinstimmen (z. B. bei einem Ratio-Spread).
    chains = _spx_chain()
    trade = _oa_trade(
        "10",
        [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1, menge="2")],
        profit="115.50",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in EXECUTIONS_SPX},
                            INSTRUMENTE_SPX)

    assert len(ergebnis.zuordnungen) == 1
    z = ergebnis.zuordnungen[0]
    assert z.fingerabdruck_treffer is False
    assert z.erkennung == "heuristik"


def test_keine_kette_gefunden_landet_in_der_fehlerliste():
    chains = _spx_chain()
    trade = _oa_trade(
        "99", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1)],
        profit="0.00",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in EXECUTIONS_SPX},
                            INSTRUMENTE_SPX)

    assert ergebnis.zuordnungen == ()
    assert len(ergebnis.fehler) == 1
    assert ergebnis.fehler[0].oa_trade == "99"
    assert ergebnis.fehler[0].grund == "keine_kette"
    assert ergebnis.abdeckung == Decimal("0")


def test_mehrdeutige_nummer_ueber_zwei_unabhaengige_ketten_landet_in_der_fehlerliste():
    # Zwei völlig unabhängige, einzeln gebildete Ketten teilen sich zufällig
    # dieselbe OA-Trade-Nummer ("77") — das darf laut Konstruktion (AP-04k,
    # „0a, OptionApp-Referenz") nicht vorkommen, die Prüfung bleibt trotzdem
    # bestehen statt einen der beiden Treffer stillschweigend zu wählen.
    instrumente_a = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
    }
    executions_a = [
        _exec("A1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="77", oa_order="1"),
        _exec("A2", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="77", oa_order="1"),
    ]
    legs_a = [_leg("A1", "A2", conid=601, offen_ja_nein=False, brutto_pnl="10.00")]

    instrumente_b = {
        602: _instrument(602, asset_class="OPT", underlying="RUT", expiry=date(2026, 10, 16),
                          strike="2000", right="C"),
    }
    executions_b = [
        _exec("B1", conid=602, side="SELL", handelszeit=datetime(2026, 9, 2, 10, 0, 0),
              oa_trade="77", oa_order="1"),
        _exec("B2", conid=602, side="BUY", handelszeit=datetime(2026, 9, 16, 15, 0, 0),
              oa_trade="77", oa_order="1"),
    ]
    legs_b = [_leg("B1", "B2", conid=602, offen_ja_nein=False, brutto_pnl="5.00")]

    chains = _chains(legs_a, executions_a, instrumente_a) + _chains(legs_b, executions_b,
                                                                      instrumente_b)
    executions = {e["exec_id"]: e for e in executions_a + executions_b}
    instrumente = {**instrumente_a, **instrumente_b}
    trade = _oa_trade(
        "77", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1)],
        profit="0.00",
    )

    ergebnis = oa_abgleich([trade], chains, executions, instrumente)

    assert ergebnis.zuordnungen == ()
    assert len(ergebnis.fehler) == 1
    assert ergebnis.fehler[0].grund == "mehrdeutig"


def test_offene_kette_hat_kein_eigenes_ergebnis_aber_gilt_als_zugeordnet():
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="11", oa_order="1"),
    ]
    legs = [_leg("E1", None, conid=601)]
    chains = _chains(legs, executions, instrumente)
    trade = _oa_trade(
        "11", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1)],
        profit="45.00", status="UNMANAGED",
    )

    ergebnis = oa_abgleich([trade], chains, {e["exec_id"]: e for e in executions}, instrumente)

    assert ergebnis.fehler == ()
    z = ergebnis.zuordnungen[0]
    assert z.ergebnis_eigen is None
    assert z.abweichung is None
    assert z.ergebnis_oa == Decimal("45.00")
    assert z.status == "UNMANAGED"


def test_abdeckung_zaehlt_heuristik_treffer_mit_nur_keine_kette_und_mehrdeutig_nicht():
    # Vier OA-Trades: zwei Treffer (einer auto, einer heuristik dank
    # abweichendem Fingerabdruck), einer ohne Kette, einer offen aber
    # trotzdem zugeordnet -> 3 von 4 zugeordnet.
    instrumente = {
        601: _instrument(601, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="5000", right="P"),
        602: _instrument(602, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4900", right="P"),
        603: _instrument(603, asset_class="OPT", underlying="SPX", expiry=date(2026, 9, 18),
                          strike="4800", right="P"),
    }
    executions = [
        _exec("E1", conid=601, side="SELL", handelszeit=datetime(2026, 9, 1, 10, 0, 0),
              oa_trade="1", oa_order="1"),
        _exec("E2", conid=601, side="BUY", handelszeit=datetime(2026, 9, 15, 15, 0, 0),
              oa_trade="1", oa_order="1"),
        _exec("E3", conid=602, side="SELL", handelszeit=datetime(2026, 9, 2, 10, 0, 0),
              oa_trade="2", oa_order="1"),
        _exec("E4", conid=602, side="BUY", handelszeit=datetime(2026, 9, 16, 15, 0, 0),
              oa_trade="2", oa_order="1"),
        _exec("E5", conid=603, side="SELL", handelszeit=datetime(2026, 9, 3, 10, 0, 0),
              oa_trade="4", oa_order="1"),
    ]
    legs = [
        _leg("E1", "E2", conid=601, offen_ja_nein=False, brutto_pnl="10.00"),
        _leg("E3", "E4", conid=602, offen_ja_nein=False, brutto_pnl="20.00"),
        _leg("E5", None, conid=603),
    ]
    chains = _chains(legs, executions, instrumente)
    exec_map = {e["exec_id"]: e for e in executions}

    trades = [
        _oa_trade("1", [_oa_leg(right="P", strike="5000", expiry=date(2026, 9, 18), richtung=-1)],
                   profit="9.00"),
        _oa_trade("2", [_oa_leg(right="P", strike="9999", expiry=date(2026, 9, 18), richtung=-1)],
                   profit="19.00"),
        _oa_trade("3", [_oa_leg(right="P", strike="1", expiry=date(2026, 9, 18), richtung=-1)],
                   profit="0.00"),
        _oa_trade("4", [_oa_leg(right="P", strike="4800", expiry=date(2026, 9, 18), richtung=-1)],
                   profit="0.00"),
    ]

    ergebnis = oa_abgleich(trades, chains, exec_map, instrumente)

    assert len(ergebnis.zuordnungen) == 3
    assert len(ergebnis.fehler) == 1
    assert ergebnis.fehler[0].oa_trade == "3"
    # Handrechnung: 3 von 4 zugeordnet = 0.75
    assert ergebnis.abdeckung == Decimal("0.75")
