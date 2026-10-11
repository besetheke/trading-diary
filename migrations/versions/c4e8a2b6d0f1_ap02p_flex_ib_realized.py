"""AP-02p: flex_ib_realized — IBs realisiertes Ergebnis je Ausführung

Revision ID: c4e8a2b6d0f1
Revises: b9d3e5a7c1f4
Create Date: 2026-10-11 12:00:00.000000

``fifoPnlRealized`` liegt bisher nur in ``executions.roh_json`` und fehlt dort
bei Ausführungen, die eine ältere Abfrage ohne das Feld zuerst lieferte — die
erste Quelle gewinnt, ``executions`` wird nie überschrieben (Regel 4; OF-78,
11.949 Zeilen). Die neue Tabelle hält IBs Wert getrennt je Ausführung und
nimmt ihn auch dann auf, wenn die Ausführung schon bekannt ist. Nur neue
Tabelle, keine bestehenden Daten betroffen.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'c4e8a2b6d0f1'
down_revision: str | None = 'b9d3e5a7c1f4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'flex_ib_realized',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('import_run_id', sa.Integer(), sa.ForeignKey('import_runs.id'), nullable=False),
        sa.Column('konto', sa.Text(), nullable=False),
        sa.Column('quell_schluessel', sa.Text(), nullable=False),
        sa.Column('exec_id', sa.Text(), nullable=False),
        sa.Column('handelstag', sa.Date(), nullable=False),
        sa.Column('conid', sa.BigInteger(), nullable=False),
        sa.Column('waehrung', sa.Text(), nullable=False),
        sa.Column('fifo_pnl_realized', ExactDecimal(), nullable=False),
        sa.Column('fx_rate_to_base', ExactDecimal(), nullable=True),
        sa.UniqueConstraint('konto', 'quell_schluessel', name='uq_flex_ib_realized_quell_schluessel'),
    )
    op.create_index('ix_flex_ib_realized_import_run_id', 'flex_ib_realized', ['import_run_id'])
    op.create_index('ix_flex_ib_realized_exec_id', 'flex_ib_realized', ['exec_id'])
    op.create_index('ix_flex_ib_realized_handelstag', 'flex_ib_realized', ['handelstag'])


def downgrade() -> None:
    op.drop_index('ix_flex_ib_realized_handelstag', table_name='flex_ib_realized')
    op.drop_index('ix_flex_ib_realized_exec_id', table_name='flex_ib_realized')
    op.drop_index('ix_flex_ib_realized_import_run_id', table_name='flex_ib_realized')
    op.drop_table('flex_ib_realized')
