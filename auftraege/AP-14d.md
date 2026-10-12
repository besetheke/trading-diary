---
titel: Roller — Geschichte der Kette im Journal bei jeder Position
modell: stark
status: fertig
abhaengig_von: AP-14b, AP-06sd, AP-06sf
aendert_tests: nein
---

# AP-14d · Was hat diese Position schon gekostet?

`GET /roller-status` ergänzt jede Position des Rollers (Spreads, Breaches) um
`kette` — die Geschichte der Kette im Journal: Zahl der Rolls, bereits
realisiertes Ergebnis der Roll-Schritte, Prämie der offenen Legs bei Eröffnung und
laut IBs Marktwert, Unrealisiertes, Strategie, Link zur Position.

- Zuordnung über Basiswert (SPXW/RUTW/NDXW zählen zum Index), Verfall und
  Short-Strike (bei Spreads auch Long-Strike); alle offenen Vertikalen des Journals
  (`BPS`, `BCS`, `Vertical` — Call-Spreads stehen dort teils als „Vertical“).
- Mehrere Ketten mit denselben Strikes sind für den Roller eine Position: Rolls =
  Maximum, Beträge = Summen, `ketten` = Anzahl.
- Nur bei Treffer gesetzt; Stand ist der des letzten Flex-Imports — heute
  Eröffnetes oder seitdem Geändertes hat (noch) keine Kette. Am 12.10.2026: 14 von
  25 Spreads zugeordnet.
- Ein Fehler in der Journal-Abfrage verhindert nie den Status des Rollers.

UI: Spalte „Kette im Journal“ in Breaches und Spreads. Test:
`tests/test_api_roller_historie.py`.
