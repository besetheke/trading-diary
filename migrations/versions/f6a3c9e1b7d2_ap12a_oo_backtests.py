"""AP-12a: Option-Omega-Backtests — ``oo_trades`` und ``oo_zuordnung``

``oo_trades`` hält je Zeile eines OO-Exports einen Backtest-Trade. Schlüssel ist
(``strategie``, ``eroeffnet``, ``legs_roh``): mehrere Strategien öffnen zum
selben Scan-Zeitpunkt (OF-76, Punkt 1). Ein Backtest ist eine Rechnung, keine
Buchung — ein neuerer Export darf die Werte einer bekannten Zeile
überschreiben (OF-83).

``oo_zuordnung`` hält nur die Entscheidungen des Nutzers zu den automatisch
errechneten Vorschlägen (OO-Strategie → OA-Strategie): ``bestaetigt`` oder
``abgelehnt``. Die Vorschläge selbst werden bei jeder Abfrage neu errechnet
und nie gespeichert — so veralten sie nicht.

Revision ID: f6a3c9e1b7d2
Revises: b2d6f8a4c1e7
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a3c9e1b7d2"
down_revision: str | None = "b2d6f8a4c1e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oo_trades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_run_id", sa.Integer(), nullable=False),
        sa.Column("strategie", sa.Text(), nullable=False),
        sa.Column("eroeffnet", sa.DateTime(), nullable=False),
        sa.Column("geschlossen", sa.DateTime(), nullable=True),
        sa.Column("basiswert", sa.Text(), nullable=False),
        sa.Column("legs_roh", sa.Text(), nullable=False),
        sa.Column("kontrakte", sa.Integer(), nullable=False),
        sa.Column("praemie", sa.String(), nullable=False),
        sa.Column("pl", sa.String(), nullable=False),
        sa.Column("kommission_eroeffnung", sa.String(), nullable=True),
        sa.Column("kommission_schluss", sa.String(), nullable=True),
        sa.Column("eroeffnungskurs", sa.String(), nullable=True),
        sa.Column("schlusskurs", sa.String(), nullable=True),
        sa.Column("grund", sa.Text(), nullable=False),
        sa.Column("offen", sa.Boolean(), nullable=False),
        sa.Column("roh_json", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["import_run_id"], ["import_runs.id"],
                                name=op.f("fk_oo_trades_import_run_id_import_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oo_trades")),
        sa.UniqueConstraint("strategie", "eroeffnet", "legs_roh",
                            name=op.f("uq_oo_trades_strategie")),
    )
    op.create_index(op.f("ix_oo_trades_eroeffnet"), "oo_trades", ["eroeffnet"])
    op.create_table(
        "oo_zuordnung",
        sa.Column("oo_strategie", sa.Text(), nullable=False),
        sa.Column("oa_strategie", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("erkennung", sa.Text(), nullable=False),
        sa.Column("entschieden_am", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("oo_strategie", "oa_strategie", name=op.f("pk_oo_zuordnung")),
        sa.CheckConstraint("status IN ('bestaetigt', 'abgelehnt')",
                           name=op.f("ck_oo_zuordnung_status")),
        sa.CheckConstraint("erkennung IN ('manuell')", name=op.f("ck_oo_zuordnung_erkennung")),
    )


def downgrade() -> None:
    op.drop_table("oo_zuordnung")
    op.drop_index(op.f("ix_oo_trades_eroeffnet"), table_name="oo_trades")
    op.drop_table("oo_trades")
