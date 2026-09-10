"""AP-02: Quellschlüssel für die Flex-Sektionstabellen

Revision ID: 8a8d06f09935
Revises: 0366113de717
Create Date: 2026-09-10 10:00:00.000000

Befund aus dem Review von AP-02: Die Sektionstabellen waren nur über den
Datei-Hash gegen Dubletten geschützt; jeder erneute oder rollierende Abruf
hätte Zinsen, Gebühren und Kapitalmaßnahmen verdoppelt. Jede Zeile bekommt
``konto`` und ``quell_schluessel``, das Paar wird eindeutig; offene Positionen
bekommen dazu ihren ``stichtag``.

Die Tabellen müssen beim Upgrade leer sein. Ein Quellschlüssel lässt sich für
vorhandene Zeilen nicht verlässlich nachtragen — das Konto steht nicht in
jeder Rohzeile, und bereits eingetragene Dubletten ließen sich nicht von
echten Doppelbuchungen unterscheiden. Die Tabellen existieren nur im nie
ausgelieferten Zwischenstand von AP-02; trifft die Migration trotzdem auf
Zeilen, bricht sie mit Nennung der Tabelle ab, statt zu raten (Regel 10).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = '8a8d06f09935'
down_revision: str | None = '0366113de717'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEKTIONSTABELLEN = (
    'flex_open_positions',
    'flex_cash_transactions',
    'flex_corporate_actions',
    'flex_transfers',
)


def _muss_leer_sein(tabelle: str) -> None:
    anzahl = op.get_bind().execute(sa.text(f'SELECT count(*) FROM {tabelle}')).scalar_one()
    if anzahl:
        raise RuntimeError(
            f'{tabelle} enthält {anzahl} Zeilen aus dem Zwischenstand von AP-02. '
            'Ein Quellschlüssel lässt sich nicht verlässlich nachtragen. '
            'Die Tabelle ist reine Rohdatenkopie der Flex-Dateien: leeren, '
            'die zugehörigen import_runs entfernen und die Dateien neu importieren.'
        )


def upgrade() -> None:
    for tabelle in SEKTIONSTABELLEN:
        _muss_leer_sein(tabelle)
        with op.batch_alter_table(tabelle) as batch:
            batch.add_column(sa.Column('konto', sa.Text(), nullable=False))
            batch.add_column(sa.Column('quell_schluessel', sa.Text(), nullable=False))
            if tabelle == 'flex_open_positions':
                batch.add_column(sa.Column('stichtag', sa.Date(), nullable=False))
            batch.create_unique_constraint(
                f'uq_{tabelle}_quell_schluessel', ['konto', 'quell_schluessel']
            )


def downgrade() -> None:
    for tabelle in reversed(SEKTIONSTABELLEN):
        with op.batch_alter_table(tabelle) as batch:
            batch.drop_constraint(f'uq_{tabelle}_quell_schluessel', type_='unique')
            if tabelle == 'flex_open_positions':
                batch.drop_column('stichtag')
            batch.drop_column('quell_schluessel')
            batch.drop_column('konto')
