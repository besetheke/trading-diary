# ruff: noqa: E501
"""Stichtag des aktuellen Depotbestands (AP-17e, Review R03).

Bisher galt als Stichtag das Maximum der gespeicherten Positionszeilen. Ein neuer vollständiger Bericht ohne
eine einzige Position (Depot leer) erzeugt aber keine Zeile, der alte Bestand blieb „aktuell“. Der Kontowert je
Tag (``flex_nav_tage``) kommt täglich und kennt den Zustand: Ist der jüngste Kontowert **neuer** als die letzte
Positionszeile und weist **keine** Wertpapierpositionen aus, ist das Depot an diesem Tag leer; der Stichtag ist
dann der Tag des Kontowerts, und die Positionsabfragen liefern nichts. Weist der neuere Kontowert Positionen
aus, fehlte nur der Positionsabschnitt: der letzte Bestand bleibt (ein fehlender Abschnitt leert das Konto nicht).

„Keine Positionen“ heißt: Aktien und Optionen sind **bekannt** und genau 0, Rohstoffe, Fonds und Anleihen 0 oder
nicht gemeldet. Ein unbekannter Aktien- oder Optionswert gilt nicht als leer.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from journal.schema import flex_nav_tage, flex_open_positions


def aktueller_depot_stichtag(verbindung: Connection) -> date | None:
    """Stichtag des jüngsten gültigen Positionsstands (siehe Modul-Kopf); ``None`` ohne Positionszeile."""
    position = verbindung.execute(select(func.max(flex_open_positions.c.stichtag))).scalar()
    if position is None:
        return None
    nav = verbindung.execute(
        select(flex_nav_tage).order_by(flex_nav_tage.c.datum.desc()).limit(1)
    ).mappings().first()
    if nav is None or nav["datum"] <= position:
        return position
    bekannt_null = all(nav[s] is not None and Decimal(nav[s]) == 0 for s in ("aktien", "optionen"))
    sonst_null = all(nav[s] is None or Decimal(nav[s]) == 0 for s in ("rohstoffe", "fonds", "anleihen"))
    return nav["datum"] if bekannt_null and sonst_null else position
