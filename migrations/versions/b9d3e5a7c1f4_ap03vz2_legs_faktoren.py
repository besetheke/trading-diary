"""AP-03vz2: legs.open_faktor und legs.close_faktor (Kapitalmaßnahmen und EUR-Analytik)

Revision ID: b9d3e5a7c1f4
Revises: aacd88fb9269
Create Date: 2026-10-11 09:00:00.000000

Nach einer Kapitalmaßnahme steht ``legs.menge`` in neuen Stücken, die
Ausführung (``executions``, unveränderlich, Regel 4) aber noch mit Menge und
Preis der alten. Wer Preis × Leg-Menge aus der Ausführung neu rechnet (EUR-
Kennzahlen, Equity, Kommissionsanteile, Prämien), brauchte den Faktor: Das
Matching speichert ihn je Leg für die Eröffnungs- und die Schließungsausführung
(neue ÷ alte Menge, mehrere Maßnahmen multiplizieren sich; 1 ohne Maßnahme).

Beide Spalten sind NOT NULL mit Serverstandard 1 — bestehende Zeilen sind damit
gültig; ``legs`` ist abgeleitet und wird bei jedem Rebuild vollständig neu
geschrieben.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'b9d3e5a7c1f4'
down_revision: str | None = 'aacd88fb9269'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('legs') as batch:
        batch.add_column(
            sa.Column('open_faktor', ExactDecimal(), nullable=False, server_default='1')
        )
        batch.add_column(
            sa.Column('close_faktor', ExactDecimal(), nullable=False, server_default='1')
        )


def downgrade() -> None:
    with op.batch_alter_table('legs') as batch:
        batch.drop_column('close_faktor')
        batch.drop_column('open_faktor')
