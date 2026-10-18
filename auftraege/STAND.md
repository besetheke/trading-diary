# Projektstand 18.10.2026

Zusammenfassung zum Wiedereinstieg. Maßgeblich bleibt `plan/trading-journal-projektplan.md`; Offenes steht in
`OFFENE_FRAGEN.md`, Aufgaben in `auftraege/`.

## Journal (trading-diary), 964 Tests grün
- **Daten:** Flex-Import (Konto seit 01.04.2022, Stand 16.10.2026), OptionApp, Option Omega; Nachtlauf (NOX: Aufgabe 05:30 aktiv).
- **Ableitung:** Matching, Strukturen, Ketten, Rolls, Zuteilungen, Kampagnen, Overrides.
- **Auswertungen:** Equity, NAV, Kosten und Erträge, Positionen (Ketten, Schritte, Aktien im Depot, Dichte, einklappbare Filter,
  Kettenverlauf als Liste), Titel (Dividenden, Originalwährung, ohne Kommission, Teil-realisiert), Strategien, OA-Abgleich, Backtests.
- **Steuer:** Zufluss je Zahlungsstrom, Quellenhierarchie mit Markern, Anlage SO, KAP in zwei Varianten, Überleitung zu IB, Listen für
  den Berater. 2025 „nicht deklarationsfähig“ allein wegen 43 ETF-Beinen.
- **Station:** Roller-Cockpit (Freigabe, Automatik, Verlauf), Momentum-Schalter, System.

## Roller (options-roller), 363 Tests grün
Strategien (SPX/RUT/DAX, Tagesprogramm 0DTE), Rollregel, Early Exit, Automatik mit Leitplanken, IB-Preisschutz (202/2161/201),
Kostenbremse, gruppiertes Fehlerprotokoll, Auswertung des Ereignisprotokolls. Nur Paper (Port 7497).

## Offen, nach Abhängigkeit
1. **Server:** Deploy des Roller-Stands `cc55049` und der Journal-Änderungen (Checkliste: `werkzeuge/server/`); danach Läufe auswerten
   (`python -m roller.auswertung`), dabei OF-90 prüfen (Startanteil 0,25, Kostenbremse 40/60 %). Mail-Passwort/Empfänger auf dem Server.
2. **Roller:** SPX-0DTE bleibt bei IB `PreSubmitted` (Ursache offen); Wiedereinstieg wartet auf Entscheidungen des Nutzers.
3. **Review-Befunde:** AP-17 (A schnelle Fixes erledigt; offen: B BCS-Typisierung, C Befehlsabsicherung, D Notizen, E Depot/Konten, F, G Ausbau).
4. **Steuer (pausiert):** ETF/ETN/ETP, Entlastung der 70,17 EUR PIL-Steuer, Abziehbarkeit der 187,06 EUR Kompensation, KAP 2026, USD-
   Sollsaldo (Rekonstruktion bis 2022 exakt, danach fehlen EUR.SEK u. a.), Kursquelle IB/EZB.
5. **Nicht anfassen:** `momentum-lab` (unversionierte Änderungen).
