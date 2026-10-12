---
titel: Station — Breakout Research (BO Research Suite) einbinden, nur lesend
modell: stark
status: fertig
abhaengig_von: AP-14a
aendert_tests: nein
---

# AP-14c · Breakout in der Station

Die BO Research Suite (`C:\10_Coding\BO Research Suite`, eigenes Forschungsprojekt
mit eigener Governance, kein Git) bleibt eigenständig. Die Station liest nur:
`PROJECT_STATE.md` (Stand, Ziel), das Hypothesenregister (Excel, Blatt „Experiment
Backlog“) und die Zusammenfassung der **Discovery**-Ergebnisse
(`data/results/hyp*_discovery_v1.json`: Status, Sitzungen, Kosten 0,5, Bootstrap p05,
Gates; verschiedene Dateiformate werden toleriert).

Nie gelesen: Validation und Holdout (bleiben versiegelt); nie ein Lauf angestoßen.
`GET /breakout-stand` (nicht `/breakout` — Seitenname), Ordner über `BO_ORDNER`.
Seite `/breakout`: Ergebnisse, Register. Test: `tests/test_api_breakout.py`.
