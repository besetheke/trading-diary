---
titel: Abnahmebasis OA-Strategie auch in der Kettensicht
modell: stark
status: fertig
abhaengig_von: AP-13w, AP-04sw, AP-04sy
aendert_tests: ja
---

# AP-13z · Abnahmebasis: OA-Abgleich auch für die Kettensicht

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-13zk (günstiges Modell). Neue Testdatei `tests/test_rebuild_oa_kette.py`,
sonst keine Änderung unter `tests/` oder `fixtures/`.

## Grund

`journal/rebuild.py` ruft `oa_werte_schreiben()` nur für die Kontosicht auf.
Die Kettensicht — Grundlage der Strategie-Auswertung — trägt daher keine
`oa_strategie` (Echtlauf 05.10.2026: 0 von 7.188 Ketten). Seit OF-68 stimmen
die Summen beider Sichten, damit ist die Kettensicht die richtige Basis für
Auswertungen je Strategie.

## Verhalten

1. Nach dem Schreiben der Kettensicht wird der OA-Abgleich **auch** auf deren
   Ketten und Strukturen angewandt (dieselbe Funktion `oa_werte_schreiben`,
   Ketten/Strukturen der Kettensicht als Eingabe).
2. `RebuildErgebnis.oa_zugeordnet` und `oa_fehler` zählen weiter **nur die
   Kontosicht** (wie `legs`, `structures`, `chains`).
3. Ein zweiter Lauf ohne OA-Daten setzt die drei Felder auch in der
   Kettensicht auf `None` zurück (die Baseline steht beim Schreiben).
4. Der Fingerabdruck wird je Sicht gegen deren eigene Strukturen geprüft: Wo
   die Kontosicht ein Bein nicht trägt (OF-36), kann die Kettensicht
   vollständig treffen (`auto`).

## Abnahme

`tests/test_rebuild_oa_kette.py` (5 Tests) und alle bisherigen Tests grün,
`ruff check .` sauber. Gegen eine Wegwerf-Umsetzung (ein Aufruf mehr in
`journal/rebuild.py`) geprüft: ohne sie schlagen 4 von 5 Tests fehl, mit ihr
laufen alle grün.
