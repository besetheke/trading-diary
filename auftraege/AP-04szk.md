---
titel: Overrides auch in der Kettensicht — Umsetzung (OF-61)
modell: guenstig
status: offen
abhaengig_von: AP-04sz
aendert_tests: nein
---

# AP-04szk · Umsetzung gegen die Abnahmebasis AP-04sz

Regel und Begründung: `auftraege/AP-04sz.md`. Maßgeblich sind die Tests in
`tests/test_rebuild_overrides_kette.py` (unveränderlich, Regel 1).

## Zu ändern

Nur `journal/rebuild.py`:

- `_overrides_anwenden` bekommt einen Parameter `sicht` (Standard `"konto"`)
  und schreibt ihn in die neuen `chain_links`-Zeilen. Die bisherigen Aufrufe
  verhalten sich unverändert.
- In `_rebuild_laufen`, nach dem Anwenden der Kontosicht-Overrides und vor
  dem OA-Abgleich: die bestätigten Overrides über die Naturschlüssel in die
  Kettensicht übersetzen (die Abbildungen
  `struktur_id_je_schluessel`/`ketten_id_je_schluessel` beider Sichten sind
  bereits vorhanden, `_SichtErgebnis`), den Rest per `_overrides_anwenden(...,
  sicht="kette")` anwenden. Als gesicherte Ketten gelten die Zielketten der
  übersetzten Overrides.
- `RebuildErgebnis` um `overrides_kette_angewandt` und
  `overrides_kette_ohne_entsprechung` erweitern (Standardwert 0).

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, `analytics/`, an der
Ausgabe von `journal rebuild` (`journal/cli.py`) oder an `chain_overrides`.
Keine Überlappungs-Heuristik: fehlt ein Schlüssel, zählt der Override als „ohne
Entsprechung".

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Echtabgleich (Kopie von `journal.db`) macht anschließend das starke Modell.
