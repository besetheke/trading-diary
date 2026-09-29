"""Abnahmetests für AP-13w: OA-Strategie/-Status/-Erkennung an Kette und
Struktur — Persistenz-Anbindung von `engine.oa_abgleich` in
`journal/rebuild.py` (neues Modul `journal/oa_persistenz.py`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-13w.md`.

Eigener, in sich geschlossener Bestand (SPX) statt
`fixtures_rebuild.AUSFUEHRUNGEN` (DAX/ESTX50/IDX9) — jene Datei ist
gemeinsames Fixture vieler bestehender, unveränderlicher Tests, die ihre
Zeilenzahlen genau prüfen (Regel 1); hier kommt nichts hinein, was dort
nicht schon stand.
"""

from datetime import date, datetime
from decimal import Decimal

from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import chains, import_runs, optionapp_legs, optionapp_trades, structures

INSTRUMENTE_SPX = [
    dict(conid=601, symbol="SPX   260918P5000", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5000"), right="P",
         multiplikator=Decimal("100"), waehrung="USD"),
]

AUSFUEHRUNGEN_SPX = [
    dict(exec_id="S1", conid=601, side="SELL", preis=Decimal("12.00"),
         handelszeit=datetime(2026, 9, 1, 10, 0, 0), oa_trade="10", oa_order="1"),
    dict(exec_id="S2", conid=601, side="BUY", preis=Decimal("6.00"),
         handelszeit=datetime(2026, 9, 15, 15, 0, 0), oa_trade="10", oa_order="1"),
]


def _optionapp_trade(
    db_pfad, *, oa_trade, richtig_strike="5000", profit="500.00", strategie="SPX: IC",
    status="CLOSED",
) -> None:
    """Legt einen OA-Trade mit genau einem Leg (Short Put, wie AUSFUEHRUNGEN_SPX) an."""
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(
            insert(import_runs).values(
                quelle="optionapp", datei_hash=f"oa-fixture-{oa_trade}",
                importiert_am=datetime(2026, 9, 20, 6, 0, 0), qualitaetsstufe="A",
                zeilen_gesamt=1, zeilen_neu=1,
            )
        ).inserted_primary_key[0]
        trade_id = verbindung.execute(
            insert(optionapp_trades).values(
                import_run_id=lauf, oa_trade=oa_trade,
                entry_zeit=datetime(2026, 9, 1, 10, 0, 0),
                schluss_zeit=datetime(2026, 9, 15, 15, 0, 0),
                strategie=strategie, name_roh=f"Test [{oa_trade}]",
                strikes_roh=f"-1P{richtig_strike}",
                menge_zaehler=Decimal("1"), menge_nenner=Decimal("1"),
                offen_preis=None, schluss_preis=None, stop_roh="-", stop_wert=None,
                profit=Decimal(profit), profit_waehrung="USD", status=status, roh_json="{}",
            )
        ).inserted_primary_key[0]
        verbindung.execute(
            insert(optionapp_legs).values(
                optionapp_trade_id=trade_id, position=1, richtung=-1, menge=Decimal("1"),
                right="P", strike=Decimal(richtig_strike), expiry=date(2026, 9, 18),
                roh=f"-1P{richtig_strike}",
            )
        )


def _kette_zeile(db_pfad) -> dict:
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        return dict(verbindung.execute(select(chains)).mappings().one())


def _struktur_zeilen(db_pfad) -> list[dict]:
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        return [dict(z) for z in verbindung.execute(select(structures)).mappings()]


def test_treffer_schreibt_strategie_status_erkennung_an_kette_und_struktur(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_SPX, instrumente_=INSTRUMENTE_SPX)
    _optionapp_trade(migrated_db, oa_trade="10", status="CLOSED")

    rebuild(migrated_db)

    kette = _kette_zeile(migrated_db)
    assert kette["oa_strategie"] == "SPX: IC"
    assert kette["oa_status"] == "CLOSED"
    assert kette["oa_erkennung"] == "auto"

    strukturen = _struktur_zeilen(migrated_db)
    assert len(strukturen) == 1
    assert strukturen[0]["oa_strategie"] == "SPX: IC"
    assert strukturen[0]["oa_status"] == "CLOSED"
    assert strukturen[0]["oa_erkennung"] == "auto"


def test_abweichender_fingerabdruck_schreibt_heuristik_statt_auto(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_SPX, instrumente_=INSTRUMENTE_SPX)
    # Falscher Strike im Export (4900 statt 5000) — die Nummer matcht, der
    # Fingerabdruck nicht.
    _optionapp_trade(migrated_db, oa_trade="10", richtig_strike="4900")

    rebuild(migrated_db)

    kette = _kette_zeile(migrated_db)
    assert kette["oa_erkennung"] == "heuristik"


def test_ohne_importierte_oa_trades_bleiben_die_felder_leer(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_SPX, instrumente_=INSTRUMENTE_SPX)

    rebuild(migrated_db)

    kette = _kette_zeile(migrated_db)
    assert kette["oa_strategie"] is None
    assert kette["oa_status"] is None
    assert kette["oa_erkennung"] is None


def test_zweiter_lauf_entfernt_eine_veraltete_zuordnung(migrated_db):
    # Erster Lauf: Zuordnung entsteht. Zweiter Lauf ohne den OA-Trade (z. B.
    # weil der Export nicht mehr vorliegt): die Felder müssen zurück auf
    # None fallen, nicht die alte Zuordnung behalten (Vertrag: Abgleich
    # statt Neuanlage gilt auch für diese drei Spalten).
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_SPX, instrumente_=INSTRUMENTE_SPX)
    _optionapp_trade(migrated_db, oa_trade="10")
    rebuild(migrated_db)
    assert _kette_zeile(migrated_db)["oa_erkennung"] == "auto"

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        verbindung.execute(optionapp_legs.delete())
        verbindung.execute(optionapp_trades.delete())

    rebuild(migrated_db)

    kette = _kette_zeile(migrated_db)
    assert kette["oa_strategie"] is None
    assert kette["oa_status"] is None
    assert kette["oa_erkennung"] is None
