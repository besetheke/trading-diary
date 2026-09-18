---
titel: Leerzeile im Importblock von test_ingest_optionapp.py (OF-32)
modell: stark
status: fertig
abhaengig_von: AP-13p
aendert_tests: ja
---

# AP-13pk · I001 in der Abnahmebasis beheben

Korrekturpaket nach CLAUDE.md, Regel 1a. **Reine Formatierung** — es ändert
sich keine Erwartung, keine Prüflogik und kein Wert. Betroffen ist genau eine
Leerzeile.

## Anlass

`ruff check .` meldet seit der Umsetzung von AP-13, Teil 1:

```
I001 Import block is un-sorted or un-formatted
  --> tests/test_ingest_optionapp.py:29
```

Zwischen `from ingest.optionapp import import_optionapp_file` und
`from journal.db import create_db_engine` steht eine Leerzeile. Beide sind
First-party — dazwischen gehört keine.

**Die Leerzeile stammt aus AP-13p, also von mir.** Ich habe sie dort mit
`ruff check --fix` erzeugt, und ruff hatte damals recht: Solange
`ingest/optionapp.py` nicht existierte, klassifizierte ruff den Import nicht
als First-party und verlangte die Trennung. Mit dem Modul kippt die
Einordnung, und dieselbe Datei ist nun falsch formatiert. Der Befund war im
Vorbereitungspaket nicht sichtbar — dieselbe Falle wie in AP-02.

Das günstige Modell durfte die Datei nicht anfassen (Regel 1) und hat den
Befund korrekt als OF-32 gemeldet, statt ihn beiläufig zu beheben. Genau so
ist es gedacht.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **`tests/test_ingest_optionapp.py`**, Zeile 30: die Leerzeile zwischen den
  beiden First-party-Importen wird gelöscht. Sonst nichts — keine Erwartung,
  kein Testname, keine Reihenfolge, keine Fixture.

## Abnahme

- `ruff check .` ist sauber.
- Alle 149 Tests bleiben grün, keiner ändert sein Ergebnis.
- `git diff --stat` zeigt genau eine Datei mit einer entfernten Zeile.

## Lehre für künftige Vorbereitungspakete

`ruff --fix` auf einer Testdatei, deren Zielmodul noch nicht existiert,
erzeugt eine Formatierung, die nach der Umsetzung falsch ist. Künftig in
einem Vorbereitungspaket entweder auf den Autofix im Importblock verzichten
oder die Sortierung von Hand so setzen, wie sie **mit** dem Modul richtig
ist. Als Kennzeichen für ruff genügt, dass das Paket den Modulnamen im
Vertrag benennt — die Datei selbst kann bereits die Zielform tragen.
