---
titel: OA-Strategie auch in der Kettensicht — Umsetzung
modell: guenstig
status: offen
abhaengig_von: AP-13z
aendert_tests: nein
---

# AP-13zk · Umsetzung gegen die Abnahmebasis AP-13z

Verhalten und Begründung: `auftraege/AP-13z.md`. Maßgeblich sind die Tests in
`tests/test_rebuild_oa_kette.py` (unveränderlich, Regel 1).

## Zu ändern

Nur `journal/rebuild.py`: Das Ergebnis von `_sicht_schreiben(..., "kette", ...)`
festhalten und `oa_werte_schreiben()` ein zweites Mal damit aufrufen
(Ketten/Strukturen und ID-Zuordnungen der Kettensicht). Die Zählwerte des
zweiten Aufrufs werden verworfen; `RebuildErgebnis` bleibt wie bisher auf die
Kontosicht bezogen. Der Aufruf steht nach dem Schreiben beider Sichten.

## Grenzen

- Keine Änderung an `journal/oa_persistenz.py`, `engine/`, `tests/`, `fixtures/`.
- Kein Override-Schutz in der Kettensicht (OF-61 bleibt offen).

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Echtabgleich (Rebuild auf einer Kopie, Zahl der Kettensicht-Ketten mit
Strategie) macht anschließend das starke Modell.
