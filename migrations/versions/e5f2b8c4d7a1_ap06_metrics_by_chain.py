"""AP-06 E2: metrics_by_chain bekommt seine Form

Revision ID: e5f2b8c4d7a1
Revises: b7f4e2a8c1d5
Create Date: 2026-10-03 10:00:00.000000

AP-06v, Entscheidung E2: Die EUR-Materialisierung der Ketten liegt in
``metrics_by_chain`` (Cache, verwerfbar), nicht in ``chains.netto_pnl_eur``
(die Spalte bleibt dauerhaft leer — der Rebuild setzt sie bei jedem Lauf auf
None). Es gibt zwei EUR-Sichten, deshalb zwei Betragsspalten mit
Sichtnamen: ``netto_eur_wirtschaftlich`` (maßgeblich, Regel 3) und
``netto_eur_ib`` (Vergichtsgröße, Regel 4). Der Währungseffekt ist die
Differenz und wird nicht gespeichert.

``chain_id`` ist Fremdschlüssel auf ``chains.chain_id`` und eindeutig —
Ketten beider Sichten tragen eigene ``chain_id``, jede Kette bekommt genau
eine Zeile. Die ``id``-Spalte bleibt (Primärschlüssel des Stellvertreters);
die Eindeutigkeit der Kette trägt ``uq_metrics_by_chain_chain_id``.

Der Fremdschlüssel trägt ``ON DELETE CASCADE`` (Löschverhalten, OF-01):
Verschwindet eine Kette im Rebuild, fällt ihre Cache-Zeile mit ihr. Der
Rebuild bleibt von der Analytik unberührt — ohne CASCADE liefe sein Löschen
verschollener Ketten auf einen IntegrityError, sobald einmal Kennzahlen
gelaufen ist (``journal/db.py`` schaltet ``PRAGMA foreign_keys`` ein); Werte
überlebender Ketten gelten fort, bis der nächste Bericht sie neu schreibt.

Bis hierher ist die Tabelle ein leerer Stellvertreter (OF-01) — die
Migration braucht keinen Backfill. Geschrieben wird sie vollständig neu von
``journal kennzahlen`` (AP-06v, Regel 11), nie vom Rebuild.
``metrics_daily``/``metrics_by_campaign`` bleiben Stellvertreter (Tranche
IV/V).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

revision: str = "e5f2b8c4d7a1"
down_revision: str | None = "b7f4e2a8c1d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("metrics_by_chain") as batch:
        batch.add_column(sa.Column("chain_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("netto_eur_wirtschaftlich", ExactDecimal(), nullable=True))
        batch.add_column(sa.Column("netto_eur_ib", ExactDecimal(), nullable=True))
        # Die Tabelle ist leer (Stellvertreter) — NOT NULL ohne Backfill safe.
        batch.alter_column("chain_id", existing_type=sa.Integer(), nullable=False)
        batch.create_foreign_key(
            "fk_metrics_by_chain_chain_id_chains",
            "chains",
            ["chain_id"],
            ["chain_id"],
            ondelete="CASCADE",
        )
        batch.create_unique_constraint("uq_metrics_by_chain_chain_id", ["chain_id"])


def downgrade() -> None:
    with op.batch_alter_table("metrics_by_chain") as batch:
        batch.drop_constraint("fk_metrics_by_chain_chain_id_chains", type_="foreignkey")
        batch.drop_constraint("uq_metrics_by_chain_chain_id", type_="unique")
        batch.drop_column("netto_eur_ib")
        batch.drop_column("netto_eur_wirtschaftlich")
        batch.drop_column("chain_id")
