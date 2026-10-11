---
titel: Auswertung der Positionen — realisiert je Tag, unrealisiert offener Positionen, Wochen
modell: stark
status: fertig
abhaengig_von: AP-07f, AP-08d, AP-03vz2
aendert_tests: nein
---

# AP-07fu · Taggenau statt aufsummiert

Wünsche des Nutzers (11.10.2026): Standard 100 Zeilen je Seite; Balken standardmäßig
in Wochen; in den Zeitreihen nicht summieren, sondern der realisierte Gewinn
taggenau; offene Positionen im Diagramm als unrealisiert.

## Umsetzung

- `analytics/unrealisiert.py`: offene Legs mit IBs letztem Marktwert gegen den
  **Journal-Einstand** (Preis ÷ Faktor, Kommission des Legs), Anteil des Legs an
  der Position; ohne Bestandszeile gezählt, nie 0. Tests `tests/test_unrealisiert.py`
  (5, von Hand gerechnet, auch mit Kapitalmaßnahme).
- `GET /auswertung` zusätzlich: `wochen` (ISO) und `unrealisiert` (Stand, EUR,
  bewertete Legs, ohne Kurs) für die offenen Legs der Auswahl — dieselbe Regel wie
  beim realisierten Ergebnis (Ketten der Auswahl, lose Legs nach ihren Werten).
  Liegt `bis` vor dem Bestandsstichtag, kein Wert. Tests
  `tests/test_api_auswertung_wochen.py` (3).
- Positionsliste: Auswertung zeigt „Realisiert je Tag" als Balken (am Tag der
  Schließung) und einen hellen, gestrichelten Balken „offen" für das
  Unrealisierte; darunter Wochen (Vorgabe) oder Monate. Standard 100 Zeilen.
- Dashboard: Balken standardmäßig in Wochen.

## Echtbestand

CAR: realisiert 5.501,95 € (= 6.464,41 USD, gleich IB auf den Cent), nichts offen.
WDC: realisiert 15.289,17 €, unrealisiert −30.018,80 € (5 offene Legs, Journal-
Einstand; IBs Wert −11.496,84 € enthält die Prämien im Einstand).
