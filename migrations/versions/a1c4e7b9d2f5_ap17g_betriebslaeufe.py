"""AP-17g (M04): ``betriebslaeufe`` — Abruf, Import und Rebuild als eigene, überprüfbare Läufe

Das Importdatum allein beweist keinen erfolgreichen Neuaufbau (Review M04). Jeder Abruf, Import und Rebuild des Nachtlaufs (und
der Handbefehle) schreibt hier eine kurze Zeile mit Ergebnis (ok / fehler / teilweise) und Meldung; die Startseite und die Seite
„Datenqualität“ unterscheiden damit „zuletzt erfolgreich abgerufen“, „zuletzt erfolgreich neu aufgebaut“ und einen Fehlschlag.

Revision ID: a1c4e7b9d2f5
Revises: f6a3c9e1b7d2
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1c4e7b9d2f5"
down_revision: str | None = "f6a3c9e1b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "betriebslaeufe",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("art", sa.Text(), nullable=False),
        sa.Column("beendet_am", sa.DateTime(), nullable=False),
        sa.Column("ergebnis", sa.Text(), nullable=False),
        sa.Column("meldung", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("art IN ('abruf', 'import', 'rebuild')", name="ck_betriebslaeufe_art"),
        sa.CheckConstraint("ergebnis IN ('ok', 'fehler', 'teilweise')", name="ck_betriebslaeufe_ergebnis"),
    )
    op.create_index("ix_betriebslaeufe_art_beendet", "betriebslaeufe", ["art", "beendet_am"])


def downgrade() -> None:
    op.drop_index("ix_betriebslaeufe_art_beendet", table_name="betriebslaeufe")
    op.drop_table("betriebslaeufe")
