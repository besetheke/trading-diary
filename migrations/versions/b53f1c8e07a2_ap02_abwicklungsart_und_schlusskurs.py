"""AP-02: Abwicklungsart am Instrument, Schlusskurs an der Ausführung

Revision ID: b53f1c8e07a2
Revises: c4b1f0a9d2e7
Create Date: 2026-09-13 11:00:00.000000

Regel 6 der AP-02-Nachbesserung (AP-02k, OF-25): Das Matching (AP-03,
Regel 7) muss bei Zuteilung und Ausübung zwischen Barausgleich und
Lieferung unterscheiden — das entscheidet, ob eine Positionsänderung oder
nur ein Geldfluss vorliegt. Beide Werte kommen aus dem Flex-Export:

- ``instruments.abwicklungsart`` aus ``SecurityInfo.settlementPolicyMethod``
  (``Delivery`` → ``lieferung``, ``Cash`` → ``barausgleich``, fehlend bleibt
  leer). Der Import bricht bei unbekannten gesetzten Werten ab; das CHECK
  zusätzlich am Schema fängt alles ab, was nicht über den Import hineinkommt.
- ``executions.schlusskurs`` aus ``Trade.closePrice`` — der Kurs, zu dem eine
  Zuteilung oder Ausübung abgerechnet wird (im Geldtest belegt: der
  Barausgleich steht dort, nicht im tradePrice). Als ExactDecimal, leer, wenn
  das Feld fehlt.

Beide Spalten sind rein ergänzend; bestehende Zeilen bleiben unangetastet
und werden beim nächsten Import gefüllt.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'b53f1c8e07a2'
down_revision: str | None = 'c4b1f0a9d2e7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('instruments', sa.Column('abwicklungsart', sa.Text(), nullable=True))
    # SQLite kennt kein ALTER CONSTRAINT; der Batch-Weg baut die Tabelle neu
    # auf, die Daten bleiben erhalten (wie in 0366113de717).
    with op.batch_alter_table('instruments') as batch:
        batch.create_check_constraint(
            'ck_instruments_abwicklungsart',
            "abwicklungsart IN ('lieferung', 'barausgleich')",
        )
    op.add_column('executions', sa.Column('schlusskurs', ExactDecimal(), nullable=True))


def downgrade() -> None:
    op.drop_column('executions', 'schlusskurs')
    with op.batch_alter_table('instruments') as batch:
        batch.drop_constraint('ck_instruments_abwicklungsart', type_='check')
        batch.drop_column('abwicklungsart')
