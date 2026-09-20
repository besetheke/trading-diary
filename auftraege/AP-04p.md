---
titel: Persistenz der Ketten und journal rebuild
modell: guenstig
status: offen
abhaengig_von: AP-04v
---

# AP-04p · Persistenz und `journal rebuild`

Umsetzungspaket nach Plan §11.2, Schritt 2: Die Abnahmebasis liegt vor
(AP-04v), hier wird gegen sie implementiert. **Tests, Fixtures und
Migration sind tabu** — fällt ein Test, ist der Code falsch.

Maßgeblich ist der Vertrag in `auftraege/AP-04v.md`, Abschnitt „Vertrag an
die Umsetzung". Lies ihn vollständig, einschließlich des Abschnitts „Die
zwei Entscheidungen, die nicht beim Umsetzer liegen" — dort steht, warum
der Rebuild abgleicht statt neu anzulegen, und warum keine Euro-Beträge
geschrieben werden.

## Aufgabe in einem Satz

Die Engine rechnet Legs, Strukturen und Ketten bereits korrekt aus, aber
nur im Speicher. Schreibe das Ergebnis in die Datenbank, mach es über
`journal rebuild` aufrufbar, und sorge dafür, dass manuelle Overrides einen
Rebuild überleben.

## Zu bauen

- `journal/rebuild.py` mit `rebuild()` und `RebuildErgebnis`
  (Vertrag 1–3).
- Unterbefehl `rebuild` in `journal/cli.py` (Vertrag 3).

Mehr nicht. `engine/` wird nicht angefasst.

## Wo du abschreiben sollst statt neu zu erfinden

- **Kapitalmaßnahmen aus `corporate_actions` ableiten:**
  `werkzeuge/abgleich/golden_bestandsabgleich_of23.py`, Funktion
  `kapitalmassnahmen_ableiten()`. Diese Datei liest Golden-Daten — **lies
  nur die Funktion, führe das Skript nicht aus** (Regel 2).
- **Datenbankanbindung:** `journal/db.py`, `create_db_engine()`. Setzt die
  Pragmas aus §4.1 bereits richtig, inklusive `busy_timeout` (Regel 9).
- **Aufrufform des CLI-Unterbefehls:** `journal/cli.py`, Befehl `import`.
- **Endzustand einer Kette:** `engine.chains.ENDZUSTAND_JE_EREIGNIS`
  importieren, nicht nachbauen.

## Die vier Stellen, an denen erfahrungsgemäß geraten wird

0. **`netto_pnl` wird addiert, nicht subtrahiert** — Vertrag 10a.
   Kommissionen tragen das Vorzeichen, das IB liefert: negativ, wenn sie
   Geld kosten. In der Golden-Historie stehen 23.971 negativen aber auch
   340 **positive** gegenüber, also echte Gutschriften. `brutto - kommission`
   dreht bei allen das Vorzeichen, `abs()` macht aus den Gutschriften Kosten.


1. **`structures.erkennung` hat ein anderes Vokabular als das Feld
   `Structure.erkennung` der Dataclass.** Die Spalte kennt
   `order_id`/`heuristik`/`manuell`, die Dataclass liefert `auto`. Die
   Spalte wird aus `Structure.methode` abgeleitet — Vertrag 12. Wer das
   Dataclass-Feld durchreicht, verletzt den CHECK.
2. **`structures.waehrung` steht nicht an der `Structure`** und muss aus
   den `executions` der Legs gelesen werden — Vertrag 11. Bei Uneinigkeit
   abbrechen, nicht die häufigste wählen.
3. **`chain_links.erkennung` unterscheidet bereits** zwischen `auto` und
   `heuristik` und kommt unverändert aus `ChainGlied` — Vertrag 14. Nicht
   vereinheitlichen.

## Grenzen

- Keine Kennzahlen, keine FX-Umrechnung, keine Campaigns, keine API.
  `netto_pnl_eur` bleibt leer, und das ist kein Versehen.
- Keine Änderung an `engine/`. Fällt dir dort ein Fehler auf, trage ihn in
  `OFFENE_FRAGEN.md` ein und brich ab — die Engine gehört zum starken
  Modell.
- Keine neue Migration. Das Schema ist vollständig; fehlt dir eine Spalte,
  ist der Auftrag falsch geschnitten und du meldest das.
- **Regel 2:** Lies keine Datei unter `fixtures/golden/` und führe kein
  Skript unter `werkzeuge/abgleich/` aus. Alle Fixtures dieses Pakets
  liegen in `tests/fixtures_rebuild.py` und sind frei erfunden.

## Abnahme

- `tests/test_rebuild.py` läuft vollständig grün.
- `pytest` und `ruff check .` sind sauber.
- `git diff --stat` zeigt Änderungen **ausschließlich** in
  `journal/rebuild.py` und `journal/cli.py`.
