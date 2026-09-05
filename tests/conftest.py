"""Gemeinsame Fixtures für die Testsuite.

Migrationsläufe gehen über die Alembic-Command-API gegen temporäre
Datenbankdateien (JOURNAL_DB); die Tests berühren nie eine echte Datenbank.
"""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import insert

from journal.schema import executions, import_runs

PROJEKTWURZEL = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_config():
    """Alembic-Konfiguration ohne alembic.ini, gerichtet auf migrations/."""
    konfiguration = Config()
    konfiguration.set_main_option("script_location", str(PROJEKTWURZEL / "migrations"))
    return konfiguration


@pytest.fixture
def migrated_db(tmp_path, monkeypatch, alembic_config):
    """Fährt die Initialmigration gegen eine leere Datei, liefert den Pfad."""
    db_pfad = tmp_path / "journal-test.sqlite"
    monkeypatch.setenv("JOURNAL_DB", str(db_pfad))
    command.upgrade(alembic_config, "head")
    return db_pfad


def insert_import_run(verbindung) -> int:
    """Legt einen Importlauf an und liefert dessen id."""
    ergebnis = verbindung.execute(
        insert(import_runs).values(
            quelle="flex",
            datei_hash="test-hash",
            importiert_am=datetime(2026, 9, 5, 4, 0, 0),
            zeitraum_von=None,
            zeitraum_bis=None,
            qualitaetsstufe="A",
            zeilen_gesamt=1,
            zeilen_neu=1,
        )
    )
    return ergebnis.inserted_primary_key[0]


@pytest.fixture
def sample_execution():
    """Fabrik für gültige execution-Zeilen; Abweichungen per Schlüsselwort.

    Ohne übergebene import_run_id wird ein eigener Importlauf angelegt.
    Alle Beträge als Decimal (CLAUDE.md, Regel 5).
    """

    def _anlegen(verbindung, exec_id="EXEC-1", import_run_id=None, **abweichungen):
        werte = {
            "exec_id": exec_id,
            "konto": "U1234567",
            "conid": 44473818,
            "symbol": "SPX",
            "side": "BUY",
            "menge": Decimal("1"),
            "preis": Decimal("10.25"),
            "waehrung": "USD",
            "handelszeit": datetime(2026, 9, 4, 15, 31, 0),
            "ereignistyp": "trade",
            "roh_json": "{}",
            "qualitaetsstufe": "A",
        }
        if import_run_id is None:
            import_run_id = insert_import_run(verbindung)
        werte["import_run_id"] = import_run_id
        werte.update(abweichungen)
        verbindung.execute(insert(executions).values(**werte))
        return exec_id

    return _anlegen
