---
titel: Verdichtung der Ansichten (Facelift) - Zuschnitt in AP-08f1 bis AP-08f5
modell: stark
status: offen
abhaengig_von: AP-08l, AP-06e
---

# AP-08f · Verdichtung der Ansichten

**Kein Arbeitspaket, eine Vormerkung.** Sie hält fest, was beim ersten
Augenschein der Oberfläche aufgefallen ist, damit es nicht in einer
Unterhaltung versickert. Geschnitten wird das Paket später, bewusst nach
AP-06 — dann steht fest, welche Kennzahlen mitkommen, und ein Facelift
zweimal zu machen wäre Verschwendung.

## Die Anforderung, in den Worten des Nutzers (22.09.2026)

> „Wir müssen aber noch mehr an effizienter Darstellung feilen. Die
> Übersichtsliste hat z. B. keine Preise. Ich möchte wenig klicken und
> direkt viel Informationen."

Das ist eine Haltung, keine Einzelanforderung: **Informationsdichte vor
Aufgeräumtheit.** Wer den ganzen Tag im Journal arbeitet, will nicht
navigieren, sondern lesen. Jede Information, die erst hinter einem Klick
liegt, ist im Zweifel eine Information, die nicht genutzt wird.

## Was konkret fehlt

**Preise in der Positionsliste.** Heute zeigt sie das Ergebnis, aber nicht,
zu welcher Prämie eröffnet und geschlossen wurde. Genau daran erkennt man
einen Vorgang wieder — und genau daran unterscheidet man einen Roll von
einem Wiedereinstieg (OF-41, die Stichprobe brauchte dieselben Werte).

**Das ist nicht nur Oberfläche.** Die Lese-API liefert die Preise heute
nicht: Sie stecken in den Ausführungen, zwei Ebenen unter der Kette. Die
Nettoprämie je Kontrakt wird bereits an zwei Stellen berechnet —
`werkzeuge/abgleich/golden_ketten_stichprobe.py` und
`journal/durchsicht.py`. Eine dritte Kopie wäre falsch; die Rechnung gehört
dann an eine Stelle und in die API. **Das Paket ist also zweigeteilt:
Felder in AP-07, Darstellung in AP-08.**

## Weitere Kandidaten, gesammelt statt entschieden

Nichts davon ist beschlossen; die Liste ist der Steinbruch für den späteren
Zuschnitt.

- **Struktur statt nur Kette in der Liste.** Strikes, Breite und Verfall
  sind die Merkmale, an denen man eine Position erkennt — sie stehen heute
  nur in der Detailansicht.
- **Zeile aufklappen statt Seite wechseln.** Der Verlauf einer gerollten
  Kette direkt in der Liste, ohne Navigation.
- **Mehr Zeilen je Bildschirm** — engere Zeilen, kleinere Schrift,
  Zahlenspalten mit fester Laufweite, damit Beträge untereinander vergleichbar
  stehen.
- **Spalten wählbar und ihre Wahl in der Adresszeile**, wie Filter und
  Blättern heute schon (AP-08lv, Vertrag 12).
- **Tastatur statt Maus** für Blättern und Öffnen.
- **Farbe sparsam und mit Bedeutung** — etwa Gewinn/Verlust, Erkennungsart
  belegt gegen erschlossen. Nicht dekorativ.

## Was dabei nicht aufgeweicht wird

- **Geld bleibt Zeichenkette** (AP-08lv, Vertrag 8). Mehr Dichte heißt nicht,
  dass gerechnet wird; auch nicht zum Sortieren — sortiert wird in der API.
- **Keine währungsübergreifende Summe**, solange die Umrechnung fehlt.
- **Jede Zahl nennt ihre Sicht** (Plan §5). Mit AP-04s werden es zwei, und
  dichtere Darstellung macht die Verwechslungsgefahr größer, nicht kleiner.
- **Was die Oberfläche rechnen müsste, fehlt der API.** Dichte entsteht
  durch mehr Felder, nicht durch Logik im Browser.

## Offen, vor dem Zuschnitt zu klären

- Kommt das Facelift vor oder nach der Durchsicht der Rollkandidaten? Die
  Durchsicht braucht ohnehin eine eigene Ansicht, und beide teilen sich die
  Frage, wie viel Vergleich nebeneinander passt.
- Braucht es dann doch ein Frontend-Testwerkzeug? Sobald die Oberfläche
  Spaltenwahl, Aufklappen und Tastaturbedienung trägt, ist sie nicht mehr
  dünn — und die Begründung aus AP-08lv, ohne Test auszukommen, fällt weg.
  Dann ist der Vergleich Vitest gegen Playwright fällig.

## Zuschnitt (Nutzer, 10.10.2026: „Fang an")

Erledigt seit der Vormerkung: Preise in der Liste (AP-08fp), sortierbare und
wählbare Spalten (AP-08s), Dashboard mit Equity-Kurve (AP-06e).

