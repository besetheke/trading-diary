"""AP-04z: Verknüpfungstypen ``zuteilung`` und ``covered_call`` in chain_links

Zuteilungen und Covered Calls gehören zur Kette der Option (OF-81), zählen aber
nicht als Roll. Die Prüfregel der Spalte ``verknuepfungstyp`` wird erweitert.

Revision ID: b2d6f8a4c1e7
Revises: c4e8a2b6d0f1
Create Date: 2026-10-11
"""

from alembic import op

revision = "b2d6f8a4c1e7"
down_revision = "c4e8a2b6d0f1"
branch_labels = None
depends_on = None

NAME = "ck_chain_links_verknuepfungstyp"


def upgrade() -> None:
    with op.batch_alter_table("chain_links") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(
            NAME,
            "verknuepfungstyp IN ('open', 'roll', 'close', 'adjust', 'zuteilung', "
            "'covered_call')",
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM chain_links WHERE verknuepfungstyp IN ('zuteilung', 'covered_call')"
    )
    with op.batch_alter_table("chain_links") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(
            NAME, "verknuepfungstyp IN ('open', 'roll', 'close', 'adjust')"
        )
