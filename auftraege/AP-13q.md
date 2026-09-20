---
titel: Parsernachbesserung - Close und Close Time als '-' (OF-37)
modell: guenstig
status: offen
abhaengig_von: AP-13pl
---

# AP-13q · Parsernachbesserung für den Strich

Umsetzungspaket nach Plan §11.2, Schritt 2: Die Abnahmebasis liegt vor
(AP-13pl), hier wird gegen sie implementiert. **Tests und Fixtures sind
tabu** — fällt ein Test, ist der Code falsch.

Maßgeblich ist der Vertrag in `auftraege/AP-13pl.md`, Abschnitt „Vertrag an
die Umsetzung". Der Befund selbst steht in `OFFENE_FRAGEN.md`, OF-37.

## Aufgabe

`ingest/optionapp.py` bricht an zwei von drei realen OA-Exporten ab, weil
die Spalten `Close` und `Close Time` bei noch nicht geschlossenen Trades
den Wert `-` tragen. Behandle ihn wie eine leere Zelle.

Zwei Stellen sind betroffen, nicht eine:

- `_zeitwert()` — liest `Close Time` (Aufruf in `_zeile_lesen`, `zeile[9]`).
  Fällt zuerst auf.
- `_zahlzelle()` — liest `Close` (`zeile[6]`) und würde unmittelbar danach
  an `Decimal('-')` scheitern.

Die Spalte `Stops` löst dasselbe Problem bereits (`_stopwert`, Vertrag 3) —
sieh dort nach, wie der Strich im Bestand behandelt wird, bevor du etwas
Neues erfindest.

## Grenzen

- **Nur der exakte Strich**, nach `strip()`. `"--"`, `"n/a"` oder sonstiges
  Unlesbares bricht weiterhin mit Nennung des Gefundenen ab. Der Vertrag
  wird um einen benannten Wert erweitert, nicht um eine allgemeine
  Nachsicht gegenüber unlesbaren Zellen.
- **Kein Bezug auf `Status`.** Die Behandlung hängt am Zellwert. `CANCELED`
  und `RUNNING` bleiben für den Parser bedeutungslose Rohwerte (Vertrag 9).
- **`Open` und `Entry Time` bleiben Pflichtfelder.** Sie tragen im gesamten
  realen Bestand nie einen Strich; dort zu lockern wäre Umfangserweiterung.
- Keine weiteren Änderungen an `ingest/optionapp.py`.

## Abnahme

- `tests/test_ingest_optionapp.py` läuft vollständig grün, die zwei neuen
  Tests eingeschlossen.
- `pytest` und `ruff check .` sind sauber.
- `git diff --stat` zeigt Änderungen **ausschließlich** in
  `ingest/optionapp.py`. Kein `tests/`, kein `fixtures/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Verknüpfung mit `executions.oa_trade`, kein Ergebnisabgleich, keine
Strategieübernahme — das ist AP-13 Teil 2 und bleibt beim starken Modell.

Führe die Dateien unter `fixtures/golden/` nicht aus und lies sie nicht
(CLAUDE.md, Regel 2). Alle Fixtures für dieses Paket liegen unter
`fixtures/optionapp/` und sind frei erfunden.
