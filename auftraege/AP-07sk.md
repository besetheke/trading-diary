---
titel: Sortierung der Kettenliste — Umsetzung
modell: guenstig
status: fertig
abhaengig_von: AP-07s
aendert_tests: nein
---

# AP-07sk · Umsetzung gegen die Abnahmebasis AP-07s

Regeln: `auftraege/AP-07s.md` (vollständig lesen). Maßgeblich sind die Tests in
`tests/test_api_sortierung.py` (unveränderlich, Regel 1); alle bisherigen
API-Tests bleiben unverändert grün.

## Zu ändern

Nur die Route `GET /ketten` in `api/app.py`:

- Parameter `sortierung` und `richtung` als `Literal`-Typen (damit das
  OpenAPI-Schema die Aufzählungen nennt), Vorgaben `eroeffnet_am` und `desc`.
- Sortierung im SQL: erst „leer zuletzt" (`spalte IS NULL`), dann die Spalte in
  der gewählten Richtung, dann `chains.chain_id` aufsteigend. Kein SQL aus
  Benutzereingaben zusammensetzen — die Spalte über die Tabelle nachschlagen,
  nachdem die Eingabe als `Literal` geprüft ist.
- `limit`/`offset` und die Filter bleiben unverändert; `gesamt` zählt wie
  bisher vor der Begrenzung.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, `journal/`, am Schema.
Keine Sortierung nach abgeleiteten Werten.

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`.
