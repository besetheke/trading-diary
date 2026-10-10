---
titel: Parsernachbesserung - Trade mit einem Leg (OF-67)
modell: guenstig
status: fertig
abhaengig_von: AP-13pp
---

# AP-13t · Parsernachbesserung: ein Leg

Umsetzungspaket nach Plan §11.2, Schritt 2, gegen AP-13pp
(`tests/test_ingest_optionapp.py`, zwei neue Tests am Ende). **Tests und
Fixtures sind tabu.**

## Zu bauen

Ausschließlich in `ingest/optionapp.py`, Funktion `_legs_zerlegen`: Die
Bedingung `if not 2 <= len(teile) <= 4:` auf `1 <= len(teile) <= 4` ändern und
den Text der Fehlermeldung anpassen (`'Strikes' zerfällt in N Legs, erwartet
sind ein bis vier (Anhang)`). Sonst nichts.

## Grenzen

- Die Obergrenze vier bleibt; fünf Legs müssen weiter abbrechen.
- Keine Änderung an Tests, Fixtures, `erzeugen.py`, Anhang, übrigen Modulen.
- **Regel 2:** Nichts unter `fixtures/golden/` lesen.

## Abnahme

- `tests/test_ingest_optionapp.py` 33/33 grün, Gesamtsuite grün,
  `ruff check .` sauber.
- `git diff --stat`: ausschließlich `ingest/optionapp.py`.
