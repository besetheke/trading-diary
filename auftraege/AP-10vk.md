---
titel: Korrektur der Abnahmebasis AP-10v - zwei Assertions in test_steuer.py
modell: stark
status: fertig
abhaengig_von: AP-10v
aendert_tests: ja
---

# AP-10vk · Zwei fehlerhafte Assertions in `tests/test_steuer.py`

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ändert zwei namentlich genannte
Erwartungen und läuft deshalb unter `locker`. `analytics/steuer.py` und
`journal/steuer.py` bleiben unberührt — beide sind korrekt (Befund der
Umsetzung AP-10k, vom günstigen Modell gemeldet und nicht selbst „geflickt",
wie Regel 1 es verlangt).

## Befund

Beide Fehler stammen aus der Abnahmebasis AP-10v, also aus der Hand des
starken Modells; die Tests waren nie grün, weil sie nie gegen eine
Implementierung liefen (Regel-8-Lehre aus OF-51: Fixtures vor der Abgabe
gegen eine Wegwerf-Umsetzung prüfen).

1. `test_details_drilldown_und_reihenfolge`: `sum()` über Tupel ohne
   Startwert wirft `TypeError`. Gemeint war die spaltenweise Summe der
   Detailzeilen 2025/termingeschaefte, die die Topfzeile deckeln soll (§5).
2. `test_kettensicht_wird_zurueckgewiesen`: Die letzte Assertion verbietet
   den Topf 2025/aktien, den `_ERWARTETE_TOEPFE` (L3, verkauft 2025-02-03)
   zwingend fordert — sie negiert ihre eigene Fixture. Gemeint war: die
   Werte der zurückgewiesenen Zeile L7 (OPT, brutto 10.00, Kommission −1.00,
   Schluss 2025-04-01) fließen in keinen Topf.

## Korrektur (nur diese beiden, Prüflogik bleibt)

1. Drei getrennte Summen (brutto, Kommission, netto) über dieselben zwei
   Detailzeilen; erwartet unverändert `350.00 / −4.00 / 346.00`.
2. Ersetzt durch `ergebnis.toepfe == _ERWARTETE_TOEPFE`. Das belegt den
   Ausschluss von L7 schärfer als die alte Zeile: Flösse L7 in den Topf
   2025/termingeschaefte/USD, stünde dort 360.00 / −5.00 / 355.00 statt
   350.00 / −4.00 / 346.00.

## Abnahme

- `pytest tests/test_steuer.py` grün gegen die AP-10k-Umsetzung.
- Gesamtsuite grün, `ruff check .` sauber.
- `git diff --stat` unter `tests/`: ausschließlich `tests/test_steuer.py`,
  ausschließlich die beiden genannten Stellen.
