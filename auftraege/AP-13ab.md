---
titel: Abgleich OA ↔ IB je Trade und Strategie
modell: stark
status: fertig
abhaengig_von: AP-13r3, AP-04z, AP-06sc
aendert_tests: nein
---

# AP-13ab · Abgleich OA ↔ IB

Wunsch des Nutzers (11.10.2026): „Abgleich ist das, was wir unbedingt brauchen."

## Vertrag

1. `analytics/oa_vergleich.py`, rein: IB-Ergebnis eines OA-Trades = Σ (brutto +
   Kommission) aller Legs der Kontosicht, deren eröffnende Ausführung die
   OA-Nummer trägt, plus Legs der daraus zugeteilten Aktien
   (`assignment_links`). Vergleich in der Währung des Trades (IB) mit OAs
   Gewinn in Originalwährung (`Profit (orig.)`, sonst OAs USD-Wert).
2. Einordnung: `offen`, `fehlt`, `waehrung`, `gleich` (|Δ| ≤ 0,05),
   `verrechnet` (über Legs mit anderen OA-Trades verbunden — Konto-FIFO hat
   Kontrakte verschiedener Bots gegeneinander geschlossen; die Gruppe stimmt),
   `zuteilung`, `schaetzung` (OA „estimated"), `gering` (|Δ| ≤ 1,00), `sonst`.
   Je Strategie und Währung Zählungen und Summen der vergleichbaren Trades.
3. Import: `anreichern=True` (`journal import-optionapp --anreichern`) — gleiche
   Trades übernehmen das vollständigere Zeilenbild des neuen Exports; Inhalt
   unverändert, alter Rohstand unter `_vorher`.
4. `GET /oa-abgleich?von&bis` (am OA-Schlusstag): Strategien und die
   nicht-gleichen Trades; Seite `/abgleich` („Abgleich OA").

Tests: `tests/test_oa_vergleich.py` (4), `tests/test_api_oa_abgleich.py` (2),
`tests/test_ingest_optionapp_anreichern.py` (2).

## Echtbestand (11.10.2026)

1.368 alte OA-Zeilen angereichert (Backup `journal-vor-oa-anreichern-20261011.db`).
2.068 Trades: gleich 1.480, verrechnet 471, gering 16, OA-Schätzung 18,
Zuteilung 2, ungeklärt 63, offen 12, fehlt 6.

**Befund:** Teilen sich Bots denselben SPX-Kontrakt, schließt IB nach FIFO über
das ganze Konto; Ergebnis wandert zwischen Trades und Strategien (Beispiel
1272 + 1286: einzeln −689,76/+11.555,04 und −1.057,38/−13.302,19, zusammen OA
−1.747,14 = IB −1.747,15). Das betrifft auch die Strategie-Scorecard (AP-06sc,
Kontosicht). Die Kettensicht mildert es (1.598 gleich), behebt es nicht →
vorgemerkt: eigene Paarung je OA-Trade („OA-Sicht", OF-82).
