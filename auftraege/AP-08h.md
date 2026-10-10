---
titel: Kontowert laut IB im Dashboard (Kurve, Gewinn laut IB, Bestandteile)
modell: guenstig
status: fertig
abhaengig_von: AP-08g1, AP-06h
aendert_tests: nein
---

# AP-08h · Kontowert laut IB in der Oberfläche

Teil des Facelifts (`auftraege/AP-08f.md`, D1–D3). Reine Oberfläche; die
Daten liefert `GET /nav` (AP-06h) mit Zeitraum. Typ und Abruf stehen in
`ui/src/api.ts` bereit (`Nav`, `NavTag`, `holeNav`), der Vite-Proxy `/nav`
ebenso.

**Erst nach AP-08g1** — nutzt dessen Diagramm-Bausteine. Reihenfolge bei
Cline: AP-06i → AP-08f1 → AP-08g1 → AP-08h → AP-08g2 (oder g2 vor h, beide
berühren das Dashboard — nicht parallel).

## Was gezeigt wird

Der Nutzer will **beides**: realisiert (Journal) und realisiert +
unrealisiert (Kontowert laut IB). Der Kontowert ist IBs eigene Zahl, keine
Rechnung des Journals.

1. **Abschnitt „Kontowert laut IB"** im Dashboard unter der Equity-Kurve.
2. **Kopf (`dl.kopf`)**: Kontowert am Ende (`endwert`), am Anfang
   (`anfangswert`, nur im Zeitraum, sonst ausblenden), **Gewinn laut IB** =
   `gewinn` des letzten Tages, Einzahlungen kumuliert des letzten Tages.
   Alles über `<Betrag>`, nichts addiert (Vertrag 8).
3. **Diagramm:** zwei Linien über `tage[]`:
   - `gesamt` (Kontowert) und `einzahlungen_kumuliert` (Treppe), Fläche
     dazwischen eingefärbt (`.positiv`/`.negativ` nach Vorzeichen von
     `gewinn`). Achsen, Raster, Tooltip wie AP-08g1.
4. **Umschalter „Gewinn laut IB"**: zeigt statt der beiden Linien die Linie
   `gewinn` (Nulllinie sichtbar). Dazu als zweite, dünnere Linie die
   **kumulierte realisierte Equity** (aus der bereits geladenen
   `holeEquity`-Antwort, `kumuliert_eur`) — so wird der Abstand zwischen
   realisiert und Kontowert sichtbar. Legende: „Gewinn laut IB (realisiert +
   unrealisiert)" und „realisiert laut Journal". Hinweis darunter: „Seit
   AP-06i enthält die Journal-Linie auch Aktien ohne Struktur; der verbleibende
   Abstand ist im Wesentlichen unrealisiert und Andienungsmethode (OF-78)."
   Im Zeitraum beginnt die Equity bei 0, der Gewinn laut IB nicht — dann
   den Umschalter-Text „im Zeitraum nicht vergleichbar" zeigen und nur
   `gewinn` zeichnen (keine Umrechnung im Browser).
5. **Bestandteile** am letzten Tag: kleine Tabelle Cash, Aktien, Optionen,
   Rohstoffe (Feld `null` → Zeile weglassen), Beträge über `<Betrag>`.
6. `anzahl_kurs_fehlt > 0` als Hinweis („n Einzahlungen ohne Kurs").
7. Leer-Zustand (keine `tage`): „Noch kein Kontowert importiert — die
   Flex-Query braucht den Abschnitt NAV (Net Asset Value) in Base."

## Grenzen

- Nichts rechnen außer Pixelkoordinaten (D2); Geld bleibt Text.
- Keine Änderung an `api/`, Python, `tests/`, `fixtures/`, `api.ts`,
  `zeitraum.ts`, `Zeitraumwahl.tsx`, `vite.config.ts`.

## Abnahme

`npm run build` fehlerfrei, Gesamtsuite grün, `ruff check .` sauber,
`git diff --stat` nur unter `ui/` und dieses Auftragsdokument. Sichtprüfung
mit „Alles" und „2025": Endwert und Gewinn stimmen mit `GET /nav` überein.
Vor Beginn und vor dem Commit `git pull --ff-only`.