| Paket | Inhalt | Wer |
|---|---|---|
| **AP-08f1** | Deutsche Schreibweise für Beträge/Daten/Quoten in allen Ansichten, rot/grün nach Vorzeichen, Rohwert im Tooltip | günstig (Cline) — Helfer stehen bereit |
| **AP-08f2** | Globaler Zeitraum-Wähler (Kopf, Adresse) + `von`/`bis` an den Kennzahlen-Endpunkten | stark |
| **AP-08f3** | Startseite „Übersicht": offene Positionen nach DTE, Ergebnis Woche/Monat/Jahr, Equity-Stand, offene Durchsicht | stark |
| **AP-08f4** | Strategie-Ansicht: Ergebnis, Trefferquote, Kommissionsanteil, Roll-Degradation je OA-Strategie | stark |
| **AP-08f5** | Durchgängige Verknüpfung (Monat → Kalender → Tag → Kette, Strategie → Ketten) | offen |

Die Durchsicht der Kandidaten in der Oberfläche (statt CSV-Rundreise) bleibt
ein eigenes, späteres Paket — sie braucht zuerst gespeicherte Rollkandidaten.

## Entscheidungen zum Zeitraum (Z1–Z4, gelten für alle Folgepakete)

- **Z1 Ein Zeitraum für alles.** Gewählt im Kopf, steht in der Adresse
  (`?von=JJJJ-MM-TT&bis=JJJJ-MM-TT`, beide Enden einschließlich), gilt für
  jede Ansicht, die Zeit kennt. Ohne Angabe: alles. Vorgaben: Diese Woche,
  Dieser Monat, Letzter Monat, Dieses Quartal, Dieses Jahr, Letztes Jahr,
  einzelnes Jahr, Alles, Von–bis.
- **Z2 Ergebnisse zählen am Tag der Schließung** (`geschlossen_am`) — wie die
  Equity-Kurve (AP-06e, E2) und die Steuer (Zuflussprinzip).
- **Z3 Positionslisten zeigen, was im Zeitraum aktiv war:** eröffnet bis
  `bis`, und offen oder beendet ab `von`.
- **Z4 Equity im Zeitraum** beginnt am Zeitraumanfang bei 0; der Drawdown
  zählt nur innerhalb des Zeitraums.

## Darstellung — Entscheidung des Nutzers (10.10.2026)

> „Ich würde gerne eine Visualisierung haben, zB Equity Linie. […] Der
> gefilterte Rest gibt ein Diagramm über P&L oder Ergebnis. Dann noch
> irgendwo Info über Kommissionen, Dividenden, Cash Settlement, Zinsen etc.
> Weiter muss es ein Diagramm geben für Drawdown, Kapitalentwicklung."

Das Prinzip „kein Diagramm" ist damit aufgehoben. Es gilt stattdessen:

- **D1 Eigene SVG-Bausteine, keine Diagramm-Bibliothek.** Linie, Fläche,
  Balken — klein, ohne neue Abhängigkeit, im Stil der Oberfläche.
- **D2 Zahl nur für die Pixellage.** Ein Diagramm darf den Text der API in
  eine Zahl wandeln, um einen Punkt zu platzieren — angezeigt (Achsen,
  Tooltip) wird weiterhin der Text der API über die Formatierer. Gerechnet
  wird im Browser nichts (Vertrag 8 bleibt für alles Angezeigte).
- **D3 Diagramm plus Tabelle.** Die Tabellen bleiben unter dem Diagramm —
  Nachvollziehen geht vor.

## Erweiterter Zuschnitt (10.10.2026)

| Paket | Inhalt | Wer |
|---|---|---|
| **AP-08g1** | Diagramm-Bausteine (Linie, Fläche, Balken) + Dashboard: Equity-Linie, Drawdown-Fläche, Monatsbalken | günstig (Cline), nach AP-08f1 |
| **AP-06f** | Kosten & Erträge: Kommissionen, Dividenden (inkl. Payment in Lieu), Quellensteuer, Zinsen erhalten/gezahlt, Gebühren, Commission Adjustments, Barausgleich — je Monat, in EUR, mit Zeitraum | stark |
| **AP-06g** | Kapitalentwicklung (realisiert): Ein-/Auszahlungen + realisiertes Ergebnis + Cash-Posten, als Tagesreihe | stark |
| **AP-07f** | Filter-Auswertung: `/ketten` mit Zeitbezug (Eröffnung/Schließung), Währung, Strategie; `GET /auswertung` liefert für dieselben Filter Verlauf und Kennzahlen in EUR | stark |
| **AP-08g2** | Positionsliste: alle Filter + Diagramm über das Ergebnis der gefilterten Ketten; Seite „Kosten & Erträge"; Kapital-Diagramm | günstig, nach AP-06f/06g/07f |

**Grenze der Kapitalentwicklung:** Die Datenbank kennt realisierte
Ergebnisse und Cash-Buchungen, aber keinen täglichen Kontowert (NAV) — dafür
fehlen Bewertungen der offenen Positionen (nur 10 Bestands-Stichtage). AP-06g
zeigt deshalb das **realisierte Kapital** und sagt das dazu. Ein echter
NAV-Verlauf braucht eine Erweiterung der Flex-Query (Abschnitt „Net Asset
Value" bzw. „Change in NAV") — Portalarbeit beim Nutzer, dann ein eigenes
Import-Paket.

**Keine Doppelzählung:** Kommissionen und Barausgleich stecken bereits im
realisierten Ergebnis (Tranche I, AP-06x). In „Kosten & Erträge" werden sie
nur *ausgewiesen*; in der Kapitalentwicklung zählen sie nicht ein zweites Mal.
