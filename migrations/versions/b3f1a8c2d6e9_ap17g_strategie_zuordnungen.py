"""AP-17g (M03): ``strategie_zuordnungen`` — dauerhafte manuelle Strategiezuordnung an Ketten

Benutzerdaten, die jeden Rebuild überleben: je Naturschlüssel einer Kette die vom Nutzer gesetzte Strategie mit Begründung, Zeitstempeln und
dem Wert, den OA vorher oder zuletzt dort gesetzt hatte (für Konfliktanzeige und Rücknahme). Rücknahmen löschen nichts, sie setzen
``zurueckgenommen_am`` (Regel 4: keine Löschung von Benutzerdaten).

Revision ID: b3f1a8c2d6e9
Revises: a1c4e7b9d2f5
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b3f1a8c2d6e9"
down_revision: str | None = "a1c4e7b9d2f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "strategie_zuordnungen",
        sa.Column("natur_schluessel", sa.Text(), nullable=False),
        sa.Column("strategie", sa.Text(), nullable=False),
        sa.Column("begruendung", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
        sa.Column("geaendert_am", sa.DateTime(), nullable=True),
        sa.Column("zurueckgenommen_am", sa.DateTime(), nullable=True),
        # Wert und Erkennung, die vor der manuellen Zuordnung an der Kette standen (Rücknahme stellt sie wieder her). An Ketten und
        # Strukturen erlaubt die Prüfregel für oa_erkennung nur auto/heuristik: die Herkunft „manuell“ steht allein hier
        sa.Column("oa_vorher", sa.Text(), nullable=True),
        sa.Column("oa_erkennung_vorher", sa.Text(), nullable=True),
        # OA widerspricht: die Strategie, die OA beim letzten Rebuild gesetzt hätte und die die manuelle ersetzt hat
        sa.Column("konflikt_oa", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("natur_schluessel"),
    )


def downgrade() -> None:
    op.drop_table("strategie_zuordnungen")
