---
titel: Formatspezifikation Option-Omega-Backtest-Export
modell: -
status: referenz
---

# Anhang · Format des Option-Omega-Backtest-Exports

Grundlage für die synthetischen Fixtures in AP-12. Abgeleitet aus einem
Beispielexport mit 60 Zeilen (Nutzer, 10.10.2026). Dieses Dokument enthält
**keine Kontodaten** — nur Struktur, Spaltenbedeutung und Grammatik; Zahlen
in den Beispielen sind frei erfunden.

**Stichprobengröße (Warnung):** Nur 60 Zeilen gesehen, gegenüber 244 Trades
bei der OA-Formatspezifikation. Als Annahme markierte Punkte unten sind
entsprechend weniger abgesichert und gehören vor der Abnahme in
`OFFENE_FRAGEN.md`.

## Datei

- **CSV**, eine Kopfzeile, jedes Feld in doppelten Anführungszeichen —
  auch Zahlenfelder (`"7816.47"`), nicht nur Text.
- 28 Spalten in fester Reihenfolge, komma-getrennt.
- Eine Zeile = ein Trade (= eine Backtest-Position mit allen Legs ihrer
  Eröffnung), nicht eine Ausführung.

## Spalten in Reihenfolge

| # | Spalte | Typ | Format / Beispiel | Hinweis |
|---|---|---|---|---|
| 0 | Date Opened | Text | `JJJJ-MM-TT` | |
| 1 | Time Opened | Text | `HH:MM:SS` | |
| 2 | Opening Price | Zahl | Dezimalpunkt | Underlying-Preis bei Eröffnung |
| 3 | Legs | Text | Leg-Grammatik, siehe unten | beschreibt die **Eröffnung**, nicht den aktuellen Stand |
| 4 | Premium | Zahl | Dezimalpunkt, Vorzeichen | negativ = Debit gezahlt, positiv = Credit erhalten (Annahme, aus Vorzeichen-Konsistenz mit P/L abgeleitet) |
| 5 | Closing Price | Zahl | Dezimalpunkt | Underlying-Preis bei Schließung |
| 6 | Date Closed | Text | `JJJJ-MM-TT` | |
| 7 | Time Closed | Text | `HH:MM:SS` | |
| 8 | Days in Trade | Ganzzahl | `0`, `1`, `5`, … | Kalendertage zwischen Open/Close (Annahme) |
| 9 | Avg. Closing Cost | Zahl | Dezimalpunkt, Vorzeichen | |
| 10 | Reason For Close | Aufzählung | siehe unten | nicht erschöpfend beobachtet |
| 11 | P/L | Zahl | Dezimalpunkt, Vorzeichen | Ergebnis in Geld |
| 12 | P/L % | Zahl | Dezimalpunkt, Vorzeichen | kann extreme Werte annehmen (beobachtet: −2000+ bei kleinem Einsatz) |
| 13 | No. of Contracts | Ganzzahl | | |
| 14 | Funds at Close | Zahl | Dezimalpunkt | laufender Kontostand der Simulation, kein Bezug zum echten Konto |
| 15 | Margin Req. | Zahl | Dezimalpunkt | |
| 16 | Underlying | Text | Ticker, z. B. `SPX`, `SPY`, `IWM` | |
| 17 | Strategy | Text | freie Strategiekennung | **Verknüpfungsschlüssel zu Journal/OptionApp (§1.3)**; beobachtete Form ähnlich der OA-Kennungen (z. B. `SPX: IC +Vo/n`-artig), aber hier mit Zusatztext/Uhrzeiten durchsetzt — keine 1:1-Normalform beobachtet |
| 18 | Opening Commissions + Fees | Zahl | Dezimalpunkt | Backtest **simuliert** Kommission — kein pauschaler Nullwert |
| 19 | Closing Commissions + Fees | Zahl | Dezimalpunkt | oft `0`, wenn die Position zum Verfall lief (keine Schließ-Order) |
| 20 | Opening Short/Long Ratio | Zahl | Dezimalpunkt | Bedeutung nicht abschließend geklärt (Annahme: Verhältnis Short- zu Long-Prämie) |
| 21 | Closing Short/Long Ratio | Zahl | Dezimalpunkt | wie oben |
| 22 | Opening VIX | Zahl | Dezimalpunkt | |
| 23 | Closing VIX | Zahl | Dezimalpunkt | |
| 24 | Gap | Zahl | Dezimalpunkt, Vorzeichen | vermutlich Overnight-Gap in Punkten (Annahme) |
| 25 | Movement | Zahl | Dezimalpunkt, Vorzeichen | vermutlich Tagesbewegung in Punkten (Annahme) |
| 26 | Max Profit | Zahl | Dezimalpunkt | |
| 27 | Max Loss | Zahl | Dezimalpunkt, meist ≤ 0 | |

