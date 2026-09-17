"""Abnahmetests für AP-02k: Der Import muss das echte IB-Flex-Format lesen.

Geschrieben nach §11.2 des Plans durch das starke Modell — für das günstige
Modell unveränderlich. Nachgeschoben, weil der Golden-Lauf zeigte, dass
``ingest/flex.py`` ein Format liest, das IB nicht liefert (OF-19), den
Ereigniscode ``P`` falsch behandelt (OF-20) und an echten CashTransactions
abbricht (OF-22).

Jeder Test nennt im Docstring, welche Regel aus ``auftraege/AP-02k.md`` er
belegt. Die Testdaten entstehen im Test selbst (``tmp_path``): Die Fälle
brauchen Konstruktionen, die es in ``fixtures/flex/`` nicht gibt (fehlendes
Feld, unbekannter Code, unerwartete Ebene) oder die dort — zu Recht — nicht
absichtlich falsch angelegt sind.

Gegen den unveränderten ``ingest/flex.py`` schlagen die meisten dieser Tests
fehl: Manche, weil ``dateTime``/``levelOfDetail`` noch nicht gelesen werden,
manche, weil ``instruments.abwicklungsart`` und ``executions.schlusskurs``
(Regel 6) noch keine Migration haben. Das ist der Zweck des Pakets — es legt
die Zielform fest, gegen die AP-02 nachgebessert wird.
"""

from decimal import Decimal

import pytest
from sqlalchemy import text

pytest.importorskip("ingest.flex")

from ingest.flex import import_flex_file  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import executions, flex_corporate_actions  # noqa: E402

# ---------------------------------------------------------------------------
# Bausteine — nur das, was ein Test tatsächlich braucht, wird gesetzt.
# ---------------------------------------------------------------------------


