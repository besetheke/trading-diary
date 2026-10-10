---
titel: Kandidatenregeln nach der Praxis des Nutzers — Umsetzung (AP-05, Teil 1)
modell: guenstig
status: fertig
abhaengig_von: AP-05r
aendert_tests: nein
---

# AP-05rk · Umsetzung gegen die Abnahmebasis AP-05r

Regeln und Begründung: `auftraege/AP-05r.md`. Maßgeblich sind die Tests in
`tests/test_campaigns_regeln.py` (unveränderlich, Regel 1);
`tests/test_campaigns.py` muss unverändert grün bleiben.

## Zu ändern

Nur `engine/campaigns.py` (rein, Regel 6: keine Datenbank, keine Uhrzeit):

- IC-Regel über ein Gliederpaar mit gleicher Expiry und überlappendem
  Glied-Intervall (offen = unbegrenzt, wie `_UNBEGRENZT`). Die bisherige
  Hilfsfunktion für die letzte Expiry kann entfallen oder bleibt, wenn sie
  noch gebraucht wird.
- Doppel-Roll-Prüfung beim Financing-Kandidaten mit dem benannten Modulwert
  `DOPPEL_ROLL_FENSTER`. Die Prüfung läuft über **alle** übergebenen Ketten.
- `CampaignKandidat` um `abstand` und `ueberlappung` erweitern (Standard
  `None`, frozen dataclass bleibt), Werte wie in AP-05r beschrieben.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/chains.py`,
`engine/structures.py`, `journal/` (die Zählung der offenen Kandidaten in
`journal/campaigns_sicht.py` und im Rebuild liest weiter die Funktion und
braucht keine Anpassung).

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` nur
`engine/campaigns.py`. Danach wird die Zahl der offenen Kandidaten nach
`journal rebuild` sich ändern (Referenz in OF-71); das ist beabsichtigt.
