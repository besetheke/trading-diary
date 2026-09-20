"""AP-04: Naturschlüssel für Strukturen und Ketten, Leg-zu-Struktur-Verweis

Revision ID: b7e2f4a9c1d6
Revises: a3e8d1c4f7b2
Create Date: 2026-09-20 10:00:00.000000

Vorbereitung der Persistenzschicht (AP-04v). Drei Spalten:

- ``legs.structure_id`` — der Verweis von der Leg auf ihre Struktur. Entleerbar,
  weil nicht jede Leg in einer Struktur landet: Der P7-Vorfilter schließt alles
  aus, was nicht per Trade eröffnet wurde, und ``bilde_structures()`` gibt diese
  Legs als ``nicht_strukturiert`` zurück.

- ``structures.natur_schluessel`` und ``chains.natur_schluessel`` — ein aus dem
  Inhalt abgeleiteter, über Läufe hinweg gleichbleibender Schlüssel.

Warum die beiden Naturschlüssel nötig sind: ``chain_overrides`` verweist per
Fremdschlüssel auf ``chains.chain_id`` und ``structures.structure_id``. Ein
Rebuild, der diese Tabellen leert und neu füllt, vergäbe dieselben Sachverhalte
unter neuen Nummern — jeder manuelle Override zeigte danach auf etwas anderes
oder ins Leere. Die Abnahme „Manuelle Overrides überleben ein vollständiges
``rebuild``" (Plan §6, AP-04) wäre nicht erfüllbar. Über den Naturschlüssel
gleicht der Rebuild stattdessen ab: Bekanntes behält seine Nummer.

Für eine Struktur sind das die aufsteigend sortierten ``open_exec_id`` ihrer
Legs, mit ``|`` verbunden — stabil, weil ``exec_id`` die IB-``tradeID`` ist.
Für eine Kette ist es der Naturschlüssel ihrer eröffnenden Struktur mit ``k:``
davor; Rolls hängen hinten an und lassen den Kettenanfang unberührt.

Die Spalten sind NOT NULL ohne Vorgabewert. Das ist zulässig, weil ``legs``,
``structures`` und ``chains`` bis hierher von nichts beschrieben werden — die
Engine rechnet ausschließlich im Speicher, die Persistenz entsteht erst in
AP-04p. Bestehende Zeilen kann es also nicht geben.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e2f4a9c1d6"
down_revision: str | None = "a3e8d1c4f7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("structures") as batch:
        batch.add_column(sa.Column("natur_schluessel", sa.Text(), nullable=False))
        batch.create_unique_constraint(
            "uq_structures_natur_schluessel", ["natur_schluessel"]
        )

    with op.batch_alter_table("chains") as batch:
        batch.add_column(sa.Column("natur_schluessel", sa.Text(), nullable=False))
        batch.create_unique_constraint("uq_chains_natur_schluessel", ["natur_schluessel"])

    with op.batch_alter_table("legs") as batch:
        batch.add_column(sa.Column("structure_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_legs_structure_id_structures", "structures", ["structure_id"], ["structure_id"]
        )
    op.create_index("ix_legs_structure_id", "legs", ["structure_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_legs_structure_id", table_name="legs")
    with op.batch_alter_table("legs") as batch:
        batch.drop_constraint("fk_legs_structure_id_structures", type_="foreignkey")
        batch.drop_column("structure_id")

    with op.batch_alter_table("chains") as batch:
        batch.drop_constraint("uq_chains_natur_schluessel", type_="unique")
        batch.drop_column("natur_schluessel")

    with op.batch_alter_table("structures") as batch:
        batch.drop_constraint("uq_structures_natur_schluessel", type_="unique")
        batch.drop_column("natur_schluessel")
