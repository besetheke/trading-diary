---
titel: Station — Bereichsnavigation, Seite System, Momentum Lab eingebettet
modell: stark
status: fertig
abhaengig_von: -
aendert_tests: nein
---

# AP-14a · Cockpit-Gerüst

Zielbild: `plan/zielbild-station.md`.

1. `GET /system`: Dienste (TWS live/Paper, IB Gateway live/Paper, Momentum Lab,
   Options Roller) mit Erreichbarkeit per TCP-Verbindungsversuch auf 127.0.0.1
   (keine API-Sitzung); Roller ohne Port → `erreichbar = null` mit Hinweis.
   Letzter Import und Datenstand je Quelle (flex, optionapp, optionomega).
   `erzeuge_app(…, pruefe_port=…)` nur für Tests.
2. UI: Titel „Trading Station“, Bereichsnavigation (Journal · Abgleich & Tests ·
   Roller · Momentum Lab · Breakout · System), Unternavigation je Bereich,
   Zeitraum nur in Journal und Abgleich & Tests. Seiten `/zustand` (System),
   `/roller` (Stufenplan), `/momentum` (eingebettet, sonst Hinweis), `/breakout`.

Test: `tests/test_api_system.py`.
