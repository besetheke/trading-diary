"""Abnahmetests für AP-02 (Ingest Flex Query), geschrieben nach §11.2 des
Plans durch das starke Modell — für das günstige Modell unveränderlich.

Vertrag an die Umsetzung:

- Einstiegspunkt ist ``ingest.flex.import_flex_file(db_pfad, datei_pfad)``;
  Rückgabe ist ein Objekt mit ``zeilen_gesamt`` und ``zeilen_neu``.
- Bis ``ingest/flex.py`` existiert, springt dieses Modul still ab; sobald es
  existiert, laufen alle Tests scharf.
- Der Ereigniscode ``P`` kennzeichnet am Golden-Export eine gewöhnliche
  Teilausführung (``ExchTrade``, eigene ``ibExecID``, Börse gesetzt) und keine
  Buchung ohne Handelsbezug — die AP-02-Annahme ``ereignistyp='unbekannt'``
  war falsch (OF-07, korrigiert in AP-02k, OF-20). ``P`` ergibt ``trade``;
  ``ereignis_code`` bleibt als Rohwert erhalten.

**Schlüsselkorrektur AP-02a.** Die Erwartungen adressieren Ausführungen seit
AP-02a über ihre ``tradeID`` (111000001 …) statt über die ``transactionID``
(9000001 …). Grund: gemessen im Überschneidungszeitraum trägt die Spalte
``Transaction ID`` des TDP-Exports die ``tradeID``, 175 von 175 Treffern, null
gegen ``transactionID`` (§5, OF-10). Die Fixtures blieben dabei unverändert —
sie führen beide Felder von Anfang an. Geprüft wird dasselbe wie zuvor, nur
unter dem richtigen Schlüssel.

**Formatkorrektur AP-02k.** Der Golden-Lauf hat gezeigt: Der Import las kein
echtes Flex-XML (OF-19) — IB liefert ``dateTime`` statt ``tradeTime``, das
Zeitformat ``JJJJMMTT;HHMMSS`` (teils nur ``JJJJMMTT``), und jede Zeile trägt
``levelOfDetail``. Alle Fixtures unter ``fixtures/flex/`` sind inhaltlich
unverändert, nur auf dieses echte Format umgestellt. Gegen den unveränderten
``ingest/flex.py`` schlagen deshalb praktisch alle Tests dieses Moduls fehl —
das ist der Zweck des Korrekturpakets: Es legt die Zielform der Abnahme fest,
bevor ``ingest/flex.py`` nachgebessert wird.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import insert, select

pytest.importorskip("ingest.flex")

from ingest.flex import import_flex_file  # noqa: E402
from journal.schema import executions, import_runs  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flex"


def _importiere(db_pfad, dateiname):
    return import_flex_file(db_pfad, FIXTURES / dateiname)


def _exec_zeile(db_pfad, exec_id):
    from journal.db import create_db_engine

    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        zeile = verbindung.execute(
            select(executions).where(executions.c.exec_id == exec_id)
        ).mappings().one_or_none()
    return zeile


def _exec_ids(db_pfad):
    from journal.db import create_db_engine

    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return {z[0] for z in verbindung.execute(select(executions.c.exec_id))}


def test_import_reports_total_and_new_rows(migrated_db):
    ergebnis = _importiere(migrated_db, "activity_2026_01.xml")
    assert ergebnis.zeilen_gesamt == 10
    assert ergebnis.zeilen_neu == 10

    from journal.db import create_db_engine

    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        lauf = verbindung.execute(select(import_runs)).mappings().one()
    assert lauf["quelle"] == "flex"
    assert lauf["qualitaetsstufe"] == "A"
    assert lauf["zeilen_gesamt"] == 10
    assert lauf["zeilen_neu"] == 10


def test_double_import_creates_no_new_rows(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zweiter = _importiere(migrated_db, "activity_2026_01.xml")
    assert zweiter.zeilen_neu == 0
    assert zweiter.zeilen_gesamt == 10
    assert len(_exec_ids(migrated_db)) == 10


def test_overlapping_files_unite_without_duplicates(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zweiter = _importiere(migrated_db, "activity_2026_02_overlap.xml")
    assert zweiter.zeilen_gesamt == 3
    assert zweiter.zeilen_neu == 2
    assert _exec_ids(migrated_db) == {f"1110000{i:02d}" for i in range(1, 13)}


def test_event_rows_classified_from_notes(migrated_db):
    _importiere(migrated_db, "activity_events.xml")
    assert _exec_zeile(migrated_db, "112000001")["ereignistyp"] == "expiry"
    assert _exec_zeile(migrated_db, "112000002")["ereignistyp"] == "exercise"
    assert _exec_zeile(migrated_db, "112000003")["ereignistyp"] == "assignment"


def test_trade_rows_without_notes_are_trades(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    assert _exec_zeile(migrated_db, "111000001")["ereignistyp"] == "trade"


def test_partial_execution_code_p_is_a_trade(migrated_db):
    """OF-20: notes='P' kennzeichnet eine Teilausführung (ExchTrade, eigene
    ibExecID, Börse gesetzt) — eine gewöhnliche Ausführung, kein
    unklassifiziertes Ereignis. ereignis_code bleibt als Rohwert erhalten."""
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "111000008")
    assert zeile is not None, "P-Zeile darf nicht still verworfen werden"
    assert zeile["ereignistyp"] == "trade"
    assert zeile["ereignis_code"] == "P"


def test_exec_batch_is_first_two_segments_of_ib_exec_id(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    combo_kopf = _exec_zeile(migrated_db, "111000001")
    combo_bein = _exec_zeile(migrated_db, "111000002")
    assert combo_kopf["exec_batch"] == "0001.0002"
    assert combo_bein["exec_batch"] == "0001.0002"
    ereignis = _exec_zeile(migrated_db, "111000006")
    assert not ereignis["exec_batch"], "ohne ibExecID bleibt exec_batch leer"


def test_structured_order_reference_populates_oa_fields(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "111000001")
    assert zeile["oa_trade"] == "42"
    assert zeile["oa_leg"] == "1"
    assert zeile["oa_rolle"] == "Open Order"
    assert zeile["oa_order"] == "1"
    ziel = _exec_zeile(migrated_db, "111000010")
    assert ziel["oa_rolle"] == "Profit Target"


def test_generic_order_reference_keeps_oa_fields_empty(migrated_db):
    _importiere(migrated_db, "activity_generic_orderref.xml")
    for exec_id in ("113000001", "113000002", "113000003"):
        zeile = _exec_zeile(migrated_db, exec_id)
        assert zeile["order_reference"], "Rohwert ist zu erhalten"
        for feld in ("oa_trade", "oa_leg", "oa_rolle", "oa_order"):
            assert not zeile[feld], f"{feld} muss bei generischer Referenz leer bleiben"


def test_unknown_asset_category_fails_with_named_value(migrated_db):
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "activity_unknown_assetcategory.xml")
    assert "WARRANT" in str(fehler.value)


def test_sections_land_in_own_tables(migrated_db):
    from sqlalchemy import text

    from journal.db import create_db_engine

    _importiere(migrated_db, "activity_2026_01.xml")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        for tabelle, erwartet in (
            ("flex_securities_info", 4),
            ("flex_cash_transactions", 2),
            ("flex_open_positions", 1),
            ("flex_transfers", 0),
        ):
            anzahl = verbindung.execute(text(f"SELECT count(*) FROM {tabelle}")).scalar_one()
            assert anzahl == erwartet, f"{tabelle}: {anzahl} statt {erwartet}"


def test_executions_carry_amounts_as_decimal(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "111000001")
    assert zeile["menge"] == Decimal("2")
    assert zeile["preis"] == Decimal("3.10")
    assert zeile["kommission"] == Decimal("-2.00")
    assert zeile["expiry"].isoformat() == "2026-02-20"


def test_executions_carry_import_run_and_quality(migrated_db):
    _importiere(migrated_db, "activity_2026_01.xml")
    zeile = _exec_zeile(migrated_db, "111000009")
    assert zeile["qualitaetsstufe"] == "A"
    from journal.db import create_db_engine

    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        lauf_id = verbindung.execute(
            select(import_runs.c.id)
        ).scalar_one()
    assert zeile["import_run_id"] == lauf_id


# ---------------------------------------------------------------------------
# AP-02a · Schlüsselkorrektur und Reihenfolgeunabhängigkeit
#
# Die Testdaten dieser drei Tests entstehen im Test selbst: `fixtures/` ist in
# AP-02a ausdrücklich tabu, die Fälle brauchen aber eigene Perioden und eine
# Zeile ohne tradeID, die es in den Fixtures nicht gibt.
# ---------------------------------------------------------------------------

STATEMENT_RUMPF = """<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryname="Activity" type="Statement">
  <FlexStatements count="1">
    <FlexStatement accountId="U7777777" fromDate="{von}" toDate="{bis}"
                   period="Test" whenGenerated="{erzeugt}">
      <Trades>{trades}</Trades>
      <SecuritiesInfo>{stammdaten}</SecuritiesInfo>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
