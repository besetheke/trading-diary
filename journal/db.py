"""Datenbankanbindung: SQLite im WAL-Modus, abgestimmt auf §4.1.

Der Options Roller hat Vorrang auf der gemeinsamen Datenbank. Deshalb:
kurze Transaktionen, ``busy_timeout`` gesetzt, und im Konfliktfall Abbrechen
statt Blockieren. ``journal_mode=WAL`` ist eine persistente Eigenschaft der
Datenbankdatei (die Initialmigration setzt sie ebenfalls); ``busy_timeout``
und ``foreign_keys`` gelten je Verbindung und werden bei jedem Connect
gesetzt.
"""

import pathlib

from sqlalchemy import create_engine as _sqlalchemy_create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine

# Annahme, dokumentiert in OFFENE_FRAGEN.md (OF-03): Der Plan schreibt den
# busy_timeout vor, nennt aber keinen Wert. 5 s halten den Schreiber kurz,
# ohne dem Roller im Weg zu stehen; je Aufruf überschreibbar.
STANDARD_BUSY_TIMEOUT_MS = 5000


def create_db_engine(
    pfad: str | pathlib.Path, *, busy_timeout_ms: int = STANDARD_BUSY_TIMEOUT_MS
) -> Engine:
    """Engine für eine SQLite-Datei mit den Pragmas aus §4.1."""
    pfad = pathlib.Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    engine = _sqlalchemy_create_engine(f"sqlite:///{pfad.as_posix()}")

    @event.listens_for(engine, "connect")
    def _setze_pragmas(dbapi_verbindung, _verbindungseintrag):  # noqa: ANN001
        cursor = dbapi_verbindung.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}")
        # Fremdschlüssel sind im SQLite-Treiber abgeschaltet; das Schema
        # lebt von ihnen, deshalb an.
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine
