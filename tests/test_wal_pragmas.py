"""Pragmas aus §4.1: WAL-Modus, busy_timeout, Fremdschlüssel.

Der Options Roller hat Vorrang auf der Datenbank — jede Verbindung, die das
Journal öffnet, muss diese Einstellungen tragen.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from journal.db import STANDARD_BUSY_TIMEOUT_MS, create_db_engine


def test_engine_sets_wal_busy_timeout_and_foreign_keys(migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        assert verbindung.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
        assert (
            verbindung.execute(text("PRAGMA busy_timeout")).scalar_one()
            == STANDARD_BUSY_TIMEOUT_MS
        )
        assert verbindung.execute(text("PRAGMA foreign_keys")).scalar_one() == 1


def test_busy_timeout_is_configurable_per_engine(migrated_db):
    engine = create_db_engine(migrated_db, busy_timeout_ms=1234)
    with engine.connect() as verbindung:
        assert verbindung.execute(text("PRAGMA busy_timeout")).scalar_one() == 1234


def test_engine_creates_missing_database_and_parent_directories(tmp_path):
    tiefer_pfad = tmp_path / "noch" / "tiefer" / "journal.sqlite"
    engine = create_db_engine(tiefer_pfad)
    with engine.connect() as verbindung:
        assert verbindung.execute(text("SELECT 1")).scalar_one() == 1
    assert tiefer_pfad.is_file()


def test_writer_conflict_fails_after_busy_timeout_instead_of_blocking(tmp_path):
    """§4.1: im Konfliktfall abbrechen statt blockieren. Hält ein Schreiber
    eine offene Transaktion, bricht der konkurrierende Schreibzugriff nach
    Ablauf des busy_timeout mit einem Fehler ab — er wartet nicht endlos
    und stößt den Roller nicht."""
    db_pfad = tmp_path / "gesperrt.sqlite"
    einrichtung = create_db_engine(db_pfad)
    with einrichtung.begin() as verbindung:
        verbindung.execute(text("CREATE TABLE t (x INTEGER)"))

    schreiber = create_db_engine(db_pfad)
    verbindung = schreiber.connect()
    transaktion = verbindung.begin()
    try:
        verbindung.execute(text("INSERT INTO t VALUES (1)"))

        konkurrenz = create_db_engine(db_pfad, busy_timeout_ms=50)
        with pytest.raises(OperationalError), konkurrenz.connect() as andere:
            andere.execute(text("INSERT INTO t VALUES (2)"))
    finally:
        transaktion.rollback()
        verbindung.close()
