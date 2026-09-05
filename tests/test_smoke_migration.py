"""Rauchtest (AP-01): die Initialmigration läuft gegen eine leere Datenbank,
legt alle Tabellen aus §5 an und ist rückabwickelbar. Dazu das
CHECK/FK-Verhalten, auf das die Abnahme von AP-02 baut („unbekannte
Feldwerte führen zu einem Fehler, nicht zu stillem Verwerfen“).
"""

import sqlite3

import pytest
from alembic import command
from sqlalchemy.exc import IntegrityError

from journal.schema import metadata


def _tabellen_lesen(db_pfad):
    verbindung = sqlite3.connect(db_pfad)
    try:
        return {
            zeile[0]
            for zeile in verbindung.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    finally:
        verbindung.close()


def test_initial_migration_on_empty_database_creates_all_plan_tables(migrated_db):
    tabellen = _tabellen_lesen(migrated_db)
    fehlen = set(metadata.tables) - tabellen
    assert not fehlen, f"Tabellen aus §5 fehlen: {sorted(fehlen)}"
    assert "alembic_version" in tabellen


def test_initial_migration_leaves_database_in_wal_mode(migrated_db):
    verbindung = sqlite3.connect(migrated_db)
    try:
        modus = verbindung.execute("PRAGMA journal_mode").fetchone()[0]
    finally:
        verbindung.close()
    assert modus == "wal"


def test_initial_migration_downgrade_removes_all_schema_tables(
    migrated_db, alembic_config, monkeypatch
):
    monkeypatch.setenv("JOURNAL_DB", str(migrated_db))
    command.downgrade(alembic_config, "base")
    uebrig = _tabellen_lesen(migrated_db)
    assert not set(metadata.tables) & uebrig
    assert uebrig == {"alembic_version"}


def test_unknown_ereignistyp_is_rejected_by_check_constraint(
    migrated_db, sample_execution
):
    from journal.db import create_db_engine

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung, pytest.raises(IntegrityError):
        sample_execution(verbindung, ereignistyp="phantasie")


def test_unknown_import_run_id_is_rejected_by_foreign_key(
    migrated_db, sample_execution
):
    from journal.db import create_db_engine

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung, pytest.raises(IntegrityError):
        sample_execution(verbindung, exec_id="EXEC-FK", import_run_id=999_999)
