"""AP-02a: exec_id auf tradeID umschlüsseln, Stammdaten mit Periodenende

Revision ID: c4b1f0a9d2e7
Revises: 8a8d06f09935
Create Date: 2026-09-12 12:00:00.000000

Zwei Änderungen, beide aus §5 und §6.2 des Plans:

1. **``executions.exec_id`` trägt künftig ``tradeID``** statt ``transactionID``
   (OF-10). Gemessen im Überschneidungszeitraum: die Spalte ``Transaction ID``
   des Trading-Diary-Pro-Exports trifft ``tradeID`` 175 von 175 Mal und
   ``transactionID`` kein einziges Mal. Ohne die Umstellung hätten Altbestand
   ab 2022 (AP-09) und laufende Flex-Importe keine gemeinsamen Schlüssel, und
   jede Buchung des Überschneidungszeitraums läge doppelt in der Datenbank.
   ``transactionID`` bleibt als Spalte ``transaction_id`` erhalten — sekundär,
   für die Abstimmung mit dem Broker, ohne Eindeutigkeitszwang.

2. **Stammdaten bekommen das Periodenende ihrer Quelle** (§6.2,
   „Reihenfolgeunabhängigkeit des Imports"): ``instruments`` und
   ``flex_securities_info`` tragen ``quell_periodenende``. Bestehende Zeilen
   bekommen NULL — „Periode unbekannt", was gegen jede datierte Quelle
   verliert und beim nächsten Import überschrieben wird.

**Vorhandene Zeilen werden umgeschlüsselt, nicht verworfen.** ``roh_json``
trägt das vollständige Attributbild jeder Ausführung, ``tradeID`` also
inbegriffen — der neue Schlüssel ist daraus ableitbar, es wird nichts geraten
(Regel 10). Ein Leeren von ``executions`` wäre auch keine Option: die
Benutzerdaten in ``assignment_links`` (Feld ``erkennung``, Wert ``manuell``)
hängen daran und dürfen nicht verlorengehen (Regel 4).

Fehlt einer vorhandenen Zeile ``tradeID`` in ``roh_json``, oder ist ein Wert
doppelt, bricht die Migration mit Nennung der Zeilen ab, statt zu raten.

Die Umschlüsselung läuft zweistufig über ein Präfix, weil ``exec_id``
Primärschlüssel ist: würde Zeile für Zeile direkt umgeschrieben, könnte ein
neuer Wert auf einen noch nicht umgeschriebenen alten treffen. Die
Fremdschlüssel in ``legs`` und ``assignment_links`` wandern mit; die
Alembic-Verbindung hat ``PRAGMA foreign_keys`` nicht gesetzt (das tut nur
``journal.db`` je Verbindung), der Zwischenstand innerhalb der Transaktion
stört daher nicht.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# Revision-Codes: nie wiederverwenden, nie bestehende Migrationen editieren
# (CLAUDE.md, Regel 3).
revision: str = 'c4b1f0a9d2e7'
down_revision: str | None = '8a8d06f09935'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Präfix für den Zwischenstand der zweistufigen Umschlüsselung. Enthält einen
# Doppelpunkt und den Paketnamen — kein Broker-Schlüssel sieht so aus.
TMP_PRAEFIX = 'ap02a-umschluesselung:'

# Alle Verweise auf executions.exec_id aus §5.
VERWEISE = (
    ('legs', 'open_exec_id'),
    ('legs', 'close_exec_id'),
    ('assignment_links', 'option_exec_id'),
    ('assignment_links', 'stock_exec_id'),
)

STAMMDATENTABELLEN = ('instruments', 'flex_securities_info')


def _verweise_mitziehen(bind) -> None:
    """Zieht die Fremdschlüssel auf den Zwischenstand nach.

    Aufgerufen wird das jeweils direkt nach Stufe 1, wenn ``executions``
    den neuen Schlüssel (mit Präfix) in ``exec_id`` und den bisherigen in
    ``transaction_id`` hält — in beiden Richtungen. ``transaction_id`` ist
    dort die Zuordnung alt → neu.
    """
    for tabelle, spalte in VERWEISE:
        bind.execute(
            sa.text(
                f'UPDATE {tabelle} SET {spalte} = ('
                f'  SELECT e.exec_id FROM executions e '
                f'  WHERE e.transaction_id = {tabelle}.{spalte}'
                f') WHERE EXISTS ('
                f'  SELECT 1 FROM executions e '
                f'  WHERE e.transaction_id = {tabelle}.{spalte}'
                f')'
            )
        )


def _praefix_entfernen(bind) -> None:
    laenge = len(TMP_PRAEFIX)
    bind.execute(
        sa.text(
            'UPDATE executions SET exec_id = substr(exec_id, :ab) '
            'WHERE exec_id LIKE :muster'
        ),
        {'ab': laenge + 1, 'muster': TMP_PRAEFIX + '%'},
    )
    for tabelle, spalte in VERWEISE:
        bind.execute(
            sa.text(
                f'UPDATE {tabelle} SET {spalte} = substr({spalte}, :ab) '
                f'WHERE {spalte} LIKE :muster'
            ),
            {'ab': laenge + 1, 'muster': TMP_PRAEFIX + '%'},
        )


def _umschluesseln_auf_tradeid(bind) -> None:
    zeilen = bind.execute(
        sa.text(
            "SELECT exec_id, json_extract(roh_json, '$.tradeID') AS trade_id FROM executions"
        )
    ).all()
    if not zeilen:
        return

    ohne_tradeid = [zeile.exec_id for zeile in zeilen if not zeile.trade_id]
    if ohne_tradeid:
        raise RuntimeError(
            'executions: in roh_json fehlt die tradeID bei den Ausführungen '
            f'{sorted(ohne_tradeid)[:20]} ({len(ohne_tradeid)} insgesamt). '
            'Der neue Schlüssel lässt sich für diese Zeilen nicht ableiten. '
            'Die Zeilen sind Rohdaten und jederzeit neu importierbar (P1): '
            'betroffene import_runs samt Zeilen entfernen und die Flex-Dateien '
            'neu einlesen.'
        )

    neue_schluessel = [str(zeile.trade_id) for zeile in zeilen]
    if len(set(neue_schluessel)) != len(neue_schluessel):
        mehrfach = sorted({s for s in neue_schluessel if neue_schluessel.count(s) > 1})
        raise RuntimeError(
            f'executions: tradeID ist nicht eindeutig — {mehrfach[:20]}. '
            'Der Plan (§5) weist tradeID über 19.425 Zeilen als eindeutig aus; '
            'ein Verstoß ist ein Defekt der Quelldaten und kein Fall für eine '
            'automatische Auflösung.'
        )

    # Stufe 1: alten Schlüssel sichern, neuen mit Präfix setzen.
    bind.execute(
        sa.text(
            'UPDATE executions SET transaction_id = exec_id, '
            "exec_id = :praefix || json_extract(roh_json, '$.tradeID')"
        ),
        {'praefix': TMP_PRAEFIX},
    )
    _verweise_mitziehen(bind)
    # Stufe 2: Präfix überall entfernen.
    _praefix_entfernen(bind)


def _zurueck_auf_transaction_id(bind) -> None:
    zeilen = bind.execute(sa.text('SELECT exec_id, transaction_id FROM executions')).all()
    if not zeilen:
        return

    ohne = [zeile.exec_id for zeile in zeilen if not zeile.transaction_id]
    if ohne:
        raise RuntimeError(
            'executions: transaction_id fehlt bei den Ausführungen '
            f'{sorted(ohne)[:20]} ({len(ohne)} insgesamt) — der alte Schlüssel '
            'lässt sich nicht wiederherstellen. Rückbau nur auf leerem '
            'Bestand oder nach Neuimport.'
        )
    werte = [str(zeile.transaction_id) for zeile in zeilen]
    if len(set(werte)) != len(werte):
        raise RuntimeError(
            'executions: transaction_id ist nicht eindeutig und taugt daher '
            'nicht als Primärschlüssel. Rückbau nicht möglich.'
        )

    # Spiegelbildlich zum Upgrade: erst Präfix, dann Verweise, dann kürzen.
    # Der alte Schlüssel steht in transaction_id, der aktuelle in exec_id —
    # deshalb wird hier über exec_id zugeordnet, bevor sie überschrieben wird.
    bind.execute(
        sa.text(
            'UPDATE executions SET exec_id = :praefix || transaction_id, '
            'transaction_id = exec_id'
        ),
        {'praefix': TMP_PRAEFIX},
    )
    _verweise_mitziehen(bind)
    _praefix_entfernen(bind)


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column('executions', sa.Column('transaction_id', sa.Text(), nullable=True))
    op.create_index(
        op.f('ix_executions_transaction_id'), 'executions', ['transaction_id'], unique=False
    )
    _umschluesseln_auf_tradeid(bind)
    for tabelle in STAMMDATENTABELLEN:
        op.add_column(tabelle, sa.Column('quell_periodenende', sa.Date(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    for tabelle in reversed(STAMMDATENTABELLEN):
        op.drop_column(tabelle, 'quell_periodenende')
    _zurueck_auf_transaction_id(bind)
    op.drop_index(op.f('ix_executions_transaction_id'), table_name='executions')
    op.drop_column('executions', 'transaction_id')
