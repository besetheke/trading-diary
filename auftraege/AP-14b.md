---
titel: Station — Roller R2 sichtbar (Status des Roller-Dienstes)
modell: stark
status: fertig
abhaengig_von: AP-14a
aendert_tests: nein
---

# AP-14b · Roller sichtbar (R2)

Gegenstück zum Roller-Dienst (`options-roller`: `python -m roller.dienst`,
Statusschnittstelle `GET http://127.0.0.1:8600/status`, nur lesend).

1. `GET /roller-status`: reicht den Status des Dienstes durch
   (`erreichbar`, `status`); nie ein Fehler, wenn der Dienst aus ist.
   (Nicht `/roller` — die Seite heißt so; API-Pfade und Seiten dürfen nicht
   kollidieren, `tests/test_ui_routen.py`.)
2. `GET /system`: die Zeile „Options Roller“ trägt Port und Erreichbarkeit, sobald
   `roller_port` gesetzt ist (Modulobjekt: Umgebungsvariable `ROLLER_STATUS_PORT`,
   Standard 8600, 0 = aus). `erzeuge_app(…)` ohne `roller_port` verhält sich wie in
   AP-14a — der dortige Test bleibt unverändert.
3. UI: Seite `/roller` mit IB-Zustand, Breaches (Danger-Strike, Puffer, Roll Theo,
   Edge, Bewertung), offenen Spreads, Protokoll; aktualisiert sich alle 15 s.

Der Roller bestellt in dieser Stufe nie. Test: `tests/test_api_roller.py`.
