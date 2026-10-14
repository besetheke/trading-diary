"""Roller-Ketten mit den Journal-Ketten verknüpfen (AP-11, Teil 1).

Der Options Roller kennzeichnet jede Order mit ``orderRef = R3|<Kette>|<Strategie>``
(z. B. ``R3|K002|T SPX: BPS D20 W25 7DTE``). IB liefert den Wert im Flex-Export als
``orderReference``; ``executions.order_reference`` trägt ihn roh. Aus der Ausführung
folgen über ``legs`` → ``chain_links`` die Journal-Ketten. Die Verknüpfung steht in
``roller_link`` und ist ein **Beleg** (Order-Identität), keine Vermutung — ``methode``
trägt ``auto: orderReference`` (Regel 7).

- Idempotent: vorhandene Zeilen bleiben, es wird nie überschrieben oder gelöscht (Regel 4).
- Je Roller-Kette gilt die Kettensicht (``sicht='kette'``); gibt es dort keine Kette, die
  Kontosicht. So zählt eine Ausführung nicht doppelt.
- Keine Zeit aus der Uhr: ``jetzt`` kommt vom Aufrufer.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Connection, insert, or_, select

from journal.schema import chain_links, chains, executions, legs, roller_link

ROLLER_REFERENZ = re.compile(r"^R3\|(K\d+)\|(.*)$")
METHODE = "auto: orderReference"


@dataclass
class RollerVerknuepfung:
    ausfuehrungen: int = 0          # Ausführungen mit Roller-Kennzeichnung
    neu: int = 0                    # neu angelegte roller_link-Zeilen
    bereits: int = 0                # schon vorhanden
    ohne_kette: list[str] = field(default_factory=list)   # Roller-Ketten ohne Journal-Kette


def verknuepfe_roller(verbindung: Connection, jetzt: datetime) -> RollerVerknuepfung:
    """Legt für jede Roller-Kette ``roller_link``-Zeilen an. Schreibt nur in ``roller_link``."""
    erg = RollerVerknuepfung()
    zeilen = verbindung.execute(
        select(executions.c.exec_id, executions.c.order_reference).where(
            executions.c.order_reference.like("R3|%")
        )
    ).all()
    je_kette: dict[str, set[str]] = {}
    for exec_id, referenz in zeilen:
        treffer = ROLLER_REFERENZ.match(referenz or "")
        if treffer is None:
            continue
        erg.ausfuehrungen += 1
        je_kette.setdefault(treffer.group(1), set()).add(exec_id)

    for roller_kette, exec_ids in sorted(je_kette.items()):
        struktur_ids = {
            z[0] for z in verbindung.execute(
                select(legs.c.structure_id).where(
                    or_(legs.c.open_exec_id.in_(exec_ids), legs.c.close_exec_id.in_(exec_ids)),
                    legs.c.structure_id.is_not(None),
                )
            )
        }
        ketten_ids: set[int] = set()
        for sicht in ("kette", "konto"):
            ketten_ids = {
                z[0] for z in verbindung.execute(
                    select(chain_links.c.chain_id)
                    .join(chains, chains.c.chain_id == chain_links.c.chain_id)
                    .where(chain_links.c.structure_id.in_(struktur_ids), chains.c.sicht == sicht)
                )
            } if struktur_ids else set()
            if ketten_ids:
                break
        if not ketten_ids:
            erg.ohne_kette.append(roller_kette)
            continue
        vorhanden = {
            z[0] for z in verbindung.execute(
                select(roller_link.c.journal_chain_id).where(
                    roller_link.c.roller_chain_id == roller_kette)
            )
        }
        for chain_id in sorted(ketten_ids):
            if chain_id in vorhanden:
                erg.bereits += 1
                continue
            verbindung.execute(insert(roller_link).values(
                roller_chain_id=roller_kette, journal_chain_id=chain_id,
                zugeordnet_am=jetzt, methode=METHODE))
            erg.neu += 1
    return erg
