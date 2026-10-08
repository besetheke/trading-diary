---
titel: Abnahmebasis Analytik III — Roll-Degradation
modell: stark
status: fertig
abhaengig_von: AP-06v, AP-06x, AP-04sz
aendert_tests: ja
---

# AP-06d · Abnahmebasis: Roll-Degradation (AP-06, Tranche III)

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-06dk (günstiges Modell). Neue Testdatei `tests/test_degradation.py`
(17 Tests), keine bestehende Erwartung wird geändert.

Plan AP-06: „Roll-Degradationskurve (Ergebnis nach 0, 1, 2, 3+ Rolls) … Sie
läuft wahlweise nur auf belegten Ketten oder auf belegten plus bestätigten und
nennt in beiden Fällen die Abdeckung. Unbestätigte Kandidaten gehen nie ein."

## Entscheidungen (E1–E8, vom Nutzer freigegeben „Vollgas weiter")

- **E1 Sicht.** Nur die Kettensicht (Plan §5: sie „trägt die Roll-Degradation").
  `sicht != 'kette'` → `ValueError`, Text nennt die Kettensicht.
- **E2 Gruppen.** Die Ketten werden nach `anzahl_rolls` in `'0'`, `'1'`, `'2'`,
  `'3+'` gruppiert (wie die Roll-Dimension der Kommissionsattribution). Das
  „Ergebnis nach n Rolls" ist das Ergebnis der Ketten mit n Rolls (nicht ein
  kumulierter Verlauf je Kette).
- **E3 Kennzahlen je Gruppe.** Anzahl abgeschlossener Ketten mit Kurs, Summe
  netto EUR (wirtschaftlich, Tranche I), Durchschnitt je Kette (zwei Stellen
  HALF_UP), Trefferquote (Anteil Ketten mit netto > 0, vier Stellen, Tranche I
  E5), Anzahl Ketten ohne Kurs (zählen nicht in Summe, Durchschnitt, Quote).
  Leere Gruppe: Anzahl 0, Summe 0.00, Durchschnitt und Quote `None`.
- **E4 Zugelassene Ketten.** Nur abgeschlossene. Modus `belegt`: alle
  Rollverknüpfungen der Kette (`verknuepfungstyp = 'roll'`) tragen Erkennung
  `auto`. Modus `belegt_bestaetigt`: `auto` oder `manuell`. Eine Kette mit
  einer anderen Erkennung (`heuristik`) geht in keinem Modus ein.
- **E5 Abdeckung** je Modus: `ketten_abgeschlossen` (alle abgeschlossenen
  Ketten der Sicht nach Stufenfilter), `ketten_ausgewertet` (zugelassene,
  auch mit Kursmangel), `abdeckung_ketten = ausgewertet / abgeschlossen`;
  `rollverknuepfungen` (Roll-Glieder der zugelassenen Ketten),
  `offene_kandidaten` (übergeben oder ermittelt), `abdeckung_rollverknuepfungen
  = rolls / (rolls + offene_kandidaten)`; ohne Angabe der Kandidaten `None`.
- **E6 Ketten an offenen Kandidaten werden nicht ausgeschlossen** (Plan:
  172 von 7.009 Ketten, 2,5 %); die Abdeckung weist das aus. Die Kandidaten
  gehen selbst nie als Roll ein.
- **E7 Stufenfilter** `--nur-stufe-a`: entfernt Ketten ganz, auch aus der
  Abdeckung (wie Tranche I/II).
- **E8 Ausgabe.** `journal kennzahlen DATEI --degradation DATEI2`, eine CSV,
  Semikolon, UTF-8 mit BOM, Zeilenende `\n`: Kopf, acht `gruppe`-Zeilen, zwei
  `abdeckung`-Zeilen (Format im Test `test_csv_format_und_inhalt`).
  `--sicht konto` zusammen mit `--degradation`: Meldung auf stderr (nennt die
  Kettensicht), Rückgabe 1, **keine** Datei wird geschrieben.

## Schnittstellen (verbindlich)

- `analytics/degradation.py`: `degradations_auswertung(ketten_zeilen,
  struktur_zeilen, glieder_zeilen, leg_zeilen, ausfuehrungs_zeilen,
  instrumenten_zeilen, *, sicht="kette", offene_kandidaten=None,
  nur_qualitaetsstufe_a=False)` (rein), `degradations_bericht(db_pfad, *,
  nur_qualitaetsstufe_a=False, offene_kandidaten=None)` (liest, **schreibt
  nichts**; ermittelt die offenen Kandidaten selbst, wenn nicht übergeben),
  `als_csv(ergebnis)`, Datenklassen `DegradationsGruppe`,
  `DegradationsAbdeckung`, `DegradationsErgebnis` (Felder wie in den Tests).
- `glieder_zeilen` tragen zusätzlich `verknuepfungstyp` und `erkennung`.
- `journal/rebuild.py`: `offene_rollkandidaten(db_pfad) -> int` — dieselbe
  Zahl wie `RebuildErgebnis.kandidaten_offen`, ohne etwas zu schreiben.

## Abnahme

`tests/test_degradation.py` grün (Handrechnung in Modul-Docstring und je
Test), alle übrigen Tests unverändert grün, `ruff check .` sauber. Gegen eine
Wegwerf-Umsetzung geprüft: alle 17 grün; ohne Modul rot (ModuleNotFoundError).
Der Echtlauf der Wegwerf-Umsetzung steht in OF-70.
