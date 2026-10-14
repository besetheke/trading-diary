"""Abnahmetest für AP-11 Teil 1: Roller-Ketten (`orderReference = R3|<Kette>|<Strategie>`)
werden über Ausführung → Leg → Struktur → Kettenglied mit Journal-Ketten verknüpft.

Erwartungen von Hand:
- Zwei Ausführungen mit `R3|K002|…` (Eröffnung und Roll) gehören zu zwei Strukturen derselben
  Journal-Kette 7 (Kettensicht) → eine `roller_link`-Zeile (K002 → 7), `methode` mit
  „orderReference“.
- Eine fremde Referenz (`OptionsApp: Trade 5, …`) und eine ohne Referenz werden nicht verknüpft.
- Zweiter Lauf: keine neue Zeile (idempotent), `bereits` = 1.
- Roller-Kette ohne Journal-Kette (Ausführung noch nicht im Bestand): in `ohne_kette`.
- Gibt es die Kette nur in der Kontosicht, gilt die; gibt es beide, zählt nur die Kettensicht.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.roller_verknuepfung import verknuepfe_roller
from journal.schema import chain_links, chains, legs, roller_link, structures

JETZT = datetime(2026, 10, 14, 7, 0, 0)


def _struktur(verbindung, structure_id, sicht="kette"):
    verbindung.execute(insert(structures).values(
        structure_id=structure_id, asset_class="OPT", typ="BPS", underlying="SPX",
        menge=Decimal("1"), eroeffnet_am=datetime(2026, 10, 13, 15, 0), waehrung="USD",
        erkennung="order_id",
        natur_schluessel=f"s{structure_id}-{sicht}", sicht=sicht))


def _kette(verbindung, chain_id, sicht="kette"):
    verbindung.execute(insert(chains).values(
        chain_id=chain_id, underlying="SPX", asset_class="OPT",
        eroeffnet_am=datetime(2026, 10, 13, 15, 0), anzahl_rolls=0,
        natur_schluessel=f"c{chain_id}-{sicht}", sicht=sicht))


def _glied(verbindung, chain_id, structure_id, sequenz=0, sicht="kette"):
    verbindung.execute(insert(chain_links).values(
        chain_id=chain_id, structure_id=structure_id, sequenz=sequenz, verknuepfungstyp="open",
        erkennung="auto", sicht=sicht))


def _leg(verbindung, leg_id, exec_id, structure_id, sicht="kette"):
    verbindung.execute(insert(legs).values(
        leg_id=leg_id, conid=1000 + leg_id, open_exec_id=exec_id, menge=Decimal("1"),
        matching_methode="fifo", offen_ja_nein=True, structure_id=structure_id, sicht=sicht))


def _aufbau(db, sample_execution, referenzen):
    engine = create_db_engine(db)
    with engine.begin() as v:
        for i, ref in enumerate(referenzen, start=1):
            sample_execution(v, exec_id=f"E{i}", conid=1000 + i, order_reference=ref)
    return engine


def test_verknuepft_ueber_ausfuehrung_und_ist_idempotent(migrated_db, sample_execution):
    strategie = "T SPX: BPS D20 W25 7DTE"
    engine = _aufbau(migrated_db, sample_execution,
                     [f"R3|K002|{strategie}", f"R3|K002|{strategie}",
                      "OptionsApp: Trade 5, Leg 1, Open Order 9", None])
    with engine.begin() as v:
        _kette(v, 7)
        for sid in (1, 2, 3):
            _struktur(v, sid)
        _glied(v, 7, 1, 0)
        _glied(v, 7, 2, 1)
        for leg_id, exec_id, sid in ((1, "E1", 1), (2, "E2", 2), (3, "E3", 3), (4, "E4", 3)):
            _leg(v, leg_id, exec_id, sid)
        erg = verknuepfe_roller(v, JETZT)
    assert (erg.ausfuehrungen, erg.neu, erg.bereits, erg.ohne_kette) == (2, 1, 0, [])
    with engine.connect() as v:
        zeilen = v.execute(select(roller_link)).mappings().all()
    assert len(zeilen) == 1
    assert (zeilen[0]["roller_chain_id"], zeilen[0]["journal_chain_id"]) == ("K002", 7)
    assert "orderReference" in zeilen[0]["methode"]
    with engine.begin() as v:
        zweit = verknuepfe_roller(v, datetime(2026, 10, 15))
    assert (zweit.neu, zweit.bereits) == (0, 1)
    with engine.connect() as v:
        # nicht überschrieben
        assert v.execute(select(roller_link.c.zugeordnet_am)).scalar() == JETZT


def test_roller_kette_ohne_journal_kette(migrated_db, sample_execution):
    engine = _aufbau(migrated_db, sample_execution, ["R3|K009|x"])
    with engine.begin() as v:
        erg = verknuepfe_roller(v, JETZT)
    assert (erg.ausfuehrungen, erg.neu, erg.ohne_kette) == (1, 0, ["K009"])


def test_kettensicht_hat_vorrang_vor_kontosicht(migrated_db, sample_execution):
    engine = _aufbau(migrated_db, sample_execution, ["R3|K001|x"])
    with engine.begin() as v:
        _kette(v, 10, "kette")
        _kette(v, 20, "konto")
        _struktur(v, 1, "kette")
        _struktur(v, 2, "konto")
        _glied(v, 10, 1, sicht="kette")
        _glied(v, 20, 2, sicht="konto")
        _leg(v, 1, "E1", 1, "kette")
        _leg(v, 2, "E1", 2, "konto")
        verknuepfe_roller(v, JETZT)
    with engine.connect() as v:
        ids = [z[0] for z in v.execute(select(roller_link.c.journal_chain_id))]
    assert ids == [10]


def test_nur_kontosicht_vorhanden(migrated_db, sample_execution):
    engine = _aufbau(migrated_db, sample_execution, ["R3|K001|x"])
    with engine.begin() as v:
        _kette(v, 20, "konto")
        _struktur(v, 2, "konto")
        _glied(v, 20, 2, sicht="konto")
        _leg(v, 2, "E1", 2, "konto")
        verknuepfe_roller(v, JETZT)
    with engine.connect() as v:
        assert [z[0] for z in v.execute(select(roller_link.c.journal_chain_id))] == [20]
