---
titel: Call-Credit-Spreads richtig typisieren (R05, Korrekturpaket)
modell: stark
status: fertig
abhaengig_von: AP-17
aendert_tests: ja
---

# AP-17b · BCS/BPS-Typisierung (Review R05)

**Befund (18.10.2026, geprüft):** `engine/structures.py` nannte einen Call-Spread mit Long am niedrigeren und Short am höheren
Strike „BCS“. Das ist ein Bull Call Spread (Debit). Ein Bear Call Spread (Call-Credit, „BCS“) hat den Short am **niedrigeren**
und den Long am **höheren** Strike. Die Put-Seite war richtig (BPS: Long niedriger, Short höher).

**Festlegung der Begriffe:** `BPS` = Put-Credit (Short Put höher, Long Put niedriger); `BCS` = Call-Credit (Short Call niedriger,
Long Call höher); alles andere mit zwei Beinen derselben Art und Fälligkeit (Call-Debit, Put-Debit) = `Vertical`.

**Wirkung am Bestand (Kontosicht):** 509 (2025) und 618 (2026) Call-Credit-Strukturen standen als `Vertical`, 17 und 130 Call-Debit-
Strukturen als `BCS`. Nur das Label ändert sich: Die P&L ändert sich nicht. Ausgewertet wird `typ` nirgends in Berechnungen,
nur als Anzeige und im Roller-Join (`_VERTIKALEN` lässt BPS, BCS und Vertical zu).

## Ändernder Test (namentlich, CLAUDE.md 1a)

`tests/test_structures.py::test_oa_referenz_gruppiert_zwei_legs_zu_einer_structure`: Die Testwelt (Call Long 5000, Short 5050) ist
ein Bull Call Spread (Debit); erwartet wird jetzt `Vertical` statt `BCS`, der Docstring nennt die richtige Richtung. Die Prüfung der
Gruppierung durch die OA-Referenz, der Strikes (Short 5050, Long 5000) und der Breite 50 bleibt unverändert.

Neu: `tests/test_structures_spreads.py` (alle vier Richtungen mit Handrechnung).

## Folgen

Nach dem Rebuild (nachts oder von Hand) tragen die rund 1.100 Strukturen den richtigen Typ; Notizen, Overrides und Kampagnen sind
nicht betroffen (der Naturschlüssel enthält den Typ nicht).
