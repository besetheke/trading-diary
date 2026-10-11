---
titel: Dashboard mit einem Diagramm (Kontowert & Ergebnis, Drawdown %, Wochen/Monate); Wertentwicklung
modell: stark
status: fertig
abhaengig_von: AP-06h, AP-06e, AP-08u
aendert_tests: nein
---

# AP-08p · Ein Diagramm, drei Ansichten

Wunsch des Nutzers (11.10.2026): „Baue in das Dashboard nur einen Chart ein, der
die verschiedenen Daten anzeigen kann. Das wichtigste ist der Kontowert, dazu
realisierter Gewinn/Verlust. Dann in einem anderen Tab der Drawdown (in % vom
Höchststand) und noch die Wochen-/Monatssicht in einem dritten Tab."

## `analytics/performance.py`, `GET /performance`

- Zeitgewichteter Index wie IBs TWR: `r_t = (K_t − E_t) / K_{t−1}` (Kontowert `K`,
  Einzahlungen `E` seit dem Vortag), Index = Π(1 + r); Basis 1 am Vortag des
  Zeitraums. **Drawdown = Index / bisheriges Hoch − 1** — Einzahlungen verfälschen
  ihn nicht.
- Gewinn laut IB je Tag `K_t − K_{t−1} − E_t`; Wochen (ISO, Mo–So) und Monate mit
  Gewinn laut IB, Rendite (zeitgewichtet) und realisiertem Ergebnis (Equity).
- Kopfwerte: Kontowert am Ende, Gewinn laut IB und Rendite im Zeitraum,
  realisiert im Zeitraum, maximaler Drawdown; dazu die realisierte Kurve, damit
  das Dashboard nur eine Abfrage braucht.
- Abnahmebasis `tests/test_performance.py` (7 Tests, von Hand gerechnet: eine
  Einzahlung ist kein Gewinn, −10 %, +10 % → −1 %), `tests/test_api_performance.py`.

## Dashboard

Kennzahlen (Kontowert, Gewinn laut IB, Rendite, realisiert, max. Drawdown,
unrealisiert) — **ein** Diagramm mit Ansichten: Kontowert & Ergebnis (zwei
Linien) · Drawdown (Fläche in %) · Wochen/Monate (Balken, umschaltbar Gewinn laut
IB / realisiert, Tabelle aufklappbar) — darunter die Überleitung. Die bisherigen
Einzeldiagramme (Equity, Drawdown in €, Monatsbalken, Kapital, Kontowert mit
Bestandteilen) entfallen. Bausteine: Fläche mit Prozent-Achse, Balken mit
freier Beschriftung (Kalenderwochen).

## Echtbestand

1.182 Tage; max. Drawdown **−51,62 % am 08.04.2025**; Rendite zeitgewichtet seit
31.03.2022 **+9,19 %**; 237 Wochen, 56 Monate.
