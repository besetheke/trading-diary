---
titel: Korrektur der Abnahmebasis AP-04s — umgeleitete Ausführung zählt nicht mehr doppelt (OF-68, Option A)
modell: stark
status: fertig
abhaengig_von: AP-04s, AP-04sw
aendert_tests: ja
---

# AP-04sx · Kettensicht ohne Doppelzählung

Korrekturpaket nach CLAUDE.md Regel 1a. **Es implementiert nichts** (Umsetzung:
AP-04sy, günstiges Modell). Es ändert *was* erwartet wird, nie *ob* geprüft wird.

## Fachlicher Grund (OF-68)

Die Entscheidung OF-52 („Ausführung zählt doppelt") bricht die Plan-Invariante
§5 (gleiche Summen in beiden Sichten). Echtlauf 05.10.2026: Kettensicht rund
32.000 EUR neben der Kontosicht. Nutzerentscheidung: **Option A**.

## Neue Regel

1. **Umgeleitete Ausführung E** (Erkennung unverändert, `engine/kettensicht.py`
   `_umgeleitet`) **eröffnet nur ihren eigenen Vorgang und schließt nie.** Der
   alte Vorgang bleibt offen, bis seine eigene Schließung kommt.
2. **Jede Ausführung kommt genau einmal vor** (Summentreue: Brutto und
   Kommission je Sicht gleich).
3. **Bestand brutto:** Je Kontrakt führt die Kettensicht Long- und Short-Lose
   getrennt; eine Ausführung schließt das älteste Los der Gegenrichtung, sonst
   eröffnet sie. Ohne umgeleitete Ausführung ist das identisch mit dem
   bisherigen FIFO.
4. **Nach dem Verfall** (Verfall des Kontrakts liegt vor der letzten
   Handelszeit des Eingabebestands) werden verbliebene gegenläufige offene Lose
   FIFO gegeneinander geschlossen (früheres Los eröffnet, späteres schließt).
   Grund: Das Konto ist dann flach, es gibt keine Ausführung mehr, die die
   Vorgänge trennt; ohne diese Regel blieben im Echtbestand 189 Legs offen und
   13.639 (USD, brutto) fehlten in den realisierten Ketten.
   **Bekannte Grenze:** Bei ITM-Verfall wird das innere Ergebnis nicht auf die
   beiden Vorgänge aufgeteilt (Summe stimmt, Zuordnung je Kette nicht).

## Geänderte Test-Erwartungen (`tests/test_kettensicht.py`), namentlich

| bisher | neu |
|---|---|
| `test_umgeleitete_ausfuehrung_oeffnet_ihre_eigene_struktur_wenn_ein_freier_closer_existiert` | `test_umgeleitete_ausfuehrung_eroeffnet_nur_den_eigenen_vorgang_und_laesst_den_alten_offen` |
| `test_umgeleitete_ausfuehrung_bleibt_offen_wenn_kein_freier_closer_existiert` | `test_nachfolgende_schliessung_wird_dem_alten_vorgang_zugeordnet` |
| `test_keine_mehrfachverwendung_in_der_kettensicht_ausser_der_umgeleiteten_ausfuehrung` | `test_jede_ausfuehrung_kommt_in_der_kettensicht_genau_einmal_vor` |

Neu hinzu: `test_summen_der_kettensicht_entsprechen_der_kontosicht`,
`test_offene_menge_je_kontrakt_entspricht_der_kontosicht`,
`test_ohne_eigene_schliessung_bleiben_beide_vorgaenge_vor_dem_verfall_offen`,
`test_nach_dem_verfall_werden_gegenlaeufige_offene_vorgaenge_zusammengefuehrt`.
Unverändert bleiben alle übrigen Tests (u. a. `test_matching.py`,
`test_rebuild_kette.py`, die erste zwei und der sechste Test der Datei).

## Nachweis gegen eine Wegwerf-Umsetzung (Echtdaten-Kopie, nur Zählwerte)

Rebuild auf einer Kopie von `journal.db` (Start 15:44, 5 Min., ein Prozess):
Kettensicht 17.343 Legs, realisiertes Brutto **identisch** zur Kontosicht
(244.622,27), Kommission identisch (−82.311,20), offene Legs 294 = 294. Vor
Regel 4 waren es 193 offene verfallene Legs und 13.639 Differenz — exakt der
rechnerische Verfallswert.
