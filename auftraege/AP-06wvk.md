---
titel: Korrektur der Abnahmebasis AP-06w - eine Assertion in test_kommissions_attribution.py
modell: stark
status: fertig
abhaengig_von: AP-06w
aendert_tests: ja
---

# AP-06wvk · Eine fehlerhafte Assertion

Korrekturpaket nach CLAUDE.md, Regel 1a (`aendert_tests: ja`, läuft unter
`locker`). `analytics/kommission.py` und `journal/cli.py` aus AP-06wk bleiben
unberührt. Befund vom günstigen Modell gemeldet, nicht selbst geflickt.

## Befund

`test_cli_ohne_kommissions_option_schreibt_keine_zweite_datei` verglich
`[p.name for p in tmp_path.iterdir()] == ["kennzahlen.csv"]`. Die Fixture
`migrated_db` legt die SQLite-Datei selbst in `tmp_path`; die Gleichheit konnte
mit keiner Implementierung wahr werden. Fehler der Abnahmebasis (AP-06w): Die
CLI-Tests liefen vor der Abgabe nicht gegen eine Umsetzung, weil die
Wegwerf-Prüfung nur die reinen Tests abdeckte (Lehre: auch die CLI-Tests mit
einer Wegwerf-CLI prüfen).

## Korrektur (nur diese Assertion, Prüfabsicht bleibt)

Verglichen werden nur die CSV-Dateien: `sorted(p.name for p in
tmp_path.glob("*.csv")) == ["kennzahlen.csv"]`. Die Absicht — ohne
`--kommission` entsteht keine zweite Berichtsdatei — bleibt vollständig
erhalten und ist nicht schwächer, weil die Datenbankdatei kein Bericht ist.

## Abnahme

- `tests/test_kommissions_attribution.py` grün gegen AP-06wk.
- `git diff --stat` unter `tests/`: nur diese Datei, nur diese Stelle.
