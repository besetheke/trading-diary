---
titel: Befehl journal import-optionapp
modell: guenstig
status: offen
abhaengig_von: AP-13
---

# AP-13y · `journal import-optionapp`

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor:
`tests/test_cli_import_optionapp.py` (4 Tests, geprüft gegen eine
Wegwerf-Fassung). **Tests und Fixtures sind tabu** — fällt ein Test, ist der
Code falsch; hält ein Test sich für unerfüllbar, melden, nicht ändern.

## Worum es geht

Der OptionApp-Parser (`ingest.optionapp.import_optionapp_file`) ist fertig und
getestet, aber nur über Tests aufrufbar: `journal/cli.py` kennt keinen
Befehl dafür. Dieses Paket verdrahtet ihn, in derselben Form wie den
Flex-Import.

## Zu bauen

Ausschließlich in `journal/cli.py`:

- Unterbefehl `import-optionapp <datei> [--db <sqlite>]` (Default für `--db`
  wie überall: Umgebungsvariable `JOURNAL_DB`, sonst `journal.db`).
- Ruft `import_optionapp_file(db_pfad, datei)`.
- Erfolg, Rückgabe 0, Ausgabe genau so (Zählwerte, keine Beträge):
  `OptionApp-Import <Dateiname>: <gelesen> Trades gelesen, <neu> neu, <übersprungen> übersprungen`
  mit `ergebnis.zeilen_gesamt`, `ergebnis.zeilen_neu`,
  `ergebnis.zeilen_uebersprungen`.
- `FileNotFoundError` und `ValueError` aus dem Parser: Rückgabe 1, auf stderr
  `Import fehlgeschlagen: <Meldung>`, kein Traceback — genau wie der
  Flex-Zweig.

## Wo du abschreiben sollst

Der Zweig `if argumente.befehl == "import":` in `journal/cli.py`: gleiche
Fehlerbehandlung, gleiche Form der Ausgabe.

## Grenzen

- Keine Änderung an `ingest/optionapp.py` (Parser, Grammatik, Fixtures).
- Kein Überschreiben, keine „Fortschreibung" vorhandener Trades — das ist
  bewusst offen (OF-65). Bei abweichendem Inhalt bricht der Parser ab; das
  ist so gewollt.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen oder ausführen.
  Der Befehl gegen die echten Exporte wird vom starken Modell/Nutzer
  ausgeführt, nicht in diesem Paket.

## Abnahme

- `tests/test_cli_import_optionapp.py` 4/4 grün, Gesamtsuite grün,
  `ruff check .` sauber.
- `git diff --stat`: ausschließlich `journal/cli.py`.
