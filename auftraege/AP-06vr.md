---
titel: "Regression nach Echtlauf: Vorzeichen und Leg-Anteile in Regel 3 (AP-06vr)"
modell: stark
status: fertig
abhaengig_von: AP-06vk
aendert: tests/test_kennzahlen_regression.py (neu), OFFENE_FRAGEN.md (OF-62 Nachtrag)
aendert_tests: ja
---

# AP-06vr · Dauerhafte Regressionstests für die Echtlauf-Korrekturen

## Ziel

AP-06vk hat zwei Defekte der Regel 3 behoben, die die eingefrorene Abnahmebasis
(`tests/test_kennzahlen.py`: alle Mengen je Leg 1, je Ausführung 1) prinzipiell
nicht sehen konnte. OF-62 hält fest: „bis ein dauerhafter Test existiert" sind
die drei Echtlauf-Handrechnungsketten die einzige Regression. Dieses Paket
legt diesen Test an — es implementiert nichts und ändert keine bestehende
Prüfung (CLAUDE.md, Regel 1a: eigene Datei, Handrechnungen, Regel 8).

## Gemessene Konvention im Echtbestand (03.10.2026, journal.db)

- `legs.menge` ist **vorzeichenlos**: 21.000 von 21.000 Zeilen positiv.
  `engine/matching.py` speichert beim Lot-Bau `abs(menge)`; FIFO-Teilmengen
  und Restmengen erben das.
- `executions.menge` trägt das **IB-Flex-Vorzeichen**: SELL negativ
  (16.244 Zeilen), BUY positiv (16.231).
- Daraus folgt: Der Kommissionsanteil `leg.menge / abs(exec.menge)` ist
  vorzeichenlos positiv — korrekt so; der Test hält diese Konvention fest,
  damit sie niemand „vereinheitlicht" und dabei den Anteil kippt.

## Testwelt (reine Funktion, Kettensicht; alle Erwartungen von Hand)

Drei Ketten, eine je Echtlauf-Defekt, in `tests/test_kennzahlen_regression.py`:

1. **K1 (7184-Muster, Vorzeichen):** Wie K1 der Abnahmebasis, aber
   `executions.menge` mit IB-Flex-Vorzeichen (SELL = −1). Erwartung
   unverändert 67.60 / 87.40 / −19.80 — der alte Code kippte jeden
   Verkaufscashflow und rechnete −2662.40.
2. **K2 (9533-Muster, Teilablösung):** Eine exec (SELL 262.30, menge −40,
   Kommission −4.00) speist zwei Legs mit je menge 10 in zwei Strukturen
   einer Kette (Roll). Hand: je Struktur 613.00 / 663.00, Kette 1276.00 —
   der alte Code wertete die volle Ausführung je Leg (+52.460 doppelt).
3. **K3 (9215-Muster, Assignment):** Ein Leg mit menge 5 gegen eine exec
   mit menge −100 (172.895, Kommission −2.00, Kurs 0.86). Hand:
   (864.475 − 0.10) × 0.86 = 743.3625 — der alte Code nahm die ganze
   Ausführung (14.866.97-fach verzerrt).
4. Aggregate: Summe 2086.9625, Trefferquote 1.0000, kein Fehler.

## Abnahme

`pytest tests/test_kennzahlen_regression.py` grün; Gesamtsuite ohne
`tests/test_steuer.py` (AP-10) grün; `ruff check .` sauber;
`git diff --stat` zeigt nur die beiden genannten Dateien.
