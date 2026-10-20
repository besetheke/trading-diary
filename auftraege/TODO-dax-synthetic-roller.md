# ToDo · DAX Synthetic im Options Roller (zurückgestellt, 19.10.2026)

**Status:** komplett zurückgestellt (20.10.2026) – auch im Journal: der Tab ist aus dem Menü genommen, die Seite bleibt unter `/dax-synthetic` erreichbar, Code und Tests bleiben. Erst muss das Journal die Strategie sauber erkennen und auswerten (Tab „DAX Synthetic“,
`analytics/dax_synthetic.py`). Der Roller-Teil wird erst nach Abnahme der Journal-Seite begonnen.

## Strategie (Nutzernotiz, mit Korrekturen vom 19.10.2026)

1. Aktuellen DAX-Future (FDAX) kaufen. Die Volatilitätsbedingung (Vola > 10 %) **entfällt**.
2. Zwei Tage vor Verfall auf den nächsten Future rollen (horizontal, ein Termin weiter).
3. Long-Put mit rund 1,5 Jahren Laufzeit kaufen (Beispiel Delta 30, etwa 1.050–1.100 EUR; Strike theoretisch frei wählbar).
4. Short-Call leicht im Geld (etwa 100–130 EUR Prämie, Delta 40–45), Laufzeit eine Woche, **meist nackt, in der Regel 1 Kontrakt**.
   - 4a. Liegt der Markt vor Verfall unter dem Strike → zurückkaufen.
   - 4b. Ist Theta < Theta des Calls der neuen Woche → zurückkaufen.
   - 4c. Neuen Short-Call eröffnen.
   - 4d. Liegt der Markt über dem Strike → rollen (**nur horizontal, eine Woche weiter**).

## Offen, bevor der Roller etwas baut

- **Freigabe:** Futures am Paper-Konto handeln (bisher handelt der Roller nur Optionsspreads).
- **Future-Kontrakt:** genaue Spezifikation (FDAX, Börse EUREX, Multiplikator, Tick), Wahl des Verfalls, Zeitpunkt der Rolle
  („zwei Tage vor Verfall“ in Handelstagen oder Kalendertagen?), Kombi-Order (Calendar) oder zwei Orders.
- **Schutz-Put:** Auswahlregel (Delta 30? Strike festhalten? Wann erneuern: bei Restlaufzeit unter X Tagen?).
- **Short-Call:** Strike-Wahl (Delta 40–45 oder Prämie 100–130 EUR – was gilt, wenn beides nicht zusammenpasst?), Zeitpunkt
  der Eröffnung und des Rollens (Wochentag, Uhrzeit), Handelsklasse ODAX (wie bei den DAX-Spreads, Multiplikator 5).
- **Regel 4b:** Wie wird Theta bestimmt (IB-Greeks live, Modell?) und verglichen (Betrag je Tag, je Kontrakt)?
- **Risiko:** nackter Short-Call – Obergrenzen (Margin, Verlust je Woche), Not-Aus, Zusammenspiel mit der Automatik.
- **Journal-Bezug:** Jede Order trägt eine eigene Referenz (`R3|…`), damit das Journal die Bausteine eindeutig zuordnet
  (heute nur Vorschlag nach Merkmalen, OF-103).

## Voraussetzungen im Journal (zuerst)

- Tab „DAX Synthetic“: Bausteine, Ergebnis je Schutz-Put, **alle Trades einzeln** (erledigt, siehe Liste im Tab).
- Zuordnung Future/Short-Call zu einer bestimmten Put-Einheit prüfen, wenn mehrere Puts laufen (OF-103).
- Als Strategie im Journal (`strategies`, `diskretionaer`) führen und den Legs zuordnen – nach Bestätigung durch den Nutzer.
