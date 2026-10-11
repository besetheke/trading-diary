---
titel: IBs realisiertes Ergebnis je Ausführung in eigener Tabelle (flex_ib_realized)
modell: stark
status: fertig
abhaengig_von: AP-02
aendert_tests: nein
---

# AP-02p · fifoPnlRealized je Ausführung

Befund (OF-78): Beim Import gewinnt die erste Quelle; `executions` wird nie
überschrieben (Regel 4). Eine ältere Flex-Abfrage ohne `fifoPnlRealized` ließ das
Feld dort für immer leer, obwohl spätere Dateien es lieferten — 11.949 von 34.510
Ausführungen. Jede Vergleichsrechnung mit IBs realisiertem Ergebnis aus der
Datenbank war dadurch zu klein.

## Umsetzung

- Neue Tabelle `flex_ib_realized` (Migration `c4e8a2b6d0f1`, nur neue Tabelle):
  je Ausführung IBs `fifoPnlRealized` (Positionswährung, netto nach Kommission)
  und `fxRateToBase`; Schlüssel `trade:<tradeID>`. Eine `0` ist ein Wert
  (eröffnende Zeile), „nicht geliefert" erzeugt keine Zeile; vorhandene Zeilen
  werden nie überschrieben.
- Der Import (`ingest/flex.py`) füllt sie für jede **neue** Datei mit — auch dann,
  wenn die Ausführungen selbst schon bekannt sind.
- `journal nachtragen-realisiert <dateien>` (`nachtragen_realisiert`) liest nur
  dieses Feld aus **bereits importierten** Dateien nach (der Import überspringt
  sie vollständig); wiederholbar.
- Abnahmebasis: `tests/test_ingest_flex_realisiert.py` (8 Tests, Fixtures
  `activity_realisiert.xml` und `activity_realisiert_nachtrag.xml`, von Hand
  gerechnet).

## Nachweis

Gesamtsuite grün, ruff sauber. Echtbestand (Sicherung davor, Migration,
Nachtrag aus den fünf Jahresdateien): **34.510 Zeilen, Abdeckung 34.510 von
34.510 Ausführungen, Summe 77.853,98 €** — identisch mit der Summe aus den
Dateien (OF-78).
