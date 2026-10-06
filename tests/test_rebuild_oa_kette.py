"""Abnahmetests für AP-13z: Der OA-Abgleich (Strategie/Status/Erkennung)
gilt auch für die Kettensicht (`sicht='kette'`), nicht nur für die Kontosicht.

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-13z.md`.

Der Bestand ist das OF-36-Muster aus `tests/test_rebuild_kette.py`: A1
(oa_trade 100) wird von B1 (oa_trade 200, 'Open Order') kontoweit
geschlossen; B1 eröffnet seinen eigenen Vorgang erst in der Kettensicht
(zusammen mit B2). Nur dort trägt Vorgang 200 beide Beine, die OA nennt.
"""

from datetime import date, datetime
from decimal import Decimal

from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import chains, import_runs, optionapp_legs, optionapp_trades, structures

INSTRUMENTE = [
    dict(conid=601, symbol="SPX   260918P5000", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5000"), right="P",
         multiplikator=Decimal("100"), waehrung="USD"),
    dict(conid=701, symbol="SPX   260918C5200", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5200"), right="C",
         multiplikator=Decimal("100"), waehrung="USD"),
]

AUSFUEHRUNGEN = [
    dict(exec_id="A1", conid=601, side="SELL", preis=Decimal("12.00"),
         handelszeit=datetime(2026, 9, 1, 10, 0, 0), oa_trade="100", oa_order="1",
         oa_rolle="Open Order"),
    dict(exec_id="B1", conid=601, side="BUY", preis=Decimal("3.00"),
         handelszeit=datetime(2026, 9, 5, 10, 0, 0), oa_trade="200", oa_order="1",
         oa_rolle="Open Order"),
    dict(exec_id="B2", conid=701, side="SELL", preis=Decimal("5.00"),
         handelszeit=datetime(2026, 9, 5, 10, 0, 0), oa_trade="200", oa_order="1",
         oa_rolle="Open Order"),
    dict(exec_id="B3", conid=601, side="SELL", preis=Decimal("2.00"),
         handelszeit=datetime(2026, 9, 10, 10, 0, 0), oa_trade="200", oa_order="2",
         oa_rolle="Close Order"),
]

# (richtung, right, strike) je Leg
LEGS_100 = [(-1, "P", "5000")]
LEGS_200 = [(1, "P", "5000"), (-1, "C", "5200")]


def _oa_trade(db_pfad, *, oa_trade, legs, strategie, status="CLOSED", profit="100.00") -> None:
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(
            insert(import_runs).values(
                quelle="optionapp", datei_hash=f"oa-kette-{oa_trade}",
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
                strikes_roh="-", menge_zaehler=Decimal("1"), menge_nenner=Decimal("1"),
                offen_preis=None, schluss_preis=None, stop_roh="-", stop_wert=None,
                profit=Decimal(profit), profit_waehrung="USD", status=status, roh_json="{}",
            )
        ).inserted_primary_key[0]
        for position, (richtung, recht, strike) in enumerate(legs, start=1):
            verbindung.execute(
                insert(optionapp_legs).values(
                    optionapp_trade_id=trade_id, position=position, richtung=richtung,
                    menge=Decimal("1"), right=recht, strike=Decimal(strike),
                    expiry=date(2026, 9, 18), roh=f"{richtung}{recht}{strike}",
                )
            )


def _ketten(db_pfad, sicht: str) -> list[dict]:
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        return [
            dict(z)
            for z in verbindung.execute(select(chains).where(chains.c.sicht == sicht)).mappings()
        ]


def _strukturen(db_pfad, sicht: str) -> list[dict]:
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        return [
            dict(z)
            for z in verbindung.execute(
                select(structures).where(structures.c.sicht == sicht)
            ).mappings()
        ]


def _aufbauen(db_pfad) -> None:
    befuelle(db_pfad, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    _oa_trade(db_pfad, oa_trade="100", legs=LEGS_100, strategie="SPX: Alt")
    _oa_trade(db_pfad, oa_trade="200", legs=LEGS_200, strategie="SPX: Neu")


def test_kettensicht_ketten_tragen_die_oa_strategie(migrated_db):
    _aufbauen(migrated_db)

    rebuild(migrated_db)

    strategien = {k["oa_strategie"] for k in _ketten(migrated_db, "kette")}
    assert "SPX: Neu" in strategien
    assert "SPX: Alt" in strategien
    for kette in _ketten(migrated_db, "kette"):
        if kette["oa_strategie"] is not None:
            assert kette["oa_erkennung"] in ("auto", "heuristik", "manuell")
            assert kette["oa_status"] == "CLOSED"


def test_strukturen_der_kettensicht_tragen_dieselben_oa_werte_wie_ihre_kette(migrated_db):
    _aufbauen(migrated_db)

    rebuild(migrated_db)

    neu = [s for s in _strukturen(migrated_db, "kette") if s["oa_strategie"] == "SPX: Neu"]
    assert neu, "keine Kettensicht-Struktur mit der Strategie des Vorgangs 200"
    assert all(s["oa_status"] == "CLOSED" for s in neu)
    assert all(s["oa_erkennung"] is not None for s in neu)


def test_fingerabdruck_trifft_nur_in_der_kettensicht_vollstaendig(migrated_db):
    # Vorgang 200 hat laut OA zwei Beine (Long Put 5000, Short Call 5200).
    # In der Kettensicht trägt er beide (B1+B2): Fingerabdruck stimmt, 'auto'.
    # In der Kontosicht fehlt B1 (verbraucht, um A1 zu schließen): dort kann
    # der Fingerabdruck nicht vollständig stimmen — nie 'auto'.
    _aufbauen(migrated_db)

    rebuild(migrated_db)

    kette_neu = [k for k in _ketten(migrated_db, "kette") if k["oa_strategie"] == "SPX: Neu"]
    assert len(kette_neu) == 1
    assert kette_neu[0]["oa_erkennung"] == "auto"
    konto_neu = [k for k in _ketten(migrated_db, "konto") if k["oa_strategie"] == "SPX: Neu"]
    assert all(k["oa_erkennung"] != "auto" for k in konto_neu)


def test_kontosicht_und_zaehlwerte_bleiben_wie_bisher(migrated_db):
    _aufbauen(migrated_db)

    ergebnis = rebuild(migrated_db)

    konto = _ketten(migrated_db, "konto")
    assert ergebnis.oa_zugeordnet == sum(1 for k in konto if k["oa_strategie"] is not None)
    assert ergebnis.oa_fehler == 0


def test_zweiter_lauf_entfernt_veraltete_oa_werte_auch_in_der_kettensicht(migrated_db):
    _aufbauen(migrated_db)
    rebuild(migrated_db)
    assert any(k["oa_strategie"] for k in _ketten(migrated_db, "kette"))

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        verbindung.execute(optionapp_legs.delete())
        verbindung.execute(optionapp_trades.delete())

    rebuild(migrated_db)

    for kette in _ketten(migrated_db, "kette"):
        assert kette["oa_strategie"] is None
        assert kette["oa_status"] is None
        assert kette["oa_erkennung"] is None
    for struktur in _strukturen(migrated_db, "kette"):
        assert struktur["oa_strategie"] is None