"""

# Echtes Format (AP-02k, OF-19): levelOfDetail an jeder Trades-Zeile,
# dateTime statt tradeTime, Zeitform JJJJMMTT;HHMMSS.
TRADE_RUMPF = (
    '<Trade levelOfDetail="EXECUTION" {trade_id}transactionID="{transaction_id}"'
    ' ibExecID="0077.0001.01.01"'
    ' ibOrderID="5559999" orderReference="" conid="{conid}" symbol="CORP"'
    ' underlyingSymbol="CORP" assetCategory="STK" buySell="BUY" quantity="10"'
    ' tradePrice="12.00" proceeds="-120.00" ibCommission="-1.00"'
    ' ibCommissionCurrency="USD" currency="USD" fxRateToBase="0.9200"'
    ' netCash="-121.00" dateTime="{zeit}" orderTime="{zeit}" exchange="MEMX"'
    ' notes="" openCloseIndicator="" />'
)

STAMMSATZ_RUMPF = (
    '<SecurityInfo conid="{conid}" symbol="CORP" underlyingSymbol="CORP"'
    ' assetCategory="STK" multiplier="{multiplikator}" currency="{waehrung}" />'
)


def _schreibe_xml(tmp_path, name, *, von, bis, erzeugt, trades="", stammdaten=""):
    ziel = tmp_path / name
    ziel.write_text(
        STATEMENT_RUMPF.format(
            von=von, bis=bis, erzeugt=erzeugt, trades=trades, stammdaten=stammdaten
        ),
        encoding="utf-8",
    )
    return ziel


def _trade(*, trade_id, transaction_id, conid="200001", zeit="20260305;153000"):
    """Eine Trades-Zeile; ``trade_id=None`` lässt das Attribut ganz weg."""
    return TRADE_RUMPF.format(
        trade_id="" if trade_id is None else f'tradeID="{trade_id}" ',
        transaction_id=transaction_id,
        conid=conid,
        zeit=zeit,
    )


def test_trade_row_without_tradeid_aborts_the_import(migrated_db, tmp_path):
    """tradeID ist Pflicht: fehlt sie, bricht der Import unter Nennung der
    betroffenen Zeile ab — kein Ausweichen auf einen Ersatzschlüssel (§5)."""
    datei = _schreibe_xml(
        tmp_path,
        "ohne_tradeid.xml",
        von="20260301",
        bis="20260331",
        erzeugt="20260401;031500",
        trades=(
            _trade(trade_id="111500001", transaction_id="9500001")
            + _trade(trade_id=None, transaction_id="9500002", zeit="20260306;153000")
        ),
    )
    with pytest.raises(ValueError) as fehler:
        import_flex_file(migrated_db, datei)
    meldung = str(fehler.value)
    assert "tradeID" in meldung
    assert "9500002" in meldung, "die betroffene Zeile muss benannt sein"
    assert _exec_ids(migrated_db) == set(), "vor dem Abbruch wird nichts geschrieben"


def test_older_master_data_does_not_overwrite_newer(migrated_db, tmp_path):
    """Stammdaten folgen dem Periodenende der Quelle, nicht der
    Importreihenfolge (§6.2). Beide Reihenfolgen liefern dasselbe Ergebnis."""
    alt = _schreibe_xml(
        tmp_path,
        "stammdaten_alt.xml",
        von="20260101",
        bis="20260131",
        erzeugt="20260201;031500",
        trades=_trade(trade_id="111600001", transaction_id="9600001", zeit="20260105;153000"),
        stammdaten=STAMMSATZ_RUMPF.format(conid="200001", multiplikator="1", waehrung="USD"),
    )
    neu = _schreibe_xml(
        tmp_path,
        "stammdaten_neu.xml",
        von="20260201",
        bis="20260228",
        erzeugt="20260301;031500",
        trades=_trade(trade_id="111600002", transaction_id="9600002", zeit="20260205;153000"),
        # Nach einem Split trägt dieselbe conid einen anderen Multiplikator.
        stammdaten=STAMMSATZ_RUMPF.format(conid="200001", multiplikator="2", waehrung="EUR"),
    )

    def _stammdaten(db_pfad):
        from journal.db import create_db_engine
        from journal.schema import flex_securities_info, instruments

        engine = create_db_engine(db_pfad)
        with engine.connect() as verbindung:
            info = verbindung.execute(select(flex_securities_info)).mappings().one()
            instrument = verbindung.execute(select(instruments)).mappings().one()
        return (
            (info["multiplikator"], info["waehrung"]),
            (instrument["multiplikator"], instrument["waehrung"]),
        )

    import_flex_file(migrated_db, neu)
    import_flex_file(migrated_db, alt)
    nach_rueckwaerts = _stammdaten(migrated_db)
    assert nach_rueckwaerts == (
        (Decimal("2"), "EUR"),
        (Decimal("2"), "EUR"),
    ), "der ältere Import darf den jüngeren Stand nicht überschreiben"

    zweite_db = tmp_path / "vorwaerts.sqlite"
    _neue_datenbank(zweite_db)
    import_flex_file(zweite_db, alt)
    import_flex_file(zweite_db, neu)
    assert _stammdaten(zweite_db) == nach_rueckwaerts, (
        "die Importreihenfolge darf das Ergebnis nicht verändern"
    )


def test_same_booking_from_two_overlapping_files_lands_once(migrated_db, tmp_path):
    """Überlappende Quelldateien: die gemeinsame Buchung steht genau einmal in
    ``executions`` — geschlüsselt über tradeID, quellenübergreifend (§5)."""
    erste = _schreibe_xml(
        tmp_path,
        "ueberlappung_a.xml",
        von="20260301",
        bis="20260315",
        erzeugt="20260316;031500",
        trades=_trade(trade_id="111700001", transaction_id="9700001"),
    )
    zweite = _schreibe_xml(
        tmp_path,
        "ueberlappung_b.xml",
        von="20260310",
        bis="20260331",
        erzeugt="20260401;031500",
        # Dieselbe Buchung, im zweiten Export mit abweichender transactionID —
        # so verhält sich der Broker laut §5; die tradeID bleibt gleich.
        trades=(
            _trade(trade_id="111700001", transaction_id="9700099")
            + _trade(trade_id="111700002", transaction_id="9700002", zeit="20260324;153000")
        ),
    )
    import_flex_file(migrated_db, erste)
    zweiter = import_flex_file(migrated_db, zweite)
    assert zweiter.zeilen_gesamt == 2
    assert zweiter.zeilen_neu == 1
    assert _exec_ids(migrated_db) == {"111700001", "111700002"}


def _neue_datenbank(db_pfad):
    """Zweite migrierte Datenbank innerhalb eines Tests (die Fixture liefert
    nur eine)."""
    import os

    from alembic import command
    from alembic.config import Config

    konfiguration = Config()
    konfiguration.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[1] / "migrations")
    )
    vorher = os.environ.get("JOURNAL_DB")
    os.environ["JOURNAL_DB"] = str(db_pfad)
    try:
        command.upgrade(konfiguration, "head")
    finally:
        if vorher is None:
            del os.environ["JOURNAL_DB"]
        else:
            os.environ["JOURNAL_DB"] = vorher


def test_import_run_reference_blocks_orphans(migrated_db):
    """executions.import_run_id ist ein Fremdschlüssel; ein Import ohne
    Importlauf kann nicht passieren — das Schema erzwingt es."""
    from datetime import datetime

    from sqlalchemy.exc import IntegrityError

    from journal.db import create_db_engine

    _importiere(migrated_db, "activity_2026_01.xml")
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung, pytest.raises(IntegrityError):
        verbindung.execute(
            insert(executions).values(
                exec_id="ORPHAN",
                konto="U7777777",
                conid=1,
                symbol="X",
                side="BUY",
                menge=Decimal("1"),
                preis=Decimal("1"),
                waehrung="USD",
                handelszeit=datetime(2026, 1, 1),
                ereignistyp="trade",
                roh_json="{}",
                qualitaetsstufe="A",
                import_run_id=999_999,
            )
        )
