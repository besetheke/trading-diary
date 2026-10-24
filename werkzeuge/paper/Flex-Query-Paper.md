# Flex-Query für das Paper-Konto anlegen

Stand 24.10.2026. Maßgeblich ist die Soll-Konfiguration aus dem Projektplan §6.2; hier die Fassung für das Paper-Konto (`DU…`). **Ob das
Paper-Konto den Flex Web Service anbietet, habe ich nicht prüfen können** — IB hat bei Paper-Konten oft eingeschränkte Berichte. Wenn die Seiten
unten fehlen, bitte Rückmeldung (dann nehmen wir den Import aus den Ausführungen der TWS statt über Flex).

## Wo

Account Management **des Paper-Kontos** (Anmeldung mit den Paper-Zugangsdaten) → *Leistung & Berichte* (Performance & Reports) →
*Flex-Abfragen* (Flex Queries) → bei „Aktivitäts-Flex-Abfrage“ (Activity Flex Query) auf **+** (Neu).

## Abfrage-Einstellungen

- **Name:** z. B. `Journal Paper`
- **Format:** XML
- **Zeitraum:** *Last 365 Calendar Days* für den ersten Abruf (höchstens 365 Tage je Abruf), danach genügt *Last 30 Calendar Days*;
  der Import vereinigt überlappende Zeiträume ohne Duplikate.
- **Basiswährung:** EUR; **fxRateToBase** aktivieren (Feld in Trades).
- **Modelle:** keine auswählen (sonst nullt IB alle Realized-P/L-Felder).
- **Datum/Zeit:** Format `yyyyMMdd`, Zeit `HHmmss`, Trennzeichen `;` (das Format, das der Import erwartet: `20261023;040109`).
- Abschnitte ohne Eintrag (z. B. Transfers) sind kein Fehler, der Import akzeptiert leere Abschnitte.

## Abschnitte und Felder

**1. Trades** — Detailebene **nur Ausführung (Execution)**; Order, Symbol Summary, Asset Class Summary und Closed Lots abschalten.
Felder: `tradeID`, `transactionID`, `ibExecID`, `ibOrderID`, `orderReference`, `conid`, `symbol`, `underlyingSymbol`, `underlyingConid`,
`assetCategory`, `multiplier`, `strike`, `expiry`, `putCall`, `buySell`, `quantity`, `tradePrice`, `proceeds`, `ibCommission`,
`ibCommissionCurrency`, `currency`, `fxRateToBase`, `netCash`, `dateTime`, `orderTime`, `exchange`, `notes`, `openCloseIndicator`, `cost`,
`mtmPnl`, `closePrice`, `fifoPnlRealized`, `accountId`.

**2. Open Positions** — nur **Zusammenfassung (Summary)**. Felder: `accountId`, `reportDate`, `conid`, `symbol`, `assetCategory`, `position`,
`markPrice`, `positionValue`, `costBasisPrice`, `currency`, `multiplier`, `strike`, `expiry`, `putCall`, `fxRateToBase`.

**3. Cash Transactions** — nur **Detail (Detail)**, Zusammenfassung abschalten. Felder: `accountId`, `transactionID`, `dateTime` (oder
`reportDate`), `type`, `amount`, `currency`, `description`, `conid`, `symbol`, `fxRateToBase`.

**4. Corporate Actions** — Detail (Paper hat selten welche). Felder: Standardfelder wählen.

**5. Transfers** — optional (Paper meist leer).

**6. Financial Instrument Information** — Felder: `conid`, `symbol`, `underlyingSymbol`, `underlyingConid`, `assetCategory`, `multiplier`,
`strike`, `expiry`, `putCall`, `currency`, `settlementPolicyMethod`, `description`.

**7. Net Asset Value (NAV) in Base** und **Change in NAV** und **Cash Report** (Kontowert je Tag, Kontowertentwicklung, Kassenbestand) —
aktivieren; Standardfelder.

**8. Realized and Unrealized Performance Summary in Base** — aktivieren (Plan §6.2).

In jedem Abschnitt zusätzlich **Konto-ID** (`accountId`) einschließen: Der Import ordnet damit Zeilen dem Konto zu.

## Token und Abfrage-ID

1. *Einstellungen → Berichte → Flex Web Service*: aktivieren und **Token** erzeugen (Gültigkeit setzen, z. B. 1 Jahr).
2. Die **Abfrage-ID** steht in der Liste der Flex-Abfragen neben dem Namen.
3. Beides in `%USERPROFILE%\.trading-journal\paper\flex-paper.cmd` eintragen (`FLEX_TOKEN`, `FLEX_QUERY_ID`). **Nie in Chat, Mail oder ins Repo.**

## Testen

Nach dem Eintragen: `werkzeuge\paper\nachtlauf-paper.cmd` einmal von Hand starten. Das Protokoll liegt in
`%USERPROFILE%\.trading-journal\paper\logs\nachtlauf-<Datum>.log`. Fehlt ein Pflichtfeld, nennt der Import das Feld und die Zeile
(„Pflichtfeld … fehlt“). Dann das Feld in der Abfrage ergänzen und erneut abrufen.
