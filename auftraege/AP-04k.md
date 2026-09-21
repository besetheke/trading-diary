---
titel: Zeitfenster-Rolls werden Kandidaten statt Ketten (OF-41)
modell: stark
status: fertig
abhaengig_von: AP-04p
aendert_tests: ja
---

# AP-04k · Vom Automatismus zum Kandidaten

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ändert eine benannte
Test-Erwartung und läuft deshalb unter `locker`.

**Vorbedingung erfüllt:** Der Plan trägt die neue Fassung von §6, AP-04,
Block B, Regel 2 samt Regel 5 (Commit `3786cb7`, 21.09.2026). Der
Vorschlagstext `auftraege/AP-04-vorschlag-kettenidentitaet.md` ist damit
erledigt und kann gelöscht werden.

## Warum

Gemessen an der durchgesehenen Stichprobe (OF-41): Von 25 über das
Zeitfenster gebildeten Ketten waren **zehn falsch** und drei unklar; von
acht über die Order-Nummer belegten war **keine** falsch. Das Zeitfenster
verwechselt den Wiedereinstieg nach einem Profit Target mit einem Roll und
übersieht zugleich Rolls jenseits der drei Minuten.

**Der Eingriff ist kleiner, als er klingt.** Über den gesamten Bestand:

| | Anzahl |
|---|---|
| Rollverknüpfungen über die Order-Nummer (bleiben) | 2.024 |
| Rollverknüpfungen über das Zeitfenster (werden Kandidaten) | **189** |
| Ketten mit mindestens einem Zeitfenster-Glied (zerfallen) | **172** von 7.009 |

## Ausdrücklich freigegebene Änderungen an Tests

Nur diese, keine weiteren.

- **`tests/test_chains.py::test_options_roll_in_zwei_orders_ueber_zeitfenster`** —
  erwartet heute eine Kette mit `anzahl_rolls == 1` und einem Glied mit
  `erkennung == 'heuristik'`. Neu: **zwei** Ketten, und das Paar erscheint
  in der Kandidatenliste. Die Prüflogik bleibt erhalten — geprüft wird
  weiterhin, was aus demselben Fixture entsteht, nur eben das Richtige.
- **Vier Tests in `tests/test_rebuild.py`**, deren Fixture den
  Zwei-Order-Roll auf ESTX50 enthält und die deshalb mechanisch nachziehen
  (beim Schneiden des Auftrags übersehen, nachgetragen 21.09.2026):
  - `test_grundlauf_schreibt_die_erwarteten_zeilen` — **5 statt 4 Ketten**;
    Legs, Strukturen und Kettenglieder bleiben unverändert, weil jede
    Struktur weiterhin genau ein Glied hat.
  - `test_naturschluessel_folgen_dem_vertrag` — `k:Z5|Z6` kommt hinzu.
  - `test_zweiter_lauf_aendert_nichts` — dieselbe Zahl.
  - `test_rollverknuepfung_traegt_ihre_erkennungsart` — **`erkennung =
    'heuristik'` kann in `chain_links` nicht mehr vorkommen**, weil es keine
    heuristische Verknüpfung mehr gibt. Geprüft wird stattdessen, dass der
    ESTX50-Fall **kein** Kettenglied erzeugt und als offener Kandidat
    gezählt wird; die belegte DAX-Verknüpfung bleibt `auto`.
- **Neue Tests** in `tests/test_chains.py` für die Kandidatenliste und in
  `tests/test_rebuild.py` für Ablehnungen (siehe Abnahme).

**Nicht freigegeben:** Jeder andere Test. Insbesondere bleiben
`test_options_roll_in_einer_order_ueber_gemeinsamen_exec_batch`,
`test_futures_*` und alle Pflichttests aus §6 unverändert — der belegte Weg
ändert sich nicht.

## Vertrag

1. **`_rolls_verketten()` verkettet nur noch über `exec_batch`.** Schritt 2
   (Zeitfenster) entfällt als Verknüpfung.
2. **Neue reine Funktion `rollkandidaten(structures)`** in
   `engine/chains.py`, gleiche Reinheit wie der Rest des Moduls (Regel 6).
   Ein Kandidat ist ein Paar (schließende Struktur, eröffnende Struktur) mit
   gleichem Basiswert, gleicher Seite (`rechte`) und einer Eröffnung nach der
   Schließung innerhalb des Kandidatenfensters.
3. **Keine Mengenbedingung als Ausschluss.** Ein Roll ist keine
   Eins-zu-eins-Nachfolge (OF-41); Positionen werden geteilt, erweitert und
   teilweise gerollt. Das Mengenverhältnis geht in die **Sortierung** ein,
   nicht in die Auswahl.
4. **Sortierung**, absteigend nach Plausibilität: geringer zeitlicher
   Abstand, Mengenverhältnis nahe 1, Preisbild, das zum Fortführen passt.
   Die Reihenfolge ist deterministisch — bei Gleichstand entscheidet der
   Naturschlüssel, nicht die Eingabereihenfolge.
