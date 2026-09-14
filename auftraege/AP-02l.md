---
titel: Buchungskurs (fxRateToBase) auf executions (OF-29)
modell: stark
status: fertig
abhaengig_von: AP-02k
aendert_tests: ja
---

# AP-02l · Buchungskurs an der Ausführung

Korrekturpaket nach CLAUDE.md, Regel 1a. Der Geldtest (letzter offene Punkt
vor der Abnahme von AP-03, OF-27/OF-28/OF-29) vergleicht realisiertes
Ergebnis gegen die Jahressummen der Kontoauszüge — in Basiswährung (EUR),
während die gehandelten Instrumente praktisch durchgehend in Fremdwährung
(USD) stehen. Der bereits entschiedene Umrechnungsweg (OF-23) braucht dafür
den Kurs, zu dem IB eine Ausführung in die Basiswährung bucht
(``fxRateToBase`` am rohen ``Trade``-Element, bestätigt an den
Golden-Exporten). Dieses Feld führt `ingest/flex.py` bisher nirgends, roh
oder normalisiert — ohne es ist der Geldtest aus den persistierten Daten
nicht rechenbar. Dieses Paket korrigiert die betroffene Abnahmebasis.
**Implementiert wird nichts** — das Lesen von `fxRateToBase` macht danach
AP-02.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Ein neuer Test** in `tests/test_ingest_flex_format.py`:
  `test_fx_rate_to_base_is_stored_on_executions` — `fxRateToBase` einer
  Ausführung landet in `executions.buchungskurs`, als `Decimal`; fehlt das
  Feld, bleibt die Spalte leer (kein Standardwert, Regel 10). Gleiches
  Muster wie `test_close_price_is_stored_on_executions` (AP-02k, Regel 6).
- **Der Test-Baustein `_trade(...)`** um den optionalen Parameter
  `fx_rate_to_base` ergänzt (Standard `"1.0000"`, wie die Zeile zuvor
  hartkodiert war — keine bestehende Erwartung ändert sich dadurch).

Bestehende Tests außerhalb dieser Stellen bleiben unverändert.

## Vertrag (Ergänzung zu AP-02.md, §5/§6)

`executions.buchungskurs` (nullable): `Trade.fxRateToBase` der Ausführung,
als `Decimal`. Kein Standardwert — fehlt das Feld an der Quelle, bleibt die
Spalte leer. Schema-Änderung über Migration `e1f4a2c8b6d3` (nur die neue
Spalte, keine sonstige Änderung an `executions`).

## Abnahme

- Der neue Test schlägt gegen den jetzigen `ingest/flex.py` fehl
  (`buchungskurs` existiert nicht/wird nicht befüllt) — Nachweis der Lücke.
- Alle übrigen Tests bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_ingest_flex_format.py`, `journal/schema.py` und der neuen
  Migration `e1f4a2c8b6d3`. Kein `ingest/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung im Import. Kein Bau des Geldtests selbst — dieses Paket
liefert nur die dafür fehlende Datengrundlage. Keine Aussage dazu, ob
`fifoPnlRealized`/`mtmPnl` zusätzlich gebraucht werden (OF-29).
