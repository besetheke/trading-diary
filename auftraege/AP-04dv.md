---
titel: Abnahmebasis fuer die Durchsicht der Rollkandidaten (Datei-Rundreise)
modell: stark
status: fertig
abhaengig_von: AP-04k
aendert_tests: ja
---

# AP-04dv · Abnahmebasis für die Durchsicht

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-04d (günstiges Modell).

Fachliche Grundlage: Plan §6, AP-04, Block B, Regel 2, Absatz „Durchsicht
über eine Datei-Rundreise, bis AP-08 steht" — ein Kommando schreibt die
offenen Kandidaten als Tabelle, gruppiert nach schließender Position mit
allen möglichen Fortsetzungen; der Nutzer markiert Annahme oder Ablehnung
in einer Tabellenkalkulation; ein zweites Kommando liest das ein und
schreibt nach `chain_overrides`.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Neue Testdatei** `tests/test_durchsicht.py` — springt still ab,
  solange `journal/durchsicht.py` fehlt.
- **Neues Fixture-Modul** `tests/fixtures_durchsicht.py` — zwei frei
  erfundene Szenarien (`MEHRDEUTIG`, `DOPPELT`), nachgerechnet gegen die
  Engine am 22.09.2026:

  | Szenario | Strukturen | Kandidaten |
  |---|---|---|
  | Standard (`fixtures_rebuild`) | 6 | `Z1\|Z2` → `Z5\|Z6`, Rang 1, 2 min |
  | `MEHRDEUTIG` | 3 | `Y1\|Y2` → `Y5\|Y6` (Rang 1, 2 min) und → `Y7\|Y8` (Rang 2, 20 min) |
  | `DOPPELT` | 3 | `P1\|P2` → `N1\|N2` und `Q1\|Q2` → `N1\|N2`, je Rang 1 |

Kein bestehender Test, kein bestehendes Fixture wird angefasst.

## Vertrag an die Umsetzung (AP-04d)

### Modul

1. **`journal/durchsicht.py`** mit zwei Funktionen:
   - `kandidaten_ausschreiben(db_pfad, ziel, *, busy_timeout_ms=...) ->
     AusschreibErgebnis` mit den Feldern `gruppen` und `kandidaten`.
   - `urteile_einlesen(db_pfad, quelle, *, ueberschreiben=False,
     jetzt=None, busy_timeout_ms=...) -> EinleseErgebnis` mit den Feldern
     `neu_bestaetigt`, `neu_abgelehnt`, `unveraendert`, `geaendert`,
     `unentschieden`.

   Beide Ergebnisse sind `@dataclass(frozen=True)`. **Nicht unter
   `engine/`** — das Modul liest und schreibt Dateien und eine Datenbank
   (Regel 6).

### Ausschreiben

2. **Nur offene Kandidaten.** Ein Kandidat ist offen, wenn es in
   `chain_overrides` keine Zeile mit derselben Kombination aus Kette der
   schließenden Seite und vorgeschlagener Struktur gibt — gleich welches
   Urteil. Dieselbe Regel wie `_offene_kandidaten()` in
   `journal/rebuild.py`.
3. **Format:** XLSX. Arbeitsblatt `Kandidaten`, **Kopfzeile in Zeile 1**,
   Spalten in genau dieser Reihenfolge:

   `Gruppe`, `Kandidaten in Gruppe`, `Rang`, `Basiswert`, `Seite`,
   `Alt: Legs`, `Alt: geschlossen`, `Alt: Preis zu`,
   `Neu: Legs`, `Neu: eröffnet`, `Neu: Preis auf`,
   `Abstand Minuten`, `Mengenverhältnis`, `Entscheidung`, `Bemerkung`,
   `Schlüssel Kette`, `Schlüssel Struktur`

   Dazu ein zweites Blatt `Anleitung` mit einer kurzen Erklärung: `ja` oder
   `nein` eintragen, leer lassen heißt unentschieden, **nicht** „Wahr" oder
   „Falsch" schreiben (Excel macht daraus Wahrheitswerte).
