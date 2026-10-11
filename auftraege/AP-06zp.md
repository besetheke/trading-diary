---
titel: Tempo — Strukturen je Kette einmal gruppieren
modell: stark
status: fertig
abhaengig_von: AP-06v
aendert_tests: nein
---

# AP-06zp · Tempo der Kennzahlen

Messung (11.10.2026, Echtdaten): `/performance` 4,7 s, `/auswertung` 3,4 s,
`/ueberleitung` 5,7 s. Fast die Hälfte von `equity_bericht` lag in
`kennzahlen_auswertung`: Je Kette lief ein Durchgang über alle Glieder, um ihre
Strukturen zu finden — quadratisch (≈ 17.000 Ketten × 17.000 Glieder).

## Umsetzung

- `analytics/kennzahlen.py`: Strukturen je Kette einmal vorab gruppiert, danach
  wie bisher sortiert. Rein mechanisch, Ergebnis unverändert (bestehende Tests
  der Kennzahlen und der Equity unverändert grün).

## Ergebnis

`equity_bericht` 2,5 s → 1,0 s; `/performance` und `/auswertung` ≈ 1,1 s,
`/ueberleitung` ≈ 2,5 s (TestClient, warm).

Bewusst **kein** Zwischenspeicher: Er müsste jeden Import und Neuaufbau sicher
erkennen; ein veralteter Wert wäre schlimmer als eine Sekunde Wartezeit.
