"""AP-04k: Urteil auf chain_overrides — Ablehnungen sind Benutzerdaten

Revision ID: c9a1d3e5b7f2
Revises: b7e2f4a9c1d6
Create Date: 2026-09-21 18:00:00.000000

Seit der Plan Zeitfenster-Rolls als Kandidaten führt (§6, Block B, Regel 2),
entscheidet der Nutzer über jeden Vorschlag. `chain_overrides` konnte bisher
nur eine Seite dieser Entscheidung ausdrücken: „diese Struktur gehört in jene
Kette". Eine Ablehnung ließ sich nicht festhalten — mit der Folge, dass jeder
abgelehnte Kandidat beim nächsten ``rebuild`` erneut erschienen wäre und eine
Durchsicht von mehreren hundert Paaren nie dauerhaft geworden wäre.

Die neue Spalte ``urteil`` trägt ``bestaetigt`` oder ``abgelehnt``.
``abgelehnt`` heißt: Diese Struktur setzt jene Kette **nicht** fort;
``chain_id`` ist dabei die Kette der schließenden Seite des Kandidaten.

Der Vorgabewert ``bestaetigt`` ist bewusst gewählt: Alle bestehenden Zeilen
sind Bestätigungen, denn eine andere Bedeutung gab es bis hierher nicht.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9a1d3e5b7f2"
down_revision: str | None = "b7e2f4a9c1d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("chain_overrides") as batch:
        batch.add_column(
            sa.Column(
                "urteil", sa.Text(), nullable=False, server_default="bestaetigt"
            )
        )
        batch.create_check_constraint(
            "ck_chain_overrides_urteil", "urteil IN ('bestaetigt', 'abgelehnt')"
        )


def downgrade() -> None:
    with op.batch_alter_table("chain_overrides") as batch:
        batch.drop_constraint("ck_chain_overrides_urteil", type_="check")
        batch.drop_column("urteil")