4. **Eine Zeile je Kandidat, gruppiert.** Eine Gruppe ist eine schließende
   Position mit all ihren Kandidaten. Gruppen sind 1…n durchnummeriert in
   der Reihenfolge ihres Schließzeitpunkts; innerhalb der Gruppe nach
   `Rang`. `Kandidaten in Gruppe` steht in jeder Zeile der Gruppe, damit
   man in Excel nach mehrdeutigen Gruppen filtern kann — dort soll die
   Durchsicht beginnen (Plan §6, B/2).
5. **Inhalte:**
   - `Basiswert` der schließenden Struktur; `Seite` wie `Chain.seite`
     (`Call`, `Put`, `n.a.`) — nutze `_seite_bestimmen()` aus
     `engine/chains.py`, statt es nachzubauen.
   - `Alt: Legs` / `Neu: Legs` als lesbarer Text je Leg mit Richtung,
     Menge, Recht, Strike und Verfall. Das genaue Format ist frei; der
     Strike muss erkennbar darin stehen.
   - `Alt: geschlossen` = `geschlossen_am` der schließenden,
     `Neu: eröffnet` = `eroeffnet_am` der eröffnenden Struktur.
   - `Abstand Minuten` und `Mengenverhältnis` aus dem `Rollkandidat`.
   - `Schlüssel Kette` = Naturschlüssel der Kette, **in der die schließende
     Struktur liegt**; `Schlüssel Struktur` = Naturschlüssel der
     vorgeschlagenen Struktur. Über diese beiden liest das Einlesen zurück —
     sie sind über `rebuild`-Läufe stabil (AP-04v, Entscheidung 1), Nummern
     sind es nicht zwingend.
6. **Preise:** `Alt: Preis zu` ist die Nettoprämie, zu der die schließende
   Struktur geschlossen wurde, `Neu: Preis auf` die, zu der die neue
   eröffnet wurde — je Kontrakt. Je Leg: Menge der **Leg** × Preis der
   Ausführung, Verkauf positiv, Kauf negativ; Summe geteilt durch die Menge
   der Struktur. **Als `Decimal`** in die Zelle (openpyxl schreibt es ohne
   `float`-Umweg; Regel 5). Die Preise werden nie zurückgelesen.
7. **Keine Datei überschreiben.** Existiert das Ziel, `FileExistsError` —
   eine vorhandene Datei kann Entscheidungen tragen.
8. **Nicht ins Repository (Regel 2).** Aus der echten Datenbank enthält die
   Datei echte Kontodaten. Liegt das Ziel innerhalb des Projektverzeichnisses
   und **nicht** unter `fixtures/golden/`, `ValueError` — vor jedem
   Schreibversuch.
9. **Erst `rebuild`.** Die Schlüssel müssen auf vorhandene Zeilen in
   `structures` und `chains` zeigen. Fehlt eine, `ValueError` mit dem
   Hinweis, zuerst `journal rebuild` auszuführen — keine Datei, die sich
   nie zurücklesen ließe.
10. **Kandidaten nicht neu erfinden.** Das Ausschreiben braucht dieselbe
    Berechnung wie der Rebuild. Lege dazu in `journal/rebuild.py` eine
    **lesende** Funktion an, die den Block „Lesen" und „Rechnen" aus
    `_rebuild_laufen()` enthält (Ausführungen, Instrumente,
    Kapitalmaßnahmen, `bilde_legs` → `bilde_structures` → `bilde_chains`),
    und lass `_rebuild_laufen()` sie aufrufen. **Kein zweiter Lesepfad** —
    zwei Kopien laufen früher oder später auseinander. Die bestehenden
    Rebuild-Tests sichern ab, dass sich dabei nichts ändert.

### Einlesen