5. **Eine bereits über `exec_batch` fortgesetzte Struktur erzeugt keinen
   Kandidaten mehr.** Was belegt ist, wird nicht zur Rückfrage.
6. **Mehrdeutigkeit wird nicht aufgelöst.** Hat eine schließende Struktur
   mehrere Kandidaten, werden alle angeboten — die heutige Praxis, den
   ersten passenden zu nehmen, hat nachweislich Rolls verbaut (OF-41,
   Gegenprobe). Gemessen: 67 von 327 schließenden Strukturen haben mehr als
   einen Kandidaten.
7. **`KettenErgebnis` trägt die Kandidaten mit** (`kandidaten: tuple[...]`).
   Sie werden **nicht persistiert** — `journal rebuild` berechnet sie neu
   und meldet nur ihre Anzahl.
8. **Das Kandidatenfenster ist ein benannter Modulwert**, kein Literal:
   `KANDIDATENFENSTER = timedelta(minutes=30)` (Plan §6, Block B, Regel 2).
   Gemessen ergibt das 597 Kandidatenpaare über den gesamten Bestand.

### Ablehnungen sind Benutzerdaten (Plan §6, Block B, Regel 2)

9. **Eine Ablehnung wird gespeichert wie eine Bestätigung.** Ohne das
   erscheint jeder abgelehnte Kandidat bei jedem `rebuild` erneut, und eine
   Durchsicht von mehreren hundert Paaren wäre nicht dauerhaft.
10. **Dafür ist eine Migration nötig** (Regel 3, bestehende bleiben
    unangetastet). `chain_overrides` kann heute nur „gehört dazu"
    ausdrücken: Neue Spalte `urteil`, Text, NOT NULL, Vorgabewert
    `'bestaetigt'`, `CHECK (urteil IN ('bestaetigt', 'abgelehnt'))`.
    Bestehende Zeilen sind damit unverändert Bestätigungen. Dazu die
    Ergänzung in `journal/schema.py`.
11. **Bedeutung einer Ablehnung:** `(chain_id, structure_id,
    urteil='abgelehnt')` heißt „diese Struktur setzt jene Kette **nicht**
    fort". `chain_id` ist die Kette der schließenden Seite des Kandidaten,
    `structure_id` die vorgeschlagene Fortsetzung. Dieselbe Stabilität wie
    bei Bestätigungen: Beide hängen am Naturschlüssel der eröffnenden
    Struktur (AP-04v, Entscheidung 1).
12. **Die Engine bleibt rein (Regel 6).** `rollkandidaten()` kennt keine
    Urteile und liefert **alle** Kandidaten. Das Ausfiltern bereits
    entschiedener Paare geschieht in `journal/rebuild.py`, wo die Datenbank
    ohnehin gelesen wird.
13. **`RebuildErgebnis`** bekommt `kandidaten_offen` — Kandidaten abzüglich
    der bereits bestätigten und abgelehnten. `journal rebuild` gibt den Wert
    aus.

## Abnahme

- `test_options_roll_in_zwei_orders_ueber_zeitfenster` in der neuen Fassung
  ist grün: zwei Ketten, Paar in der Kandidatenliste.
- Neue Tests: eine über `exec_batch` belegte Fortsetzung erzeugt **keinen**
  Kandidaten; eine Schließung mit zwei möglichen Fortsetzungen erzeugt
  **zwei** Kandidaten; ein Kandidat mit stark abweichender Menge wird
  angeboten, aber hinten einsortiert; die Reihenfolge ist von der
  Eingabereihenfolge unabhängig.
- **Ablehnung überlebt den Rebuild:** Ein abgelehnter Kandidat wird nach
  zwei `rebuild`-Läufen nicht erneut angeboten, `chain_overrides` bleibt
  unverändert, und die Struktur hängt an keiner Kette. Ebenso bleibt die
  Prüfung bestehen, dass eine **Bestätigung** den Rebuild überlebt.
- Alle übrigen Tests bleiben grün, insbesondere die Pflichttests aus §6.
- Die vier Golden-Invarianten halten weiterhin
  (`werkzeuge/abgleich/golden_ketten_invarianten.py`).
- Der OA-Abgleich bleibt unverändert: 299 von 325 exakt, 26 kontoweit
  verrechnet, 0 unerklärt — OA-Ketten entstehen über Schritt 0a und sind
  vom Zeitfenster nicht betroffen.
- `ruff check .` sauber.

## Ausdrücklich nicht Teil dieses Pakets

Keine Oberfläche zum Bestätigen (AP-08), keine Sortierung durch ein
gelerntes Modell (OF-41, zurückgestellt), keine Änderung an Block A — der
Befund zu mehrterminigen Strukturen aus einer Order (OF-42) ist ein eigenes
Paket. Keine Abdeckungskennzahl in den Auswertungen (AP-06).
