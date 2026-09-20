---
titel: Korrektur der Abnahmebasis AP-04v - Testaufbau des verwaisten Overrides (OF-38)
modell: stark
status: offen
abhaengig_von: AP-04v
aendert_tests: ja
---

# AP-04vk · Testaufbau des verwaisten Overrides

Korrekturpaket nach CLAUDE.md, Regel 1a. Es behebt einen Defekt **meiner
eigenen Abnahmebasis** (AP-04v), nicht der Umsetzung.

## Der Defekt

`tests/test_rebuild.py::test_verwaister_override_wird_gezaehlt_und_nicht_geloescht`
löscht im Aufbau die Ausführung `A2` per nacktem `DELETE FROM executions`.
Das kann nicht gelingen: Nach Vertrag 15 schreibt der Rebuild `legs`
vollständig, darunter die offene Aktien-Leg mit `open_exec_id = 'A2'`, und
`legs.open_exec_id` verweist mit `NO ACTION` auf `executions.exec_id` bei
eingeschaltetem `PRAGMA foreign_keys`. Derselbe Codepfad müsste die Leg
schreiben (`test_grundlauf…` verlangt `legs == 10`) und zugleich nicht
geschrieben haben.

AP-04v wurde ohne Referenzimplementierung committet — der Test konnte nie
grün gelaufen sein. Das ist mein Fehler, kein Befund an AP-04p.

**Das günstige Modell hat sich richtig verhalten:** Es hat den Widerspruch
bewiesen, ihn als OF-38 eingetragen, den Test **nicht** angefasst und
abgebrochen. Genau das verlangt Regel 1 — und es hat zusätzlich
nachgewiesen, dass die Umsetzung jede Assertion dieses Tests erfüllt,
sobald der Aufbau ausführbar ist.

## Warum nicht die empfohlene Variante

OF-38 empfiehlt eine Migration mit `ON DELETE CASCADE` auf
`legs.open_exec_id`/`close_exec_id`. Das lehne ich ab:

Der Fehler steckt im Testaufbau, nicht im Schema. Eine Kaskade würde das
Schema ändern, damit ein schlecht geschriebener Aufbau ausführbar wird —
die falsche Richtung. Sie brächte auch nichts: Produktiv löscht niemand
Ausführungen (Regel 4), und der nächste `rebuild()` entfernt eine
verwaiste Leg ohnehin, weil er `legs` vollständig neu schreibt. Die
Kaskade fügte dem Schema also einen stillen Löschpfad hinzu, der nur im
Test je feuert.

Variante 2 dagegen hält die Prüflogik **unverändert**: Es ändert sich
nicht, *was* erwartet wird, und nicht, *ob* geprüft wird — nur der Aufbau
wird ausführbar. Das ist die engstmögliche Korrektur.

## Ausdrücklich freigegebene Änderungen

Nur diese, keine weiteren.

- **`tests/test_rebuild.py`, ausschließlich im Aufbau von
  `test_verwaister_override_wird_gezaehlt_und_nicht_geloescht`:** Vor dem
  `DELETE` auf `executions` werden die abhängigen `legs`-Zeilen gelöscht.
  Das entspricht dem Vorgang, den der Test selbst zitiert — eine
  zurückgenommene Fehleinspielung nimmt die abgeleiteten Zeilen mit.
  **Keine Assertion dieses Tests wird geändert**, keine hinzugefügt, keine
  entfernt.
- **`tests/test_rebuild.py`, Importblock:** Reihenfolge nach `ruff`
  sortiert. Kein inhaltlicher Eingriff — seit `journal/rebuild.py`
  existiert, ordnet `ruff` es als projekteigenes Modul ein und verlangt
  eine andere Sortierung als zum Zeitpunkt, als die Datei geschrieben
  wurde. Ohne diese Zeile ist `ruff check .` nicht sauber.
- **`auftraege/AP-04v.md`, Vertrag 12:** Ergänzung um
  `methode = 'zuteilung'` (siehe unten). Reine Vertragsklarstellung, kein
  Test.

**Nicht freigegeben:** jeder andere Test, jedes Fixture, jede Migration,
`journal/rebuild.py`, `journal/cli.py`.

## Vertragslücke, die dabei auffiel

Vertrag 12 listete für `structures.erkennung` nur `oa`, `exec_batch` und
`zeitfenster`. `engine/chains.py` erzeugt aber synthetische Strukturen für
den Zuteilungsübergang mit `methode = 'zuteilung'` (Zeile 156) — ein
vierter Wert, den mein Vertrag nicht abdeckte.

Das günstige Modell hat ihn auf `order_id` abgebildet und die Annahme im
Modul-Docstring begründet: Die Spalte kennt kein `auto`, und eine
Zuteilung ist eine Brokertatsache, kein Schluss aus zeitlicher Nähe.
**Das ist richtig** und deckt sich damit, wie `chain_links.erkennung` für
denselben Übergang gesetzt wird (`auto`, AP-04). Die Annahme wird in den
Vertrag übernommen und nach Regel 10 in `OFFENE_FRAGEN.md` festgehalten,
statt nur im Docstring zu stehen.

## Abnahme

- `tests/test_rebuild.py` läuft vollständig grün, alle 16 Tests.
- Die Gesamtsuite ist grün, `ruff check .` sauber.
- `git diff` zeigt unter `tests/` ausschließlich die beiden Aufbauzeilen
  in `test_verwaister_override_wird_gezaehlt_und_nicht_geloescht`. Keine
  Assertion verändert.