11. **Bedeutung der Entscheidung** je Zeile:
    - `ja` → Zeile in `chain_overrides` mit `urteil = 'bestaetigt'`,
    - `nein` → dieselbe Zeile mit `urteil = 'abgelehnt'`,
    - leer → keine Zeile, zählt als `unentschieden`.

    `chain_id` aus `Schlüssel Kette`, `structure_id` aus `Schlüssel
    Struktur`, jeweils über den Naturschlüssel in der Datenbank aufgelöst.
    `notiz` = `Bemerkung` (leer bleibt leer). `erstellt_am` = `jetzt`, ohne
    Angabe die aktuelle Zeit.
12. **Nur gültige Werte:** `ja`, `j`, `nein`, `n`, Groß- und Kleinschreibung
    egal, umgebende Leerzeichen egal. **Alles andere bricht ab** — auch ein
    Wahrheitswert (`True`/`False`), den Excel aus „Wahr"/„Falsch" macht,
    und auch Zahlen. Die Meldung nennt **Gruppe und Rang** der Zeile
    (Wortlaut „Gruppe <n>").
13. **Idempotenz:** Steht dieselbe Entscheidung schon in
    `chain_overrides`, ist das kein Fehler und keine neue Zeile, sondern
    `unveraendert`.
14. **Keine stille Änderung (Regel 4).** Widerspricht eine Zeile einer
    gespeicherten Entscheidung (`ja` gegen gespeichertes `abgelehnt` oder
    umgekehrt), bricht das Einlesen ab und nennt Gruppe und Rang. Nur mit
    `ueberschreiben=True` wird das Urteil geändert (`geaendert`), `notiz`
    und `erstellt_am` dabei neu gesetzt.
15. **Alles oder nichts.** Erst alle Zeilen prüfen, dann in **einer** kurzen
    Transaktion schreiben (Regel 9). Bricht irgendetwas ab, steht danach
    nichts Neues in der Datenbank — auch nicht die gültigen Zeilen.
16. **Keine Struktur in zwei Ketten** (AP-04v, Vertrag 21): Würden nach dem
    Einlesen zwei Bestätigungen dieselbe Struktur verschiedenen Ketten
    zuordnen — aus der Datei selbst oder zusammen mit bereits gespeicherten
    —, bricht das Einlesen vor dem Schreiben ab.
17. **Unbekannte Schlüssel** (Struktur oder Kette nicht in der Datenbank)
    brechen ab. Das Einlesen führt **keinen** `rebuild` aus; es schreibt nur
    die Entscheidungen.

### Kommandos

18. In `journal/cli.py`, mit `--db` wie die übrigen Unterbefehle:
    - `journal kandidaten-ausschreiben <datei>` — gibt Gruppen und
      Kandidaten aus.
    - `journal kandidaten-einlesen <datei> [--ueberschreiben]` — gibt die
      Zählwerte aus **und den Hinweis, danach `journal rebuild`
      auszuführen** (der Test prüft auf das Wort „rebuild").

    Rückgabe 0 im Erfolgsfall; bei `ValueError` oder `FileExistsError`
    Meldung auf `stderr` und Rückgabe 1, kein Traceback.

## Abnahme

- `tests/test_durchsicht.py` — 18 Tests — läuft vollständig grün.
- Alle übrigen Tests bleiben grün, insbesondere `tests/test_rebuild.py`
  nach dem Herauslösen der lesenden Funktion (Vertrag 10).
- `ruff check .` sauber.
- `git diff --stat` der Umsetzung zeigt ausschließlich
  `journal/durchsicht.py`, `journal/rebuild.py` und `journal/cli.py`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Oberfläche (AP-08), keine automatische Ausführung von `rebuild` nach
dem Einlesen, keine Sortierhilfe durch ein gelerntes Modell (OF-41), keine
Futures-Kandidaten (die entstehen weiterhin nicht — eigener Schritt).
