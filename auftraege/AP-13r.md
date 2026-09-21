---
titel: Parsernachbesserung - nicht ausgefuehrte Trades und Januar-Exportvariante (OF-40)
modell: guenstig
status: offen
abhaengig_von: AP-13pm
---

# AP-13r · Parsernachbesserung, zweite Runde

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-13pm). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag 14–18 in `auftraege/AP-13pm.md`. Lies dort
auch den Abschnitt „Warum hier ein Statusbezug — und bei AP-13pl nicht";
er erklärt, warum die Regeln genau so eng geschnitten sind.

## Aufgabe

`ingest/optionapp.py` so erweitern, dass die acht neuen Tests am Ende von
`tests/test_ingest_optionapp.py` grün werden. Betroffen sind:

- die Leg-Zerlegung (`_legs_zerlegen` bzw. ihr Aufruf in `_trade_zeile`) —
  Vertrag 14 und 15,
- `Open` in `_trade_zeile` — Vertrag 14,
- `_profitwert` — Vertrag 16,
- `_stopwert` — Vertrag 17 und 18,
- das Lesen von `Strikes` über `_textwert` — ein leeres `Strikes` bei
  `CANCELED` darf nicht mehr als fehlendes Pflichtfeld abbrechen.

`_zahlzelle` kennt seit AP-13q ein ausdrückliches Opt-in
(`strich_heisst_leer`). Nutze dieses Muster wieder, statt eine allgemeine
Nachsicht einzubauen.

## Die zwei Gegenproben sind der Kern

`test_freitext_bei_ausgefuehrtem_trade_bricht_weiter_ab` und
`test_mehrere_stops_mit_unlesbarer_zeile_brechen_ab` sind **heute schon
grün und müssen es bleiben.** Sie prüfen, dass die Lockerung eng bleibt.
Wer `_legs_zerlegen` einfach in ein `try/except` packt oder Freitext
allgemein durchlässt, macht die neuen Tests grün und bricht die
Gegenprobe — und bei ausgeführten Trades verschwänden Legs dann still.

## Grenzen

- Der Statusbezug gilt **nur** für `CANCELED` (Vertrag 14) und `RUNNING`
  (Vertrag 15). Kein anderer Status lockert irgendetwas.
- `Status` wird weiter roh gespeichert, nie abgebildet (Vertrag 9).
- Keine Zerlegung der Mehrfachstops, keine Auswertung der DTE-Legs.
- Keine Schemaänderung; `stop_roh` und `strikes_roh` sind Pflichtspalten,
  deshalb `""` statt leer.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, kein Skript
  unter `werkzeuge/abgleich/` ausführen.

## Abnahme

- `tests/test_ingest_optionapp.py` vollständig grün.
- `pytest` und `ruff check .` sauber.
- `git diff --stat` zeigt Änderungen **ausschließlich** in
  `ingest/optionapp.py`.
