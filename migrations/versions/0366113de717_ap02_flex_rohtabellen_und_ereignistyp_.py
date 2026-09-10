"""AP-02: Flex-Rohdaten-Tabellen und Ereignistyp 'unbekannt'

Revision ID: 0366113de717
Revises: 2c5c7d327f00
Create Date: 2026-09-06 15:08:21.245391

Erweitert den CHECK auf ``executions.ereignistyp`` um ``'unbekannt'`` — der
Ereigniscode ``P`` ist keinem der vier Typen aus §1.4 zuordenbar (OF-07) — und
legt die fünf Tabellen für die Flex-Sektionen aus §6.2 an (Rohdaten, AP-02).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal


# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = '0366113de717'
down_revision: str | None = '2c5c7d327f00'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EREIGNISTYP_ALT = "ereignistyp IN ('trade', 'expiry', 'exercise', 'assignment')"
EREIGNISTYP_NEU = (
    "ereignistyp IN ('trade', 'expiry', 'exercise', 'assignment', 'unbekannt')"
)


def _tausche_ereignistyp_check(wertebereich: str) -> None:
    """Ersetzt den CHECK auf ``executions.ereignistyp``.

    SQLite kennt kein ALTER CONSTRAINT; ``batch_alter_table`` baut die Tabelle
    deshalb neu auf (neu anlegen, Daten übernehmen, alte löschen, umbenennen).
    Primärschlüssel, Fremdschlüssel, der zweite CHECK und alle Indizes bleiben
    erhalten — die Migration ist damit auch auf bebilderter Datenbank
    verlustfrei. Alembic verbindet ohne das PRAGMA aus ``journal.db``, die
    Foreign-Key-Prüfung während der Migration ist daher aus.
    """
    with op.batch_alter_table('executions') as batch:
        batch.drop_constraint('ck_executions_ereignistyp', type_='check')
        batch.create_check_constraint('ck_executions_ereignistyp', wertebereich)


def upgrade() -> None:
    _tausche_ereignistyp_check(EREIGNISTYP_NEU)
    op.create_table('flex_open_positions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('import_run_id', sa.Integer(), nullable=False),
    sa.Column('conid', sa.BigInteger(), nullable=False),
    sa.Column('symbol', sa.Text(), nullable=False),
    sa.Column('asset_class', sa.Text(), nullable=False),
    sa.Column('menge', ExactDecimal(), nullable=False),
    sa.Column('kostenbasis_preis', ExactDecimal(), nullable=True),
    sa.Column('fifo_pnl_unrealisiert', ExactDecimal(), nullable=True),
    sa.Column('waehrung', sa.Text(), nullable=False),
    sa.Column('roh_json', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['import_run_id'], ['import_runs.id'], name=op.f('fk_flex_open_positions_import_run_id_import_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_flex_open_positions'))
    )
    op.create_index(op.f('ix_flex_open_positions_conid'), 'flex_open_positions', ['conid'], unique=False)
    op.create_index(op.f('ix_flex_open_positions_import_run_id'), 'flex_open_positions', ['import_run_id'], unique=False)
    op.create_table('flex_cash_transactions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('import_run_id', sa.Integer(), nullable=False),
    sa.Column('datum', sa.DateTime(), nullable=False),
    sa.Column('typ', sa.Text(), nullable=False),
    sa.Column('betrag', ExactDecimal(), nullable=False),
    sa.Column('waehrung', sa.Text(), nullable=False),
    sa.Column('beschreibung', sa.Text(), nullable=True),
    sa.Column('roh_json', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['import_run_id'], ['import_runs.id'], name=op.f('fk_flex_cash_transactions_import_run_id_import_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_flex_cash_transactions'))
    )
    op.create_index(op.f('ix_flex_cash_transactions_import_run_id'), 'flex_cash_transactions', ['import_run_id'], unique=False)
    op.create_table('flex_corporate_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('import_run_id', sa.Integer(), nullable=False),
    sa.Column('conid', sa.BigInteger(), nullable=True),
    sa.Column('typ', sa.Text(), nullable=False),
    sa.Column('datum', sa.DateTime(), nullable=False),
    sa.Column('beschreibung', sa.Text(), nullable=True),
    sa.Column('roh_json', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['import_run_id'], ['import_runs.id'], name=op.f('fk_flex_corporate_actions_import_run_id_import_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_flex_corporate_actions'))
    )
    op.create_index(op.f('ix_flex_corporate_actions_conid'), 'flex_corporate_actions', ['conid'], unique=False)
    op.create_index(op.f('ix_flex_corporate_actions_import_run_id'), 'flex_corporate_actions', ['import_run_id'], unique=False)
    op.create_table('flex_transfers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('import_run_id', sa.Integer(), nullable=False),
    sa.Column('conid', sa.BigInteger(), nullable=True),
    sa.Column('typ', sa.Text(), nullable=False),
    sa.Column('datum', sa.DateTime(), nullable=False),
    sa.Column('beschreibung', sa.Text(), nullable=True),
    sa.Column('roh_json', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['import_run_id'], ['import_runs.id'], name=op.f('fk_flex_transfers_import_run_id_import_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_flex_transfers'))
    )
    op.create_index(op.f('ix_flex_transfers_conid'), 'flex_transfers', ['conid'], unique=False)
    op.create_index(op.f('ix_flex_transfers_import_run_id'), 'flex_transfers', ['import_run_id'], unique=False)
    op.create_table('flex_securities_info',
    sa.Column('conid', sa.BigInteger(), nullable=False),
    sa.Column('symbol', sa.Text(), nullable=False),
    sa.Column('underlying', sa.Text(), nullable=True),
    sa.Column('asset_class', sa.Text(), nullable=False),
    sa.Column('expiry', sa.Date(), nullable=True),
    sa.Column('strike', ExactDecimal(), nullable=True),
    sa.Column('right', sa.Text(), nullable=True),
    sa.Column('multiplikator', ExactDecimal(), nullable=True),
    sa.Column('waehrung', sa.Text(), nullable=True),
    sa.Column('roh_json', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('conid', name=op.f('pk_flex_securities_info'))
    )


def downgrade() -> None:
    # Abwärts mit vorhandenen 'unbekannt'-Zeilen scheitert die Übernahme am
    # CHECK — gewollt: Die Zeilen wären sonst still unbrauchbar, der Fehler
    # nennt die Ursache.
    op.drop_table('flex_securities_info')
    op.drop_index(op.f('ix_flex_transfers_import_run_id'), table_name='flex_transfers')
    op.drop_index(op.f('ix_flex_transfers_conid'), table_name='flex_transfers')
    op.drop_table('flex_transfers')
    op.drop_index(op.f('ix_flex_corporate_actions_import_run_id'), table_name='flex_corporate_actions')
    op.drop_index(op.f('ix_flex_corporate_actions_conid'), table_name='flex_corporate_actions')
    op.drop_table('flex_corporate_actions')
    op.drop_index(op.f('ix_flex_cash_transactions_import_run_id'), table_name='flex_cash_transactions')
    op.drop_table('flex_cash_transactions')
    op.drop_index(op.f('ix_flex_open_positions_import_run_id'), table_name='flex_open_positions')
    op.drop_index(op.f('ix_flex_open_positions_conid'), table_name='flex_open_positions')
    op.drop_table('flex_open_positions')
    _tausche_ereignistyp_check(EREIGNISTYP_ALT)
