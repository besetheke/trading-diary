---
titel: Abnahmebasis fuer AP-03 (Leg-Matching)
modell: stark
status: offen
abhaengig_von: AP-02a
aendert_tests: ja
---

# AP-03v · Abnahmebasis für AP-03

Vorbereitungspaket nach Plan §11.2, Schritt 1: Das starke Modell schreibt die
Abnahmetests und Fixtures, das günstige Modell implementiert danach dagegen.
Dieses Paket **implementiert nichts**.

## Anlass

AP-03 verlangte die synthetischen Fixtures und das Testmodul „in diesem Paket
anzulegen", läuft aber auf dem günstigen Modell unter dem Profil `streng`, das
weder `tests/` noch `fixtures/` beschreiben darf. Der Auftrag war damit nicht
erfüllbar; das günstige Modell hat korrekt abgebrochen (OF-12). Dieses Paket
schließt die Lücke.

## Umzusetzen

1. **Vertrag festlegen.** Einstiegspunkt und Rückgabeform des Matchings
   bestimmen, so wie AP-02 es für den Import hat. Das Modul liegt unter
   `engine/` und ist rein (Regel 6): keine Uhr, kein Netz, Zeit als Parameter.
   Den Vertrag in `auftraege/AP-03.md` unter „Vertrag an die Umsetzung"
   eintragen — Signatur, Eingaben, Rückgabe, Fehlerverhalten. Die Tests rufen
   genau diesen Einstiegspunkt auf.
2. **Fixtures anlegen** unter `fixtures/synthetisch/`. Nur erfundene Daten;
   `fixtures/golden/` wird nicht gelesen und nicht angefasst. Jede Datei trägt
   einen Kopfkommentar, der ihren Fall benennt. Pflichtfälle aus AP-03:
   - Teilschließung mit Restmenge,
   - Aktiensplit vor dem Matching,
   - Futures-Position mit Tickwert,
   - offene Position am Periodenende,
   - Kommissionsaufteilung über drei Teilschließungen.
   Dazu je ein Fall für die Fehlerpfade: fehlende `instruments`-Zeile zu einem
   `conid` und eine Ereigniszeile, die kein Trade ist.
3. **Testmodul `tests/test_matching.py`** mit mindestens 35 Tests. Es springt
   still ab, solange das Matching-Modul nicht existiert (`importorskip`, wie
   `tests/test_ingest_flex.py` es vormacht), damit `pytest` bis zur Umsetzung
   grün bleibt und danach scharf läuft.
4. **Erwartungswerte von Hand nachrechnen** (Regel 8). Jeder Erwartungswert
   trägt die Rechnung als Kommentar — Stückzahl, Multiplikator, Preis,
   Kommission, Zwischensumme. Ein Wert, der aus einer Implementierung stammt,
   ist wertlos; es gibt hier noch keine.
5. **Summenprobe abbilden.** Die Abnahme von AP-03 verlangt, dass die Summe
   aller Leg-P&L plus offener Positionen der Broker-Summe auf den Cent
   entspricht, getrennt für Optionen, Futures und Aktien. Mindestens ein
   Fixture trägt deshalb eine ausgewiesene Broker-Summe, gegen die ein Test
   genau das prüft.

## Ausdrücklich nicht Teil dieses Pakets

Kein Code unter `engine/`, keine Migration, keine Strukturbildung. Wer hier
implementiert, nimmt AP-03 die Prüfung weg — die Trennung nach §11 ist der
einzige Grund, warum die Vergabe an ein günstigeres Modell überhaupt trägt.

Bestehende Tests und Fixtures bleiben unverändert. Dieses Paket **legt neu an**;
es baut nichts um. Fällt dabei ein bestehender Test, ist das ein Abbruchgrund
und kein Anlass, ihn anzupassen.

## Abnahme

- `fixtures/synthetisch/` enthält die oben genannten Fälle, `fixtures/golden/`
  ist unverändert.
- `tests/test_matching.py` enthält mindestens 35 Tests, jeder mit
  nachgerechnetem Erwartungswert samt Rechenweg im Kommentar.
- `pytest` läuft grün: die neuen Tests überspringen sich, solange das
  Matching-Modul fehlt.
- `ruff check .` ist sauber.
- `git diff --stat` zeigt Änderungen ausschließlich in `tests/test_matching.py`,
  `fixtures/synthetisch/`, `auftraege/AP-03.md` (Vertrag) und
  `OFFENE_FRAGEN.md`. Kein `engine/`, kein `ingest/`, keine Migration.
- Was beim Nachrechnen unklar blieb, steht in `OFFENE_FRAGEN.md` — nicht als
  Annahme im Test versteckt.
