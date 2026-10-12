---
titel: Backtest gegen Live — Ursache der Abweichung, Monatsvergleich, CSV
modell: stark
status: fertig
abhaengig_von: AP-12a
aendert_tests: nein
---

# AP-12c · Warum weicht der Bot vom Backtest ab?

Vorlage: die Pipeline aus dem früheren Chat (Zusammenfassung des Nutzers
12.10.2026; sie lag nur in einem temporären Arbeitsbereich und ging verloren).
Jetzt Teil des Projekts, damit sie nicht mehr verschwindet.

## Vertrag

1. **Paarung** eines bestätigten Paars OO ↔ Bot: `engine.oo_zuordnung.
   zuordnen_eins_zu_eins` — gleicher Tag, Familie, Signatur und Breite wie die
   Vorschläge, aber **90 Minuten** Fenster und **eins zu eins** (jeder Bot-Trade
   nur einmal; kleinster Zeitabstand gewinnt, dann Strike-Abstand). Die Vorschläge
   bleiben bei 20 Minuten.
2. **Ursache je Paar, genau eine**, Prüfreihenfolge: offen · Kontraktzahl ·
   Toleranz (≤ 10 USD je Kontrakt) · Einstiegszeit (> 3 min) · Strikeauswahl ·
   Exit-Logik (Verfall gegen vorzeitig, oder > 5 min) · Slippage (Rest). Die
   Summen der Ursachen ergeben die Differenz je Kontrakt; der **Kontrakteffekt**
   = (Kontrakte Bot − Kontrakte Backtest) · Ergebnis Bot je Kontrakt steht
   daneben (Dollar insgesamt).
3. **Monatsvergleich**: `von`/`bis` (Tag der Eröffnung) an `GET /backtests`,
   `GET /backtests/paare` und dem globalen Zeitraum der Seite; „nur Backtest“ und
   „nur Bot“ zählen nur im gemeinsamen Zeitraum.
4. **CSV**: `journal backtest-bericht <datei> [--von] [--bis]` — alle Paare und
   Einzelfälle mit Ursache, Semikolon, UTF-8 mit BOM.
5. UI: Seite `/backtest` zeigt die Ursachen je Zuordnung, Versatz und Ursache je
   Paar und folgt dem Zeitraum.

## Monatlicher Ablauf

Neue OO-Exporte nach `C:\Trading\oo` legen (der nächtliche Abruf liest sie ein,
sonst `journal import-optionomega <Ordner>`), Seite **Backtests** öffnen, Monat im
Zeitraum wählen, neue Strategien unter „Ohne Bot“ bestätigen oder ablehnen,
Entscheidungen bleiben gespeichert.

Tests: `tests/test_backtest_ursachen.py`, `tests/test_api_backtests_ursachen.py`,
`tests/test_backtest_csv.py`, `tests/test_api_backtests_spy_xsp.py`.