def _statement(
    *,
    konto="U9999999",
    von="20260601",
    bis="20260630",
    erzeugt="20260701;031500",
    trades="",
    open_positions="",
    cash="",
    corp="",
    transfers="",
    sec="",
    perf="",
) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryname="Activity" type="Statement">
  <FlexStatements count="1">
    <FlexStatement accountId="{konto}" fromDate="{von}" toDate="{bis}"
                   period="Test" whenGenerated="{erzeugt}">
      <Trades>{trades}</Trades>
      <OpenPositions>{open_positions}</OpenPositions>
      <CashTransactions>{cash}</CashTransactions>
      <CorporateActions>{corp}</CorporateActions>
      <Transfers>{transfers}</Transfers>
      <SecuritiesInfo>{sec}</SecuritiesInfo>
      {perf}
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
"""


def _schreiben(tmp_path, name: str, inhalt: str):
    ziel = tmp_path / name
    ziel.write_text(inhalt, encoding="utf-8")
    return ziel


def _trade(
    *,
    trade_id,
    transaction_id="9990001",
    conid="500001",
    symbol="CORPX",
    asset_category="STK",
    put_call=None,
    strike=None,
    side="BUY",
    menge="1",
    preis="1.00",
    notes="",
    level="EXECUTION",
    zeitfeld=None,
    order_time="",
    close_price=None,
    oci="",
    fx_rate_to_base="1.0000",
    model=None,
) -> str:
    """Eine Trades-Zeile im echten Format (Regel 1: ``dateTime``, kein
    ``tradeTime``). ``zeitfeld`` ist die rohe Zeitattribut-Deklaration
    (Standard: ``dateTime="20260601;120000"``) — Tests, die eine kaputte oder
    fehlende Zeitangabe prüfen, geben sie explizit vor."""
    if zeitfeld is None:
        zeitfeld = 'dateTime="20260601;120000"'
    putcall_attr = f' putCall="{put_call}"' if put_call else ""
    strike_attr = f' strike="{strike}"' if strike is not None else ""
    close_price_attr = f' closePrice="{close_price}"' if close_price is not None else ""
    fx_rate_attr = f' fxRateToBase="{fx_rate_to_base}"' if fx_rate_to_base is not None else ""
    model_attr = f' model="{model}"' if model else ""
    trade_id_attr = f'tradeID="{trade_id}" ' if trade_id is not None else ""
    level_attr = f'levelOfDetail="{level}" ' if level is not None else ""
    return (
        f"<Trade {level_attr}{trade_id_attr}transactionID=\"{transaction_id}\""
        f' ibExecID="0099.0001.01.01" ibOrderID="5599999" orderReference=""'
        f' conid="{conid}" symbol="{symbol}" underlyingSymbol="{symbol}"'
        f' assetCategory="{asset_category}"{putcall_attr}{strike_attr} buySell="{side}"'
        f' quantity="{menge}" tradePrice="{preis}" proceeds="0.00" ibCommission="-1.00"'
        f' ibCommissionCurrency="USD" currency="USD"{fx_rate_attr}{model_attr}'
        f' netCash="0.00"'
        f" {zeitfeld} orderTime=\"{order_time}\" exchange=\"MEMX\" notes=\"{notes}\""
        f' openCloseIndicator="{oci}"{close_price_attr} />'
    )


def _lot(*, conid="500001", transaction_id="8880001") -> str:
    """Eine Closed-Lot-Zeile — eigenes Element ``<Lot>``, kein ``<Trade>``
    (Regel 3): wird nicht über ``./Trades/Trade`` gefunden und darf den
    Import nicht stören."""
    return (
        f'<Lot levelOfDetail="CLOSED_LOT" transactionID="{transaction_id}" tradeID="8880001"'
        f' conid="{conid}" symbol="CORPX" assetCategory="STK" buySell="SELL" quantity="1"'
        f' tradePrice="1.00" cost="1.00" fifoPnlRealized="0.00"'
        f' openDateTime="20260501;120000" dateTime="20260601;120000" />'
    )


def _cash(*, transaction_id, typ, betrag="1.00", zeitwert="20260601;120000", level="DETAIL") -> str:
    tx_attr = f'transactionID="{transaction_id}" ' if transaction_id else ""
    return (
        f'<CashTransaction levelOfDetail="{level}" {tx_attr}accountId="U9999999"'
        f' currency="USD" fxRateToBase="1.0000" amount="{betrag}" type="{typ}"'
        f' dateTime="{zeitwert}" description="" />'
    )


def _corp(*, transaction_id, typ="FS", conid="500001", level="DETAIL") -> str:
    return (
        f'<CorporateAction levelOfDetail="{level}" transactionID="{transaction_id}"'
        f' accountId="U9999999" conid="{conid}" symbol="CORPX" assetCategory="STK"'
        f' type="{typ}" dateTime="20260601;120000" quantity="1" currency="USD"'
        f' description="Test" />'
    )


def _transfer(*, transaction_id="6660001", conid="500001") -> str:
    return (
        f'<Transfer levelOfDetail="TRANSFER" transactionID="{transaction_id}"'
        f' accountId="U9999999" conid="{conid}" symbol="CORPX" assetCategory="STK"'
        f' type="INTERNAL" direction="IN" quantity="1" dateTime="20260601;120000"'
        f' currency="USD" description="Test" />'
    )


def _open_position(*, conid="500001", report_date="20260630") -> str:
    return (
        f'<OpenPosition levelOfDetail="SUMMARY" accountId="U9999999" reportDate="{report_date}"'
        f' conid="{conid}" symbol="CORPX" underlyingSymbol="CORPX" assetCategory="STK"'
        f' position="1" markPrice="1.00" costBasisPrice="1.00" costBasisMoney="1.00"'
        f' fifoPnlUnrealized="0.00" currency="USD" fxRateToBase="1.0000" />'
    )


def _sec_info(*, conid="500002", symbol="OPTX", asset_category="OPT", settlement=None) -> str:
    settlement_attr = f' settlementPolicyMethod="{settlement}"' if settlement is not None else ""
    return (
        f'<SecurityInfo conid="{conid}" symbol="{symbol}" underlyingSymbol="CORPX"'
        f' assetCategory="{asset_category}" putCall="C" strike="100" expiry="20260919"'
        f' multiplier="100" currency="USD"{settlement_attr} />'
    )


def _exec_zeile(db_pfad, exec_id):
    from sqlalchemy import select

    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return verbindung.execute(
            select(executions).where(executions.c.exec_id == exec_id)
        ).mappings().one_or_none()


def _spaltenwert(db_pfad, sql, **params):
    """Rohe SQL-Abfrage statt ORM-Zugriff: Die Spalten aus Regel 6
    (``instruments.abwicklungsart``, ``executions.schlusskurs``) haben noch
    keine Migration (die legt die Nachbesserung von AP-02 an, nicht dieses
    Paket) und stehen deshalb nicht in ``journal/schema.py``."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return verbindung.execute(text(sql), params).scalar_one()


