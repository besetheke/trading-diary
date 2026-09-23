---
titel: Verdichtung der Ansichten (Facelift) - vorgemerkt, noch kein Auftrag
modell: stark
status: vorgemerkt
abhaengig_von: AP-08l
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
