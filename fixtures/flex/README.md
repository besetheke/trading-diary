# Synthetische Flex-Fixtures (AP-02, Format korrigiert in AP-02k)

Aufgebaut nach der dokumentierten Struktur des IBKR Activity-Flex-Exports
(Plan §6.1, §6.2 — Pflichtfelder, Sektionen, Ereigniscodes, orderReference-
Muster). **Kein Wert stammt aus echten Kontodaten**: Konto, Beträge, Symbole,
conids und Kennnummern sind frei erfunden.

**Format seit AP-02k: das echte IB-Schema**, gemessen an sechs Golden-Exporten
2022–2026 (OF-19). Der Inhalt jeder Datei ist gegenüber der ursprünglichen
AP-02-Fassung unverändert — dieselben Zeilen, IDs, Beträge, Mengen, Codes und
Zeitpunkte —, nur die Schreibweise wurde korrigiert:

- Trades tragen kein `tradeTime`; die Handelszeit steht in `dateTime`.
- Zeitpunkte haben die Form `JJJJMMTT;HHMMSS`; `activity_2026_01.xml` enthält
  mit der Interest-Buchung auch die reine Datumsform `JJJJMMTT` (real
  vorkommend, ohne Uhrzeit).
- `whenGenerated` hat dieselbe Form, mit `;` statt `T`.
- Jede Zeile trägt `levelOfDetail`: `EXECUTION` (Trade), `DETAIL`
  (CashTransaction, CorporateAction), `TRANSFER` (Transfer), `SUMMARY`
  (OpenPosition).
- `FlexStatement` hat kein `currency`, `OpenPosition` kein `markValue` — beide
  liefert IB nicht.

Dateien:

- `activity_2026_01.xml` — Hauptdatei: 10 Ausführungen über OPT/STK/FUT/CASH,
  Combo mit zwei Legs (gemeinsames `ibExecID`-Präfix), strukturierte und
  generische `orderReference`, Ereigniszeilen (Ep/A/P), USD und EUR mit
  `fxRateToBase`. Dazu Sektionen SecuritiesInfo (4), OpenPositions (1),
  CashTransactions (2, eine davon mit reiner Datumsform), CorporateActions und
  Transfers leer.
- `activity_2026_02_overlap.xml` — überlappt mit der Hauptdatei: enthält eine
  bereits bekannte `transactionID` erneut plus zwei neue Zeilen.
- `activity_events.xml` — drei Ereigniszeilen (Ep/Ex/A) ohne `ibExecID`.
- `activity_generic_orderref.xml` — drei Zeilen mit generischen
  Werkzeugnamen (`ActivityMonitor`, `OptTrader`, `OptionChain`).
- `activity_unknown_assetcategory.xml` — eine Zeile mit
  `assetCategory="WARRANT"`; der Import muss mit genannten Wert fehlschlagen.

Nachgereicht nach dem Review von AP-02 (Sektionen ohne Duplikate):

- `activity_2026_03a.xml` / `activity_2026_03b.xml` — zwei überlappende
  Abrufe (1.–15. und 10.–31. März) mit allen Sektionen. Buchungen,
  Kapitalmaßnahme und Transfer tragen eine `transactionID`, wie echte
  Exporte; `7100002`, `7200001`, `7300001` und die Ausführung `9400001`
  stehen in beiden Dateien. Die offene Position erscheint zu zwei
  Stichtagen (`reportDate` 15. und 31. März).
- `activity_identische_buchungen.xml` — zwei inhaltsgleiche Gebühren ohne
  `transactionID` in derselben Datei: zwei echte Buchungen, keine Dublette.
- `activity_doppelte_buchungs_id.xml` — zwei Buchungen mit derselben
  `transactionID` **und** demselben `type` (Regel 4, AP-02k: Identität einer
  Sektionszeile ist das Paar); der Import muss mit genanntem Wert
  fehlschlagen.

Nachgereicht in AP-02k (echtes Format, OF-19/OF-20/OF-22):

- `tests/test_ingest_flex_format.py` bringt eigene Testdaten mit (im Test
  erzeugt), für Zeitformen, `notes`-Codelisten, Ebenen, die
  (`transactionID`, `type`)-Identität und die Abwicklungsart. Keine neuen
  Dateien hier nötig.

Den erneuten Abruf derselben Periode (gleicher Inhalt, neuer
`whenGenerated`-Stempel) erzeugen die Tests selbst aus der jeweiligen Datei.

Diese Dateien sind Teil der Abnahmebasis von AP-02 und für Folgesitzungen
unveränderlich (`streng`-Profil).
