---
titel: Fingerabdruck-Vorzeichen und Ergebnisbasis korrigiert (OF-55, OF-56)
modell: stark
status: fertig
abhaengig_von: AP-13vk
aendert_tests: ja
---

# AP-13vk2 · Zwei Befunde aus der ersten echten Golden-Messung

Korrekturpaket nach CLAUDE.md, Regel 1a. Läuft unter `locker`, weil es
`tests/test_oa_abgleich.py` um zwei Tests erweitert. Beide Befunde kamen
aus demselben Anlass: dem ersten Lauf des neuen Werkzeugs
`werkzeuge/abgleich/golden_oa_abgleich_verknuepfung.py` gegen einen
echten OA-Export — der Nachweis, den AP-13 laut Plan verlangt, aber bis
jetzt niemand erbracht hatte, weil `engine/oa_abgleich.py` bis AP-13wk
nur gegen erfundene Fixtures lief.

## Befund 1 (OF-55): Fingerabdruck verglich Vorzeichen gegen Betrag

`executions.menge` trägt bei IBs Flex-Import das Vorzeichen von
`quantity` unverändert (negativ bei Sell). OAs `Strikes`-Spalte meldet je
Leg nur den Betrag. Der in AP-13vk ergänzte Mengenvergleich verglich beide
ungeprüft — Ergebnis am echten Bestand: 0 von 66 statt ~61 von 66
Treffern. Die AP-13vk-Fixtures deckten das nicht auf, weil sie
`executions.menge` immer positiv konstruiert hatten.

**Korrektur:** `engine/oa_abgleich.py`, `_eigene_legs()` vergleicht jetzt
`abs(menge)`.

## Befund 2 (OF-56): Ergebnisabgleich verglich Brutto statt Netto

`ergebnis_eigen` war `chain.brutto_pnl`. Gegen den echten Bestand traf das
nur 1 von 66 Trades näherungsweise. Gegen das Netto-Ergebnis
(`brutto_pnl + kommission_gesamt`) trafen 36 von 66 — OAs `Profit` ist
erkennbar bereits kommissionsbereinigt.

**Korrektur:** `engine/oa_abgleich.py`, `oa_abgleich()` — `ergebnis_eigen
= chain.brutto_pnl + chain.kommission_gesamt`.

**Nicht gelöst durch dieses Paket:** 29 von 66 Ergebnisabweichungen
bleiben auch gegen Netto unerklärt — `OFFENE_FRAGEN.md`, OF-57. Diese
Korrektur bringt den Ergebnisabgleich auf die richtige Basis, löst aber
nicht die gesamte AP-13-Abnahme.

## Geänderte Tests (namentlich, Regel 1a)

`tests/test_oa_abgleich.py` — zwei neue Tests, keine bestehende Assertion
geändert:

- `test_signierte_ausfuehrungsmenge_zaehlt_trotzdem_als_treffer` (OF-55)
- `test_ergebnisabgleich_vergleicht_netto_nicht_brutto` (OF-56, Handrechnung
  120,00 + (−3,00) = 117,00)

## Abnahme

- `tests/test_oa_abgleich.py`: 9 von 9 grün (vorher 7).
- Gesamte Suite grün, `ruff check .` sauber.
- Golden-Nachweis (`golden_oa_abgleich_verknuepfung.py Trades_2026-
  02_OA.xlsx`, Regel 2, nur vom starken Modell ausgeführt): 66 von 66
  eindeutig zugeordnet (100 %, davon 61 auto/5 heuristik), 0 Fehler —
  deckungsgleich mit dem unabhängigen `golden_oa_abgleich.py` (61 von 66
  exakte Leg-Signaturen ohne Menge).
- `git diff --stat` zeigt `engine/oa_abgleich.py`, `tests/
  test_oa_abgleich.py`, `werkzeuge/abgleich/golden_oa_abgleich_
  verknuepfung.py` (Kommentar-Präzisierung, keine Logik).
