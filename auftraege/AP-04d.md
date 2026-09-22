---
titel: Durchsicht der Rollkandidaten - Datei-Rundreise
modell: guenstig
status: offen
abhaengig_von: AP-04dv
---

# AP-04d · Durchsicht der Rollkandidaten

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-04dv). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag 1–18 in `auftraege/AP-04dv.md`. Lies ihn
vollständig.

## Worum es geht

Seit AP-04k verketten Rolls ohne gemeinsame Order-Nummer nicht mehr
automatisch; sie werden als **Kandidaten** vorgeschlagen, über die der
Nutzer entscheidet. Bestätigung und Ablehnung landen in `chain_overrides`
(Spalte `urteil`). Es fehlt der Weg, über mehrere hundert Kandidaten zu
entscheiden: zwei Kommandos, die sie als Excel-Datei ausschreiben und die
Entscheidungen wieder einlesen.

## Zu bauen

- `journal/durchsicht.py` mit `kandidaten_ausschreiben()` und
  `urteile_einlesen()` samt ihrer Ergebnisklassen.
- In `journal/rebuild.py`: eine lesende Funktion, die Lesen und Rechnen aus
  `_rebuild_laufen()` enthält; `_rebuild_laufen()` ruft sie auf
  (Vertrag 10).
- Zwei Unterbefehle in `journal/cli.py` (Vertrag 18).

## Wo du abschreiben sollst statt neu zu erfinden

- **Offene Kandidaten:** `_offene_kandidaten()` in `journal/rebuild.py`.
- **Naturschlüssel:** `_struktur_schluessel()` und `_kette_schluessel()` in
  `journal/rebuild.py`.
- **Seite:** `_seite_bestimmen()` in `engine/chains.py`.
- **Vertrag-21-Prüfung:** `_overrides_anwenden()` in `journal/rebuild.py`
  prüft dasselbe für gespeicherte Bestätigungen.
- **CLI-Muster:** die Unterbefehle `import` und `rebuild` in
  `journal/cli.py`.

## Die Stellen, an denen erfahrungsgemäß geraten wird

1. **Excel-Wahrheitswerte.** Tippt der Nutzer „Falsch", liest openpyxl
   `False` — einen `bool`, keinen Text. Vorsicht: In Python ist `bool` eine
   Unterklasse von `int`. Ein Wahrheitswert ist **keine** gültige
   Entscheidung (Vertrag 12).
2. **Alles oder nichts** (Vertrag 15). Erst prüfen, dann schreiben. Wer
   zeilenweise prüft und schreibt, lässt bei einem Fehler in Zeile 7 die
   Zeilen 1–6 stehen.
3. **Geld als `Decimal`** (Regel 5). Die Preise gehen als `Decimal` in die
   Zelle, nicht als `float`.
4. **Nicht ins Repository** (Vertrag 8). Prüfen, **bevor** geschrieben
   wird — der Test sieht nach, dass keine Datei entstanden ist.
5. **Kein zweiter Lesepfad** (Vertrag 10). Die Versuchung ist groß, die
   Lese- und Rechenzeilen aus dem Rebuild in das neue Modul zu kopieren.
   Nicht tun: herauslösen und gemeinsam nutzen.

## Grenzen

- Keine Änderung an `engine/`, an der Migration oder am Schema.
- Kein automatischer `rebuild` nach dem Einlesen.
- **Regel 2:** Lies keine Datei unter `fixtures/golden/`, führe kein
  Skript unter `werkzeuge/abgleich/` aus und führe die neuen Kommandos
  **nicht** gegen eine echte Datenbank aus. Alle Tests arbeiten auf
  temporären Datenbanken mit erfundenen Daten.

## Abnahme

- `tests/test_durchsicht.py` vollständig grün, alle übrigen Tests grün.
- `pytest` und `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `journal/durchsicht.py`,
  `journal/rebuild.py` und `journal/cli.py`.
