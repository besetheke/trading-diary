"""AP-05dk: campaign_ablehnungen — abgelehnte Paare sind Benutzerdaten

Revision ID: d2b6f4a8c0e3
Revises: e5f2b8c4d7a1
Create Date: 2026-10-08 20:00:00.000000

Die Klassifikation der Campaign-Kandidaten läuft über eine Datei-Rundreise
(AP-05d): Der Nutzer bestätigt Paare (``campaign_links`` mit
``erkennung = 'manuell'``) oder lehnt sie ab. Eine Ablehnung ließ sich bisher
nicht festhalten — jeder abgelehnte Kandidat wäre bei der nächsten Durchsicht
erneut erschienen, und die Übersicht über hunderte Vorschläge wär nie
dauerhaft geworden.

``campaign_ablehnungen`` speichert die abgelehnten Paare:
(``chain_id_a``, ``chain_id_b``, ``typ``) ist der Primärschlüssel — die
Ablehnung gilt genau für diesen Kandidaten, nicht für das Kettenpaar
insgesamt. ``chain_id_a`` ist die früher eröffnete bzw. bei ``financing`` die
Bestandskette (wie ``CampaignKandidat.kette_a``); die IDs sind
Kontosicht-Ketten. Beide verweisen per Fremdschlüssel auf ``chains``: Der
Rebuild sichert diese Ketten deshalb gegen Löschung (Regel 4), sonst bräche
er ab, sobald eine klassifizierte Kette verschwindet.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2b6f4a8c0e3"
down_revision: str | None = "e5f2b8c4d7a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "campaign_ablehnungen",
        sa.Column("chain_id_a", sa.Integer(), nullable=False),
        sa.Column("chain_id_b", sa.Integer(), nullable=False),
        sa.Column("typ", sa.Text(), nullable=False),
        sa.Column("notiz", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chain_id_a"],
            ["chains.chain_id"],
            name=op.f("fk_campaign_ablehnungen_chain_id_a_chains"),
        ),
        sa.ForeignKeyConstraint(
            ["chain_id_b"],
            ["chains.chain_id"],
            name=op.f("fk_campaign_ablehnungen_chain_id_b_chains"),
        ),
        sa.PrimaryKeyConstraint(
            "chain_id_a", "chain_id_b", "typ", name=op.f("pk_campaign_ablehnungen")
        ),
        sa.CheckConstraint(
            "typ IN ('ic', 'financing')", name=op.f("ck_campaign_ablehnungen_typ")
        ),
    )


def downgrade() -> None:
    op.drop_table("campaign_ablehnungen")
