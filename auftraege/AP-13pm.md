---
titel: Abnahmebasis erweitern - nicht ausgefuehrte Trades und Januar-Exportvariante (OF-40)
modell: stark
status: offen
abhaengig_von: AP-13pl
aendert_tests: ja
---

# AP-13pm · Nicht ausgeführte Trades und zweite Exportvariante

Korrekturpaket nach CLAUDE.md, Regel 1a, und Vorbereitungspaket nach Plan
§11.2. **Es implementiert nichts.** Die Umsetzung ist AP-13r (günstiges
Modell).

## Der Befund (OF-40)

Nach AP-13q liest der Parser die Februardatei vollständig, bricht an den
beiden anderen realen Exporten aber an weiteren Stellen ab, die der Vertrag
aus AP-13p nicht kennt. Gemessen — nur Formen und Zählwerte (Regel 2):

| Fall | Januar | August | Februar |
|---|---|---|---|
| `Profit` als Zahl, ohne Währungszeichen | alle 268 | 0 | 0 |
| `Stops` leer | 50 | 0 | 0 |
| `Stops` mit zwei Werten, zeilengetrennt | 3 (je 3 Legs) | 31 (je 4 Legs) | 0 |
| `Strikes` ohne Leg-Grammatik | 207 Ausschnitte | 0 | 0 |
| `Open` = `-` | 179 | 0 | 0 |

Die entscheidende Messung betrifft `Strikes`: **Alle 207 abweichenden
Ausschnitte gehören zu Trades mit Status `CANCELED` (179) oder `RUNNING`
(28 Ausschnitte in 8 Trades).** Bei `CANCELED` steht ein Abbruchgrund
(„Entry condition not met", „No option chain for …", „Aborted by user")
oder nichts; bei `RUNNING` stehen geplante Legs mit Restlaufzeit
(`-1xP5000-7DTE`) statt Verfallsdatum. Über **alle 1.114 Legs ausgeführter
Trades** in den drei Dateien hält die Grammatik ausnahmslos.

Ein Trockenlauf mit genau den Regeln unten liest alle drei Exporte
vollständig: 268, 66 und 178 Trades. Ohne Legs bleiben exakt die 179
`CANCELED`- und die 8 `RUNNING`-Trades — kein einziger sonst.

Die Januardatei ist erkennbar eine **zweite Exportvariante** (Profit als
Zahl, leere Stops, nicht ausgeführte Trades enthalten), nicht eine
fehlerhafte Datei.

## Warum hier ein Statusbezug — und bei AP-13pl nicht

AP-13pl band die Behandlung des Strichs bewusst an den Zellwert, nicht an
den Status: Der Strich heißt überall „gibt es nicht". Hier geht es um etwas
anderes — **ob es überhaupt ausgeführte Legs gibt**, und das ist eine
Eigenschaft des Zustands. Den Statusbezug eng zu fassen hält die Grammatik
genau dort streng, wo es darauf ankommt: Bei jedem ausgeführten Trade
bleibt eine Abweichung ein Defekt der Quelle, der benannt abbricht.
Vertrag 9 bleibt unberührt — `Status` wird weiter roh gespeichert und nie
auf andere Werte abgebildet.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Drei neue Fixtures**, erzeugt durch Ergänzungen in
  `fixtures/optionapp/erzeugen.py`, Werte frei erfunden, Formen nach der
  Messung:
  - `oa_nicht_ausgefuehrt.xlsx` — `[4001]` `CANCELED` mit Abbruchgrund,
    `[4002]` `CANCELED` mit leerem `Strikes`, `[4003]` `RUNNING` mit
    DTE-Legs, `[4004]` `CLOSED` der Januarvariante (Profit als Zahl, Stops
    leer), `[4005]` `PARTIALLY STOPPED` mit zwei Stops.
  - `oa_freitext_ausgefuehrt.xlsx` — `[4101]` `CLOSED` mit Freitext in
    `Strikes` (Gegenprobe: muss abbrechen).
  - `oa_mehrstop_defekt.xlsx` — `[4201]` mit unlesbarer zweiter
    Stop-Zeile (Gegenprobe: muss abbrechen).
- **Acht neue Tests** am Ende von `tests/test_ingest_optionapp.py`.
- **Vertrag 14–18** in `auftraege/AP-13p.md`.

Die bestehenden fünf Fixtures und alle bestehenden Tests bleiben
unangetastet.

## Vertrag an die Umsetzung (AP-13r)

14. **`CANCELED` heißt „nie eröffnet".** `Strikes` wird nicht als
    Leg-Spezifikation gelesen, was immer darin steht; der Trade wird ohne
    Legs gebucht, `strikes_roh` behält den Inhalt, ein leeres `Strikes`
    wird zu `""`. `Open` darf den Strich tragen (`offen_preis` leer) —
    **nur bei `CANCELED`**; bei jedem anderen Status bleibt `Open` Pflicht.
15. **`RUNNING` mit geplanten Legs.** Folgen **alle** Ausschnitte der Form
    `[-]<Menge>x<C|P><Strike>-<n>DTE`, wird der Trade ohne Legs gebucht,
    Rohwert erhalten. Folgen alle der normalen Grammatik, werden sie normal
    zerlegt. Gemischt oder anders: Abbruch mit Nennung.
16. **`Profit` als Zahl.** Steht in der Zelle eine Zahl statt Text, wird sie
    über `Decimal(str(wert))` gelesen; `profit_waehrung` bleibt leer — eine
    Währung steht nicht da und wird nicht unterstellt.
17. **`Stops` leer** heißt „keine Angabe": `stop_roh = ""`, `stop_wert`
    leer. Das ist weder `-` noch `0`.
18. **`Stops` mit mehreren Zeilen.** Jede Zeile muss für sich Vertrag 3
    genügen, sonst Abbruch mit Nennung. `stop_roh` behält den Wert
    vollständig, samt Zeilenumbruch; `stop_wert` bleibt leer, weil es
    keinen einzelnen Wert gibt.

Für jeden anderen Status gilt Vertrag 5 unverändert streng: Freitext oder
Grammatikbruch bei einem ausgeführten Trade bricht ab.

## Abnahme

- Die acht neuen Tests sind rot, solange `ingest/optionapp.py` unverändert
  ist — die zwei Gegenproben ausgenommen, die schon heute grün sind und es
  bleiben müssen.
- Alle bestehenden Tests bleiben unverändert und grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_ingest_optionapp.py`, `fixtures/optionapp/erzeugen.py`, den
  drei neuen Fixtures und `auftraege/AP-13p.md`. **Kein `ingest/`.**

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung. Keine Auswertung der geplanten DTE-Legs, keine Zerlegung
der Mehrfachstops in Einzelwerte — der Rohwert trägt alles, was bisher
gebraucht wird.
