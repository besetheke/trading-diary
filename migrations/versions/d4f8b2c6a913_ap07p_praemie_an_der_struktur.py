"""AP-07p: Eröffnungs- und Schlussprämie an der Struktur

Revision ID: d4f8b2c6a913
Revises: c9a1d3e5b7f2
Create Date: 2026-09-23 09:00:00.000000

Die Positionsliste zeigt bisher nur das Ergebnis, nicht den Preis, zu dem
eröffnet und geschlossen wurde (Nutzer, 22.09.2026: „Die Übersichtsliste hat
z. B. keine Preise"). An genau diesen beiden Zahlen erkennt man einen Vorgang
wieder — und an ihnen unterscheidet man einen Roll von einem Wiedereinstieg
(OF-41).

Zwei Spalten auf ``structures``, beide entleerbar:

- ``eroeffnungspreis`` — Nettoprämie je Kontrakt bei Eröffnung,
- ``schlusspreis`` — dieselbe Größe bei Schließung; leer, solange die
  Struktur offen ist.

**Warum an der Struktur und nicht in der API.** Die Größe wird heute an zwei
Stellen gerechnet (``werkzeuge/abgleich/golden_ketten_stichprobe.py`` und
``journal/durchsicht.py``); eine dritte Kopie in der Lese-API liefe
absehbar auseinander. Sie hängt an Legs und Ausführungen, also genau an dem,
was der Rebuild ohnehin zur Hand hat, wenn er ``netto_pnl`` und ``waehrung``
füllt (AP-04v, Vertrag 10a und 11). Die API reicht sie dann nur durch, wie
alle anderen Beträge auch.

**Vorzeichen:** Verkauf positiv (Prämie eingenommen), Kauf negativ. Eine
verkaufte Vertikale hat also einen positiven Eröffnungs- und einen negativen
Schlusspreis; ihre Summe mal Menge mal Multiplikator ist das Bruttoergebnis.

**Genauigkeit:** acht Nachkommastellen. Gemessen am echten Bestand tragen
die Ausführungspreise bis zu acht Stellen (32.475 Zeilen: 16.894 mit zwei,
39 mit drei, 18 mit vier, 12 mit fünf, 2 mit acht). Bei Menge 1 — dem
Regelfall — ist die Prämie damit exakt; gekürzt wird ausschließlich der Rest
einer Division, und 723 Strukturen haben Mengen wie 3 oder 15, bei denen sie
nicht aufgeht. Ohne festgelegte Tiefe schnitte ``Decimal`` still bei 28
Stellen ab — eine Rundung ohne Namen (Regel 5).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from journal.schema import ExactDecimal

revision: str = "d4f8b2c6a913"
down_revision: str | None = "c9a1d3e5b7f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("structures") as batch:
        batch.add_column(sa.Column("eroeffnungspreis", ExactDecimal(), nullable=True))
        batch.add_column(sa.Column("schlusspreis", ExactDecimal(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("structures") as batch:
        batch.drop_column("schlusspreis")
        batch.drop_column("eroeffnungspreis")
