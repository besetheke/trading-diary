"""AP-02: realized_pnl_verfuegbar auf import_runs (OF-21, OF-24)

Revision ID: f2a7c3d9b5e1
Revises: e1f4a2c8b6d3
Create Date: 2026-09-17 10:00:00.000000

IB schaltet jedes Feld zum realisierten Ergebnis ab, sobald ein Modell in die
Abfrage einbezogen ist: In den Exporten mit ``model="Independent"`` steht an
jeder Zeile ``fifoPnlRealized="0"``, und Closed Lots bleiben leer (OF-21).
Gemessen 17.09.2026: 14.009 ``tradeID``s kommen in beiden Exportvarianten vor,
und in jedem einzelnen Fall steht die 0 im Modell-Export.

Dieser Befund stand bisher nur als Notiz in ``OFFENE_FRAGEN.md`` — und wurde
beim Bau des Geldtests trotzdem übersehen, was eine Trefferquote von 59 %
statt 93 % vortäuschte. Als Datenfeld am Importlauf kann derselbe Fehler nicht
wiederkehren, unabhängig davon, wer das Vergleichsskript schreibt (Plan §5).

Neue Spalte ``import_runs.realized_pnl_verfuegbar``, NOT NULL mit
Serverstandard 1 (wahr) — bestehende Läufe bleiben damit gültig; ob sie
tatsächlich Modellzeilen enthielten, lässt sich nachträglich nicht aus der
Datenbank entscheiden und wird nicht geraten (Regel 10).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'f2a7c3d9b5e1'
down_revision: str | None = 'e1f4a2c8b6d3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'import_runs',
        sa.Column(
            'realized_pnl_verfuegbar', sa.Boolean(), nullable=False, server_default='1'
        ),
    )


def downgrade() -> None:
    op.drop_column('import_runs', 'realized_pnl_verfuegbar')
