---
titel: Kontowert-Kurve laut IB und Gewinn laut IB (GET /nav)
modell: stark
status: fertig
abhaengig_von: AP-02n, AP-06f
aendert_tests: ja
---

# AP-06h · Kontowert-Kurve

Vorbereitung und Umsetzung in einem (starkes Modell). Neue Testdateien
`tests/test_nav.py` (4, von Hand gerechnet) und `tests/test_api_nav.py` (3).

## Entscheidungen

- **V1** Kontowert je Tag unverändert aus `flex_nav_tage` (realisiert und
  unrealisiert, Währungen zum Tageskurs, wie IB ihn ausweist) — keine eigene
  Rechnung.
- **V2 Gewinn laut IB** = Kontowert − kumulierte Ein-/Auszahlungen bis
  einschließlich des Tages (Cash-Buchungen der Kategorie `ein_auszahlungen`
  × fxRateToBase). Vergleichsgröße zum realisierten Ergebnis (OF-78).
- **V3 Zeitraum** wie AP-06g K3: absolute Werte, `anfangswert` = Kontowert am
  letzten Tag vor dem Zeitraum.
- Annahme (Regel 10): Eine Einzahlung zählt am Buchungstag bereits in den
  Kontowert dieses Tages.

## Schnittstellen

`analytics/nav.py`: `nav_auswertung(nav_zeilen, cash_zeilen, *, von, bis)`
(rein), `nav_bericht(db_pfad, *, von, bis)`; `api/app.py`: `GET /nav`.

## Echtlauf

1.182 Tage; am 2026-10-09 Kontowert 244.672,85 €, Einzahlungen 219.998,88 €,
Gewinn laut IB +24.673,97 €. Befund zur Abweichung vom Journal: OF-78.
