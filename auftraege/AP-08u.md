---
titel: Überleitung vom Ergebnis zum Kontostand
modell: stark
status: fertig
abhaengig_von: AP-02p, AP-08d, AP-06g, AP-06h
aendert_tests: nein
---

# AP-08u · Überleitung

Wunsch des Nutzers (11.10.2026): „Führe dann alles zusammen" — Equity, Kapital,
Kontostand und Unrealisiertes sollen eine Geschichte ergeben.

## `GET /ueberleitung`

Zerlegt IBs Gewinn (Kontowert − Einzahlungen, aus `/nav`) in:

| Posten | Quelle |
|---|---|
| realisiert (IB) | Σ `fifoPnlRealized` × Kurs je Ausführung bis zum NAV-Tag (`flex_ib_realized`) |
| unrealisiert (IB) | Σ unrealisiertes Ergebnis des jüngsten Bestands (`/depot`) |
| sonstige Buchungen | Cash-Posten ohne Ein-/Auszahlungen (`/kapital`) |
| Rest | Gewinn − (realisiert + unrealisiert + sonstige): Währung, Abgrenzungen, nicht einzeln Ausgewiesenes |

Daneben das realisierte Ergebnis des Journals (Equity) und die Differenz zu IB.
`abdeckung` sagt, für wie viele Ausführungen IBs Wert vorliegt. Nur lesend, Geld
als Text. Abnahmebasis `tests/test_api_ueberleitung.py` (7 Tests, von Hand
gerechnet).

## Oberfläche

Dashboard, ganz oben: Abschnitt „Vom Ergebnis zum Kontostand" (`ui/src/Ueberleitung.tsx`)
mit Tabelle der Posten, Quelle je Zeile und dem Vergleich Journal ↔ IB.

## Echtbestand (Stand 09.10.2026)

Einzahlungen 219.998,88 + realisiert (IB) 77.853,98 + unrealisiert −46.361,74 +
sonstige Buchungen −1.125,53 + Rest −5.692,73 = **Kontowert 244.672,85 €**
(Gewinn laut IB 24.673,97 €). Journal realisiert 88.384,62 €, Unterschied zu IB
**+10.530,64 €**, überwiegend Prämienmethode bei Zuteilungen (OF-78).

## Grenze

Der Rest (−5.692,73 €) ist ein Saldo: IB weist Währungsumrechnung und
Abgrenzungen im Change in NAV nicht einzeln aus (die Posten kommen leer). Er
wird nicht weiter zerlegt, nichts wird dafür geschätzt.