# ---------------------------------------------------------------------------
# Regel 1 — Zeitformen
# ---------------------------------------------------------------------------


def test_datetime_with_semicolon_is_the_trade_time(migrated_db, tmp_path):
    """Regel 1: ``dateTime`` in der Form JJJJMMTT;HHMMSS ergibt die
    Handelszeit; ``tradeTime`` wird nicht mehr gelesen."""
    from datetime import datetime

    datei = _schreiben(
        tmp_path,
        "regel1_dateTime.xml",
        _statement(trades=_trade(trade_id="900001001")),
    )
    import_flex_file(migrated_db, datei)
    zeile = _exec_zeile(migrated_db, "900001001")
    assert zeile is not None
    assert zeile["handelszeit"] == datetime(2026, 6, 1, 12, 0, 0)


def test_trade_without_datetime_aborts(migrated_db, tmp_path):
    """Regel 1: Fehlt ``dateTime``, bricht der Import ab, auch wenn ein
    (nicht mehr gelesenes) ``tradeTime`` vorhanden ist."""
    datei = _schreiben(
        tmp_path,
        "regel1_ohne_dateTime.xml",
        _statement(
            trades=_trade(
                trade_id="900001002",
                zeitfeld='tradeTime="20260601 12:00:00"',
            )
        ),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei)
    assert "dateTime" in str(fehler.value)


def test_date_only_cash_booking_gets_midnight(migrated_db, tmp_path):
    """Regel 1: ``JJJJMMTT`` ohne Uhrzeit ergibt 00:00:00 — eine
    dokumentierte Annahme, keine Information der Quelle."""
    from datetime import datetime

    datei = _schreiben(
        tmp_path,
        "regel1_datumsform.xml",
        _statement(
            cash=_cash(transaction_id="7770001", typ="Dividends", zeitwert="20260615")
        ),
    )
    import_flex_file(migrated_db, datei)
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        datum = verbindung.execute(
            text("SELECT datum FROM flex_cash_transactions")
        ).scalar_one()
    if isinstance(datum, str):  # SQLite liefert Decimal/Datetime teils als Text
        datum = datetime.fromisoformat(datum)
    assert datum == datetime(2026, 6, 15, 0, 0, 0)


def test_unknown_time_form_aborts_with_named_field(migrated_db, tmp_path):
    """Regel 1: Jede andere Form als JJJJMMTT;HHMMSS oder JJJJMMTT bricht mit
    genanntem Feld ab — hier die whenGenerated-Form ('T') an ``dateTime``."""
    datei = _schreiben(
        tmp_path,
        "regel1_unbekannte_form.xml",
        _statement(
            trades=_trade(
                trade_id="900001003",
                zeitfeld='dateTime="20260601T120000"',
            )
        ),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei)
    meldung = str(fehler.value)
    assert "dateTime" in meldung
    assert "20260601T120000" in meldung


# ---------------------------------------------------------------------------
# Regel 2 — Codes in notes
# ---------------------------------------------------------------------------


def test_modifier_codes_are_trades(migrated_db, tmp_path):
    """Regel 2: IA, L, IA;P und FP;P sind Zusatzkennzeichen einer
    gewöhnlichen Ausführung und ergeben ``trade``; ``ereignis_code`` trägt den
    Rohwert."""
    faelle = [
        ("900002001", "IA"),
        ("900002002", "L"),
        ("900002003", "IA;P"),
        ("900002004", "FP;P"),
    ]
    datei = _schreiben(
        tmp_path,
        "regel2_zusatzkennzeichen.xml",
        _statement(
            trades="".join(
                _trade(trade_id=trade_id, transaction_id=f"tx{trade_id}", notes=code)
                for trade_id, code in faelle
            )
        ),
    )
    import_flex_file(migrated_db, datei)
    for trade_id, code in faelle:
        zeile = _exec_zeile(migrated_db, trade_id)
        assert zeile["ereignistyp"] == "trade", code
        assert zeile["ereignis_code"] == code


