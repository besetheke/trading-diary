"""AP-13w: OA-Strategie und -Status an Kette und Struktur

Revision ID: a3e8f1c9d426
Revises: d4f8b2c6a913
Create Date: 2026-09-29 09:00:00.000000

Plan §6, AP-13: „`Strategy` und `Status` ergänzen Kette und Strukturen.
Der `Status` überschreibt nie eine aus Brokerdaten abgeleitete Tatsache,
sondern ergänzt sie." Drei Spalten je Tabelle, alle entleerbar:

- ``oa_strategie`` — roh aus ``optionapp_trades.strategie``, unverändert.
- ``oa_status`` — roh aus ``optionapp_trades.status`` (EXPIRED/CLOSED/
  PARTIALLY STOPPED/…), eigener Name, damit er ``structures.status``
  (offen/geschlossen, aus Brokerdaten) nicht überschreibt, sondern daneben
  steht.
- ``oa_erkennung`` — Pflichtfeld für eine automatisch erzeugte Verknüpfung
  (CLAUDE.md Regel 7): ``auto`` oder ``heuristik``, je nachdem, ob der
  Fingerabdruck (``engine.oa_abgleich``) bestätigt hat. Leer, solange kein
  OA-Trade zugeordnet ist.

**Warum an beiden Tabellen.** Ein OA-Trade verknüpft sich mit genau einer
Kette (§6.1), aber die Strategie soll auch an der einzelnen Struktur
sichtbar sein (Drilldown, wie ``eroeffnungspreis``/``schlusspreis`` in
AP-07p) — derselbe Wert, auf jedes Kettenglied gespiegelt, weil OA seine
Kennung nicht feiner als je Trade vergibt.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3e8f1c9d426"
down_revision: str | None = "d4f8b2c6a913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABELLEN = ("structures", "chains")


def upgrade() -> None:
    for tabelle in _TABELLEN:
        with op.batch_alter_table(tabelle) as batch:
            batch.add_column(sa.Column("oa_strategie", sa.Text(), nullable=True))
            batch.add_column(sa.Column("oa_status", sa.Text(), nullable=True))
            batch.add_column(sa.Column("oa_erkennung", sa.Text(), nullable=True))
            batch.create_check_constraint(
                f"ck_{tabelle}_oa_erkennung",
                "oa_erkennung IN ('auto', 'heuristik')",
            )


def downgrade() -> None:
    for tabelle in _TABELLEN:
        with op.batch_alter_table(tabelle) as batch:
            batch.drop_constraint(f"ck_{tabelle}_oa_erkennung", type_="check")
            batch.drop_column("oa_erkennung")
            batch.drop_column("oa_status")
            batch.drop_column("oa_strategie")
