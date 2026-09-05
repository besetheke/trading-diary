# Trading Journal

Lokales Trading-Journal nach `plan/trading-journal-projektplan.md` — die
fachliche Wahrheit liegt dort, die Arbeitsregeln in `CLAUDE.md`.

## Einrichtung (einmalig)

```
setup.cmd          legt .venv an und installiert alle Abhängigkeiten
```

Voraussetzung: Python 3.12 im PATH.

## Alltag

```
test.cmd           pytest (entspricht `make test`)
check.cmd          ruff check . + pytest  ← das Gate vor jeder Abgabe
backup.cmd <quelldatei> <zieldatei>    konsistentes Backup via VACUUM INTO
.\ap.ps1 -Liste    Aufträge mit Modell und Status
.\ap.ps1 AP-xx     Arbeitspaket starten
.\ap.ps1 AP-xx -Review   Diff-Review durch das starke Modell
```

## Aufbau

| Verzeichnis | Inhalt |
|---|---|
| `journal/` | Anwendungs-Kern: Schema (`schema.py`), DB-Anbindung (`db.py`), Backup (`backup.py`) |
| `ingest/` | L1 — Import (AP-02 ff.) |
| `engine/` | L2 — Matching/Erkennung, rein und deterministisch (P2) |
| `analytics/` | L3 — Kennzahlen (AP-06 ff.) |
| `api/` | L4 — FastAPI (AP-07 ff.) |
| `migrations/` | Alembic; Schemaänderungen nur über Migrationen (Regel 3) |
| `tests/` | pytest-Suite |
| `fixtures/` | Testdaten; `fixtures/golden/` enthält echte Kontodaten — Zugriff nur für Pakete beim starken Modell (Regel 2), steht in `.gitignore` |

## Datenbank

SQLite im WAL-Modus, `busy_timeout` gesetzt, Fremdschlüssel an
(`journal/db.py`). Umgebungsvariable `JOURNAL_DB` wählt die Datenbankdatei,
Standard ist `journal.db`. Migrationen: `alembic upgrade head` respektive
`JOURNAL_DB=<pfad> alembic upgrade head`.

Nächtliches Backup (§3): `backup.cmd` auf einen Zielpfad im Netzlaufwerk;
Aufbewahrung der letzten 14 Stände rotiert der Aufrufer (Taskplaner-Skript).
