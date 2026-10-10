---
titel: Tagesübersicht und Kalender der Lese-API — Umsetzung
modell: guenstig
status: fertig
abhaengig_von: AP-07t
aendert_tests: nein
---

# AP-07tk · Umsetzung gegen die Abnahmebasis AP-07t

Vertrag und Endpunkte: `auftraege/AP-07t.md` (vollständig lesen). Maßgeblich
sind die Tests in `tests/test_api_tage.py` (unveränderlich, Regel 1); die
bisherigen API-Tests bleiben unverändert grün.

## Zu ändern

Nur `api/app.py` (oder ein neues Modul unter `api/`, das dort eingebunden
wird):

- `GET /tage/{datum}` und `GET /kalender` mit Pydantic-v2-Modellen. Lesen aus
  `chains`, `chain_links`, `structures`, jeweils mit `sicht = 'konto'`.
- Tagesgrenzen als Halboffene Intervalle `[Tag 00:00, nächster Tag 00:00)`.
- Summen je Währung als `Decimal`, Ausgabe als Zeichenkette ohne Rundung
  (`format(x, "f")`); Kommission und Brutto leerer Felder zählen als 0 nur
  beim Summieren geschlossener Strukturen (die haben immer Werte).
- Die Routen **vor** die Rückfall-Route der Oberfläche setzen.
- Kein `mit_journal`-Schalter: beide Endpunkte sind immer aktiv.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, `analytics/`, am Schema.
Keine Kennzahlen, keine Umrechnung, kein Schreiben.

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Probelauf gegen eine Kopie von `journal.db` macht anschließend das starke
Modell.
