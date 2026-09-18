---
titel: Abnahmebasis für den OptionApp-Parser (AP-13, Teil 1)
modell: stark
status: fertig
abhaengig_von: -
aendert_tests: ja
---

# AP-13p · Abnahmebasis für den OptionApp-Parser

Vorbereitungspaket nach CLAUDE.md, Regel 1a und Plan §11.2: Das starke Modell
schreibt Tests und Fixtures, das günstige implementiert dagegen. **Dieses
Paket implementiert nichts.** Der Parser selbst ist danach AP-13, Teil 1
(günstiges Modell).

Der Plan teilt AP-13 ausdrücklich: Der Parser hängt an nichts und kann
jederzeit gebaut werden; Verknüpfung mit den Ketten und Ergebnisabgleich
brauchen AP-04 und bleiben beim starken Modell.

Maßgeblich für das Format ist `auftraege/AP-13-anhang-oa-format.md`.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Vier neue Fixtures** unter `fixtures/optionapp/` (synthetisch, erzeugt vom
  Skript `fixtures/optionapp/erzeugen.py`, damit die Binärdateien
  nachvollziehbar bleiben):
  - `oa_standard.xlsx` — der Regelfall: Trades mit zwei, drei und vier Legs,
    `Stops` einmal `-` und einmal `0`, `Profit` negativ und positiv, ein noch
    offener Trade mit leerem `Close` und `Close Time`.
  - `oa_grammatik_defekt.xlsx` — eine `Strikes`-Zelle, die der Grammatik nicht
    folgt.
  - `oa_ohne_klammernummer.xlsx` — ein `Name` ohne Klammernummer.
  - `oa_doppelte_nummer.xlsx` — dieselbe Klammernummer zweimal mit
    abweichendem Inhalt.
- **Eine neue Testdatei** `tests/test_ingest_optionapp.py`.
- **Schema und Migration** `a3e8d1c4f7b2`: `optionapp_trades` und
  `optionapp_legs`. Ohne sie ist der Vertrag nicht testbar (Regel 3).
- **`openpyxl`** als Abhängigkeit in `pyproject.toml` — der Export ist eine
  echte XLSX-Datei, ohne Leser nicht einlesbar.

## Vertrag an die Umsetzung

1. **Quelle.** Arbeitsblatt `Trades`, eine Kopfzeile, elf Spalten in fester
   Reihenfolge. Fehlt das Blatt oder weicht die Kopfzeile ab, bricht der
   Import mit Nennung des Gefundenen ab — kein Raten über Spaltenpositionen.
2. **Zahlen (Regel 5).** `Open` und `Close` stehen als Zahl in der Zelle,
   `Stops` und `Profit` als Text. Alle drei werden zu `Decimal`; Zahlwerte
   über `Decimal(str(wert))`, niemals über `float`-Arithmetik. `Profit` trägt
   deutsches Format mit Währungszeichen (`-1.234,56 $`): Währungszeichen
   abtrennen und in `profit_waehrung` ablegen, Tausenderpunkte entfernen,
   Komma zu Punkt.
3. **`Stops`.** `-` heißt „kein Stop": `stop_roh` behält `-`, `stop_wert`
   bleibt leer. `0` ist ein gesetzter Stop und etwas anderes. Der Rohwert
   bleibt in beiden Fällen erhalten.
4. **`Quantity`.** Verhältnis `n/m`; beide Zahlen getrennt speichern. Ihre
   Gleichheit wird nicht vorausgesetzt.
5. **Leg-Grammatik.** `Strikes` zerfällt an ` / ` in zwei bis vier Legs, je
   Leg `[-]<Menge>x<C|P><Strike> (<JJMMTT>)`. Führendes Minus ist short
   (`richtung = -1`), sonst long (`+1`). Strike darf einen Dezimalteil
   tragen, auch wenn in den Referenzexporten keiner vorkam. Die Reihenfolge
   der Legs wird als `position` festgehalten. **Jede Abweichung bricht mit
   Nennung der Zeile und des Leg-Ausschnitts ab** — die Grammatik ist über
   856 Legs ausnahmslos stabil, eine Abweichung ist ein Defekt der Quelle.
6. **Schlüssel.** Die **letzte** Klammergruppe in `Name` ist die
   OA-Trade-Nummer (`oa_trade`); der freie Text davor kann selbst Klammern
   enthalten. Fehlt sie, bricht der Import mit Nennung der Zeile ab.
7. **Zeitstempel.** `Entry Time` und `Close Time` im Format
   `JJJJ/MM/TT hh:mm:ss`, als naives `datetime` gespeichert (OF-04, wie die
   Quelle liefert). **Sie dürfen nicht zum Abgleich dienen** — das Format ist
   ein drittes neben TDP und Flex, die Zeitzone ungeprüft; die Verknüpfung
   stiftet ausschließlich die Klammernummer.
8. **Offene Trades.** `Close` und `Close Time` dürfen leer sein; dann bleiben
   `schluss_preis` und `schluss_zeit` leer. Der Trade wird trotzdem gebucht.
9. **`Status`.** Rohwert speichern. Unbekannte Werte werden **nicht** auf
   bekannte abgebildet, sondern gebucht und in `OFFENE_FRAGEN.md` gemeldet.
10. **Idempotenz.** Zweimal dieselbe `oa_trade`-Nummer mit identischem Inhalt
    ist derselbe Trade und wird einmal gebucht. Mit abweichendem Inhalt ist
    es ein Fehlerfall mit Nennung der Nummer — keine stille Entscheidung,
    kein Überschreiben.
11. **Importlauf.** Eine Zeile in `import_runs` mit `quelle = 'optionapp'`,
    `qualitaetsstufe = 'B'` (kein Brokerbeleg) und
    `realized_pnl_verfuegbar = false` — ein OA-Lauf trägt keine
    IB-Ergebnisse, und kein Vergleich darf dort welche suchen.
12. **Einstiegspunkt.** `ingest/optionapp.py` mit
    `import_optionapp_file(db_pfad, datei_pfad)` — dieselbe Form wie
    `ingest.flex.import_flex_file`, damit beide Importwege gleich aufgerufen
    werden.
13. **Nicht Teil des Vertrags:** Verknüpfung mit `executions.oa_trade`,
    Fingerabdruckprüfung, Übernahme von `Strategy` und `Status` in Ketten,
    Ergebnisabgleich. Alles das braucht AP-04 und bleibt beim starken Modell.

## Abnahme

- `tests/test_ingest_optionapp.py` springt still ab, solange
  `ingest/optionapp.py` fehlt (`pytest.importorskip`, dieselbe Regel wie in
  `tests/test_matching.py`), und läuft scharf, sobald das Modul existiert.
  Die 16 Tests sind erst grün, wenn der Parser den Vertrag erfüllt.
- Alle übrigen Tests bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_ingest_optionapp.py`, `fixtures/optionapp/`, `journal/schema.py`,
  der Migration `a3e8d1c4f7b2` und `pyproject.toml`. Kein `ingest/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung des Parsers. Keine Verknüpfung, kein Ergebnisabgleich, keine
Strategieübernahme.
