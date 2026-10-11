---
titel: Positionen — Spalte Unrealisiert, Filterleiste, Zeilen je Seite, Legenden unten
modell: stark
status: fertig
abhaengig_von: AP-07fu, AP-07fm, AP-08s
aendert_tests: nein
---

# AP-07ku · Unrealisiert je Position und Feinschliff

Wünsche des Nutzers (11.10.2026):

1. Legenden unter das Diagramm → `ZweiLinien` setzt die Legende unter die
   Grafik (alle Diagramme mit Legende nutzen diese Komponente).
2. Spalte für offene Positionen mit unrealisiertem Gewinn → `GET /ketten` trägt
   je Kette `unrealisiert_eur` (offene Legs zu IBs letztem Marktwert gegen den
   Einstand des Journals, EUR — dieselbe Rechnung wie AP-07fu; geschlossene
   Ketten und offene ohne Bestand: `null`) und `offene_legs_ohne_kurs`. Spalte
   „Unrealisiert²" (Fußnote ²; „?" bei Legs ohne Bestand). Eine gespeicherte
   Spaltenwahl (v2) wird übernommen und um die Spalte ergänzt (v3).
3. Filterleiste: „Eröffnet von/bis" beginnt die zweite Reihe; „Rolls von/bis"
   schmal.
4. „Nur offene, wie kann realisiert sein?" — Bei 33 der 118 offenen Ketten sind
   frühere Roll-Schritte schon geschlossen (87 Strukturen); deren Ergebnis ist
   realisiert. Der Kopf der Auswertung erklärt das (Tooltip) und zeigt neu
   „Realisiert + unrealisiert" (`unrealisiert.mit_realisiert_eur`, AP-07fv).
5. „Beträge unpassend (−46k €, +28k USD)" — Prüfung: −39.002 € DAX-Rolls,
   −8.888 € ESTX50-Rolls; USD +15.577 WDC, +5.604 KNSL, +5.098 ASTS, +4.895 GLW
   u. a. Die Summe in EUR (−21.891 €) = −46.729 € + 28.854 USD zum jeweiligen
   Tageskurs. Rechnerisch stimmig; aussagekräftig erst zusammen mit dem
   Unrealisierten (Punkt 4).
6. Zeilen je Seite: Vorgabe 200, Auswahl 50/100/200/500.

Tests: `tests/test_api_ketten_unrealisiert.py` (3, von Hand gerechnet).
