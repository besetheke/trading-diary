"""AP-13: Rohtabellen für den OptionApp-Trade-Export

Revision ID: a3e8d1c4f7b2
Revises: f2a7c3d9b5e1
Create Date: 2026-09-18 08:00:00.000000

Der OA-Trade-Export ist eine XLSX-Datei mit einem Arbeitsblatt ``Trades`` und
elf Spalten (Format und Fallstricke: ``auftraege/AP-13-anhang-oa-format.md``).
Der Parser legt die Trades mit ihren Legs ab; die Verknüpfung mit den Ketten
und der Ergebnisabgleich gehören nicht dazu (AP-04, starkes Modell).

Zwei Tabellen:

- ``optionapp_trades`` — eine Zeile je Trade. Schlüssel ist die Klammernummer
  aus ``Name`` (``oa_trade``), die gegen ``executions.oa_trade`` läuft; sie ist
  in beiden Referenzexporten über alle 244 Zeilen vorhanden und eindeutig.
  ``Quantity`` ist ein Verhältnis und wird als zwei Werte gehalten; ``Stops``
  behält seinen Rohwert, weil ``-`` („kein Stop") etwas anderes bedeutet als
  ``0``.
- ``optionapp_legs`` — zwei bis vier Legs je Trade aus der Grammatik der Spalte
  ``Strikes``, positionsbehaftet.

Zeitstempel werden gespeichert, dürfen aber nicht zum Abgleich dienen: Das
Format ist ein drittes neben TDP und Flex, die Zeitzone ist ungeprüft. Die
Verknüpfung stiftet ausschließlich die Klammernummer.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'a3e8d1c4f7b2'
down_revision: str | None = 'f2a7c3d9b5e1'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'optionapp_trades',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('import_run_id', sa.Integer(), nullable=False),
        sa.Column('oa_trade', sa.Text(), nullable=False),
        sa.Column('entry_zeit', sa.DateTime(), nullable=False),
        sa.Column('schluss_zeit', sa.DateTime(), nullable=True),
        sa.Column('strategie', sa.Text(), nullable=False),
        sa.Column('name_roh', sa.Text(), nullable=False),
        sa.Column('strikes_roh', sa.Text(), nullable=False),
        sa.Column('menge_zaehler', ExactDecimal(), nullable=False),
        sa.Column('menge_nenner', ExactDecimal(), nullable=False),
        sa.Column('offen_preis', ExactDecimal(), nullable=True),
        sa.Column('schluss_preis', ExactDecimal(), nullable=True),
        sa.Column('stop_roh', sa.Text(), nullable=False),
        sa.Column('stop_wert', ExactDecimal(), nullable=True),
        sa.Column('profit', ExactDecimal(), nullable=False),
        sa.Column('profit_waehrung', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('roh_json', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['import_run_id'], ['import_runs.id']),
        sa.UniqueConstraint('oa_trade', name='uq_optionapp_trades_oa_trade'),
    )
    op.create_index(
        op.f('ix_optionapp_trades_import_run_id'), 'optionapp_trades', ['import_run_id']
    )
    op.create_index(op.f('ix_optionapp_trades_oa_trade'), 'optionapp_trades', ['oa_trade'])

    op.create_table(
        'optionapp_legs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('optionapp_trade_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('richtung', sa.Integer(), nullable=False),
        sa.Column('menge', ExactDecimal(), nullable=False),
        sa.Column('right', sa.Text(), nullable=False),
        sa.Column('strike', ExactDecimal(), nullable=False),
        sa.Column('expiry', sa.Date(), nullable=False),
        sa.Column('roh', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['optionapp_trade_id'], ['optionapp_trades.id']),
        sa.UniqueConstraint(
            'optionapp_trade_id', 'position', name='uq_optionapp_legs_position'
        ),
        sa.CheckConstraint('richtung IN (-1, 1)', name='ck_optionapp_legs_richtung'),
        sa.CheckConstraint('"right" IN (\'C\', \'P\')', name='ck_optionapp_legs_right'),
    )
    op.create_index(
        op.f('ix_optionapp_legs_optionapp_trade_id'),
        'optionapp_legs',
        ['optionapp_trade_id'],
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_optionapp_legs_optionapp_trade_id'), table_name='optionapp_legs')
    op.drop_table('optionapp_legs')
    op.drop_index(op.f('ix_optionapp_trades_oa_trade'), table_name='optionapp_trades')
    op.drop_index(
        op.f('ix_optionapp_trades_import_run_id'), table_name='optionapp_trades'
    )
    op.drop_table('optionapp_trades')