def test_event_code_inside_a_list_sets_the_event_type(migrated_db, tmp_path):
    """Regel 2: Ep, Ex und A bestimmen den Ereignistyp auch als Teil einer
    Liste — hier eine Ausübung mit Zusatzkennzeichen ('IA;Ex')."""
    datei = _schreiben(
        tmp_path,
        "regel2_code_in_liste.xml",
        _statement(trades=_trade(trade_id="900002005", notes="IA;Ex")),
    )
    import_flex_file(migrated_db, datei)
    zeile = _exec_zeile(migrated_db, "900002005")
    assert zeile["ereignistyp"] == "exercise"
    assert zeile["ereignis_code"] == "IA;Ex"


def test_unknown_code_inside_a_list_aborts_with_named_code(migrated_db, tmp_path):
    """Regel 2: Ein unbekannter Code bricht ab, auch als Teil einer Liste —
    das gilt unverändert für einzelne Codes (OF-08)."""
    datei = _schreiben(
        tmp_path,
        "regel2_unbekannt_in_liste.xml",
        _statement(trades=_trade(trade_id="900002006", notes="P;XX")),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei)
    assert "XX" in str(fehler.value)


def test_two_event_codes_abort(migrated_db, tmp_path):
    """Regel 2: Zwei Ereigniscodes in einer Liste sind mehrdeutig und
    brechen ab, statt einen davon stillschweigend zu wählen."""
    datei = _schreiben(
        tmp_path,
        "regel2_zwei_ereignisse.xml",
        _statement(trades=_trade(trade_id="900002007", notes="Ep;A")),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei)
    meldung = str(fehler.value)
    assert "Ep" in meldung
    assert "A" in meldung


# ---------------------------------------------------------------------------
# Regel 3 — Ebenen je Sektion
# ---------------------------------------------------------------------------


def test_summary_cash_rows_are_counted_not_booked(migrated_db, tmp_path):
    """Regel 3 + 5: SUMMARY-Zeilen werden nicht gebucht, aber gezählt
    (``nicht_gebuchte_zeilen``) — nur DETAIL landet in
    ``flex_cash_transactions``."""
    datei = _schreiben(
        tmp_path,
        "regel3_summary_cash.xml",
        _statement(
            cash=(
                _cash(transaction_id="7770010", typ="Dividends", level="DETAIL")
                + _cash(transaction_id=None, typ="Dividends", level="SUMMARY")
            )
        ),
    )
    ergebnis = import_flex_file(migrated_db, datei)
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        anzahl = verbindung.execute(
            text("SELECT count(*) FROM flex_cash_transactions")
        ).scalar_one()
    assert anzahl == 1
    assert ergebnis.nicht_gebuchte_zeilen == 1


def test_unknown_or_missing_level_aborts(migrated_db, tmp_path):
    """Regel 3: Jede unerwartete oder fehlende Ebene bricht mit genannter
    Sektion und Ebene ab — auch eine Trade-Zeile der Closed-Lot-Ebene."""
    datei_closed_lot = _schreiben(
        tmp_path,
        "regel3_trade_closed_lot.xml",
        _statement(trades=_trade(trade_id="900003001", level="CLOSED_LOT")),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei_closed_lot)
    assert "CLOSED_LOT" in str(fehler.value)

    datei_fehlend = _schreiben(
        tmp_path,
        "regel3_trade_ohne_ebene.xml",
        _statement(trades=_trade(trade_id="900003002", level=None)),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei_fehlend)
    assert "levelOfDetail" in str(fehler.value)


def test_same_transaction_id_with_different_type_are_two_bookings(migrated_db, tmp_path):
    """Regel 4: Zwei Zeilen mit gleicher transactionID, aber verschiedenem
    type, sind zwei Buchungen — wie das echte Zinspaar Paid/Received. Ein
    erneuter Abruf legt nichts doppelt an."""
    inhalt = _statement(
        cash=(
            _cash(transaction_id="7770020", typ="Broker Interest Paid")
            + _cash(transaction_id="7770020", typ="Broker Interest Received")
        )
    )
    datei = _schreiben(tmp_path, "regel4_paar.xml", inhalt)
    import_flex_file(migrated_db, datei)
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        anzahl = verbindung.execute(
            text("SELECT count(*) FROM flex_cash_transactions")
        ).scalar_one()
    assert anzahl == 2

    neuabruf = _schreiben(
        tmp_path,
        "regel4_paar_neuabruf.xml",
        inhalt.replace('whenGenerated="20260701;031500"', 'whenGenerated="20260702;031500"'),
    )
    import_flex_file(migrated_db, neuabruf)
    with engine.connect() as verbindung:
        anzahl = verbindung.execute(
            text("SELECT count(*) FROM flex_cash_transactions")
        ).scalar_one()
    assert anzahl == 2, "Wiederholter Abruf darf das Paar nicht verdoppeln"


