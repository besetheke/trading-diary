---
titel: Positionsliste und Detailansicht (schmale erste Fassung)
modell: guenstig
status: fertig
abhaengig_von: AP-08lv
---

# AP-08l · Positionsliste und Detailansicht

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-08lv). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag 1–13 in `auftraege/AP-08lv.md`. Lies ihn
vollständig, samt dem Abschnitt „Die Entscheidung, die dieses Paket prägt".

## Worum es geht

Seit AP-07l liefert eine Lese-API Ketten, Strukturen und den Drilldown bis
zur Ausführung. Dieses Paket macht sie sichtbar: eine Positionsliste und
eine Detailansicht, sonst nichts.

**Die Oberfläche bleibt absichtlich dünn.** Es gibt für sie noch kein
Testwerkzeug — das wird später entschieden. Je weniger eigene Logik sie
trägt, desto weniger fehlt der fehlende Test. Alles, was rechnet, sortiert
oder filtert, gehört in die API; die ist geprüft. Wenn dir auffällt, dass
die Oberfläche etwas rechnen müsste, ist das ein Hinweis auf eine fehlende
Abfrage, kein Anlass, es im Browser zu tun.

## Zu bauen

- `ui/` — Vite mit React und TypeScript, zwei Ansichten (Vertrag 6, 7).
- In `api/app.py` — die statische Auslieferung samt Rückfall (Vertrag 1–5).
- `.gitignore` — `node_modules/` und `ui/dist/` sind bereits eingetragen.

## Die vier Stellen, an denen erfahrungsgemäß geraten wird

1. **Geld nie durch eine JavaScript-Zahl schicken** (Vertrag 8). `parseFloat`
   oder `Number()` auf ein Geldfeld hebt genau den Schutz auf, den die API
   aufbaut: Ihre Beträge sind Zeichenketten, weil JavaScript-Zahlen
   Gleitkommazahlen sind. Rechtsbündig ausrichten ja, umrechnen nein. Auch
   nicht „nur zum Sortieren" — sortiert wird in der API.
2. **Der Rückfall darf die API nicht verschlucken** (Vertrag 3). Erst die
   API-Routen, dann die Dateien, dann `index.html`. Ein `/ketten/abc` muss
   422 bleiben; wer hier `index.html` liefert, verwandelt jede kaputte
   Anfrage in eine leere Seite.
3. **Filter und Blättern gehören in die Adresszeile** (Vertrag 12), nicht in
   einen Zustand, der beim Neuladen verschwindet. Ein Stand muss teilbar
   sein.
4. **Leerer Treffer ist nicht dasselbe wie ein Fehler** (Vertrag 11). Beides
   braucht eine eigene Anzeige; eine leere Seite sieht sonst aus wie ein
   leeres Konto.

## Grenzen

- Keine Kennzahl, keine Summe über Positionen, keine Umrechnung — es gibt
  keine Euro-Umrechnung (AP-06), und eine Spalte, die mehrere Währungen
  addiert, wäre falsch.
- Kein Dashboard, keine Kampagnen, kein Kalender, kein Journal-Editor.
- Keine Schreibfunktion; die API kennt ohnehin nur `GET`.
- Kein Frontend-Testwerkzeug einführen — auch nicht „nur einen kleinen
  Test". Das wird gesondert entschieden.
- **Regel 2:** Starte die Oberfläche nicht gegen die echte Datenbank
  (`journal.db`), sondern gegen eine mit erfundenen Daten. Lies keine Datei
  unter `fixtures/golden/`.

## Abnahme

- `tests/test_api_statisch.py` — zehn Fälle — grün; gesamte Suite grün;
  `ruff check .` sauber.
- `npm run build` erzeugt `ui/dist/index.html`.
- **Du klickst die Oberfläche selbst durch** (`npm run dev` gegen die API
  mit erfundenen Daten) und berichtest, **was du gesehen hast** — Liste,
  Filter, Blättern, Detailansicht, Drilldown, tiefer Verweis nach Neuladen,
  leerer Treffer, gestoppte API. Nicht, was du erwartest. Ohne diesen
  Durchgang ist das Paket nicht fertig; es gibt für die Oberfläche keinen
  Test, der ihn ersetzt.
- `git diff --stat` zeigt `api/app.py`, `ui/`, `.gitignore` und
  `OFFENE_FRAGEN.md`.
