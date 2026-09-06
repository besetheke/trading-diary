# Synthetische Flex-Fixtures (AP-02)

Aufgebaut nach der dokumentierten Struktur des IBKR Activity-Flex-Exports
(Plan §6.1, §6.2 — Pflichtfelder, Sektionen, Ereigniscodes, orderReference-
Muster). **Kein Wert stammt aus echten Kontodaten**: Konto, Beträge, Symbole,
conids und Kennnummern sind frei erfunden.

- `activity_2026_01.xml` — Hauptdatei: 10 Ausführungen über OPT/STK/FUT/CASH,
  Combo mit zwei Legs (gemeinsames `ibExecID`-Präfix), strukturierte und
  generische `orderReference`, Ereigniszeilen (Ep/A/P), USD und EUR mit
  `fxRateToBase`. Dazu Sektionen SecuritiesInfo (4), OpenPositions (1),
  CashTransactions (2), CorporateActions und Transfers leer.
- `activity_2026_02_overlap.xml` — überlappt mit der Hauptdatei: enthält eine
  bereits bekannte `transactionID` erneut plus zwei neue Zeilen.
- `activity_events.xml` — drei Ereigniszeilen (Ep/Ex/A) ohne `ibExecID`.
- `activity_generic_orderref.xml` — drei Zeilen mit generischen
  Werkzeugnamen (`ActivityMonitor`, `OptTrader`, `OptionChain`).
- `activity_unknown_assetcategory.xml` — eine Zeile mit
  `assetCategory="WARRANT"`; der Import muss mit genannten Wert fehlschlagen.

Diese Dateien sind Teil der Abnahmebasis von AP-02 und für Folgesitzungen
unveränderlich (`streng`-Profil).
