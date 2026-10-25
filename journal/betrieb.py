# ruff: noqa: E501
"""Betriebsläufe protokollieren (AP-17g, M04): Abruf, Import und Rebuild mit Ergebnis.

Eine kurze Zeile je Lauf in ``betriebslaeufe`` (kurze Transaktion, Regel 9: der Roller hat Vorrang). Ein Fehler beim Protokollieren
darf den eigentlichen Lauf nie verändern oder aufhalten.
"""
import pathlib
from datetime import datetime

from sqlalchemy import insert

from journal.db import create_db_engine
from journal.schema import betriebslaeufe

ARTEN = ("abruf", "import", "rebuild")
ERGEBNISSE = ("ok", "fehler", "teilweise")


def protokolliere(db_pfad: str | pathlib.Path, art: str, ergebnis: str, meldung: str | None = None,
                  beendet_am: datetime | None = None) -> bool:
    """Schreibt eine Zeile; ``False``, wenn es nicht möglich war (dann bleibt der eigentliche Lauf unberührt)."""
    if art not in ARTEN or ergebnis not in ERGEBNISSE:
        raise ValueError(f"unbekannte Art {art!r} oder Ergebnis {ergebnis!r}")
    try:
        with create_db_engine(db_pfad).begin() as verbindung:
            verbindung.execute(insert(betriebslaeufe).values(
                art=art, beendet_am=beendet_am or datetime.now(), ergebnis=ergebnis, meldung=(meldung or "")[:500] or None))
        return True
    except Exception:  # noqa: BLE001 — das Protokoll darf nie etwas aufhalten
        return False