def test_open_positions_summary_and_transfer_level_are_accepted(migrated_db, tmp_path):
    """Regel 3: OpenPositions nur SUMMARY, Transfers nur TRANSFER — beide
    Ebenen sind die erwarteten, der Import bricht dafür nicht ab."""
    datei = _schreiben(
        tmp_path,
        "regel3_summary_transfer.xml",
        _statement(open_positions=_open_position(), transfers=_transfer()),
    )
    import_flex_file(migrated_db, datei)
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        offene = verbindung.execute(text("SELECT count(*) FROM flex_open_positions")).scalar_one()
        transfers = verbindung.execute(text("SELECT count(*) FROM flex_transfers")).scalar_one()
    assert offene == 1
    assert transfers == 1


def test_lot_elements_and_performance_summary_do_not_abort_and_are_not_executions(
    migrated_db, tmp_path
):
    """Regel 3: ``Lot``-Elemente (eigener Tag, nicht ``Trade``) und der
    Abschnitt ``FIFOPerformanceSummaryInBase`` werden nicht gelesen — sie
    dürfen den Import nicht stören und landen nicht in ``executions``."""
    perf = (
        "<FIFOPerformanceSummaryInBase>"
        '<FIFOPerformanceSummaryUnderlying conid="500001" assetCategory="STK"'
        ' totalRealizedPnl="123.45" />'
        "</FIFOPerformanceSummaryInBase>"
    )
    datei = _schreiben(
        tmp_path,
        "regel3_lot_und_summary.xml",
        _statement(
            trades=_trade(trade_id="900003003") + _lot(),
            perf=perf,
        ),
    )
    ergebnis = import_flex_file(migrated_db, datei)
    assert ergebnis.zeilen_gesamt == 1
    assert _exec_zeile(migrated_db, "900003003") is not None
    assert _exec_zeile(migrated_db, "8880001") is None, "Lot ist keine Ausführung"


def test_closed_lot_corporate_action_is_counted_not_booked(migrated_db, tmp_path):
    """Regel 3: Eine CorporateAction der Ebene CLOSED_LOT wird nicht
    gebucht, aber gezählt — analog zu SUMMARY bei CashTransactions."""
    datei = _schreiben(
        tmp_path,
        "regel3_closed_lot_corpaction.xml",
        _statement(
            corp=(
                _corp(transaction_id="6660010", level="DETAIL")
                + _corp(transaction_id="6660011", level="CLOSED_LOT")
            )
        ),
    )
    ergebnis = import_flex_file(migrated_db, datei)
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        from sqlalchemy import select

        anzahl = verbindung.execute(
            select(flex_corporate_actions.c.id)
        ).scalars().all()
    assert len(anzahl) == 1
    assert ergebnis.nicht_gebuchte_zeilen == 1


# ---------------------------------------------------------------------------
# Regel 6 — Abwicklungsart und Schlusskurs (OF-25, entschieden)
# ---------------------------------------------------------------------------


def test_settlement_method_is_stored_on_option_instruments(migrated_db, tmp_path):
    """Regel 6: ``Delivery`` ergibt ``lieferung``, ``Cash`` ergibt
    ``barausgleich``, fehlend bleibt leer — je Option in ``instruments``."""
    datei = _schreiben(
        tmp_path,
        "regel6_abwicklungsart.xml",
        _statement(
            sec=(
                _sec_info(conid="500011", settlement="Delivery")
                + _sec_info(conid="500012", settlement="Cash")
                + _sec_info(conid="500013", settlement=None)
            )
        ),
    )
    import_flex_file(migrated_db, datei)
    assert _spaltenwert(
        migrated_db, "SELECT abwicklungsart FROM instruments WHERE conid = :c", c=500011
    ) == "lieferung"
    assert _spaltenwert(
        migrated_db, "SELECT abwicklungsart FROM instruments WHERE conid = :c", c=500012
    ) == "barausgleich"
    assert _spaltenwert(
        migrated_db, "SELECT abwicklungsart FROM instruments WHERE conid = :c", c=500013
    ) in (None, "")


def test_unknown_settlement_method_aborts_with_named_value(migrated_db, tmp_path):
    """Regel 6: Ein anderer als die beiden gemessenen Werte bricht ab, statt
    ihn stillschweigend zu übernehmen."""
    datei = _schreiben(
        tmp_path,
        "regel6_unbekannte_abwicklungsart.xml",
        _statement(sec=_sec_info(conid="500014", settlement="Physisch")),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei)
    assert "Physisch" in str(fehler.value)


def test_close_price_is_stored_on_executions(migrated_db, tmp_path):
    """Regel 6: ``closePrice`` einer Ausführung landet in
    ``executions.schlusskurs``, als ``Decimal``; fehlt das Feld, bleibt die
    Spalte leer."""
    datei = _schreiben(
        tmp_path,
        "regel6_schlusskurs.xml",
        _statement(
            trades=(
                _trade(
                    trade_id="900006001",
                    asset_category="OPT",
                    put_call="C",
                    strike="100",
                    side="BUY",
                    notes="A",
                    close_price="42.50",
                )
                + _trade(trade_id="900006002", close_price=None)
            )
        ),
    )
    import_flex_file(migrated_db, datei)
    mit_kurs = _spaltenwert(
        migrated_db, "SELECT schlusskurs FROM executions WHERE exec_id = :e", e="900006001"
    )
    assert Decimal(str(mit_kurs)) == Decimal("42.50")
    ohne_kurs = _spaltenwert(
        migrated_db, "SELECT schlusskurs FROM executions WHERE exec_id = :e", e="900006002"
    )
    assert ohne_kurs in (None, "")


def test_model_export_marks_realized_pnl_as_unavailable(migrated_db, tmp_path):
    """OF-21/OF-24: Trägt der Export Modell-Attribute, schaltet IB jedes Feld
    zum realisierten Ergebnis ab — ``fifoPnlRealized`` steht dann überall auf
    0. Der Importlauf hält das als Datenfeld fest
    (``import_runs.realized_pnl_verfuegbar``), damit kein Vergleich diese
    Nullen als Referenz nimmt. Ein Export ohne Modellzeilen bleibt wahr."""
    ohne_modell = _schreiben(
        tmp_path,
        "of21_ohne_modell.xml",
        _statement(trades=_trade(trade_id="900021001")),
    )
    mit_modell = _schreiben(
        tmp_path,
        "of21_mit_modell.xml",
        _statement(trades=_trade(trade_id="900021002", model="Independent")),
    )
    import_flex_file(migrated_db, ohne_modell)
    import_flex_file(migrated_db, mit_modell)

    erster = _spaltenwert(
        migrated_db,
        "SELECT realized_pnl_verfuegbar FROM import_runs ORDER BY id LIMIT 1",
    )
    zweiter = _spaltenwert(
        migrated_db,
        "SELECT realized_pnl_verfuegbar FROM import_runs ORDER BY id DESC LIMIT 1",
    )
    assert bool(erster) is True
    assert bool(zweiter) is False


def test_fx_rate_to_base_is_stored_on_executions(migrated_db, tmp_path):
    """OF-29: ``fxRateToBase`` einer Ausführung landet in
    ``executions.buchungskurs``, als ``Decimal`` — Grundlage des
    IB-vergleichbaren Geldtests (OF-23). Fehlt das Feld, bleibt die Spalte
    leer, kein Standardwert (Regel 10)."""
    datei = _schreiben(
        tmp_path,
        "of29_buchungskurs.xml",
        _statement(
            trades=(
                _trade(trade_id="900029001", fx_rate_to_base="0.9231")
                + _trade(trade_id="900029002", fx_rate_to_base=None)
            )
        ),
    )
    import_flex_file(migrated_db, datei)
    mit_kurs = _spaltenwert(
        migrated_db, "SELECT buchungskurs FROM executions WHERE exec_id = :e", e="900029001"
    )
    assert Decimal(str(mit_kurs)) == Decimal("0.9231")
    ohne_kurs = _spaltenwert(
        migrated_db, "SELECT buchungskurs FROM executions WHERE exec_id = :e", e="900029002"
    )
    assert ohne_kurs in (None, "")
