---
titel: Positionsfilter mit Mehrfachauswahl
modell: stark
status: fertig
abhaengig_von: AP-07f, AP-07fw, AP-08g2b
aendert_tests: nein
---

# AP-07fm · Mehrere Werte je Filter

Wunsch des Nutzers (11.10.2026): In den Positionen mehrere Werte eines Filters
gleichzeitig wählen (bisher je Filter nur einer).

## Vertrag

1. `GET /ketten` und `GET /auswertung`: Basiswert, Anlageklasse, Währung,
   Strategie, Seite und Endzustand dürfen wiederholt werden
   (`?basiswert=AAA&basiswert=BBB`). Innerhalb eines Filters ODER, zwischen den
   Filtern UND. Leere Werte zählen nicht; ein einzelner Wert wirkt wie bisher
   (alle bestehenden Filtertests unverändert grün).
2. Lose Legs (AP-07f) folgen derselben Regel: `LoseLegFilter` nimmt für
   Basiswert, Anlageklasse und Währung einen Wert oder eine Menge
   (`analytics.equity.im_filter`); ebenso die offenen Legs fürs Unrealisierte.
3. Oberfläche: Die fünf Auswahlfelder sind aufklappbare Listen mit Häkchen
   („alle", solange nichts gewählt ist; „Auswahl leeren"). Basiswert bleibt ein
   Textfeld — mehrere mit Komma (`DAX, ESTX50`). In der Adresse stehen die Werte
   als wiederholter Parameter (Lesezeichen, Neuladen).

Tests: `tests/test_api_filter_mehrfach.py` (8, von Hand gerechnet, Welten aus
`test_api_filter.py` und `test_api_filter_lose_legs.py`).
