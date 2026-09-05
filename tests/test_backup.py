"""Backup nach §3 / AP-01-Abnahme: `VACUUM INTO` erzeugt eine konsistente
Kopie, während ein Schreibzugriff läuft — kein Dateikopieren bei aktivem WAL,
keine Blockade des Options Rollers (§4.1).

Der Snapshot enthält genau den committeten Stand: die offene, nicht
committete Änderung des Schreibers fehlt in der Kopie.
"""

import pytest
from sqlalchemy import select

from journal.backup import create_backup
from journal.db import create_db_engine
from journal.schema import executions


def _exec_ids(db_pfad):
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return {zeile[0] for zeile in verbindung.execute(select(executions.c.exec_id))}


def test_backup_copies_committed_state_while_writer_transaction_is_open(
    migrated_db, tmp_path, sample_execution
):
    ziel = tmp_path / "backups" / "stand.sqlite"

    # committeter Grundstand
    quelle = create_db_engine(migrated_db)
    with quelle.begin() as verbindung:
        sample_execution(verbindung, exec_id="EXEC-1")

    # zweiter Schreiber hält eine offene, NICHT committete Transaktion
    schreiber = create_db_engine(migrated_db)
    verbindung = schreiber.connect()
    transaktion = verbindung.begin()
    sample_execution(verbindung, exec_id="EXEC-2")

    # Backup muss möglich sein, ohne auf den Schreiber zu warten
    create_backup(migrated_db, ziel)

    assert _exec_ids(ziel) == {"EXEC-1"}, (
        "Snapshot soll den committeten Stand enthalten und die offene "
        "Änderung nicht vorwegnehmen"
    )

    # nach dem Commit enthält das nächste Backup auch die neue Zeile
    transaktion.commit()
    verbindung.close()

    ziel2 = tmp_path / "backups" / "stand-2.sqlite"
    create_backup(migrated_db, ziel2)
    assert _exec_ids(ziel2) == {"EXEC-1", "EXEC-2"}


def test_backup_refuses_to_overwrite_existing_target(migrated_db, tmp_path):
    ziel = tmp_path / "vorhanden.sqlite"
    ziel.write_bytes(b"keine datenbank")
    with pytest.raises(FileExistsError):
        create_backup(migrated_db, ziel)
    assert ziel.read_bytes() == b"keine datenbank", "Bestehende Dateien bleiben unangetastet"


def test_backup_fails_on_missing_source(tmp_path):
    fehlend = tmp_path / "gibt-es-nicht.sqlite"
    ziel = tmp_path / "ziel.sqlite"
    with pytest.raises(FileNotFoundError):
        create_backup(fehlend, ziel)
    assert not ziel.exists()
