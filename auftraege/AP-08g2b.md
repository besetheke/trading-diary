---
titel: Filterleiste der Positionsliste und Auswertung der gefilterten Positionen
modell: stark
status: fertig
abhaengig_von: AP-07f, AP-07fw, AP-08z, AP-08g1
aendert_tests: nein
---

# AP-08g2b · Positionsfilter in der Oberfläche

Teil des Facelifts (`auftraege/AP-08f.md`). Umsetzung durch das starke Modell
(Cline war im Creditlimit). Reine Oberfläche, Backend aus AP-07f/AP-07fw.

## Was die Positionsliste jetzt kann

- **Filterleiste:** Basiswert (Freitext mit Vorschlägen), Anlageklasse,
  Währung, Strategie, Seite, Endzustand (Auswahllisten aus
  `GET /filterwerte`, mit Rückfallwerten, falls die API nicht antwortet),
  Eröffnet von/bis, Geschlossen von/bis, Rolls von/bis. Alle Filter stehen in
  der Adresse unter den Namen der API (Lesezeichen, Neuladen); „Zurücksetzen"
  räumt nur diese, der globale Zeitraum bleibt.
- **Auswertung der Auswahl** über der Tabelle (`ui/src/FilterAuswertung.tsx`,
  `GET /auswertung`): Positionen in der Auswahl, abgeschlossene Strukturen,
  Ergebnis netto, maximaler Drawdown, Stand am letzten Tag; Equity-Kurve und
  Monatsbalken; Hinweis, wenn lose Aktiengeschäfte nicht mitzählen (Strategie,
  Seite, Endzustand, Rolls) oder fehlende Kurse.
- Die Liste und die Auswertung laden bei Filter- und Zeitraumänderung neu;
  Blättern und Sortieren laden nur die Liste.

## Entscheidungen

- **Zeitraum:** Die Liste zeigt „aktiv im Zeitraum" (Z3), die Auswertung zählt
  am Schließungstag (Z2). Die Fußnote der Auswertung sagt das.
- **Ganze Positionen:** Die Filter wählen Ketten; von einer gewählten Kette
  zählen alle Strukturen, auch früher geschlossene Rolls. Die Kurve kann daher
  vor einem „Geschlossen von" beginnen — ebenfalls in der Fußnote.
- Nichts wird im Browser gerechnet: Beträge sind API-Text, `Number()` nur für
  Pixel (D2).

## Dateien

`ui/src/api.ts` (gemeinsame `KettenFilter`, `holeFilterwerte`, `holeAuswertung`,
Lose-Leg-Felder der Equity-Typen), `ui/src/Positionen.tsx`,
`ui/src/FilterAuswertung.tsx`, `ui/src/stil.css`, `ui/vite.config.ts`
(Proxy `/auswertung`, `/filterwerte`).

## Nachweis

`tsc --noEmit` und `npm run build` fehlerfrei, `ruff check .` sauber,
Gesamtsuite grün. Sichtprüfung mit einem Browser gegen die echte Datenbank
(Chrome headless): ohne Filter, `waehrung=USD&geschlossen_ab=2025-01-01`,
`strategie=SPX: FKK10`. Werte gegen die API: ohne Filter 102.334,80 €, 2025
26.620,98 €, Strategie SPX: FKK10 −1.302,72 € bei 116 Positionen.

## Beobachtung (nicht Teil dieses Pakets)

`GET /auswertung` braucht rund 2,3 s je Aufruf (wie `/equity`): jeder Aufruf
liest alle Ausführungen und rechnet die Kennzahlen neu. Reicht für den
Einzelnutzer; bei häufigem Filtern wäre ein Zwischenspeicher der
Kennzahlen je Rebuild-Stand ein eigenes Paket.