## Leg-Grammatik der Spalte `Legs`

Legs getrennt durch ` | ` (Leerzeichen-Pipe-Leerzeichen). Je Leg:

```
<Menge> <Monat> <Tag> <Strike> <C|P> <STO|BTO> <Preis>
```

Beispiel (erfundene Zahlen): `1 Nov 21 4500 P STO 12.50 | 1 Nov 21 4400 P BTO 4.75`

- `Menge`: Ganzzahl, immer positiv — Richtung steckt in `STO`/`BTO`, nicht im
  Vorzeichen (anders als bei OptionApp).
- `Monat`: englische Drei-Buchstaben-Abkürzung (`Oct`, `Nov`, …), **ohne
  Jahr** — das Jahr muss aus `Date Opened`/`Date Closed` erschlossen werden
  (Annahme: nächstliegendes Jahr, Jahreswechsel am Dezember/Januar-Übergang
  gesondert behandeln).
- `Tag`: Tag des Monats ohne führende Null.
- `Strike`: Dezimalzahl (nur Ganzzahlen beobachtet, Dezimalstrikes nicht
  ausgeschlossen).
- `C`/`P`: Call/Put.
- `STO`/`BTO`: **nur Eröffnungsaktionen beobachtet** — die Spalte
  beschreibt ausschließlich die Eröffnungsstruktur, nicht Änderungen über
  die Laufzeit (kein Beleg für `BTC`/`STC` in den 60 Zeilen). Ob gerollte
  Trades andere Aktionskürzel oder mehrere Legs mit derselben Richtung
  zeigen, ist **ungeklärt**.
- Jede Zeile kann 2 bis mindestens 4 Legs haben (Vertical, Iron Condor,
  Butterfly beobachtet); keine Obergrenze belegt.

## `Reason For Close` — beobachtete Werte (nicht erschöpfend)

`Backtest Completed`, `Expired`, `Exited at Specified Time`, `Below Delta`,
`Above Delta`, `VIX Move Down`, `Stop Loss`. Weitere Werte (z. B. für
manuelle Eingriffe oder Zuteilung) sind in der Stichprobe nicht aufgetreten.

## Mehrdeutigkeiten / offene Punkte (vor der Abnahme zu klären)

1. Mehrere Zeilen können `Date Opened`+`Time Opened`+`Opening Price`
   identisch tragen (verschiedene Strategien, gleicher Scan-Zeitpunkt) —
   eindeutiger Schlüssel ist mindestens `(Date Opened, Time Opened,
   Strategy)`, vermutlich zusammen mit `Legs`.
2. Vorzeichenkonvention von `Premium`/`P/L`/`Avg. Closing Cost` nur aus dem
   Zusammenspiel der Beispielzeilen erschlossen, nicht dokumentiert belegt.
3. `Opening/Closing Short/Long Ratio` — Bedeutung geraten, nicht bestätigt.
4. Zeitzone von `Time Opened`/`Time Closed` unbekannt (vermutlich US-Ostküste
   wie die Handelszeiten, analog Flex/OA — Annahme, nicht geprüft).
