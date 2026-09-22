---
titel: Zuteilungspaare nur einmal schreiben (Fund am echten Bestand)
modell: stark
status: fertig
abhaengig_von: AP-04p
aendert_tests: ja
---

# AP-04pk · Zuteilungspaare nur einmal schreiben

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ergänzt einen **neuen** Test —
keine bestehende Erwartung wird geändert.

## Der Fund

Beim ersten `journal rebuild` über den echten Bestand (22.09.2026, 29.926
Ausführungen) bricht der Lauf ab:

> `UNIQUE constraint failed: assignment_links.option_exec_id,
> assignment_links.stock_exec_id`

`_assignment_links_neu_schreiben()` legt für **jede Kombination** aus
Options-Leg und Fortsetzungs-Leg eine Zeile an. Schließt **eine**
Zuteilungsausführung **zwei Legs derselben Struktur**, entsteht dasselbe
Paar zweimal — und der Primärschlüssel verbietet das zu Recht:
`assignment_links` ist eine Menge von Paaren, keine Liste.

**Gemessen am echten Bestand:** 330 erzeugte Paare, davon 320 verschieden;
**10 Paare entstehen doppelt**, jedes genau zweimal. Die Form dahinter ist
in allen Fällen dieselbe — eine Optionsstruktur mit mehreren Legs, die von
einer einzigen Zuteilungsausführung geschlossen wird (FIFO verteilt sie auf
beide Legs).

**Warum es die Testsuite nicht fand:** In den erfundenen Beständen schließt
jede Zuteilung genau ein Leg. Das ist der Normalfall (295 von 320), aber
eben nicht der einzige.

**Warum es kein Fehler des Umsetzers ist:** Vertrag 22 aus AP-04v regelte,
*welche* Zeilen neu geschrieben werden, nicht, dass ein Paar nur einmal
entstehen darf. Die Lücke ist meine.

## Ausdrücklich freigegebene Änderungen

Nur diese, keine weiteren.

- **Ein neuer Test** in `tests/test_rebuild.py`:
  `test_zuteilung_mit_zwei_legs_schreibt_das_paar_einmal`, samt dem dafür
  nötigen Import von `assignment_links`. Das Szenario ist frei erfunden und
  gegen die Engine nachgerechnet: zwei Eröffnungen desselben Kontrakts in
  einer Order (gemeinsamer `exec_batch`, also **eine** Struktur mit zwei
  Legs), eine Zuteilungsausführung über beide, eine Aktiengegenbuchung.
- **`journal/rebuild.py`:** Die Paare werden vor dem Schreiben verdichtet.

Kein bestehender Test, kein bestehendes Fixture wird angefasst.

## Vertrag

1. **Ein Paar wird einmal geschrieben.** `(option_exec_id, stock_exec_id)`
   ist eine Menge; Wiederholungen aus der Kombinatorik über Legs werden
   verdichtet, nicht eingefügt.
2. **Nichts anderes ändert sich.** Insbesondere bleibt Vertrag 22
   unberührt: Zeilen mit `erkennung = 'manuell'` werden weiterhin nicht
   angefasst, alle übrigen neu geschrieben.
3. **Keine stille Toleranz.** Verdichtet wird die erzeugte Menge —
   `INSERT OR IGNORE` oder ein abgefangener `IntegrityError` wären etwas
   anderes: Sie würden auch echte Widersprüche verschlucken.

## Abnahme

- Der neue Test ist rot vor der Korrektur, grün danach.
- Alle übrigen Tests bleiben grün, `ruff check .` sauber.
- **`journal rebuild` läuft über den echten Bestand durch** — die
  eigentliche Probe; sie war der Anlass.
- `git diff` zeigt unter `tests/` ausschließlich den neuen Test und seinen
  Import.
