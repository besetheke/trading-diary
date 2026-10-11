---
titel: Auswertung der Positionen — eine aufsummierte Linie Tag für Tag, Ergebnis je Währung
modell: stark
status: fertig
abhaengig_von: AP-07fu
aendert_tests: nein
---

# AP-07fv · Eine Linie, taggenau aufsummiert; EUR und Positionswährung

Wunsch des Nutzers (11.10.2026), Korrektur von AP-07fu: In der Positionsauswertung
keine Balken, sondern **ein** Diagramm mit der aufsummierten Linie, Tag für Tag.
Das Realisierte im Kopf in EUR **und** in der Positionswährung (z. B. USD).

## Umsetzung

- `analytics/equity.py`: `EquityErgebnis.netto_je_waehrung` (Vorgabe `()`) —
  realisiert netto je Positionswährung, nativ, über dieselbe Auswahl wie die
  EUR-Werte: Strukturen mit `structures.netto_pnl`, lose Legs mit
  `brutto_pnl + kommission_gesamt` unter der Währung der schließenden Ausführung.
- `GET /auswertung` zusätzlich:
  - `verlauf`: jeder Kalendertag vom ersten bis zum letzten Schließungstag mit
    dem aufsummierten EUR-Stand (Tage ohne Schließung tragen den Vortageswert);
  - `netto_je_waehrung` (oberste Ebene — `ergebnis` bleibt unverändert, weil
    `tests/test_api_filter.py` es vollständig vergleicht);
  - `unrealisiert.mit_realisiert_eur`: Realisiert + Unrealisiert, Endpunkt der
    gestrichelten Linie (das Frontend rechnet kein Geld, Vertrag 8).
  Tests `tests/test_api_auswertung_verlauf.py` (5, von Hand gerechnet).
- Oberfläche: `FilterAuswertung` zeigt nur noch `ZweiLinien` — kräftige Linie
  realisiert aufsummiert, gestrichelte Verlängerung vom letzten Punkt bis zum
  Bestandsstichtag um das Unrealisierte. Im Kopf „in Positionswährung: …" je
  Währung (nicht umgerechnet). `ZweiLinien` hat dafür die Eigenschaft
  `gestrichelt`. Die Tages-, Wochen- und Monatsbalken der Positionsauswertung
  entfallen (die Wochenwerte der API bleiben, das Dashboard nutzt eigene).

## Abgleich (Echtdaten, 11.10.2026)

- CAR: 5.501,95 € · 6.464,41 USD — USD gleich IB (`fifoPnlRealized`).
- WDC: 15.289,17 € · 11.219,64 USD. Der Unterschied ist kein Fehler: die
  Strukturen allein 24.700,89 € gegen 26.723,41 USD (Kurs ≈ 0,92); fünf lose
  Aktien-Legs aus Zuteilungen −15.503,77 USD, aber nur −9.411,73 € — Kauf und
  Verkauf je zu ihrem Tageskurs (Währungsmethode des Journals, vgl. OF-78).

## Grenzen

- Strukturen ohne Wechselkurs fehlen in der EUR-Summe (gezählt), stehen aber in
  der Summe je Währung — die Fußnote „ohne Wechselkurs" nennt ihre Zahl.
