---
titel: Option-Omega-Backtests einlesen und automatisch den OA-Strategien zuordnen
modell: stark
status: fertig
abhaengig_von: AP-13ab
aendert_tests: nein
---

# AP-12a · Backtests: Import, Zuordnung, Live gegen Backtest

Erster Teil von AP-12. Wunsch des Nutzers (11./12.10.2026): OO-Backtests
einbauen, „eine Möglichkeit, wie sie automatisch erkannt werden". Die
**Zerlegung der Differenz** (Kommission, Slippage, Roll, Timing; OF-76 Punkt 6)
bleibt ausdrücklich außen vor — sie ist vom Nutzer zurückgestellt.

## Befund am Echtbestand (Prototyp, 12.10.2026)

Die Spalte `Strategy` von OO und die OA-Strategie haben keine gemeinsame
Normalform (OO `-26 -FKK- D35-10 >SMA5 13:15 & 14:15`, OA `SPX: FKK10`). Sie
lassen sich aber über die Trades selbst verbinden: OO und die Bots öffnen am
selben Tag, zur selben Uhrzeit (beide US-Ostküstenzeit — damit ist OF-76
Punkt 4 belegt), dieselbe Struktur. 1.530 OO-Zeilen, 19 OO-Strategien: 18 davon
finden ihren Bot eindeutig oder mit klarer Mehrheit; Sonderfälle sind ein
Backtest, der zwei Bots speist (SPY- und XSP-Variante), ein umbenannter Bot
(RIC1 → RIF50, zeitlich getrennt) und zwei OO-Varianten, die auf einen Bot
fallen (FKK D35/D45, DC 5/7 EO/StefanL).

## Vertrag

1. **Import** `ingest/optionomega.py`, `journal import-optionomega <datei|ordner>`:
   CSV mit 28 Spalten (Anhang `AP-12-anhang-oo-format.md`), BOM erlaubt.
   Tabelle `oo_trades` (Migration). Schlüssel `(strategie, eroeffnet, legs_roh)`.
   Erneuter Import derselben Datei ist idempotent (`import_runs`, Hash). Ein
   neuerer Export überschreibt die Werte einer schon bekannten Zeile — ein
   Backtest ist eine Rechnung, keine Buchung (Annahme, `OFFENE_FRAGEN.md`
   OF-83). `Reason For Close = Backtest Completed` heißt: am Ende des
   Backtests noch offen.
2. **Leg-Grammatik**: `<Menge> <Mon> <Tag> <Strike> <C|P> <STO|BTO> <Preis>`;
   Jahr des Verfalls = Jahr der Eröffnung, liegt der Monat vor dem
   Eröffnungsmonat, das Folgejahr.
3. **Zuordnung** `engine/oo_zuordnung.py` (rein): Ein OO-Trade passt zu einem
   Live-Trade (OA-Nummer, eröffnende Ausführungen = alle innerhalb von 2 Minuten
   nach der ersten), wenn
   - gleicher Tag, gleiche Familie des Basiswerts (SPX/XSP/SPY · RUT/IWM ·
     NDX/QQQ, sonst der Basiswert selbst),
   - gleiche **Signatur**: je (Seite, Call/Put, Tage bis Verfall) die Menge,
     geteilt durch den ggT aller Mengen,
   - relative Spannweite (max. − min. Strike) ÷ mittlerer Strike in Promille
     höchstens um max(1, 30 %) verschieden,
   - Eröffnungszeiten höchstens 20 Minuten auseinander.
   Je OO-Trade gewinnt der zeitlich nächste Kandidat.
   **Vorschlag** je (OO-Strategie, OA-Strategie): Treffer, Anteil an allen
   Treffern der OO-Strategie (4 Stellen, HALF_UP), erster und letzter Tag;
   gezeigt, wenn Treffer ≥ 2 oder Anteil ≥ 0,5. `eindeutig` bei Anteil ≥ 0,8.
   `erkennung = heuristik` (Regel 7).
4. **Entscheidung** des Nutzers in `oo_zuordnung` (Migration): `bestaetigt`
   oder `abgelehnt`, `erkennung = manuell`. Abgelehnte Vorschläge erscheinen
   nicht mehr im Vergleich; bestätigte auch ohne Treffer.
5. **Vergleich** `analytics/backtest.py`, je Zuordnung (nicht abgelehnt), in USD
   **je Kontrakt** (Kontrakte = ggT der Leg-Mengen, auf beiden Seiten gleich
   gerechnet): Paare mit P/L Backtest, P/L Live (OA-Gewinn in USD) und Δ;
   Summen. `nur_backtest`: geschlossene OO-Trades ohne jeden Live-Partner an
   Tagen, an denen der Bot lief (erster bis letzter Live-Trade der
   OA-Strategie). `nur_live`: geschlossene Live-Trades der OA-Strategie ohne
   jeden OO-Partner an Tagen im Zeitraum des Backtests. Je Zuordnung steht
   auch die Zahl aller Trades der OO-Strategie (`oo_anzahl`). Offene
   Trades (OO `Backtest Completed`, OA `RUNNING`) zählen nur in `offen`.
   Live-Trades mit OA-Gewinn in anderer Währung als USD bleiben außen vor.
6. `GET /backtests`, `POST /journal/backtests/zuordnung`; Seite `/backtests`.

## Tests (vor dem Code)

`tests/test_ingest_optionomega.py`, `tests/test_oo_zuordnung.py`,
`tests/test_api_backtests.py`, Fixture `fixtures/optionomega/oo_beispiel.csv`
(frei erfunden). Erwartungswerte von Hand in den Docstrings (Regel 8).
