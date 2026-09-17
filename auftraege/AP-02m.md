---
titel: realized_pnl_verfuegbar am Importlauf (OF-21, OF-24)
modell: stark
status: fertig
abhaengig_von: AP-02l
aendert_tests: ja
---

# AP-02m · Modell-Exporte als Datenfeld kenntlich machen

Korrekturpaket nach CLAUDE.md, Regel 1a. IB schaltet jedes Feld zum
realisierten Ergebnis ab, sobald ein Modell in die Abfrage einbezogen ist: In
den Exporten mit `model="Independent"` steht an jeder Zeile
`fifoPnlRealized="0"`, und Closed Lots bleiben leer. Das ist seit OF-21
bekannt und in Plan §6.2 festgehalten.

**Der Befund stand nur in einer Textdatei — und hat deshalb nicht gewirkt.**
Beim Bau des Geldtests (OF-24) wurde die Referenz je `tradeID` aus der zuerst
gelesenen Datei genommen; in 14.009 Fällen war das die abgeschaltete 0 aus
einem Modell-Export. Das Ergebnis: eine gemeldete Trefferquote von 59 % statt
93 %, mit einem daraus abgeleiteten „großen ungeklärten Rest", den es nie gab.
Ein Vergleichsskript kann diesen Fehler jederzeit wiederholen, solange die
Eigenschaft nicht in den Daten steht.

**Konsequenz (Plan §5, Nutzer 17.09.2026):** Die Eigenschaft wird ein
Datenfeld am Importlauf. Dieses Paket legt die Abnahmebasis dafür.
**Implementiert wird nichts** — das Setzen des Feldes macht danach AP-02.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Ein neuer Test** in `tests/test_ingest_flex_format.py`:
  `test_model_export_marks_realized_pnl_as_unavailable` — ein Export mit
  Modellzeilen setzt `realized_pnl_verfuegbar` auf falsch, einer ohne auf
  wahr.
- **Der Test-Baustein `_trade(...)`** um den optionalen Parameter `model`
  ergänzt (Standard: kein Attribut, wie bisher). Keine bestehende Erwartung
  ändert sich dadurch.

Bestehende Tests außerhalb dieser Stellen bleiben unverändert.

## Vertrag (Ergänzung zu AP-02.md)

`import_runs.realized_pnl_verfuegbar` (NOT NULL, Standard wahr): **falsch,
sobald mindestens eine Zeile des Exports ein nicht leeres `model`-Attribut
trägt**, sonst wahr. Maßgeblich ist der gesamte Export, nicht die einzelne
Zeile — IB schaltet die Felder für die ganze Abfrage ab, und ein Lauf ist
entweder brauchbar oder nicht.

Der Import bricht bei Modellzeilen **nicht** ab: Bestände, Ausführungen und
Kommissionen sind in diesen Exporten vollständig und richtig; abgeschaltet
sind allein die Realized-P&L-Felder.

**Pflicht für jeden Vergleich:** Werte aus `fifoPnlRealized`,
`FIFOPerformanceSummaryInBase` und Closed Lots eines Laufs mit
`realized_pnl_verfuegbar = false` dürfen nicht als Referenz verwendet werden.
`werkzeuge/abgleich/golden_geldtest_fifopnl.py` setzt das bereits um, indem es
Zeilen mit `model` übergeht; nach der Nachbesserung soll es sich auf das Feld
stützen können.

Schema-Änderung über Migration `f2a7c3d9b5e1` (nur die neue Spalte).
Bestehende Läufe behalten den Standard wahr — ob sie Modellzeilen enthielten,
lässt sich nachträglich nicht aus der Datenbank entscheiden und wird nicht
geraten (Regel 10).

## Abnahme

- Der neue Test schlägt gegen den jetzigen `ingest/flex.py` fehl (das Feld
  wird nicht gesetzt) — Nachweis der Lücke.
- Alle übrigen Tests bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_ingest_flex_format.py`, `journal/schema.py` und der neuen
  Migration `f2a7c3d9b5e1`. Kein `ingest/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung im Import. Keine nachträgliche Bewertung bestehender
Importläufe. Keine Änderung an den Abgleichsskripten.
