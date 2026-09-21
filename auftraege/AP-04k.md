---
titel: Zeitfenster-Rolls werden Kandidaten statt Ketten (OF-41)
modell: stark
status: offen
abhaengig_von: AP-04p
aendert_tests: ja
---

# AP-04k · Vom Automatismus zum Kandidaten

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ändert eine benannte
Test-Erwartung und läuft deshalb unter `locker`.

> **Vorbedingung: Der Plantext muss stehen.** Grundlage ist §6, AP-04,
> Block B, Regel 2 in der neuen Fassung (Vorschlagstext in
> `auftraege/AP-04-vorschlag-kettenidentitaet.md`). Solange der Plan die
> alte Fassung trägt, darf dieses Paket nicht laufen — es würde eine
> Test-Erwartung gegen den geltenden Plan ändern.

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
- **Neue Tests** in derselben Datei für die Kandidatenliste (siehe Abnahme).

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
   und meldet nur ihre Anzahl. Bestätigt werden sie über `chain_overrides`,
   wie bisher (kein Schemaeingriff).
8. **Das Kandidatenfenster ist ein benannter Modulwert**, kein Literal im
   Code, und es ist weiter als die drei Minuten der alten Regel — die
   Stichprobe fand echte Rolls jenseits davon. Vorschlag: 30 Minuten.
   Gemessen ergibt das 597 Kandidatenpaare über den gesamten Bestand;
   bei 3 Minuten wären es 402, bei 60 Minuten 752.

## Abnahme

- `test_options_roll_in_zwei_orders_ueber_zeitfenster` in der neuen Fassung
  ist grün: zwei Ketten, Paar in der Kandidatenliste.
- Neue Tests: eine über `exec_batch` belegte Fortsetzung erzeugt **keinen**
  Kandidaten; eine Schließung mit zwei möglichen Fortsetzungen erzeugt
  **zwei** Kandidaten; ein Kandidat mit stark abweichender Menge wird
  angeboten, aber hinten einsortiert; die Reihenfolge ist von der
  Eingabereihenfolge unabhängig.
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
