---
titel: Steuer nach Zufluss je Zahlungsstrom — Umsetzung
modell: guenstig
status: offen
abhaengig_von: AP-10b
aendert_tests: nein
---

# AP-10c · Steuer nach Zufluss — Umsetzung

Maßgeblich ist AP-10b (Regeln R1–R12 und die dort angelegten Tests). Hier steht nur, wie gebaut wird. Ziel: Die
Seite „Steuer“ und der CSV-Export folgen den Regeln des Steuerberaters, **ohne** `analytics/steuer.py` (AP-10,
unveränderliche Tests) anzufassen.

## Konkretisierung

1. **Neues Modul** `analytics/steuer_zufluss.py` — rein (keine DB, keine Uhr, `Decimal`). Eingabe: Legs der
   Kontosicht, Ausführungen mit `dateTime`, `tradeDate`, `settleDateTarget`, `fxRateToBase`, `ereignistyp`,
   Kommission; Instrumente (Klasse, Abwicklungsart, Land); Cash-Buchungen mit `settleDate`, `dividendType`,
   `issuerCountryCode`, `description`. Ausgabe je Formularjahr: Stillhalter-Zufluss, Glattstellungen, Barausgleich,
   Termingeschäfte, Aktienveräußerung (Strike plus Transaktionskosten), Dividenden, anrechenbare/nicht
   anrechenbare Quellensteuer, SO-Kandidaten, Zinsen, nicht abziehbare Posten — je Posten mit Kursquelle und
   Datumsfeld.
2. **Rechengrundlage:** Die Zahlungsströme je Bein entstehen aus Eröffnungs- und Schließungsausführung; jeder
   Strom nimmt Datum und Kurs **seiner** Ausführung. Die vorhandene Zerlegung `leg_seiten` (analytics/kennzahlen)
   wird gelesen, nicht verändert (CLAUDE.md Regel 8: keine zweite, abweichende EUR-Rechnung — Abweichung zur
   Equity ist hier die Methode, nicht ein Fehler, und wird im Abgleich gezeigt).
3. **Hülle** `journal/steuer_zufluss.py`: liest und übergibt; Konfiguration (`ZUFLUSS_DATUM`, Satztabelle je
   Land, KAP-Zeilentabelle je Formularjahr) liegt in **einer** Datei `analytics/steuer_konfig.py`, nicht verteilt.
4. **API:** `GET /steuer-auswertung` liefert die neue Methode (Felder je Jahr wie oben, dazu `methode` mit
   Kursquelle, Datumsfeld, Formularjahr, Status „geprüft/ungeprüft“); `GET /steuer-csv` bekommt das neue Format;
   die alte Methode (Schließungsjahr) bleibt als `/steuer-csv?methode=alt` für den Vergleich.
5. **UI:** Seite `/steuer` zeigt Töpfe getrennt nach den Posten der Regeln (Aktien, Termingeschäfte, Stillhalter,
   Dividenden, Quellensteuer anrechenbar/nicht, **SO-Kandidaten**, Zinsen, nicht abziehbar), je Jahr; Kopfzeile
   nennt Methode, Kursquelle und Datumsfeld. Die Liste „Offene Fragen“ der Seite wird auf den Stand von OF-92
   gebracht (Prämie bei Zuteilung ist entschieden, vorbehaltlich Bestätigung). **Keine Summe „steuerpflichtig“** und
   keine Verrechnung — nur Aufbereitung.
6. **Betroffenheit:** je Jahr die Zahl der Buchungen, die bei Wechsel von `settle` auf `handel` in ein anderes Jahr
   fielen (Regel R1), sichtbar auf der Seite und im CSV.

## Reihenfolge

1. AP-10b (stark): Regeln, Tests, Fixtures, Abgleichsskript. **Danach Abnahme der Regeln durch den Steuerberater.**
2. AP-10c (günstig): 1–4 gegen die Tests, dann 5–6.
3. Abgleich am Echtbestand (stark): neue gegen alte Methode je Jahr; Abweichungen nach Ursache aufgeschlüsselt
   (Zeitpunkt, Kurs, Töpfe); Ergebnis in `OFFENE_FRAGEN.md`.
4. Deploy wie üblich (`Deploy.ps1`), danach Journal-Dienst neu starten.

## Plan (Vorschlag, nicht eigenmächtig)

`plan/trading-journal-projektplan.md`, Abschnitt AP-10, nennt „Jahresabgrenzung nach Zuflussprinzip“. Die jetzige
Umsetzung (Ergebnis im Schließungsjahr) erfüllt das nicht je Zahlungsstrom. **Vorschlag an den Nutzer:** AP-10 als
„erste Fassung“ kennzeichnen und AP-10b/10c/10d als Fortsetzung aufnehmen. Der Plan ist fachliche Wahrheit — Änderung
nur mit Zustimmung.

## Ausdrücklich nicht Teil dieses Pakets

- Ersatzzahlungs-Ursachen, USD-Kontoeffekte, Anfangsbestände (AP-10d).
- Verlustverrechnung, Anlage-KAP-Ausfüllhilfe, Anlage SO ausfüllen.
- Änderung von AP-10-Code und -Tests.
