"""AP-02: buchungskurs (fxRateToBase) auf executions (OF-29)

Revision ID: e1f4a2c8b6d3
Revises: d7c4b6a1f9e3
Create Date: 2026-09-14 10:00:00.000000

OF-29: Der Geldtest (AP-03, letzter offener Punkt vor der Abnahme) braucht
den Umrechnungskurs, zu dem IB eine Ausführung in die Basiswährung bucht
(``fxRateToBase`` am rohen ``Trade``-Element) — ohne ihn lässt sich das
realisierte Ergebnis nicht IB-vergleichbar in Basiswährung ausdrücken
(OF-23, „Entschieden 13.09.2026, getrennt nach Zweck"). Das Feld wird bisher
nirgends im Journal geführt, roh oder normalisiert.

Neue Spalte ``executions.buchungskurs`` (nullable — ältere, unvollständige
Quellen könnten das Feld auslassen; kein Standardwert, s. Regel 10).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'e1f4a2c8b6d3'
down_revision: str | None = 'd7c4b6a1f9e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'executions',
        sa.Column('buchungskurs', ExactDecimal(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('executions', 'buchungskurs')
