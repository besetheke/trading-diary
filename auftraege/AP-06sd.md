---
titel: Scorecard mit Roll-Schritten und „bisher realisiert“ bei offenen Ketten
modell: stark
status: fertig
abhaengig_von: AP-06sc, AP-04z
aendert_tests: nein
---

# AP-06sd · Roll-Schritte sichtbar machen

Anlass (12.10.2026, Fall DAX: BPS noExit): Eine Kette, die ihre Verluste durch
Rollen offen hält, zeigt 100 % Treffer und Drawdown 0 — die realisierten
Roll-Verluste erscheinen erst, wenn sie endet. Nutzerwunsch: das sichtbar
machen und die Rollvorgänge einzeln zählen können, um sie mit OA zu vergleichen.

## Vertrag

1. `GET /ketten`: offene Ketten tragen `realisiert_bisher` — Summe der Ergebnisse
   ihrer geschlossenen Glieder in der Kettenwährung (nur bei einer Währung und
   mindestens einem Ergebnis). `struktur_summe_netto` bleibt leer (Entscheidung 4).
2. Scorecard-Zeile bekommt `bisher_offene_eur` (realisierte Teile offener
   Positionen) und `max_drawdown_schritte_eur` (Drawdown über alle realisierten
   Schritte der Strategie in Reihenfolge der Schließung).
3. `GET /strategien?ansicht=schritte`: jedes Kettenglied ist eine eigene Position
   (Strategie und Zuteilung erbt es von seiner Kette); ein offenes Glied zählt
   nur als offen. `ansicht=positionen` ist der bisherige Stand.
4. UI: Positionsliste zeigt „… bisher“, Scorecard Umschalter „Ketten / Schritte
   einzeln (wie OA)“ und die zwei Spalten.

Nicht Teil: unrealisierte Ergebnisse in der Scorecard; die OA-Sicht je Trade
(OF-82 Punkt 2).

Tests: `tests/test_strategien_schritte.py`, `tests/test_api_strategien_schritte.py`,
`tests/test_api_ketten_bisher.py`.

## Nachtrag AP-06se (12.10.2026)

`GET /ketten?ansicht=schritte`: eine Zeile je Kettenglied (Filter wirken auf die
Kette, Glieder stehen beieinander; `schritt`/`schritte_gesamt`; Ergebnis,
Zeiten, Preise und Menge des Glieds; Endzustand und Unrealisiert nur am letzten
Glied). Positionsliste: Umschalter wie in der Scorecard, in der Adresse
(`ansicht=schritte`); die Scorecard-Links geben die Ansicht weiter. Die
Auswertung oben auf der Seite bleibt die der Ketten.
Test: `tests/test_api_ketten_schritte.py`.

## Nachtrag AP-06sf (12.10.2026)

Prämienwert offener Positionen: `GET /ketten` trägt `praemie_offen_eur` (Prämie
der offenen Legs bei Eröffnung, ohne Kommission; auch ohne Bestand laut IB
bekannt, sofern ein Buchungskurs da ist) und `praemie_aktuell_eur` (−IBs
Marktwert der bewerteten Legs); EUR, Verkäufersicht, Credit positiv. Probe:
offen − aktuell − Kommission = Unrealisiert. Positionsliste: zwei neue Spalten
(„Prämie offen³“, „Prämie aktuell³“), in der Schrittansicht am offenen Glied.
Test: `tests/test_api_ketten_praemie.py`.
