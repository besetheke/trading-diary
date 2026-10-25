"""AP-17g (M07): ``backtest_partner`` — vom Nutzer korrigierte Live-Partner von Backtest-Trades

Die Paarung eines Option-Omega-Trades mit seinem Live-Trade ergibt sich aus dem Zeitfenster. Sie kann falsch sein; der Nutzer korrigiert sie
(anderer Live-Trade oder ausdrücklich „kein Partner“). Schlüssel ist der Naturschlüssel des Backtest-Trades (Strategie, Eröffnung, Legs), nicht
seine Zeilennummer. Eine Rücknahme löscht nichts, sie setzt ``zurueckgenommen_am`` (Regel 4).

Revision ID: c7d2e9f4a1b8
Revises: b3f1a8c2d6e9
Create Date: 2026-10-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7d2e9f4a1b8"
down_revision: str | None = "b3f1a8c2d6e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_partner",
        sa.Column("oo_strategie", sa.Text(), nullable=False),
        sa.Column("oo_eroeffnet", sa.DateTime(), nullable=False),
        sa.Column("oo_legs_roh", sa.Text(), nullable=False),
        # OA-Trade-Nummer des Live-Partners; leer = ausdrücklich kein Partner
        sa.Column("oa_trade", sa.Text(), nullable=True),
        sa.Column("begruendung", sa.Text(), nullable=True),
        sa.Column("erkennung", sa.Text(), nullable=False),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
        sa.Column("zurueckgenommen_am", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("oo_strategie", "oo_eroeffnet", "oo_legs_roh"),
        sa.CheckConstraint("erkennung IN ('manuell')", name="ck_backtest_partner_erkennung"),
    )


def downgrade() -> None:
    op.drop_table("backtest_partner")
