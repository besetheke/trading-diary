---
titel: Globaler Zeitraum wirkt auf der Positionsliste
modell: guenstig
status: fertig
abhaengig_von: AP-08f2, AP-07f
aendert_tests: nein
---

# AP-08z · Zeitraum auf der Positionsliste

Teil des Facelifts (`auftraege/AP-08f.md`, Z1 und Z3). Der Zeitraum-Wähler im
Kopf (AP-08f2) wirkt bisher nur auf `/dashboard` und `/kosten`. Er soll auch
die Positionsliste (`/`) steuern. Das Backend ist fertig (AP-07f):
`GET /ketten?von=…&bis=…` liefert nach **Z3** die Ketten, die im Zeitraum
**aktiv** waren (eröffnet bis `bis` und offen oder beendet ab `von`, beide
Enden einschließlich).

Reine Oberfläche, **klein halten**. Kein Testlauf der Gesamtsuite nötig
(siehe Abnahme).

## Was zu tun ist

1. **`ui/src/api.ts`:** `KettenAbfrage` um `von?: string | null` und
   `bis?: string | null` erweitern; `holeKetten` setzt sie nur, wenn
   gesetzt (`zusaetze.set('von', …)`). **Sonst nichts** an `api.ts` ändern
   (die übrigen Filter kommen mit AP-08g2b).
2. **`ui/src/main.tsx`:** `'/'` in `ZEITRAUM_SEITEN` aufnehmen, damit der
   Wähler dort wirkt (nicht nur angezeigt wird).
3. **`ui/src/Positionen.tsx`:**
   - Den Zeitraum aus der Adresse lesen (`useZeitraum()` aus `zeitraum.ts`,
     wie `Dashboard.tsx`) und an `holeKetten({ …, von, bis })` übergeben;
     Neuladen, wenn er sich ändert; Blätterstand (`offset`) dann auf 0.
   - **Die Adressparameter `von`/`bis` dürfen beim Anwenden, Zurücksetzen,
     Blättern, Sortieren, Seitengröße und Spaltenwahl nicht verloren gehen.**
     `Positionen.tsx` baut dafür teils neue `URLSearchParams` auf
     (`anwenden`, `zuruecksetzen`): dort `von`/`bis` aus der aktuellen Adresse
     übernehmen. „Zurücksetzen" setzt nur die Filter der Liste zurück, nicht
     den globalen Zeitraum.
   - Über der Tabelle eine Zeile mit dem Zeitraum, wenn einer gewählt ist:
     „Aktiv im Zeitraum: 01.01.2025 – 31.12.2025 (eröffnet bis zum Ende und
     offen oder beendet ab dem Anfang)" mit `datumDe`. Ohne Zeitraum keine
     Zeile.
   - Der Leer-Zustand sagt bei gewähltem Zeitraum: „Keine Positionen in
     diesem Zeitraum aktiv."
4. Die Spalte „Eröffnung" bleibt, wie sie ist; keine neuen Spalten.

## Grenzen

- Nichts rechnen, keine Zeitraumlogik im Browser — gefiltert wird im
  Backend. Keine Änderung an `python`, `tests/`, `fixtures/`,
  `zeitraum.ts`, `Zeitraumwahl.tsx`, `vite.config.ts` (`/ketten` ist dort
  schon durchgeleitet).
- Keine weiteren Filterfelder (Währung, Strategie, Schließung): das ist
  AP-08g2b.

## Abnahme

Kein `pytest` (nur UI): `npx tsc --noEmit` im Ordner `ui`, `npm run build`
im Ordner `ui` (der Klon liegt auf C:, es geht), `ruff check .`,
`git diff --stat` nur unter `ui/` und dieses Auftragsdokument (Status auf
`fertig`). Sichtprüfung: „Alles" zeigt wie vorher; „Letztes Jahr" verkürzt die
Liste, `von`/`bis` bleiben nach „Anwenden", „Zurücksetzen" und Blättern in der
Adresse. Vor Beginn und vor dem Commit `git pull --ff-only`. Melde danach nur
„gepusht, Commit-Nummer".
