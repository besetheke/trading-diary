---
titel: Strategie-Scorecard
modell: stark
status: fertig
abhaengig_von: AP-04z, AP-13r3, AP-06v
aendert_tests: nein
---

# AP-06sc · Welche Strategien verdienen

Hebel 2 aus der Planung vom 11.10.2026, vom Nutzer freigegeben. Seit AP-13r3
tragen 2.063 Positionen eine OA-Strategie, seit AP-04z steht das Ergebnis von
Zuteilungen und Covered Calls bei der Position, die sie ausgelöst hat.

## Vertrag

1. `analytics/strategien.py`, rein: je Strategie (`None` = ohne) über die
   **geschlossenen** Positionen der Kontosicht, Ergebnis netto EUR
   wirtschaftlich (`kennzahlen_auswertung`, wie Equity/Positionen): Anzahl,
   offen, Gewinner, Verlierer, ohne Kurs, Trefferquote, Summe, Ø je Position,
   Ø Gewinn, Ø Verlust, Profit-Faktor (ohne Verluste `None`), größter Gewinn
   und Verlust, max. Drawdown der aufsummierten Kurve in Schließungsreihenfolge
   (Start 0), Zuteilungsquote, Ø Haltedauer. Rundung benannt: Quoten und
   Profit-Faktor 4 Stellen, Haltedauer 1 Stelle, HALF_UP; Beträge ungerundet.
   Sortierung nach Summe absteigend.
2. `strategie_bericht(db, von, bis)`: Zeitraum am Tag der Schließung; liefert
   die Überleitung zum realisierten Gesamtergebnis (Equity): Σ Strategien
   + realisierte Teile offener Positionen (Abgrenzung, als Differenz; ohne
   Zeitraum genau die geschlossenen Strukturen offener Ketten) + Geschäfte
   ohne Position (lose Legs) = realisiert netto.
3. `GET /strategien?von&bis` (422 bei von > bis); Seite `/strategie`
   („Strategien" in der Navigation), Zeitraum aus dem Kopf, sortierbar über die
   Spaltenköpfe (nur Reihenfolge), Strategie verweist auf die gefilterte
   Positionsliste, Überleitung darunter.

Tests: `tests/test_strategien.py` (5), `tests/test_api_strategien.py` (4), von
Hand gerechnet.

## Echtbestand (11.10.2026)

57 Strategien. Überleitung: 114.876,13 € (Strategien) − 15.535,31 € (realisierte
Teile offener Positionen) − 10.956,16 € (ohne Position) = 88.384,66 € — gleich
dem Dashboard. Antwortzeit ≈ 2 s.
