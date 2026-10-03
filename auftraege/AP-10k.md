# AP-10k — Umsetzung: Steuerliche Auswertung

modell: guenstig
status: offen
aendert: analytics/steuer.py (neu), journal/steuer.py (neu), journal/cli.py (Subcommand steuer)
aendert_tests: nein
abhaengig_von: AP-10v (Vertrag + Abnahmetests liegen vor und sind unveränderlich)

## Aufgabe

Umsetzung der Abnahmebasis AP-10v. Der Vertrag steht in
`auftraege/AP-10v.md`; die Abnahmetests in `tests/test_steuer.py` sind per
Hand gerechnet und dürfen nicht geändert werden (CLAUDE.md, Regel 1b). Rot
bis zur Umsetzung — der aktuelle Importfehler ist der erwartete Zustand.

## Ablauf (verbindlich)

1. `analytics/steuer.py`: Datenklassen und `steuer_auswertung(...)` nach
   Vertrag 1–11 (rein, Regel 6: keine DB, keine Uhrzeit, kein Zufall).
2. `analytics/steuer.py`: `als_csv(ergebnis, jahr=None)` nach Vertrag 12.
3. `journal/steuer.py`: `steuer_bericht(db_pfad)` nach Vertrag 13.
4. `journal/cli.py`: Subcommand `steuer <datei> [--jahr N]`, schreibt
   UTF-8 mit BOM (Excel), Exit 0 nur bei geschriebenem Dateikörper.
5. `ruff check .` und `pytest` — alles grün, keine anderen Dateien angefasst.

## Grenzen

- Keine Änderungen an tests/, engine/, journal/rebuild.py, schema.py.
- Keine neuen offenen Fragen im Code: Was wie OF-24/OF-58/OF-59 geparkt ist,
  bleibt geparkt; kommentiert, nicht implementiert.
- Die Ausweise sind Vorbereitung für den Steuerberater, keine Steuerberatung.

## Abnahme

- `pytest` vollständig grün (inkl. `tests/test_steuer.py`), `ruff check .`
  sauber. `git diff --stat` zeigt nur die drei genannten Stellen.
