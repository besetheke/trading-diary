---
titel: Journal-Endpunkte der API — Umsetzung
modell: guenstig
status: offen
abhaengig_von: AP-07j
aendert_tests: nein
---

# AP-07jk · Umsetzung gegen die Abnahmebasis AP-07j

Vertrag, Entscheidungen und Endpunkte: `auftraege/AP-07j.md` (vollständig
lesen). Maßgeblich sind die Tests in `tests/test_api_journal.py`
(unveränderlich, Regel 1); `tests/test_api_lesen.py` und
`tests/test_api_statisch.py` bleiben unverändert grün.

## Zu ändern

Nur `api/app.py` (und, falls für den Schnitt sinnvoll, ein neues Modul unter
`api/`, das `erzeuge_app` einbindet):

- Parameter `mit_journal: bool = False` an `erzeuge_app`; Modulobjekt `app`
  mit `mit_journal=True`.
- Pydantic-v2-Modelle für Ein- und Ausgabe; die Routen aus der Tabelle in
  AP-07j. Prüfung des Bereichs vor jedem Schreiben. Eine kurze Transaktion je
  Aufruf (`engine.begin()`), Regel 9.
- Die Journal-Routen **vor** der Rückfall-Route `/{voller_pfad:path}`
  einhängen, sonst fängt diese sie ab.
- Nur `journal_entries`, `tags`, `entity_tags` beschreiben.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, `analytics/`, am Schema.
Kein neues Schema, keine Migration (die Tabellen existieren).

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Probelauf gegen eine Kopie von `journal.db` macht anschließend das starke
Modell.
