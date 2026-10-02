"""AP-04sw: `sicht` als Pflichtfeld auf legs/structures/chains/chain_links

Revision ID: b7f4e2a8c1d5
Revises: a3e8f1c9d426
Create Date: 2026-10-01 09:00:00.000000

Plan §5, „Zwei Sichten auf dieselben Ausführungen": die Kontosicht
(kontoweite FIFO-Verrechnung, bereits gebaut) und die Kettensicht
(Zurechnung je Vorgang, AP-04s/AP-04sk) sind **zwei getrennte Zuordnungen**
derselben Ausführungen, nie vermischt. `sicht` (`konto`/`kette`) ist
deshalb Pflichtfeld in jeder abgeleiteten Tabelle — „jede angezeigte Zahl
nennt sie".

**Bestehende Zeilen sind ausnahmslos Kontosicht.** Die Spalte kommt mit
``server_default='konto'`` — nicht als Dauerzustand (jeder künftige
Schreibvorgang setzt `sicht` explizit, AP-04swk), sondern damit die
Migration selbst keine Sonderbehandlung für Altdaten braucht.

**Naturschlüssel sind jetzt nur noch je Sicht eindeutig.** Dieselbe
Struktur/Kette existiert künftig als zwei Zeilen — eine je Sicht, mit
demselben `natur_schluessel`, aber eigener `structure_id`/`chain_id`. Die
bisherige Eindeutigkeit über `natur_schluessel` allein (`uq_structures_
natur_schluessel`, `uq_chains_natur_schluessel`) wird durch eine
zusammengesetzte Eindeutigkeit `(natur_schluessel, sicht)` ersetzt.

`legs` und `chain_links` brauchen keine Eindeutigkeitsänderung — sie
tragen ohnehin keinen Naturschlüssel, nur `sicht` als zusätzliche Spalte
zur Einordnung.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7f4e2a8c1d5"
down_revision: str | None = "a3e8f1c9d426"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("legs") as batch:
        batch.add_column(sa.Column("sicht", sa.Text(), nullable=False, server_default="konto"))
        batch.create_check_constraint("ck_legs_sicht", "sicht IN ('konto', 'kette')")

    with op.batch_alter_table("chain_links") as batch:
        batch.add_column(sa.Column("sicht", sa.Text(), nullable=False, server_default="konto"))
        batch.create_check_constraint("ck_chain_links_sicht", "sicht IN ('konto', 'kette')")

    with op.batch_alter_table("structures") as batch:
        batch.add_column(sa.Column("sicht", sa.Text(), nullable=False, server_default="konto"))
        batch.create_check_constraint("ck_structures_sicht", "sicht IN ('konto', 'kette')")
        batch.drop_constraint("uq_structures_natur_schluessel", type_="unique")
        batch.create_unique_constraint(
            "uq_structures_natur_schluessel_sicht", ["natur_schluessel", "sicht"]
        )

    with op.batch_alter_table("chains") as batch:
        batch.add_column(sa.Column("sicht", sa.Text(), nullable=False, server_default="konto"))
        batch.create_check_constraint("ck_chains_sicht", "sicht IN ('konto', 'kette')")
        batch.drop_constraint("uq_chains_natur_schluessel", type_="unique")
        batch.create_unique_constraint(
            "uq_chains_natur_schluessel_sicht", ["natur_schluessel", "sicht"]
        )


def downgrade() -> None:
    with op.batch_alter_table("chains") as batch:
        batch.drop_constraint("uq_chains_natur_schluessel_sicht", type_="unique")
        batch.create_unique_constraint("uq_chains_natur_schluessel", ["natur_schluessel"])
        batch.drop_constraint("ck_chains_sicht", type_="check")
        batch.drop_column("sicht")

    with op.batch_alter_table("structures") as batch:
        batch.drop_constraint("uq_structures_natur_schluessel_sicht", type_="unique")
        batch.create_unique_constraint("uq_structures_natur_schluessel", ["natur_schluessel"])
        batch.drop_constraint("ck_structures_sicht", type_="check")
        batch.drop_column("sicht")

    with op.batch_alter_table("chain_links") as batch:
        batch.drop_constraint("ck_chain_links_sicht", type_="check")
        batch.drop_column("sicht")

    with op.batch_alter_table("legs") as batch:
        batch.drop_constraint("ck_legs_sicht", type_="check")
        batch.drop_column("sicht")
