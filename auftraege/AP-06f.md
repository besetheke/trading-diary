---
titel: Kosten & Erträge (Kommissionen, Gebühren, Zinsen, Dividenden, Quellensteuer, Barausgleich, Ein-/Auszahlungen)
modell: stark
status: fertig
abhaengig_von: AP-06x, AP-08f2
aendert_tests: ja
---

# AP-06f · Kosten & Erträge

Teil des erweiterten Facelift-Zuschnitts (`auftraege/AP-08f.md`).
Vorbereitung und Umsetzung in einem (starkes Modell). Neue Testdateien
`tests/test_cashflows.py` (6, von Hand gerechnet) und
`tests/test_api_cashflows.py` (3).

## Entscheidungen

- **C1 Kategorien** in fester Reihenfolge: `kommissionen`,
  `kommissionsanpassungen`, `gebuehren`, `zinsen_erhalten`, `zinsen_gezahlt`,
  `dividenden` (Dividends + Payment In Lieu Of Dividends), `quellensteuer`,
  `barausgleich`, `sonstige`, `ein_auszahlungen`. Jede erscheint, auch ohne
  Buchung. Unbekannte Flex-Typen → `sonstige`, nie verworfen.
- **C2 EUR ohne zweite Rechnung.** Kommission × `buchungskurs` der Ausführung
  (wie Tranche I); Barausgleich über `bewerte_barausgleich` (AP-06x):
  Seitenvorzeichen × schlusskurs × |menge| × multiplikator × buchungskurs;
  Cash-Buchungen `betrag × fxRateToBase` aus dem Flex-Rohsatz. Fehlt ein Kurs:
  nur `anzahl_kurs_fehlt`, kein Ersatzkurs.
- **C3 Keine Doppelzählung.** Kommissionen und Barausgleich stecken im
  realisierten Ergebnis — `im_ergebnis_enthalten = true`; sie werden hier
  ausgewiesen, nicht hinzugerechnet.
- **C4 Zeitraum** nach Buchungs- bzw. Ausführungsdatum, beide Enden
  einschließlich; `von > bis` → Fehler (API 422).

## Schnittstellen

- `analytics/cashflows.py`: `cashflow_auswertung(ausfuehrungs_zeilen,
  instrumenten_zeilen, cash_zeilen, *, von=None, bis=None)` (rein),
  `cashflow_bericht(db_pfad, *, von=None, bis=None)` (liest nur),
  `KATEGORIEN`, Datenklassen `CashflowKategorie`, `CashflowMonat`,
  `CashflowErgebnis`.
- `api/app.py`: `GET /cashflows?von=&bis=`.

## Echtlauf (10.10.2026, nur Summen)

Alle 1.325 Cash-Buchungen und alle Ausführungen mit Kurs; `sonstige` leer.
Laufzeit unter einer halben Sekunde.

## Offen

Die Oberfläche dafür (Seite „Kosten & Erträge") ist Teil von AP-08g2.
