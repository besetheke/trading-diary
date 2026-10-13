---
titel: Roller R3 — Strategie-Vorschlag und Roll-Freigabe per Klick (Paper)
modell: stark
status: fertig
abhaengig_von: AP-14b
aendert_tests: nein
---

# AP-14e · Roll-Freigabe in der Station (Roller R3)

Gegenstück zu `options-roller` (Commits R3): Der Dienst läuft mit
`python -m roller.dienst --paper-orders --ib-port 7497`, beobachtet die
Strategie-Position (SPX BPS D10 W25 21DTE PT50, Roll bei |Δ| > 0,38), rechnet bei
Signal einen Roll-Vorschlag und führt ihn erst auf Befehl aus.

1. `POST /journal/roller-befehl/{name}` (nur mit `mit_journal`, Pfad unter `/journal`, weil schreibende Routen dort liegen): reicht `roll-freigabe` und
   `strategie-pruefen` an `POST http://127.0.0.1:8600/befehl/<name>` durch. Andere
   Namen: 404. Die Antwort des Dienstes kommt unverändert zurück; Ablehnungen
   (Leitplanken, nicht Paper) mit demselben Statuscode und Begründung.
2. `/roller-status` trägt `strategie` (Position, Delta, Signal, Vorschlag, letzter
   Roll) und `orders.modus`, soweit der Dienst sie liefert.
3. UI: Karte „Strategie (Paper)“ auf der Roller-Seite mit „Neu prüfen“ und
   „Roll freigeben“ (nur aktiv bei Vorschlag und Paper).

Leitplanken liegen im Dienst, nicht in der Station: nur Paper (Port 7497 und
Konto `DU…`), Vorschlag höchstens 15 min alt, höchstens 3 Rolls je Kette, ein Roll je
Tag, nur Netto-Kredit ≥ 0, Limit-Orders, ein Roll gleichzeitig. Ohne
`--paper-orders` bleibt der Dienst lesend (POST → 405).

Test: `tests/test_api_roller_befehl.py`.
