---
titel: Steuer nach Zufluss je Zahlungsstrom — Umsetzung
modell: guenstig
status: fertig
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
   Termingeschäfte, Aktienanschaffung/-veräußerung (Strike, Erwerbs- und Veräußerungskosten getrennt, R5/R6), Dividenden, anrechenbare/nicht
   anrechenbare Quellensteuer, SO-Kandidaten, Zinsen, nicht abziehbare Posten — je Posten mit Kursquelle und
   Datumsfeld.
2. **Rechengrundlage:** Die Zahlungsströme je Bein entstehen aus Eröffnungs- und Schließungsausführung; jeder
   Strom nimmt Datum und Kurs **seiner** Ausführung (Regeltabelle je Vorgangsart, AP-10b R7). **`leg_seiten` ist
   nicht die Grundlage** (AP-10b R14): sie liefert bei fehlendem Kurs `None` für die ganze Leg-Liste, eine bekannte
   Eröffnungsprämie würde verschwinden. Eigene Zerlegung `zahlungsstroeme(...)`, ein Eintrag je Strom, jede
   Eröffnungsprämie und Kommission genau einmal; offene Beine, Teilglattstellungen, Restmengen und Rolls gehören
   dazu. Die Abweichung zur Equity ist die Methode, nicht ein Fehler, und wird im Abgleich gezeigt.
   Ausübung gekaufter Optionen mit Lieferung (R5) und Instrumentklassifikation ETF/ETN/ETP (R13, `subCategory` aus
   dem Rohsatz der Ausführung, keine Schemaänderung) gehören in diese Rechnung.
   `cashflows.py` bleibt unverändert (unveränderliche Tests): Dividenden und Ersatzzahlungen werden hier **eigens**
   getrennt (`dividendType`, Beschreibung, Typ „Payment In Lieu“), und der Kursmangel der Cash-Buchungen
   (`anzahl_kurs_fehlt`) wird bis in die API **durchgereicht**, nicht verworfen.
3. **Hülle** `journal/steuer_zufluss.py`: liest und übergibt; Konfiguration (Regeltabelle Steuerdatum/FX-Datum je
   Vorgangsart statt globalem Schalter, Satztabelle je Land, KAP-Zeilentabelle je Formularjahr) liegt in **einer**
   Datei `analytics/steuer_konfig.py`. Kursbeschaffung hinter der Schnittstelle `Kursquelle` (IB-Kurs je
   Ausführung zuerst; EZB später ohne Umbau). Eingang für **Anfangsbestände** und **Verlustvorträge** (R16), leer
   erlaubt, mit Warnung.
4. **API:** `GET /steuer-auswertung` liefert die neue Methode: je Jahr Gewinne und Verluste **getrennt** je Topf,
   Quellensteuer in drei Zuständen, `datenluecken` und `regeln_offen` getrennt, dazu `methode` (Kursquelle,
   Datumsregeln, Formularjahr, Prüfstatus, Warnungen). `GET /steuer-csv` bekommt das neue Format; die alte Methode
   bleibt als `/steuer-csv?methode=alt` mit Kennzeichnung ALTVERFAHREN. Der CLI-Export `journal steuer` wird
   umgestellt oder gekennzeichnet (AP-10b). Der bisherige API-Test `test_api_steuer.py` wird in AP-10b ersetzt.
5. **UI:** Seite `/steuer` zeigt Töpfe getrennt nach den Posten der Regeln (Aktien, Termingeschäfte, Stillhalter,
   Dividenden, Quellensteuer vorläufig anrechenbar / möglicherweise erstattungsfähig / ungeklärt, **SO-Kandidaten
   (Einordnung offen)**, ETF (ungeklärt), Zinsen, nicht abziehbar), je Jahr, Gewinne und Verluste getrennt; Kopfzeile
   nennt Methode, Kursquelle und Datumsfeld. Die Liste „Offene Fragen“ der Seite wird auf den Stand von OF-92
   gebracht (Prämie bei Zuteilung ist entschieden, vorbehaltlich Bestätigung). **Keine Summe „steuerpflichtig“** und
   keine Verrechnung — nur Aufbereitung.
6. **Betroffenheit:** je Jahr die Zahl der Buchungen, die bei Wechsel der Datumsregel (R7) in ein anderes Jahr
   fielen, sichtbar auf der Seite und im CSV.

## Sofortmaßnahme (schon erledigt, 17.10.2026)

Die bestehende Seite „Steuer“ kennzeichnet ihre Zahlen als **Altberechnung (Schließungsjahr), nicht zur Übernahme in
die Steuererklärung** und trägt den Stand von OF-92 statt der überholten Frage zur Prämie bei Zuteilung.

## Reihenfolge

0. **Parallel ab sofort (AP-10d, Datenprüfung):** betroffene Buchungen und Beträge für die Beraterfragen
   zusammenstellen (Ersatzzahlungen, ETF-Lieferungen, Jahreswechsel, Quellensteuer-Überhang).
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

## Stand (17.10.2026)

Umgesetzt: `analytics/steuer_zufluss.py`, `analytics/steuer_konfig.py`, `journal/steuer_zufluss.py`, API
(`/steuer-auswertung`, `/steuer-csv?methode=zufluss|alt`), CLI `journal steuer-zufluss`, Seite `/steuer`,
Abgleich `werkzeuge/abgleich/steuer_zufluss_abgleich.py`. Alle 18 Fälle von AP-10b bestehen. **Fachliche Abnahme
steht aus** (Bestätigung der Regeln durch den Steuerberater, OF-92/OF-93, Ergebnis des Abgleichs: OF-94).
Entfernt: `analytics/steuer_jahre.py` (Jahresübersicht der Altmethode).

## Ausdrücklich nicht Teil dieses Pakets

- Ersatzzahlungs-Ursachen, USD-Kontoeffekte, Anfangsbestände (AP-10d).
- Verlustverrechnung, Anlage-KAP-Ausfüllhilfe, Anlage SO ausfüllen.
- Änderung von AP-10-Code und -Tests.
