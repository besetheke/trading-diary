---
titel: Abnahmebasis Sortierung der Kettenliste
modell: stark
status: fertig
abhaengig_von: AP-07l
aendert_tests: ja
---

# AP-07s · Abnahmebasis: Sortierung von `GET /ketten`

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-07sk (günstiges Modell). Neue Testdatei `tests/test_api_sortierung.py`
(18 Läufe); `tests/test_api_lesen.py` bleibt unverändert und
grün.

Anlass (Rückmeldung des Nutzers, 09.10.2026): In der Positionsliste muss die
Sortierung nach Spalten möglich sein. Sortiert wird **auf dem Server**, vor dem
Blättern — nur so ist die Reihenfolge über Seiten hinweg richtig. Die
Oberfläche (AP-08s) sortiert nie selbst.

## Regeln

- Neue Abfrageparameter an `GET /ketten`: `sortierung` und `richtung`.
  `sortierung` ∈ `eroeffnet_am`, `beendet_am`, `underlying`, `asset_class`,
  `seite`, `anzahl_rolls`, `endzustand`, `oa_strategie` (Spalten der Tabelle
  `chains`); `richtung` ∈ `asc`, `desc`. Alles andere → 422, im OpenAPI-Schema
  als Aufzählung (`Literal`). Groß-/Kleinschreibung wird nicht zurechtgebogen.
- **Vorgabe unverändert:** Eröffnung absteigend. Fehlt nur `richtung`, ist die
  Sortierung die Eröffnung in dieser Richtung; fehlt nur `sortierung`, ist die
  Richtung absteigend.
- **Leere Werte stehen immer zuletzt**, in beiden Richtungen (offene Ketten
  haben kein Ende, Aktienketten keine Seite).
- **Gleichstand:** `chain_id` aufsteigend, damit die Reihenfolge deterministisch
  ist und das Blättern nichts doppelt oder gar nicht liefert.
- Nicht sortierbar sind abgeleitete Werte (`struktur_summe_netto`, Preise): Sie
  werden je Seite zusammengestellt, eine Sortierung nur über die aktuelle Seite
  wäre irreführend → 422.
- Die Filter, `gesamt`, `limit` und `offset` verhalten sich wie bisher.

## Abnahme

`tests/test_api_sortierung.py` und alle bisherigen API-Tests grün, `ruff check
.` sauber. Gegen eine Wegwerf-Umsetzung geprüft: 41 von 41 grün (die neuen und
`test_api_lesen.py`).
