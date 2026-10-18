---
titel: Steuer — Quellenhierarchie, Anlage SO, Rückkäufe nach BMF, Zeile 18 (Korrekturpaket zu AP-10b/10c)
modell: stark
status: fertig
abhaengig_von: AP-10b, AP-10c
aendert_tests: ja
---

# AP-10e · Korrektur der Steuer-Regeln nach Rückmeldung (OF-99)

Korrekturpaket nach CLAUDE.md 1a: Die fachlichen Erwartungen mehrerer Tests aus AP-10b/10c ändern sich, weil die
Rückmeldung vom 17.10.2026 (OF-99) Regeln ersetzt. Geändert wird, **was** erwartet wird, nie **ob** geprüft wird. Nur
die unten genannten Tests dürfen geändert werden.

## Fachliche Änderungen

1. **Quellenhierarchie statt „Bestätigung durch den Steuerberater“:** Gesetz, BMF-Schreiben vom 14.05.2025, amtlicher
   Vordruck 2025, BFH-Rechtsprechung, IB-Unterlagen nur zur Klärung des Sachverhalts. Jede Regel trägt einen Marker
   `amtlich_belegt`, `aus_daten_belegt` oder `vorsichtige_standardbehandlung` (`analytics/steuer_konfig.py`, `REGELN`).
   Der Prüfstatus „ungeprueft“/„laut_berater_antwort“ entfällt (`pruefstatus` = „regelweise“).
2. **Ersatzzahlungen und SYEP (Anlage SO, § 22 Nr. 3 EStG):** empfangene PIL abzüglich Stornos (REVERSAL), laufende
   SYEP-Vergütung (Zins-Buchung mit „(SYEP)“) getrennt, Freigrenze 256 € auf die Summe (ab 256 € überschritten); die
   PIL-Belastung aus einem Leerverkauf (negative PIL ohne Storno) wird nicht saldiert und nicht angesetzt; die
   Quellensteuer auf PIL (auch Erstattungen) steht nie in Zeile 41.
3. **Rückkäufe (BMF 14.05.2025, Rn. 25):** im Saldo (Zeile 19) und zusätzlich als enthaltener Verlust in Zeile 22;
   Standard `rueckkauf_als_verlust=True`, der Vergleich ohne Rückkäufe bleibt als „Vergleichsrechnung“.
4. **Deutsche Emittenten (§ 34d EStG):** Aktienergebnis deutscher Emittenten (ISIN DE) in Zeile 18, Zeile 19 ohne sie,
   Zeile 20 unverändert.
5. **Deklarationsstatus:** „nicht deklarationsfähig“ nur bei blockierenden Gründen (Datenlücken, ETF-Anteile, Optionskosten
   ohne Lieferung, ungeklärte Basis); sonst „deklarierbar mit Erläuterung“ (§ 150 Abs. 7 AO), die nicht blockierenden Punkte
   stehen als Hinweise.

## Ändernde Tests (namentlich)

- `tests/test_steuer_zufluss.py`: `test_10_…` (jetzt Standardbehandlung Anlage SO statt „Einordnung offen“),
  `test_11_…` (Status `amtlich_belegt`/`vorsichtige_standardbehandlung`, Zeile 18 in der Zeilentabelle),
  `test_18_…` (`pruefstatus` „regelweise“, Quellenhierarchie und Regeln mit Marker).
- `tests/test_steuer_kap.py`: `test_variante_a_…` (Zeile 22 = 300: Termingeschäft 100 + Rückkauf 200; Vergleichswert 100),
  `test_negativer_stillhaltersaldo_…` (Zeile 22 = 400, Vergleichswert 300).
- `tests/test_steuer_haertung.py`: `test_6_…` (Status mit Gründen und Hinweisen), `test_7_…` (Standard mit Rückkäufen,
  Vergleich ohne), `test_8_…` (Zeile 18 statt Hinweis auf Zeile 18 oder 19).
- `tests/test_api_steuer.py`: `test_steuer_auswertung_leer_…` (`pruefstatus` „regelweise“, Regeln und Quellenhierarchie).

Neu: `tests/test_steuer_so.py` (Anlage SO mit Handrechnung).

## Am Echtbestand geprüft (2025, EUR)

Anlage SO: Ersatzzahlungen netto 758,48; SYEP 238,86; Summe 997,34 (Freigrenze überschritten); PIL-Belastung −187,06;
PIL-Quellensteuer 70,17. KAP: Zeile 18 = 164,29; Zeile 19 = 80.021,61; Zeile 20 = 14.495,67; Zeile 22 = 2.367.907,87
(Vergleich ohne Rückkäufe 803.595,03); Zeile 23 = 67.019,25; Zeile 41 = 226,07. Das Jahr bleibt „nicht deklarationsfähig“,
solange 43 ETF-Beine (Investmentsteuergesetz) nicht behandelt sind.

## Ausdrücklich nicht Teil dieses Pakets

Rechtsprüfung der Zitate, Verlustverrechnung, Anlage-KAP-Ausfüllhilfe, ETF-Behandlung, USD-Kurseffekte.
