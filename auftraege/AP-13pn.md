---
titel: Abnahmebasis des OA-Parsers erweitert - Eurex-Produktcode in der Leg-Grammatik (OF-66)
modell: stark
status: fertig
abhaengig_von: AP-13
aendert_tests: ja
---

# AP-13pn · Produktcode in der Leg-Grammatik

Korrekturpaket nach CLAUDE.md, Regel 1a (`aendert_tests: ja`, `modell: stark`,
läuft unter `locker`), **implementiert nichts**. Die Parsernachbesserung ist
AP-13s (günstiges Modell); dasselbe Muster wie AP-13pl → AP-13q und
AP-13pm → AP-13r.

## Befund (OF-66)

Der Gesamtexport der OptionApp (`Trades_2026-10-04_16-02-17_all.xlsx`, 5.358
Trades) lässt sich nicht laden: Eine Zeile (ausgeführter DAX-Trade, CLOSED) trägt
vor dem Recht einen Eurex-Produktcode (`-1xODAP P23000 (260918)`). Der Parser
bricht dort ab, was nach AP-13 (Vertrag 5) richtig ist — die Grammatik kennt ihn
nicht. Alle übrigen 5.357 Zeilen sind parserkonform (CANCELED und RUNNING über die
Regeln aus OF-40).

## Was dieses Paket festlegt

Neue Erwartungen, nichts Bestehendes geändert:

- Produktcode: drei bis sechs Großbuchstaben, ein Leerzeichen, **je Leg
  optional**; Richtung, Menge, Recht, Strike, Verfall wie bisher.
- Der Code ist **nicht** Teil der Leg-Identität; der Rohwert `roh` behält ihn.
- Gegenproben: ein ungültiges Recht (`Z`) mit Code und ein kleingeschriebener Code
  bleiben Defekte der Quelle, benannt mit der Trade-Nummer.

## Geändert (alles neu, kein bestehender Wert angefasst)

- `fixtures/optionapp/erzeugen.py`: drei neue Listen und drei neue Aufrufe;
  neu erzeugt wurden **nur** `oa_produktcode.xlsx`,
  `oa_produktcode_defekt_recht.xlsx`, `oa_produktcode_defekt_klein.xlsx`
  (bestehende Fixtures byteweise unverändert, deshalb nicht das ganze Skript
  ausgeführt).
- `tests/test_ingest_optionapp.py`: fünf neue Tests am Ende der Datei, keine
  bestehende Assertion geändert.
- `auftraege/AP-13-anhang-oa-format.md`: Absatz „Produktcode".

## Prüfung der Abnahmebasis (vor der Abgabe)

Vor der Abgabe gegen eine Wegwerf-Grammatik (`(?:[A-Z]{3,6} )?` vor dem Recht)
geprüft: 31/31 grün; danach zurückgesetzt. Ohne die Änderung rot allein an den
drei Zerlegungs-Tests (`ValueError: ... folgt nicht der Leg-Grammatik`); die zwei
Gegenproben laufen schon heute grün und bleiben es.
