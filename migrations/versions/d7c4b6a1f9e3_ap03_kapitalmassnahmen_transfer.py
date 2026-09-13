"""AP-03: Kapitalmaßnahmen als Transfer (OF-23), angepasste Instrumente, basis_ungeklaert

Revision ID: d7c4b6a1f9e3
Revises: b53f1c8e07a2
Create Date: 2026-09-14 09:00:00.000000

OF-23: IB bucht eine Kapitalmaßnahme nicht als Faktor auf derselben ``conid``
(die Vor-OF-23-Fassung von ``corporate_actions``), sondern als Abgang auf der
alten und Zugang auf einer neuen — gemessen an allen 10 Maßnahmen der
Golden-Exporte, ausnahmslos. ``corporate_actions`` wird deshalb neu gefasst:

- ``aktion_id`` gruppiert Abgang und Zugang derselben Maßnahme (IBs
  ``actionID``).
- ``alter_conid``/``alte_menge`` sind NULL bei einem reinen Zugang (z. B.
  ``DI``) — keine abgebende Seite.
- ``kosten_neu`` trägt IBs Kostenangabe für den Zugang, falls geliefert.
- Der CHECK auf ``typ`` entfällt: Split/Reverse/Merger/Spinoff war eine vor
  jeder Messung geratene Taxonomie. ``typ`` trägt jetzt den Rohwert der
  Quelle (FS, RS, TO, TC, FI, DI, …), bis eine echte Zuordnung vorliegt.

``corporate_actions`` enthält noch keine Zeilen (nichts befüllt die Tabelle
bisher — die Ableitung aus ``flex_corporate_actions`` ist ein eigenes,
späteres Paket), ein Drop-and-recreate der Spalten verliert daher keine
Daten.

Dazu zwei neue Spalten aus derselben Entscheidung:
- ``instruments.angepasst``: Zugang einer Kapitalmaßnahme — der
  Lieferumfang ist nicht mehr standardisiert.
- ``legs.basis_ungeklaert``: ein reiner Zugang ohne IBs Kostenangabe — kein
  stiller Nullwert.

Beide neuen Boole'schen Spalten sind NOT NULL mit Serverstandard 0/false,
damit bestehende Zeilen (falls vorhanden) gültig bleiben.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'd7c4b6a1f9e3'
down_revision: str | None = 'b53f1c8e07a2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALTE_CORPORATE_ACTIONS_SPALTEN = ('conid', 'typ', 'stichtag', 'faktor', 'roh_json')


def upgrade() -> None:
    with op.batch_alter_table('corporate_actions', recreate='always') as batch:
        batch.drop_constraint('ck_corporate_actions_typ', type_='check')
        # Der Index auf der alten conid-Spalte muss vor dem Drop weg — sonst
        # versucht die Batch-Rekonstruktion, ihn auf der bereits entfernten
        # Spalte neu anzulegen.
        batch.drop_index('ix_corporate_actions_conid')
        batch.add_column(sa.Column('aktion_id', sa.Text(), nullable=False, server_default=''))
        batch.add_column(sa.Column('konto', sa.Text(), nullable=False, server_default=''))
        batch.add_column(sa.Column('alter_conid', sa.BigInteger(), nullable=True))
        batch.add_column(sa.Column('alte_menge', ExactDecimal(), nullable=True))
        batch.add_column(sa.Column('neuer_conid', sa.BigInteger(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('neue_menge', ExactDecimal(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('kosten_neu', ExactDecimal(), nullable=True))
        batch.drop_column('conid')
        batch.drop_column('faktor')
    op.create_index(
        op.f('ix_corporate_actions_aktion_id'), 'corporate_actions', ['aktion_id']
    )
    op.create_index(
        op.f('ix_corporate_actions_alter_conid'), 'corporate_actions', ['alter_conid']
    )
    op.create_index(
        op.f('ix_corporate_actions_neuer_conid'), 'corporate_actions', ['neuer_conid']
    )
    # Serverstandards waren nur zum sicheren Hinzufügen nötig (Regel für
    # NOT-NULL-Spalten ohne Bestandsdaten); die Spalten sind von Anfang an
    # ohne Datensätze, ein anschließendes Entfernen des Defaults ist ohne
    # Wirkung auf SQLite und deshalb hier unterlassen.

    op.add_column(
        'instruments',
        sa.Column('angepasst', sa.Boolean(), nullable=False, server_default='0'),
    )
    op.add_column(
        'legs',
        sa.Column('basis_ungeklaert', sa.Boolean(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('legs', 'basis_ungeklaert')
    op.drop_column('instruments', 'angepasst')

    op.drop_index(op.f('ix_corporate_actions_neuer_conid'), table_name='corporate_actions')
    op.drop_index(op.f('ix_corporate_actions_alter_conid'), table_name='corporate_actions')
    op.drop_index(op.f('ix_corporate_actions_aktion_id'), table_name='corporate_actions')
    with op.batch_alter_table('corporate_actions', recreate='always') as batch:
        batch.add_column(sa.Column('conid', sa.BigInteger(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('faktor', ExactDecimal(), nullable=False, server_default='1'))
        batch.drop_column('kosten_neu')
        batch.drop_column('neue_menge')
        batch.drop_column('neuer_conid')
        batch.drop_column('alte_menge')
        batch.drop_column('alter_conid')
        batch.drop_column('konto')
        batch.drop_column('aktion_id')
        batch.create_check_constraint(
            'ck_corporate_actions_typ',
            "typ IN ('Split', 'Reverse', 'Merger', 'Spinoff')",
        )
    op.create_index(
        op.f('ix_corporate_actions_conid'), 'corporate_actions', ['conid']
    )
