---
titel: Barausgleich in der wirtschaftlichen EUR-Rechnung — Umsetzung (OF-69)
modell: guenstig
status: fertig
abhaengig_von: AP-06x
aendert_tests: nein
---

# AP-06xk · Umsetzung gegen die Abnahmebasis AP-06x

Regel und Begründung: `auftraege/AP-06x.md`. Maßgeblich sind die Tests in
`tests/test_eur_barausgleich.py` (unveränderlich, Regel 1).

## Zu ändern

- `analytics/kennzahlen.py` und `analytics/kommission.py`: Die Bewertung zum
  Abrechnungskurs **an einer Stelle** umsetzen (eine kleine Funktion in
  `analytics/kennzahlen.py`, von `kommission.py` importiert — dort wird
  `STUFEN_RANG` schon von dort bezogen) und am Anfang beider reinen
  Funktionen auf die Ausführungszeilen anwenden. Nicht in zwei Kopien.
- Beide I/O-Hüllen (`kennzahlen_bericht`, `kommissions_bericht`) lesen
  zusätzlich `executions.ereignistyp`, `executions.schlusskurs` und
  `instruments.abwicklungsart`.
- Eingabedicts nicht verändern (Kopie mit ersetztem Preis). Decimal, kein float.

## Grenzen

Kein Eingriff in `engine/`, `journal/` außer den beiden Hüllen oben, `tests/`,
`fixtures/`. `analytics/steuer.py` rechnet über Leg-Ergebnisse und bleibt
unverändert.

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Echtabgleich (Kopie von `journal.db`) macht anschließend das starke Modell.
