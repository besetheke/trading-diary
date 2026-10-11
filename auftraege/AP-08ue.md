---
titel: Startseite „Übersicht"
modell: stark
status: fertig
abhaengig_von: AP-06h, AP-06e, AP-08d, AP-13r2, AP-08r
aendert_tests: nein
---

# AP-08ue · Übersicht

Vorschlag aus der Arbeitsplanung (11.10.2026), vom Nutzer freigegeben („so viele
wie möglich"): eine Startseite mit dem Wichtigsten auf einen Blick.

## Vertrag

1. `GET /uebersicht?heute=JJJJ-MM-TT` (ohne `heute`: Datum des Servers; die
   Oberfläche schickt das lokale Datum des Browsers):
   - `kontowert_eur`/`kontowert_stand`: letzter NAV-Tag bis `heute` (`/nav`);
   - `realisiert_woche_eur`, `_monat_eur`, `_jahr_eur`: Equity netto am Tag der
     Schließung für ISO-Woche (Mo–`heute`), Monat und Jahr bis `heute`;
   - `unrealisiert_eur`/`bestand_stand`/`offene_positionen`: Bestand laut IB
     (`/depot`);
   - `verfaelle`: offene Optionen mit Verfall ab `heute`, je Tag und Basiswert
     gezählt, höchstens zehn.
   Nichts neu berechnet — alle Zahlen aus den bestehenden Quellen.
2. Seite `/start` („Übersicht", erster Eintrag der Navigation): drei Kacheln
   (Kontowert, Realisiert, Offene Positionen), Tabelle der nächsten Verfälle
   (Verweis auf die Positionsliste, Basiswert und Endzustand „Offen"), Liste
   „Zu erledigen" (Rolls prüfen; OA-Export, solange Trades ohne Strategie sind).
   `Schnellstart` öffnet `/start`; `/` bleibt die Positionsliste (Lesezeichen).

Tests: `tests/test_api_uebersicht.py` (4, Welt aus `test_api_ueberleitung.py`).
