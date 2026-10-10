---
titel: GET /filterwerte — wählbare Werte der Positionsfilter
modell: guenstig
status: offen
abhaengig_von: AP-07f
aendert_tests: nein
---

# AP-07fw · Auswahlwerte der Filter

Die Filterleiste der Positionsliste (AP-08g2b) braucht Auswahlfelder statt
Freitext: Basiswert, Anlageklasse, Währung, Strategie, Seite, Endzustand. Das
Backend liefert die Listen. Kleines, rein lesendes Paket.

Abnahmebasis (starkes Modell, eigener Commit): `tests/test_api_filterwerte.py`
(5 Fälle), **unveränderlich**, derzeit rot.

## Vertrag

`GET /filterwerte` (immer aktiv, vor der Rückfall-Route, nur lesend, Kontosicht
wie alle Leseendpunkte) liefert genau sechs Listen:

```json
{ "basiswerte": [...], "anlageklassen": [...], "waehrungen": [...],
  "strategien": [...], "seiten": [...], "endzustaende": [...] }
```

- Jede Liste: Zeichenketten, **aufsteigend sortiert, ohne Doppelte, ohne
  `NULL` und ohne leere Zeichenketten**.
- `basiswerte`, `anlageklassen`: Werte aus `chains` (`underlying`,
  `asset_class`) der Kontosicht **vereinigt mit den Werten der losen Legs**
  (Legs der Kontosicht mit `structure_id IS NULL`; Basiswert aus
  `instruments.underlying`, sonst `instruments.symbol`; Klasse aus
  `instruments.asset_class`). Sonst wäre ein Ticker, der nur als loses Leg
  vorkommt, nicht wählbar, obwohl der Filter für ihn gilt (AP-07f).
- `waehrungen`: `structures.waehrung` der Kontosicht **vereinigt mit** der
  Währung der **schließenden** Ausführung der losen Legs
  (`executions.waehrung`).
- `strategien`: `chains.oa_strategie` (nur gesetzte Werte).
- `seiten`: `chains.seite` (nur gesetzte Werte).
- `endzustaende`: `chains.endzustand` (nur gesetzte Werte).
- Keine Zählwerte, keine weiteren Felder (das Antwortmodell hat genau diese
  sechs).

## Umsetzung

Neues Antwortmodell `FilterwerteAntwort` und Route in `api/app.py`;
`select(...).distinct()` je Liste, das Vereinigen und Sortieren in Python.
Keine SQL-Zeichenketten aus Eingaben (es gibt keine Eingabe).

## Ausdrücklich nicht Teil dieses Pakets

- Oberfläche, Vite-Proxy (kommt mit AP-08g2b), `api.ts`.
- Änderungen an `analytics/`, `engine/`, `journal/`, `tests/`, `fixtures/`.

## Abnahme

Kein Gesamtlauf nötig. Gezielt: `.venv\Scripts\python.exe -m pytest -q
tests/test_api_filterwerte.py tests/test_api_filter.py
tests/test_api_filter_lose_legs.py tests/test_api_kampagnen.py` (Sekunden;
Ergebnis direkt lesen, nichts mehrfach pollen), `ruff check .`,
`git diff --stat` nur `api/app.py` und dieses Auftragsdokument (Status auf
`fertig`). Vor Beginn und vor dem Commit `git pull --ff-only`. Melde nur
„gepusht, Commit-Nummer"; die Gesamtsuite führt das starke Modell aus.
