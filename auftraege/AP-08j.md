---
titel: Oberfläche für das tägliche Journal (Notizen, Tags, Tagesansicht, Kalender)
modell: guenstig
status: offen
abhaengig_von: AP-07jk, AP-07tk
aendert_tests: nein
---

# AP-08j · Oberfläche für das tägliche Journal

Umsetzungspaket für den MVP-Schnitt (OF-73): Der Nutzer will zuerst das tägliche
Journal mit den Basisfunktionen benutzen. Die API dafür liefern AP-07j/jk
(Notizen, Tags, Tagesjournal) und AP-07t/tk (Tagesübersicht, Kalender). **Es
gibt keine Abnahmebasis aus Tests** — die Oberfläche hat nach Entscheidung vom
22.09.2026 (AP-08lv) kein Frontend-Testwerkzeug. Sie bleibt deshalb **dünn**:
Alles, was rechnet, sortiert oder filtert, gehört in die API.

Voraussetzung: AP-07jk und AP-07tk sind abgenommen und eingespielt.

## Zu bauen (im Verzeichnis `ui/src`)

1. **`api.ts`:** Typen und Abrufe für `GET /tage/{datum}`, `GET /kalender`,
   `GET /journal/{scope_typ}/{scope_id}`, `POST …/notizen`, `PUT/DELETE
   /journal/notizen/{id}`, `PUT …/tags`, `GET /tags`. Geld bleibt
   Zeichenkette (nie `parseFloat`, `Number`, `toFixed`). Fehler der API
   (404, 422) als lesbare Meldung zeigen, nicht verschlucken.
2. **Baustein `Journal.tsx`** (`scopeTyp`, `scopeId`): zeigt die Notizen
   (neueste zuerst, wie geliefert) mit Zeitstempel; Neue Notiz (Textfeld,
   Speichern); eine Notiz bearbeiten (inline) und löschen (mit Rückfrage);
   Tags: Anzeige als Liste, Bearbeiten als kommagetrennte Eingabe mit
   Vorschlägen aus `GET /tags` (`<datalist>`), Speichern ersetzt die
   Zuordnung. Leere Notizen werden nicht gesendet.
3. **`PositionDetail.tsx`:** den Baustein für die Kette (`chain`) einbinden,
   unterhalb der bestehenden Inhalte.
4. **Neue Ansicht `Tag.tsx`** unter `/tag/:datum`: Titel mit Datum und
   Hinweis „Kontosicht"; Knöpfe „Vortag" und „Folgetag"; die vier Listen der
   Tagesübersicht (eröffnet, beendet, Rolls, realisiert je Währung) mit
   Verweisen auf `/positionen/:chainId`; darunter der Baustein für den
   Handelstag (`tag`, Datum). Leere Listen mit Hinweistext.
5. **Neue Ansicht `Kalender.tsx`** unter `/kalender`: Monatsauswahl
   (`<input type="month">`, Standard: aktueller Monat) mit Knöpfen für den
   Vor- und Folgemonat; eine Tabelle der Tage mit Ereignissen (Datum als
   Verweis auf `/tag/:datum`, Anzahlen, realisiertes Netto je Währung). Leerer
   Monat: Hinweistext.
6. **`main.tsx`:** Routen `/kalender` und `/tag/:datum`; im Kopf eine kleine
   Navigation: „Positionen", „Kalender", „Heute" (Verweis auf `/tag/<heutiges
   Datum>`; das Datum der lokalen Zeit des Browsers). Ungültige Adressen
   zeigen wie bisher den Hinweis.
7. **`stil.css`:** das Nötigste im Stil der bestehenden Ansichten.

## Grenzen

- Keine neue Abhängigkeit (`package.json` unverändert), kein Test-Werkzeug.
- Nichts berechnen: keine Summen, keine Prozentwerte, keine Umrechnung. Die
  Tagessummen und Kalenderwerte kommen fertig aus der API; die Währung steht
  immer dabei, nie eine Summe über Währungen.
- Keine Änderung an `api/`, `tests/`, `fixtures/`, `journal/`, `engine/`.
- Jede Geldangabe zeigt die Sicht (Kontosicht), wie in der Positionsliste.

## Abnahme

- `npm run build` im Verzeichnis `ui` läuft fehlerfrei (`tsc --noEmit` und
  Vite).
- `pytest` bleibt grün (insbesondere `tests/test_api_statisch.py`), `ruff
  check .` sauber.
- **Begutachtung im Browser durch das starke Modell vor der Übergabe** und
  danach durch den Nutzer — kein Testersatz (siehe AP-08lv).
