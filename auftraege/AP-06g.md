---
titel: Kapitalentwicklung, realisiert (Einzahlungen + Ergebnis + Cash-Posten)
modell: stark
status: fertig
abhaengig_von: AP-06e, AP-06f
aendert_tests: ja
---

# AP-06g · Kapitalentwicklung (realisiert)

Teil des erweiterten Facelift-Zuschnitts (`auftraege/AP-08f.md`).
Vorbereitung und Umsetzung in einem (starkes Modell). Neue Testdateien
`tests/test_kapital.py` (4, von Hand gerechnet) und `tests/test_api_kapital.py`
(3).

## Entscheidungen

- **K1 Kapital = Ein-/Auszahlungen + realisiertes Ergebnis + Cash-Posten**
  (Dividenden, Quellensteuer, Zinsen, Gebühren, Kommissionsanpassungen,
  Sonstiges). Ergebnis aus der Equity-Kurve (AP-06e); Kommissionen und
  Barausgleich stecken darin und zählen nicht doppelt (AP-06f, C3).
- **K2 Realisiert, nicht NAV.** Unrealisierte Ergebnisse offener Positionen
  fehlen — kein täglicher Kontowert in der Datenbank. Ein echter NAV-Verlauf
  braucht eine Erweiterung der Flex-Query (siehe AP-08f).
- **K3 Zeitraum zeigt den Bestand.** Kapital ist ein Bestand: Die Tagesreihe
  trägt absolute, seit Beginn kumulierte Werte; `anfangskapital` ist der
  Stand vor dem Zeitraum, die Veränderung im Zeitraum ist nach Einzahlungen,
  Ergebnis und Cash aufgeteilt (Anfang + Teile = Ende).

## Schnittstellen

- `analytics/kapital.py`: `kapital_auswertung(equity_tage, cash_zeilen, *,
  von=None, bis=None)` (rein; `equity_tage` über die ganze Historie),
  `kapital_bericht(db_pfad, *, von=None, bis=None)`.
- `analytics/cashflows.py`: `cash_zeilen_lesen(verbindung)` — eine Lesestelle
  für AP-06f und AP-06g.
- `api/app.py`: `GET /kapital?von=&bis=`.

## Echtlauf (10.10.2026)

Gesamt und 2025: Ergebnis identisch mit der Equity-Kurve, Cash-Summe
identisch mit „Kosten & Erträge", Probe Anfang + Teile = Ende erfüllt.
