# Offene Fragen

Nach CLAUDE.md, Regel 10: hier steht alles, was nicht aus dem Plan ableitbar
war und per Annahme entschieden wurde. Die Annahmen sind im Code an der
genannten Stelle dokumentiert.

## OF-01 · Form der Cache-Tabellen `metrics_daily`, `metrics_by_chain`, `metrics_by_campaign`

Plan §5 nennt nur die Namen („Materialisiert, Cache, verwerfbar“), keine Spalten.
AP-01 legt sie als Stellvertreter mit Surrogatschlüssel an, damit die
Initialmigration das vollständige Schema aus §5 enthält und der Rauchtest
„alle Tabellen gefunden“ maschinell prüfbar ist.
**Annahme:** `journal/schema.py`, Abschnitt „Materialisiert“. Die echte Form
(Spalten, Aggregationsebene, Löschverhalten) sollte AP-06 über eine Migration
festlegen.

## OF-02 · Form der Override-Tabellen `chain_overrides` und `campaign_overrides`

Plan §5 nennt sie ohne Spalten („manuelle Korrekturen der Erkennung“).
**Annahme:** Overrides spiegeln die manuell festgelegte Zuordnung
(Struktur→Kette beziehungsweise Kette→Kampagne) mit Notiz und Zeitstempel.
Der Rebuild (AP-04) liest sie, um die automatische Erkennung zu korrigieren —
damit überleben manuelle Korrekturen ein vollständiges `rebuild` (P1).
Das endgültige Verhalten legt AP-04 fest; die Tabellenform würde dann ggf. per
Migration erweitert.

## OF-03 · Wert für `busy_timeout`

§4.1 schreibt vor, dass `busy_timeout` gesetzt ist, nennt aber keinen Wert.
**Annahme:** 5.000 ms als Standard, je Engine-Aufruf überschreibbar
(`journal/db.py`, `STANDARD_BUSY_TIMEOUT_MS`). Wenn der Options Roller eigene
Vorgaben macht, ist der Wert dort zu übernehmen.

## OF-04 · Zeitstempel ohne Zeitzonen-Information

`handelszeit` und alle `_am`-Felder werden als naive DateTime gespeichert, so
wie die Quelle liefert; eine Normalisierung (Zeitzonen, UTC) passiert nicht
still, sondern ist Gegenstand des Imports (AP-02).
**Offen:** ob die Auswertung (AP-06) oder die Steuer (AP-10) UTC braucht —
dann per Migration ändern, nicht per stiller Konvention.

## OF-05 · Speichertyp für conid

`conid` ist als BigInteger gespeichert (nicht Text). Die Flex-Quelle liefert
ihn als Zahl; ein Join über die Tabellen hinweg bleibt so typsicher.
**Offen:** falls eine künftige Quelle nicht-numerische conids liefert, ist
auf Text umzustellen — dann über Migration, damit alle Tabellen konsistent
bleiben.

## OF-06 · Datenbankpfad-Konvention

Der Standardpfad der Entwicklungsdatenbank ist `sqlite:///journal.db`
(`alembic.ini`); zur Laufzeit hat die Umgebungsvariable `JOURNAL_DB` Vorrang
(`migrations/env.py`, `journal/db.py` nimmt einen Pfad-Parameter).
**Offen:** welcher Pfad auf dem Trading-Server (§3) endgültig gelten soll —
Betriebsentscheidung, nicht Codefrage.

## OF-07 · Ereigniscode `P` ist im Wertebereich von `ereignistyp` nicht unterbringbar

§1.4 nennt vier Ereignistypen (trade/expiry/exercise/assignment); §6.1 zeigt
aber einen fünften Code: `notes = P` mit 266 Vorkommen im Referenzexport.
Der AP-02-Auftrag sagt, `P` bleibe „zunächst unklassifiziert" — bei NOT NULL
plus CHECK ist dafür aber kein Zustand vorgesehen; der Import würde scheitern
oder still verwerfen, beides verboten.
**Annahme:** `P` wird als `ereignistyp='unbekannt'` gespeichert (Code bleibt
in `ereignis_code` erhalten). AP-02 erweitert den CHECK um diesen Wert — per
Migration, nicht durch Editieren der Initialmigration (Regel 3). P7 bleibt
gewahrt: Strukturen entstehen nur aus `ereignistyp = 'trade'`, also nie aus
`unbekannt`.
**Offen:** was `P` fachlich bedeutet (Kandidaten: Payment in lieu, Partial?).
Das sollte anhand eines echten Exports geklärt werden; danach kann der Wert
per Migration auf die richtige Klasse gemappt werden — die Rohzeilen
(`roh_json`, `ereignis_code`) bleiben unverändert interpretierbar.

## OF-08 · Unbekannte Ereigniscodes in `notes` führen zum Abbruch

Der AP-02-Auftrag legt die Zuordnung für die vier belegten Codes fest
(leer/`Ep`/`Ex`/`A`/`P`), sagt aber nichts über weitere Werte in `notes`.
§6.1 belegt nur diese Codes; ob `notes` in echten Exporten freien Text trägt,
ist ungeprüft.
**Annahme:** Jeder nicht leere Code außerhalb der bekannten vier lässt den
Import mit `ValueError` (Wert genannt) fehlschlagen — konsistent mit der
Abnahme „unbekannte Feldwerte führen zu einem Fehler, nicht zu stillem
Verwerfen". Stelle: `ingest/flex.py`, `EREIGNISTYPEN` und
`_ereignistyp_aus_notes`.
**Offen:** Tritt in einem echten Export ein fünfter Code oder Freitext auf,
ist die Zuordnung fachlich zu entscheiden und die Tabelle zu erweitern.

## OF-09 · Idempotenz- und Ergänzungsmodell der Flex-Sektionstabellen

Der Auftrag legt fest, dass jede Sektion eine eigene Tabelle bekommt, aber
nicht, wie sich wiederholte oder überlappende Importe auf diese Tabellen
auswirken (die Abnahmekriterien sprechen nur von `executions`).
**Annahme (`ingest/flex.py`):**

1. **Gleiche Datei** (gleicher SHA-256 in `import_runs.datei_hash`) wird
   vollständig übersprungen — auch für die Sektionen.
2. **`flex_securities_info`** ist Stammdaten mit natürlichem Schlüssel
   `conid`: ein erneuter Import überschreibt den Eintrag mit dem jüngsten
   Stand (einschließlich `roh_json`).
3. **`flex_open_positions`, `flex_cash_transactions`, `flex_corporate_actions`,
   `flex_transfers`** — *nach dem Review von AP-02 neu geregelt* (Migration
   `8a8d06f09935`, Tests `tests/test_ingest_flex_sektionen.py`). Die erste
   Fassung fügte diese Zeilen je Lauf ein; jeder erneute oder rollierende
   Abruf (neuer `whenGenerated`, also neuer Datei-Hash) hätte Zinsen,
   Gebühren und Kapitalmaßnahmen verdoppelt. Jetzt trägt jede Zeile `konto`
   und `quell_schluessel`, das Paar ist eindeutig, eine vorhandene Zeile wird
   nie überschrieben:
   - mit `transactionID` der Quelle: `tx:<id>`; dieselbe ID zweimal in einer
     Datei bricht den Import ab;
   - ohne: `inhalt:<sha256 über roh_json>#<n>`, `n` zählt inhaltsgleiche
     Zeilen derselben Datei — zwei gleiche Gebühren bleiben zwei Buchungen;
   - offene Positionen tragen `stichtag` (`reportDate`, sonst `toDate` des
     Statements) und gehen in den Inhalts-Hash ein: ein Bestand je Stichtag.

   **Annahme, ungeprüft:** Echte Exporte tragen an CashTransactions,
   CorporateActions und Transfers eine `transactionID` (so die IB-Feldliste;
   an den Golden-Daten nicht nachgezählt). Fehlt sie, greift der Inhalts-Hash.
   Dessen Grenze: Ändert IB zwischen zwei Abrufen ein Attribut derselben
   Buchung, entstehen zwei Zeilen — sichtbar, nicht still verloren. Mit dem
   ersten echten Export prüfen (starkes Modell, Golden-Daten).
4. **`instruments`** wird aus Trades und SecuritiesInfo gefüllt: erste
   Anlage per conid, danach gewinnt der jüngste Import für abweichende
   nicht-leere Felder; leere Felder überschreiben nichts. tickwert bleibt
   leer — die Flex-Quelle liefert ihn nicht (§5 nennt ihn, AP-03 braucht
   ihn je Anlageklasse; dann pflegen oder aus anderer Quelle speisen).
   Gleiches gilt für `flex_securities_info`. **Achtung beim Nachladen der
   Historie (§6.2, jahresweise):** „jüngster Import" heißt zuletzt
   importiert, nicht jüngster Datenstand. Wer 2022/23 nach einem aktuellen
   Lauf lädt, überschreibt neuere Stammdaten mit älteren — etwa angepasste
   Multiplikatoren nach einem Split. Bis das geregelt ist: Historie zuerst,
   dann die laufenden Abrufe.

**Offen:** (a) Die `transactionID`-Annahme aus Punkt 3 am echten Export
bestätigen. (b) Stammdaten nach Datenstand statt Importreihenfolge
fortschreiben (Punkt 4) — spätestens, bevor die Historie produktiv
nachgeladen wird.

**Stand 10.09.2026:** (b) ist entschieden — Plan §6.2 „Reihenfolgeunabhängigkeit
des Imports": Stammdaten tragen das Periodenende ihrer Quelle, nur eine jüngere
Quelle überschreibt. Umsetzung in AP-02a. (a) ist **weiter offen**: Die Messung
des Planers (19.425 Zeilen, `tradeID` lückenlos) betrifft die Trades-Zeilen,
nicht `transactionID` auf CashTransactions, CorporateActions und Transfers.

**Gemessen 12.09.2026 an beiden Golden-Exporten (nur Zählwerte):** Der
Referenzexport 2022/23 enthält keine dieser Sektionen. Im Export 2026 tragen
211 von 327 CashTransactions eine `transactionID` (116 ohne, gut ein Drittel),
8 von 12 CorporateActions; Transfers gibt es keine. Die Annahme aus Punkt 3
trägt damit nur teilweise: Der Inhalts-Hash ist kein theoretischer Rückfall,
sondern für rund ein Drittel der Kassenbuchungen der tatsächliche Schlüssel —
und seine Grenze (ein zwischen zwei Abrufen geändertes Attribut erzeugt eine
zweite Zeile) betrifft genau diese Zeilen. **Offen:** welche Buchungsarten ohne
`transactionID` kommen; danach entscheiden, ob der Inhalts-Hash für sie genügt.

**Korrigiert 12.09.2026 (siehe OF-22):** Die Folgerung im vorigen Absatz ist
falsch. Die 116 CashTransactions ohne `transactionID` sind ausnahmslos Zeilen
der Ebene `SUMMARY`, also Aggregate; jede Einzelbuchung (`DETAIL`) trägt eine
ID. Der Inhalts-Hash ist damit nicht für ein Drittel der Kassenbuchungen der
tatsächliche Schlüssel — das eigentliche Problem ist, dass der Import beide
Ebenen übernimmt und Geldflüsse doppelt bucht.

**Erledigt 12.09.2026 in AP-02a — Punkt (b), Stammdaten nach Datenstand.**
`instruments` und `flex_securities_info` tragen die Spalte
`quell_periodenende`: das `toDate` des FlexStatements, aus dem der Satz stammt.
Zusammengeführt wird in `_stammsatz_verschmelzen` (`ingest/flex.py`) nach einer
Regel, die in beide Richtungen dasselbe Ergebnis liefert:

- Eine **ältere** Quelle überschreibt nichts, sie füllt nur leere Felder.
- Jede andere Quelle setzt ihre besetzten Felder durch; `None` löscht nie.
- Gespeichert wird das spätere der beiden Periodenenden.

Damit entfällt die Bedienanweisung „erst Historie, dann Laufendes". Punkt 4
oben ist in diesem Teil überholt: „jüngster Import" heißt jetzt jüngste
Quellperiode. Die Warnung zum Nachladen der Historie gilt nicht mehr.

**Annahme, dokumentiert:** Ein fehlendes `toDate` heißt „Periode unbekannt"
und ist die schwächere Angabe — es überschreibt keinen datierten Stand, wird
aber von jedem datierten Stand überschrieben. Echte Flex-Statements tragen
immer ein `toDate`; der Fall ist Absicherung, kein Normalfall.

**Rest, bewusst offengelassen:** Tragen zwei *verschiedene* Quelldateien
dasselbe Periodenende und widersprechen sich in einem besetzten Feld, gewinnt
die zuletzt importierte. Innerhalb einer Datei ist genau das gewollt — Trades
werden zuerst übernommen, die Sektion `SecuritiesInfo` danach, und sie ist die
bessere Quelle für Multiplikator und Währung. Über Dateigrenzen hinweg fehlt
für gleiche Perioden jede Grundlage, eine der beiden Quellen vorzuziehen; eine
Reihenfolgeregel wäre geraten. Fällt das im Betrieb auf, braucht es ein
zusätzliches Merkmal (etwa `whenGenerated`) und eine fachliche Entscheidung.

Punkt (a) — `transactionID` auf CashTransactions, CorporateActions und
Transfers — bleibt **weiter offen**. AP-02a hat daran nichts geändert: die
Quellschlüssel der Sektionszeilen (`_quell_schluessel_vergeben`) sind
unverändert, `tx:<id>` beziehungsweise `inhalt:<sha256>#<n>`. Nur `executions`
ist umgeschlüsselt worden.

## OF-10 · Plan nennt zwei verschiedene Schlüsselfelder für `exec_id`

§5 (Abschnitt `executions`, „Schlüsselgleichheit über Quellen hinweg") nennt
`tradeID` in IB Flex als Gegenstück zur TDP-Spalte `Transaction ID`. §6.1
(„Weitere Feldbefunde") belegt am echten Export: `transactionID` entspricht
`Transaction ID`.
**Umgesetzt:** `exec_id` = `transactionID` (`ingest/flex.py`), gestützt auf den
empirischen Befund in §6.1; die AP-02-Abnahmetests setzen es ebenso voraus.
**Offen:** §5 im Plan korrigieren (Plan ist für die Modelle schreibgeschützt).
Wichtig für AP-09: Der TDP-Legacy-Import muss auf dieselbe Spalte schlüsseln,
sonst entstehen Dubletten zwischen Altbestand und Flex.

**Geklärt 10.09.2026:** §5 hatte recht, §6.1 war falsch. Gemessen im
Überschneidungszeitraum: 175 von 175 TDP-Zeilen treffen `tradeID`, keine
`transactionID`. Plan und AP-02.md sind korrigiert; `exec_id` = `tradeID`,
`transactionID` sekundär. Die Umstellung von Code und Test-Erwartungen erfolgt
in AP-02a. Bis dahin schlüsselt `ingest/flex.py` noch auf `transactionID`.

**Erledigt 12.09.2026 in AP-02a.** `exec_id` trägt `tradeID`; das Feld
`transactionID` steht in der neuen Spalte `executions.transaction_id`,
indiziert, ohne Eindeutigkeitszwang — Beleg für die Abstimmung mit dem Broker,
nicht Schlüssel. Eine fehlende `tradeID` bricht den Import unter Nennung der
Trades-Zeile ab, statt auf einen Ersatzschlüssel auszuweichen (§5,
Vollständigkeit über 19.425 Zeilen belegt).

Die Migration `c4b1f0a9d2e7` schlüsselt vorhandene Zeilen **um**, statt sie zu
verwerfen: `roh_json` trägt das vollständige Attributbild, `tradeID` also
inbegriffen. Die Verweise aus `legs` und `assignment_links` wandern mit — an
`assignment_links` hängen mit `erkennung = 'manuell'` Benutzerdaten, die nach
Regel 4 nicht verlorengehen dürfen. Fehlt einer vorhandenen Zeile die `tradeID`
in `roh_json`, oder ist ein Wert doppelt, bricht die Migration mit Nennung der
Zeilen ab.

**Offen, kein Blocker:** Für den Umschlüsselungspfad der Migration gibt es
keinen automatischen Test. Die Testsuite fährt jede Migration gegen eine leere
Datenbank (`tests/conftest.py`, Fixture `migrated_db`), und die Testfreigabe
von AP-02a nennt ausschließlich `tests/test_ingest_flex.py` mit drei
namentlich verlangten neuen Tests — ein Migrationstest gehörte nicht dazu.
Nachgewiesen wurde der Pfad in AP-02a von Hand gegen einen künstlichen
Altbestand (Hin- und Rückweg, Verweise und Benutzerdaten erhalten, keine
Fremdschlüsselverstöße). **Vorschlag für ein Folgepaket:** einen Migrationstest
in `tests/` ergänzen, der einen Bestand auf `8a8d06f09935` anlegt und den
Upgrade prüft; das gilt allgemein, nicht nur für diese Migration.

**Ebenfalls ohne eigenen Test:** dass `executions.transaction_id` beim Import
gefüllt wird. Auch das lag außerhalb der drei freigegebenen Tests. Die Spalte
ist heute reiner Beleg; spätestens wenn AP-09 oder eine Broker-Abstimmung sie
liest, gehört eine Erwartung dazu.

## OF-12 · AP-03: Auftrag verlangt das Anlegen der Abnahmebasis, das Profil des Pakets verweigert es

**Gemeldet 12.09.2026, Umsetzung abgebrochen, kein Code geschrieben.**

`auftraege/AP-03.md` legt die Testdaten „in diesem Paket" an: synthetische
Fixtures unter `fixtures/synthetisch/` und mindestens 35 Tests mit von Hand
nachgerechneten Erwartungswerten (Regel 8), kommentiert im Test. Das Paket
läuft laut Kopf auf dem günstigen Modell — Profil `streng`: `tests/` und
`fixtures/` sind schreibgeschützt (Hook, Deny-Regeln, CLAUDE.md Regel 1).

Nach dem Arbeitsmuster §11.2 schreibt das starke Modell Abnahmetests und
Fixtures eines Pakets *vor* der Umsetzung — so war es bei AP-02 („Abnahmebasis
liegt vor: `tests/test_ingest_flex.py` und `fixtures/flex/` sind von AP-01
nach §11.2 geschrieben"). Für AP-03 fehlt dieser Schritt: es gibt kein
Verzeichnis `fixtures/synthetisch/` und kein Matching-Testmodul in `tests/`
(nur die 37 Tests aus AP-01/AP-02). Der Auftrag ist für das zugewiesene
Profil falsch geschnitten.

**Zwei Wege, den Widerspruch zu lösen (Entscheidung beim Nutzer, nicht beim
Modell):**

1. Das starke Modell schreibt die Abnahmebasis vorab — eigener Vorbereitungs-
   Lauf analog zur AP-02-Vorbereitung oder als Teil des AP-03-Auftrags mit
   `modell: stark` und explicitem Vorbereitungsschritt. Danach läuft die
   Umsetzung wie geplant auf dem günstigen Modell.
2. AP-03 wird vollständig an das starke Modell vergeben (`modell: stark` im
   Kopf), das Tests und Umsetzung in einer Hand hält.

Nicht zulässig: den Schutz für diese Session lockern (CLAUDE.md, Regel 1) oder
das Matching ohne Abnahmebasis umsetzen. Die 35 Tests sind Abnahmekriterium,
und die Fachdetails — Rundungsreste auf die letzte Teilmenge,
Kommissionsaufteilung, Split-Wirkung auf Menge *und* Preis, Rolle des
Tickwerts, Behandlung von Ereigniszeilen beim Matching — werden erst durch
handgerechnete Erwartungswerte verbindlich. Sie im Rahmen der Umsetzung selbst
zu entscheiden, wäre Raterei gegen Regel 10 und würde die Abnahme zirkulär
machen.

**Nebenbefund, kein formaler Blocker:** AP-02a (Schlüsselkorrektur `exec_id` =
`tradeID`) steht auf `offen`; AP-03 hängt formal nur an AP-02. Da `legs`
Ausführungs-IDs speichert und jederzeit neu berechenbar ist, wäre AP-02a
zuvor aber die sauberere Reihenfolge.

**Erledigt 12.09.2026 auf Nutzerentscheidung: Weg 1.** `auftraege/AP-03v.md`
legt die Abnahmebasis an (starkes Modell, `aendert_tests: ja`, implementiert
nichts), danach läuft AP-03 unverändert auf dem günstigen Modell. Reihenfolge:
AP-02a, dann AP-03v samt Review, dann AP-03 — der Nebenbefund ist damit
berücksichtigt. Der Vorbereitungsfall steht jetzt als Regel in `CLAUDE.md`
(1a) und in `START.md`, weil er bei AP-07 bis AP-10 erneut auftritt.

## OF-11 · AP-02a: drei Punkte vor dem Start klären

**Erledigt 12.09.2026 auf Nutzerentscheidung:** Alle drei Vorschläge sind in
`auftraege/AP-02a.md` eingearbeitet. Entschieden hat der Nutzer, nicht der
Planer — bei Widerspruch gilt dessen Fassung.

1. **Umzusetzen, Punkt 3 („Der Inhalts-Hash als Ersatzschlüssel entfällt")**
   beruht auf einer ungenauen Formulierung in OF-09. Für `executions` gibt es
   keinen Inhalts-Hash: eine fehlende ID bricht dort schon heute ab
   (`ingest/flex.py`, `_pflichtwert`). Der Hash existiert nur als
   Quellschlüssel der Sektionszeilen (`_quell_schluessel_vergeben`), vor allem
   für `OpenPositions`, die gar keine ID tragen. Fällt er weg, bricht der
   Sektionsimport und die Dublettensicherung aus OF-09.
   **Vorschlag:** Punkt 3 gilt nur für `executions` (Pflichtfeld `tradeID`);
   die Quellschlüssel der Sektionszeilen bleiben unverändert.
2. **Freigabe und Abnahme widersprechen sich.** „Ausdrücklich freigegebene
   Änderungen an Tests — nur diese, keine weiteren" erlaubt nur das Umstellen
   von Erwartungen; die Abnahme verlangt drei neue Tests (fehlende `tradeID`,
   Stammdaten-Reihenfolge, überlappende Dateien). Da `fixtures/` tabu ist,
   müssen deren Testdaten im Test selbst entstehen (`tmp_path`).
   **Vorschlag:** Neue Tests in `tests/test_ingest_flex.py` mit im Test
   erzeugten XML-Daten ausdrücklich freigeben; bestehende Tests bleiben bis
   auf die genannten Erwartungen unberührt.
3. **Die Abnahme listet `OFFENE_FRAGEN.md` nicht** unter den erlaubten
   Änderungen, OF-09 und OF-10 müssen aber fortgeschrieben werden.
   **Vorschlag:** in die Liste aufnehmen.

**Geschlossen 12.09.2026 mit der Umsetzung von AP-02a.** Alle drei Punkte sind
in der umgesetzten Fassung so gehalten, wie der geschärfte Auftrag sie
vorgibt: die Quellschlüssel der Sektionszeilen sind unverändert (Punkt 1), die
drei neuen Tests erzeugen ihre Daten in `tmp_path` und lassen `fixtures/`
unberührt (Punkt 2), OF-09 und OF-10 sind fortgeschrieben (Punkt 3).

**Eine Abweichung, die zu melden ist:** In `tests/test_ingest_flex.py` wurde
zusätzlich eine Leerzeile zwischen zwei Importzeilen entfernt. Sie war ein
seit AP-02 bestehender `ruff`-Verstoß (I001) — `ruff check .` war auf `master`
nicht sauber, und AP-02 lief unter `streng` und konnte ihn nicht beheben. Die
Abnahme von AP-02a verlangt einen sauberen Lauf; ohne diese Änderung wäre sie
nicht zu erfüllen gewesen. Es ist eine reine Formatierung: keine Erwartung,
keine Prüflogik, kein Testverhalten ist davon berührt.

## OF-13 · Vorzeichen von `executions.menge` ist uneinheitlich

Der Flex-Export führt `quantity` bei Verkäufen teils negativ, teils positiv.
Belegt an den eigenen Fixtures aus AP-01: `activity_2026_01.xml` schreibt
`buySell="SELL" quantity="2"`, `activity_2026_02_overlap.xml` und
`activity_2026_03b.xml` schreiben `buySell="SELL" quantity="-10"`. AP-02
speichert den Rohwert unverändert, was richtig ist (P1) — für das Matching
bleibt damit aber offen, woran die Richtung hängt.

**Entscheidung für den AP-03-Vertrag:** Die Richtung kommt aus `side`, die
Stückzahl aus `abs(menge)`. Das ist gegen beide Schreibweisen robust.

**Offen:** Welche Schreibweise der echte Export tatsächlich verwendet, ist
nicht nachgemessen — die Fixtures sind synthetisch und widersprechen sich.
Führt der echte Export das Vorzeichen verlässlich, wäre eine Prüfung auf
Widerspruch zwischen `side` und dem Vorzeichen von `menge` sinnvoll: sie
fände Importfehler, die der jetzige Vertrag stillschweigend überdeckt. Mit dem
ersten echten Export prüfen (starkes Modell, Golden-Daten).

**Gemessen 12.09.2026 an beiden Golden-Exporten (18.049 Trades):** Das
Vorzeichen ist in echten Daten verlässlich — jede SELL-Zeile trägt eine
negative, jede BUY-Zeile eine positive `quantity` (Export 1: 2.019 und 1.952,
Export 2: 7.045 und 7.033, keine Ausnahme). Uneinheitlich sind nur die
synthetischen AP-01-Fixtures. `side` plus `abs(menge)` bleibt richtig.
**Vorschlag, nicht dringend:** Eine Widerspruchsprüfung zwischen `side` und
Vorzeichen im Import würde echte Daten nie stören und Importfehler finden. Sie
bräche aber `fixtures/flex/activity_2026_01.xml` (SELL mit positiver Menge) und
bräuchte deshalb ein Korrekturpaket.

## OF-14 · Verhältnis von `tickwert` und `multiplikator` bei Futures

§5 nennt beide Felder auf `instruments`, der Plan verlangt in AP-03
„Multiplikator und Tickwert je Anlageklasse korrekt angewandt", sagt aber
nicht, wie sie sich zueinander verhalten. Ein Tickwert im engeren Sinn — der
Geldwert einer kleinsten Preisbewegung — ließe sich ohne **Tickgröße** gar
nicht in einen P&L umrechnen, und eine Tickgröße gibt es im Schema nicht.
OF-09 hält außerdem fest, dass die Flex-Quelle `tickwert` nicht liefert; er
müsste gepflegt oder aus anderer Quelle gespeist werden.

**Entscheidung für den AP-03-Vertrag:** Bei `FUT` und `FOP` gilt ein gesetzter
`tickwert` als **Geldwert einer Preiseinheit** (eines vollen Punkts) und hat
Vorrang vor `multiplikator`; ist er leer, gilt `multiplikator`. Bei allen
anderen Anlageklassen gilt `multiplikator`. Das Fixture
`fixtures/synthetisch/futures_tickwert.json` setzt beide Felder absichtlich
verschieden (5 gegen 25), damit im Test sichtbar wird, welcher angewandt wurde.

**Offen, und vor AP-03 zu entscheiden:** Ob diese Auslegung die gewollte ist.
Zwei Alternativen wären vertretbar: (a) `tickwert` ist reine Berichtsgröße und
geht nicht in den P&L ein — dann trägt `multiplikator` bei Futures den
Punktwert; (b) `tickwert` ist der Wert einer kleinsten Preisbewegung — dann
fehlt dem Schema die Tickgröße und es braucht eine Migration. Fällt die
Entscheidung anders aus, sind `futures_tickwert.json` und die vier
Futures-Tests über ein Korrekturpaket nach Regel 1a anzupassen; die übrigen
53 Tests sind davon nicht berührt.

**Entschieden 12.09.2026 auf Nutzerentscheidung: Variante (a).**
`multiplikator` trägt bei allen Anlageklassen den Preisfaktor, bei Futures den
Punktwert; `tickwert` geht nicht in den P&L ein. Begründung: Die Auslegung aus
AP-03v öffnet eine stille Falle. Beim ES (Multiplikator 50, Tickgröße 0,25,
Tickwert 12,50) würde ein nach seinem Namen befülltes Feld `tickwert` den
Futures-P&L um den Faktor 4 verfälschen, ohne dass ein Test anschlägt. IB
liefert `tickwert` nicht, und der Tickwert ist aus Multiplikator und Tickgröße
ableitbar, nicht umgekehrt.

**Gegenprobe:** Eine unabhängige Referenz, geschrieben nur aus dem Vertrag,
besteht alle 57 Tests der Basis aus AP-03v. Nach Variante (a) fallen genau
**zwei** Tests, nicht vier:
`test_futures_tickwert_hat_vorrang_vor_dem_multiplikator` und
`test_futures_multiplikator_allein_waere_das_falsche_ergebnis`. Umsetzung im
Korrekturpaket `AP-03vk`; der Vertrag in `AP-03.md`, Regel 3, ist angepasst.

**Offen für den Planer:** §6, AP-03 verlangt „Multiplikator und Tickwert je
Anlageklasse korrekt angewandt". Nach dieser Entscheidung wird der Tickwert
bewusst nicht angewandt; die Formulierung im Plan ist anzupassen (`plan/` ist
für die Modelle gesperrt).

**Umgesetzt 12.09.2026 in AP-03vk:** die zwei Erwartungen in
`tests/test_matching.py` umgestellt und umbenannt, ein Test für fehlenden
`multiplikator` ergänzt, die Beschreibung in `futures_tickwert.json` und der
Kommentar an `instruments.tickwert` angepasst. Offen bleibt nur der
Planhinweis oben.

## OF-15 · Stichtagsgrenze bei Kapitalmaßnahmen

`corporate_actions.stichtag` ist ein Datum ohne Uhrzeit. Der Plan sagt, der
Split-Faktor werde „auf die Bestandsmenge angewandt, bevor gematcht wird",
nicht aber, ob eine Ausführung **am** Stichtag noch zu alten oder schon zu
neuen Konditionen gebucht ist.

**Entscheidung für den AP-03-Vertrag:** Angepasst werden Ausführungen mit
`handelszeit.date() < stichtag`. Eine Ausführung am Stichtag selbst gilt
bereits zu neuen Konditionen. Begründung: Der Split ist zum Handelsbeginn des
Stichtags wirksam, die Kurse des Tages sind bereits bereinigt; eine an diesem
Tag gehandelte Menge wäre sonst doppelt angepasst. `aktiensplit.json` prüft
die Grenze mit conid 500009 ausdrücklich.

**Offen:** Am echten Export gegenprüfen, sobald eine Kapitalmaßnahme im
Datenbestand liegt — die Frage entscheidet sich an der Buchungspraxis von IB,
nicht am Plan. Ebenfalls offen: `faktor` ist im Vertrag als „Zahl neuer Stücke
je altem Stück" definiert (Split 2:1 → 2, Reverse 1:10 → 0.1). Woher der Wert
kommt und in welcher Form IB ihn liefert, klärt erst das Paket, das
`corporate_actions` befüllt — `flex_corporate_actions` trägt bisher nur den
Rohtyp (z. B. `FS`) und die Beschreibung.

## OF-16 · Behandlung von `ereignistyp = 'unbekannt'` im Matching

Der Ereigniscode `P` liegt seit AP-02 als `ereignistyp = 'unbekannt'` in
`executions` (OF-07, 266 Zeilen im Referenzexport). Was das Matching damit tun
soll, sagt weder Plan noch Auftrag. Beide denkbaren Wege sind falsch: als
Schließung buchen hieße raten, verwerfen hieße Positionen verlieren.

**Entscheidung für den AP-03-Vertrag:** Solche Zeilen nehmen nicht am Matching
teil und werden mit Grund in `nicht_gematcht` gemeldet; die betroffene
Position bleibt offen. Damit ist der Fall sichtbar statt still.

**Offen:** Sobald `P` fachlich geklärt ist (OF-07), gehört er in die Liste der
matchenden Ereignisarten. Bis dahin bleibt jede Position, die auf einer
P-Zeile endet, offen und verfälscht die Summenprobe gegen echte Daten — beim
ersten Golden-Lauf zu erwarten und dort zu erklären.

## OF-17 · `executions.kommission = NULL` im Matching

Der Flex-Import speichert `ibCommission` als NULL, wenn die Quelle das Feld
leer liefert (`ingest/flex.py`, `_dezimalwert`); das Schema lässt NULL zu
(`journal/schema.py`). Der AP-03-Vertrag nennt nur die Felder, nicht ihre
Nullbarkeit.

**Annahme:** NULL heißt „keine Kommission gebucht" und wirkt wie 0 — die
Verteilung der Kommission auf Teilmengen läuft mit 0 durch, kein Leg trägt
einen Anteil (`engine/matching.py`, `_buchung`). Die Alternative, NULL als
„unbekannt" zu lesen und abzubrechen, würde jeden Bestand ohne explizite
Nullbuchung (etwa Ereigniszeilen) unbrauchbar machen.

**Offen:** Sollten echte Daten NULL in einem Sinne führen, der Geld bedeutet,
ist das ein Abbruchgrund wie beim fehlenden Multiplikator. Mit dem ersten
Lauf gegen Golden-Daten prüfen (starkes Modell).

**Gemessen 12.09.2026 an beiden Golden-Exporten:** In 18.049 Trades ist
`ibCommission` kein einziges Mal leer, weder in Handels- noch in
Ereigniszeilen — IB bucht dort eine ausdrückliche 0. Der Fall NULL kommt in
echten Daten nicht vor; die Begründung „jeder Bestand ohne explizite
Nullbuchung wäre unbrauchbar" trifft nicht zu. Eine NULL wäre damit ein
Importdefekt. **Empfehlung, nicht blockierend:** auf Abbruch umstellen, wie
beim fehlenden Multiplikator.

## OF-18 · Kommissionsverteilung rundet den letzten Anteil — Summe nicht exakt

**Befund aus dem Review von AP-03 (12.09.2026), blockiert die Abnahme.**
`engine/matching.py`, `_kommission_verteilen`, rundet auch den letzten Anteil
auf den Cent. Hat die gebuchte Kommission mehr als zwei Nachkommastellen, geht
die Summe über die Legs nicht mehr in der gebuchten Kommission auf; bei einer
ungeteilten Ausführung wird sie ohne jede Aufteilung still gerundet (etwa
−1,0472 → −1,05). Das verletzt Vertrag Regel 5 („damit die Summe exakt
bleibt") und CLAUDE.md Regel 5 („keine stillen Rundungen").

**Belege:** Differenztest gegen eine unabhängige Referenz, je 3.000
Zufallsszenarien: bei Kommissionen auf den Cent identisch (3.000 von 3.000);
bei Kommissionen mit vier Nachkommastellen bleibt die Summe je `conid` nur in
7 von 3.000 Szenarien exakt. An den Golden-Exporten tragen 3.102 von 3.971
(78 %) und 8.538 von 14.078 (61 %) Ausführungen eine Kommission mit mehr als
zwei Nachkommastellen — der Fehler träfe die Mehrheit der echten Buchungen und
ließe die Summenprobe gegen die Broker-Summe (Plan §6, AP-03) scheitern.

**Warum die Tests es nicht fanden:** Kein Fixture der Abnahmebasis enthält eine
Kommission mit mehr als zwei Nachkommastellen. Das ist eine Lücke in AP-03v,
die das Review von AP-03v hätte finden müssen.

**Vorschlag:** (1) Nachtrag zur Abnahmebasis durch das starke Modell — ein
Fixture mit gebrochenen Kommissionen, Tests für die ungeteilte Ausführung, für
die Aufteilung mit exaktem Rest und für die exakte Summe; Vertrag Regel 5
präzisieren: die ersten Teilmengen auf den Cent, die letzte trägt den exakten
Rest, die gebuchte Kommission wird nie gerundet. (2) Nachbesserung von AP-03
durch das günstige Modell gegen diese Tests.

**Stand 12.09.2026:** Schritt (1) ist mit AP-03vn erledigt — Fixture
`kommission_nachkommastellen.json`, drei Tests und Vertrag Regel 5
präzisiert. Die Tests schlagen gegen den jetzigen `engine/matching.py` fehl und
bestehen gegen die unabhängige Referenz. **Offen:** Schritt (2), die
Nachbesserung in AP-03.

**Erledigt 12.09.2026:** Schritt (2) ist umgesetzt — die letzte Teilmenge trägt
den exakten Rest (`engine/matching.py`, `_kommission_verteilen`). Review: 101
Tests grün; der Differenztest gegen die unabhängige Referenz ergibt in 3.000
Szenarien mit Cent-Kommissionen und 3.000 mit vier Nachkommastellen identische
Legs, die Kommissionssumme je `conid` geht in allen 6.000 exakt auf.

## OF-19 · Der Flex-Import liest das echte IB-Format nicht

**Befund aus dem Golden-Lauf (12.09.2026), blockiert jeden Import echter
Daten.** Die synthetischen Fixtures bilden ein Format ab, das die echten
Exporte nicht haben; alle Tests laufen gegen dieses Format grün.

| | Import und Fixtures | Echte Exporte (beide) |
|---|---|---|
| Handelszeit der Trades | Attribut `tradeTime` | kein `tradeTime`, stattdessen `dateTime` |
| Zeitformat | `JJJJMMTT HH:MM:SS` | `JJJJMMTT;HHMMSS`; bei CashTransactions 158 von 327 und CorporateActions 4 von 12 nur `JJJJMMTT` |
| `FlexStatement.whenGenerated` | `JJJJMMTTTHHMMSS` | `JJJJMMTT;HHMMSS` |
| nur in den Fixtures | `FlexStatement.currency`, `OpenPosition.markValue` | — |

Ohne Anpassung scheitert der Import an der ersten Ausführung beider Exporte
(Pflichtfeld `tradeTime` fehlt). Mit einer provisorischen Anpassung nur im
Speicher lassen sich alle 18.049 Ausführungen lesen; die Umstellung auf
`dateTime` greift dabei 18.049-mal, das Zeitformat 18.226-mal, die reine
Datumsform 162-mal. Die übrigen vom Import gelesenen Attribute kommen im echten
Format vor.

**Vorschlag:** Korrekturpaket zu AP-02 (starkes Modell, `aendert_tests: ja`):
Fixtures unter `fixtures/flex/` auf das echte Attributschema und die echten
Zeitformen umstellen; danach Nachbesserung des Imports gegen diese Fixtures.
Für künftige Abnahmebasen: Ein synthetisches Fixture wird am Attributschema
eines echten Exports geprüft, bevor es unveränderlich wird.

**Umgesetzt in AP-02k (13.09.2026).** Alle neun Fixtures unter
`fixtures/flex/` sind inhaltlich unverändert, nur auf das echte Format
umgestellt (`dateTime` statt `tradeTime`, `JJJJMMTT;HHMMSS`, `levelOfDetail`
je Zeile, kein `FlexStatement.currency`/`OpenPosition.markValue`).
`activity_2026_01.xml` enthält zusätzlich eine CashTransaction in reiner
Datumsform, damit die dokumentierte Annahme „ohne Uhrzeit heißt 00:00:00"
(Regel 1 des Vertrags in `auftraege/AP-02k.md`) mitgeprüft wird. Der
Schema-Abgleich jedes Fixtures gegen die gemessene Tabelle ist durchgeführt
(Attributnamen, Zeitformen, Ebenen) — ohne Befund. Der Import selbst ist noch
nicht nachgebessert; `ingest/flex.py` gehört nicht zu AP-02k.

## OF-20 · `notes = P` ist eine Teilausführung, kein unklassifiziertes Ereignis

**Befund aus dem Golden-Lauf (12.09.2026); widerlegt die Annahme aus OF-07 und
die Behandlung in OF-16.** In beiden Exporten (266 und 1.972 Zeilen) haben
P-Zeilen dasselbe Profil wie gewöhnliche Börsenausführungen:
`transactionType = ExchTrade`, eigene `ibExecID`, Börse und Preis gesetzt, und
jede P-Zeile gehört zu einer Order mit mehreren Ausführungen. Echte Ereignisse
(`Ep`, `A`, `Ex`) sind dagegen `BookTrade` ohne `ibExecID`. `P` kennzeichnet
die Teilausführung einer Order.

**Wirkung im Matching** (Export 2026, provisorischer Import im Speicher):

| | P = unbekannt (wie implementiert) | P = trade |
|---|---|---|
| Ausführungen nicht gematcht | 1.972 (14 %) | 0 |
| IB-Schließungen (`C`), die im Matching voll schließen | 2.122 von 2.377 (89,3 %) | 2.365 von 2.377 (99,5 %) |
| offene Positionen am Stichtag gleich IB | 171 | 174 von 180 |
| nur im Matching offen | 552 | 44 |

Die 12 verbleibenden C-Zeilen sind jeweils die erste Ausführung ihrer `conid`,
schließen also Bestand aus der Zeit vor dem Export.

**Vorschlag:** Der Import ordnet `P` dem `ereignistyp = 'trade'` zu,
`ereignis_code = 'P'` bleibt erhalten. Das betrifft `ingest/flex.py` und den
Test `test_unclassified_event_code_p_is_stored_as_unbekannt`, gehört also in
dasselbe Korrekturpaket wie OF-19. OF-16 bleibt als Regel für künftig
unbekannte Codes bestehen, trifft `P` aber nicht mehr.

**Nachtrag 13.09.2026 (Jahresexporte 2022–2026):** Weitere Codes treten auf:
`IA` (8), `L` (1) und die zusammengesetzten Codes `IA;P` (1) und `FP;P` (1).
Alle diese Zeilen sind `ExchTrade` mit eigener `ibExecID` und Börse, also
gewöhnliche Ausführungen mit Zusatzkennzeichen. `notes` ist damit eine durch
`;` getrennte Liste. **Vorschlag:** `Ep`, `Ex` und `A` bestimmen den
Ereignistyp; die gemessenen Zusatzkennzeichen `P`, `IA`, `FP` und `L` ergeben
`trade`; jeder andere Code bricht weiter ab (OF-08) — Kennzeichen etwa für
stornierte oder korrigierte Ausführungen dürfen nicht still als Trade
durchgehen.

**Umgesetzt in AP-02k (13.09.2026).** `tests/test_ingest_flex.py`:
`test_unclassified_event_code_p_is_stored_as_unbekannt` heißt jetzt
`test_partial_execution_code_p_is_a_trade` und erwartet `ereignistyp='trade'`.
`tests/test_ingest_flex_format.py` deckt zusätzlich die Codeliste ab: die
Zusatzkennzeichen `IA`, `L`, `IA;P`, `FP;P` ergeben `trade`; ein Ereigniscode
innerhalb einer Liste (z. B. `IA;Ex`) bestimmt weiterhin den Ereignistyp; ein
unbekannter Code und zwei Ereigniscodes in einer Liste brechen ab. Der Import
selbst liest `notes` noch nicht als Liste — das macht die Nachbesserung von
AP-02.

## OF-21 · Die Abnahme von AP-03 ist mit den vorliegenden Exporten nicht belegbar

**Befund aus dem Golden-Lauf (12.09.2026).** Plan §6 verlangt für AP-03 die
Summenprobe gegen die Broker-Summe und den Abgleich gegen die
Closed-Lots-Ebene. Beides geht mit diesen Exporten nicht:

1. **Kein Broker-P&L:** `fifoPnlRealized` ist in allen 18.049 Trades 0; eine
   P&L-Zusammenfassung enthält keiner der Exporte.
2. **Keine Closed Lots:** Die Trades liegen nur auf der Ebene `EXECUTION` vor.
3. **Lücke in der Historie:** Die Exporte decken 04/2022–03/2023 und
   01–09/2026 ab. Bestände aus der Zeit dazwischen sind unbekannt.

**Was an Echtdaten trotzdem belegt ist** (mit `P = trade`, provisorischem
Import im Speicher, nur Zählwerte): 174 von 180 offenen Positionen stimmen am
Stichtag exakt mit IBs OpenPositions überein; 99,5 % der IB-Schließungen
schließen im Matching voll. Die übrigen 50 abweichenden `conid`s sind einzeln
eingeordnet. 48 passen zur Lücke in der Historie — die erste Ausführung
schließt einen unbekannten Bestand (etwa 15 Aktienverkäufe ohne vorherigen Kauf,
12 Optionen aus vermutetem Vortrag) oder ein Bestand hat im Zeitraum gar keine
Ausführung. Belegen lässt sich diese Erklärung erst mit den fehlenden
Jahresexporten. Nicht so erklärbar sind 2: ein Optionsleg mit Verfallsbuchung,
das ohne vermuteten Vortrag offen bleibt, und eine Aktie mit Zuteilung.

**Nötig für eine belastbare Abnahme (AP-00, Portal):** in der Flex-Abfrage den
realisierten P&L und die Ebene Closed Lots aktivieren; die fehlenden
Jahresexporte 2023/24, 2024/25 und 2025/26 abrufen (§6.2).

**Nachtrag 13.09.2026:** Die Jahresexporte 2022 bis 2026 schließen die Lücke.
**Closed Lots und realisierter P&L fehlen aber weiterhin in allen sechs
Dateien**, auch im Export bis 11.09.2026: Trades nur auf Ebene `EXECUTION`,
`fifoPnlRealized` überall 0. Die Summenprobe bleibt damit unmöglich.

Ersatzweise ist das Matching über die ganze Historie gegen IBs Bestände
geprüft — provisorischer Import im Speicher, 32.475 Ausführungen nach Entfernen
von 14.078 dateiübergreifenden Dubletten über `tradeID`, nur Zählwerte:

| Stichtag | IB-Positionen | gleich | nur IB | nur Matching | Menge verschieden |
|---|---|---|---|---|---|
| 30.12.2022 | 143 | 136 | 7 | 0 | 0 |
| 29.12.2023 | 43 | 38 | 5 | 0 | 0 |
| 31.12.2024 | 61 | 48 | 10 | 4 | 3 |
| 31.12.2025 | 49 | 48 | 0 | 13 | 1 |
| 01.09.2026 | 180 | 179 | 1 | 14 | 0 |
| 11.09.2026 | 180 | 179 | 1 | 14 | 0 |

Die Abweichungen haben zwei Ursachen: Optionen mit Verfall am oder vor dem
Stichtag, die IBs Bestand noch führt (21 Fälle 2022–2024), und
Kapitalmaßnahmen, die das Matching noch nicht anwendet, weil
`corporate_actions` bisher nicht befüllt wird (OF-15). Alle Abweichungen 2025
und 2026 tragen eine Kapitalmaßnahme. Ohne erkennbare Ursache bleiben zwei
Aktien mit abweichender Menge am 31.12.2024. Ein Fehler des Matchings selbst
ist nicht erkennbar.

**Vorschlag für die Abnahme von AP-03 (Entscheidung Planer und Nutzer):**
Solange die Flex-Abfrage keine Closed Lots liefert, gilt der Bestandsabgleich
je Stichtag als Ersatz für die Summenprobe; Kapitalmaßnahmen werden als
bekannte, eigens zu lösende Ursache ausgewiesen.

**Entscheidung und Nachtrag 13.09.2026:** Closed Lots sind endgültig kein
Weg — auch mit den Optionen Execution und Closed Lots liefert die Abfrage keine
Lot-Zeilen (drei Testexporte). Der Bestandsabgleich ist als Ersatz dafür
angenommen, **als Abnahme von AP-03 aber nicht ausreichend**: Er prüft, welche
Positionen offen sind, nicht, wie viel Geld realisiert wurde. Dafür kommt ein
Geldtest hinzu (realisiertes Ergebnis je Jahr und Anlageklasse gegen die
Jahressummen der Kontoauszüge).

**Jede Abweichung zugeordnet.** Mit zwei Regeln verschwinden alle
Abweichungen an allen fünf Stichtagen (30.12.2022, 29.12.2023, 31.12.2024,
31.12.2025, 11.09.2026). Jede einzelne ist einer konkreten Ursache
zugewiesen; die Liste liegt pseudonymisiert vor, Klarnamen gehören nach
Regel 2 nicht ins Repo.

1. **Stichtag nach Buchungstag (`reportDate`), nicht nach Handelstag.** IB
   zählt eine Buchung zum Bestand eines Stichtags, wenn ihr `reportDate`
   nicht danach liegt. Das erklärt alle Verfälle am Stichtag (7, 5 und 7 Fälle
   2022–2024) und 4 weitere am 31.12.2024 gehandelte, aber erst im Januar
   gebuchte Ausführungen (2 Aktien, 2 Optionen). Eine pauschale Regel „am
   Stichtag verfallende Optionen zählen noch zum Bestand" wäre falsch: Sie
   erzeugt am 31.12.2025 und 11.09.2026 16 bzw. 34 neue Abweichungen, weil
   Verfall und Buchung dort auf denselben Tag fallen.
2. **Kapitalmaßnahmen als Abgang und Zugang je `conid`.** So gebucht, lösen sie
   alle übrigen Abweichungen auf — 6 am 31.12.2024, 14 am 31.12.2025, 15 am
   11.09.2026 —, jede einer bestimmten Maßnahme mit Art, Richtung und Datum
   zugeordnet. Wie das im Vertrag abzubilden ist, steht in OF-23.

**Ergebnis: 0 Abweichungen an allen fünf Stichtagen.** Die 17 Abweichungen am
31.12.2024 (13 IB-Positionen und 4 nur im Matching) teilen sich auf in 11 nach
Buchungstag und 6 nach Kapitalmaßnahme.

**Offen:** (a) Für Bestände zum Stichtag gilt der Buchungstag; `executions`
führt ihn bisher nur in `roh_json`. Ob er eine eigene Spalte braucht, ist mit
dem Paket zu entscheiden, das Bestandsauswertungen baut. (b) Der Geldtest
braucht die Jahressummen des realisierten Ergebnisses; sie liegen nicht vor.

**Stand 13.09.2026, spät:** Die Stichtagsregel nach Buchungstag ist
angenommen und im Plan nachgezogen; die pauschale Verfallsregel ist ersatzlos
gestrichen. Die Ursache für fehlende Closed Lots und den überall leeren
`fifoPnlRealized` ist geklärt (Plan, Planer): IB schaltet alle Felder und
Abschnitte zum realisierten Ergebnis ab, sobald ein Modell einbezogen ist, und
alle bisherigen Exporte trugen `model="Independent"`. Die ohne Modellauswahl
gezogenen Exporte liefern Closed Lots, `fifoPnlRealized` und den Abschnitt
`FIFOPerformanceSummaryInBase`. Die Abnahme bleibt dabei: Bestandsabgleich als
strukturelle Hälfte, Geldtest gegen die Ergebnissummen als monetäre Hälfte,
Closed Lots höchstens als Zweitmeinung. Offen ist (b) damit nicht mehr aus
Mangel an Daten; die Ergebnissummen liegen je Exportzeitraum (April bis März)
vor, nicht je Kalenderjahr.

## OF-22 · CashTransactions: doppelte `transactionID`s und doppelte Buchung über SUMMARY-Zeilen

**Befund aus dem Golden-Lauf (12.09.2026); blockiert den Import des Exports
2026 und würde Geldflüsse doppelt buchen.**

1. **Abbruch:** Dieselbe `transactionID` kommt in drei Fällen zweimal vor,
   jeweils als Paar `Broker Interest Paid` und `Broker Interest Received` mit
   gleichem Datum und gleicher Währung. Nach OF-09 Punkt 3 bricht der Import
   dann ab.
2. **Doppelte Buchung:** Der Export liefert CashTransactions auf zwei Ebenen —
   211 Zeilen `DETAIL`, alle mit `transactionID`, und 116 Zeilen `SUMMARY`,
   alle ohne. Jede Buchungsart kommt auf beiden Ebenen vor. Die SUMMARY-Zeilen
   sind Aggregate: Bei 110 von 116 entspricht ihr Betrag genau der Summe der
   DETAIL-Zeilen gleicher Art, Währung, `conid` und gleichen Tages; 6 weichen
   bei dieser Schlüsselwahl ab. Auch CorporateActions enthalten 4
   SUMMARY-Zeilen. Der Import übernimmt heute beide Ebenen — Zinsen,
   Dividenden, Quellensteuer und Gebühren stünden damit doppelt in der
   Datenbank.

**Vorschlag, Entscheidung nötig:** (a) Der Import übernimmt nur
`levelOfDetail = DETAIL`; SUMMARY-Zeilen werden nicht gebucht, aber gezählt und
im Importbericht ausgewiesen, eine unbekannte Ebene bricht ab. (b) Zusätzlich
die Flex-Abfrage im Portal auf DETAIL beschränken (AP-00). Für die Paare: der
Quellschlüssel besteht aus `transactionID` und `type`. Beides gehört in das
Korrekturpaket zu AP-02, zusammen mit OF-19 und OF-20.

**Nachtrag 13.09.2026 (alle sechs Exporte):** Die neuen Jahresexporte liefern
CashTransactions und CorporateActions nur noch auf Ebene `DETAIL`;
SUMMARY-Zeilen enthält nur noch der ältere Export bis 01.09.2026. Doppelte
`transactionID`s treten 2023, 2025 und in beiden 2026-Exporten auf (3–4 je
Datei), ausnahmslos als Paar `Broker Interest Paid` / `Broker Interest
Received`; **die Kombination aus `transactionID` und `type` ist in allen sechs
Dateien eindeutig.** Die übrigen Sektionen tragen andere Ebenen:
`OpenPosition` kommt als `SUMMARY`, `Transfer` als `TRANSFER`. Die
Ebenen-Regel muss deshalb je Sektion gelten — CashTransactions und
CorporateActions nur `DETAIL`, OpenPositions `SUMMARY`, Transfers `TRANSFER`;
jede andere Ebene bricht ab.

**Umgesetzt in AP-02k (13.09.2026).** `activity_doppelte_buchungs_id.xml`
trägt jetzt zwei Zeilen mit gleicher `transactionID` **und** gleichem `type`
(„Dividends") — nur so bleibt sie nach der neuen Identitätsregel
(`transactionID` + `type`) ein echter Duplikat-Fall; vorher hätte die
unterschiedliche Art (Dividends/Withholding Tax) sie zu zwei gültigen
Buchungen gemacht. `tests/test_ingest_flex_format.py` deckt zusätzlich ab:
SUMMARY-Zeilen werden gezählt, nicht gebucht (`nicht_gebuchte_zeilen`); ein
Interest-Paar mit gleicher `transactionID`, verschiedenem `type` bleibt zwei
Buchungen und verdoppelt sich bei erneutem Abruf nicht; OpenPositions/SUMMARY
und Transfers/TRANSFER lösen keinen Abbruch aus; eine CLOSED_LOT-CorporateAction
wird gezählt, nicht gebucht. Der Import selbst liest `levelOfDetail` und die
zusammengesetzte Identität noch nicht — das macht die Nachbesserung von AP-02.

## OF-23 · Kapitalmaßnahmen: Vertrag von AP-03 passt nicht zu IBs Buchungsform

**Befund 13.09.2026; Entscheidung nötig vor der Umsetzung.** Vertrag Regel 6
sieht einen Faktor auf derselben `conid` vor (Menge × Faktor, Preis ÷ Faktor).
IB bucht Kapitalmaßnahmen anders. Von den 10 Maßnahmen in den Exporten
2022–2026 buchen 7 einen Abgang auf der alten und einen Zugang auf einer
**neuen** `conid` (3 × RS, je 1 × FI, FS, TO, TC); 2 (DI) sind reine Zugänge;
1 (ED) betrifft keinen gehandelten Titel. Bei den Optionsanpassungen (FS, FI)
weicht das Mengenverhältnis vom Split-Verhältnis ab — IB ändert dort offenbar
auch Kontraktgröße oder Lieferumfang.

**Für den Bestand genügt Abgang und Zugang** (belegt in OF-21: 0 Abweichungen).
**Für das Geld nicht:** Würde der Abgang wie ein Verkauf zu 0 gebucht,
entstünde ein realisierter Scheinverlust in Höhe der Anschaffungskosten und
beim späteren Verkauf der neuen `conid` ein Scheingewinn. Eine
Kapitalmaßnahme darf nichts realisieren.

**Vorschlag:** Regel 6 neu fassen — eine Kapitalmaßnahme überträgt die offenen
Lots der alten auf die neue `conid`: Menge nach IB-Buchung, Anschaffungskosten
je Lot unverändert (der Preis je Stück wird entsprechend umgerechnet),
Eröffnungsausführung und Eröffnungszeit bleiben erhalten, realisiert wird
nichts. Für reine Zugänge (DI) ist zu entscheiden, ob sie ein Lot mit Kosten 0
oder mit IBs Kostenangabe eröffnen. Umsetzung: Vorbereitungspaket mit
Fixtures je Maßnahmenart (starkes Modell), dann Nachbesserung von AP-03 und
Befüllen von `corporate_actions` im Import.

**Entschieden 13.09.2026 (Planer, im Plan nachgezogen):** Der Vorschlag ist
angenommen — offene Lots wandern auf die neue `conid`, Anschaffungskosten,
Eröffnungsausführung und Eröffnungszeit bleiben erhalten, realisiert wird
nichts. Ergänzt um:

1. **Die Kette überlebt den Übergang.** Alte und neue `conid` gehören zu
   derselben Position; die Maßnahme erscheint als Ereignis im Zeitstrahl der
   Detailansicht. Keine Position darf ihr Instrument unerklärt wechseln.
2. **Angepasste Optionskontrakte tragen ein Kennzeichen am Instrument.** Nach
   einem Split ist der Lieferumfang nicht mehr standardisiert; die Analytik
   darf deren Strikes und Multiplikatoren nicht mit Standardkontrakten
   vergleichen.
3. **Reine Zugänge:** IBs Kostenangabe, wo eine vorliegt. Meldet IB null, wird
   nicht null gebucht, sondern das Lot mit `basis_ungeklaert` gekennzeichnet
   und der Einzelfall hier eingetragen — eine stille Nullbasis erzeugt beim
   späteren Verkauf einen Scheingewinn in voller Höhe und ist über AP-10
   steuerlich relevant.

**Umgesetzt 13.09.2026 (AP-03vm, AP-03):** Vertrag Regel 6 in `engine/matching.py`
neu gefasst — Kapitalmaßnahmen sind ein Transfer auf eine neue `conid`
(`alter_conid`/`neuer_conid`, Faktor aus `alte_menge`/`neue_menge`), reine
Zugänge eröffnen ein synthetisches Lot mit `basis_ungeklaert = True`, wenn
IB keine Kostenangabe liefert. `legs.basis_ungeklaert`, `instruments.angepasst`
und die neue `corporate_actions`-Form liegen als Migration `d7c4b6a1f9e3` vor.
**Weiterhin offen, außerhalb dieser Nachbesserung:** Punkt 1 (die Kette
überlebt den Übergang) gehört zur Struktur-/Kettenerkennung in AP-04; Punkt 2
(`instruments.angepasst` setzen) und das Befüllen von `corporate_actions` aus
`flex_corporate_actions` sind eigene, noch nicht begonnene Pakete — bis dahin
nimmt `bilde_legs` `kapitalmassnahmen` nur als Eingabe entgegen, leitet sie
aber nicht selbst aus dem Import ab.

**Währung (entschieden, Plan):** Maßgeblich ist `fxRateToBase` an der
jeweiligen Ausführung — IBs eigener Buchungskurs, mit Bezugszeitpunkt
gespeichert (P4). Basiswährung ist EUR; die EUR-Zeilen tragen den Kurs 1.

**Gemessen 13.09.2026, zur Bestätigung:** IB rechnet das realisierte Ergebnis
einer Schließung **vollständig mit dem `fxRateToBase` der schließenden
Ausführung** um — nicht die Anschaffungskosten zum Eröffnungskurs und den Erlös
zum Schließkurs. In den Zeiträumen 04/2023 bis 09/2026 entspricht IBs Summe in
EUR bei 11.757 `conid`s in Fremdwährung genau der Summe von
`fifoPnlRealized × fxRateToBase` ihrer Ausführungen; 13 haben keine
Entsprechung. „Maßgeblich ist `fxRateToBase` an der jeweiligen Ausführung" ist
damit zu präzisieren: an der schließenden. Eine getrennte Umrechnung von Kosten
und Erlös wäre eine andere Methodik und verfehlt den Abgleich deutlich; ob sie
für die Steuer (AP-10) geboten ist, ist eine eigene Frage.

**Entschieden 13.09.2026 (Planer, im Plan nachgezogen), getrennt nach Zweck:**
Für den **Abgleich mit IB** gilt IBs Konvention — der Kurs der schließenden
Ausführung auf das gesamte realisierte Ergebnis. Für das **Journal** ist die
maßgebliche Zahl das Ergebnis in Instrumentwährung (P4). Daraus werden zwei
Sichten abgeleitet: die IB-vergleichbare mit dem Schlusskurs und die
wirtschaftliche mit dem jeweiligen Kurs je Zahlungsstrom; deren Differenz wird
als Währungseffekt ausgewiesen.

**Vor der Abnahme offen:** Die 13 Ausnahmen von der Umrechnungsregel sind
einzeln zu benennen. Bestätigt sich eine gemeinsame Ursache, wird die Regel
verfeinert, statt die Fälle zu dulden. Die Messung rechnet bereits je
Ausführung mit deren eigenem Kurs; mehrere Schließungen zu verschiedenen
Kursen sind darin enthalten. Zu prüfen sind deshalb vor allem `costAdj` und
`transferredPnl` der IB-Zusammenfassung.

**Einzeln benannt (13.09.2026):** Über alle fünf Zeiträume sind es 14 Ausnahmen
(der Zeitraum 2022/23 war in der ersten Zählung nicht enthalten).
- **12 sind CASH-Positionen ohne eine einzige realisierende Ausführung.** IB
  weist dort ein realisiertes Ergebnis aus dem Devisenumtausch selbst aus; es
  entsteht nicht aus einem Trade und liegt außerhalb des Matchings (CASH ist
  ausgeschlossen). Eine Verfeinerung der Regel ist dafür nicht nötig; ob das
  Journal Devisenergebnisse führen soll, ist eine eigene Frage.
- **2 sind Aktien** mit je einer realisierenden Ausführung und einem Kurs,
  Differenz unter 1 %, `costAdj` gesetzt. `costAdj` erklärt die Differenz
  weder in lokaler Währung noch umgerechnet. **Noch ohne Ursache.**

Die Vermutung „mehrere Schließungen zu verschiedenen Kursen" trifft auf keine
der 14 zu.

## OF-24 · Prämie bei Zuteilung und Ausübung: IB verrechnet sie in die Aktienbasis

**Befund aus dem Geldtest (13.09.2026); Entscheidung nötig.** Verglichen wurde
je schließender Ausführung IBs `fifoPnlRealized` mit Brutto plus Kommission des
Matchings, in lokaler Währung, über 32.475 Ausführungen 04/2022–09/2026
(provisorischer Import im Speicher, nur Zählwerte):

- Optionen: 14.040 von 15.261 centgenau; Futures und FOP: alle. Die
  Abweichungen bei Optionen liegen fast ausschließlich an Zuteilungen und
  Ausübungen — bei 603 davon meldet IB ein realisiertes Ergebnis von 0.
- Aktien: 407 Abweichungen, fast alle an Aktien aus Zuteilung oder Ausübung,
  mit denselben Lots wie IB, aber anderem Betrag.

**Nachweis je Basiswert** (Differenz Matching − IB über die ganze Historie,
Optionen und Aktien zusammen): exakt bei 126 von 127 Basiswerten ohne
Zuteilung (der letzte ≤ 1 €); bei den 161 Basiswerten mit Zuteilung oder
Ausübung exakt bei 106 und ≤ 1 € bei 17. IB verrechnet die Prämie also in
Anschaffungskosten beziehungsweise Erlös der Aktie; das Matching realisiert sie
an der Option. Offen in der Einzelzuordnung: 13 Basiswerte mit noch offener
Aktie aus Zuteilung, bei denen die Prämie in IBs Anschaffungskosten steckt, und
25 weitere.

**Nachtrag:** Die 13 Basiswerte mit offener Aktie sind einzeln belegt — ihre
Differenz entspricht bis auf höchstens 1 € der Differenz zwischen den
Anschaffungskosten des Matchings und IBs `costBasisMoney` der noch offenen
Aktien, also genau der dort geparkten Prämie. Die übrigen 25 werden mit einer
Zuordnung über `underlyingConid` statt über das Symbol nachgeprüft.

**Stand nach Zuordnung über `underlyingConid`** (Basiswerte über
Kapitalmaßnahmen hinweg verkettet): ohne Zuteilung 127 exakt, 1 ≤ 1 €; mit
Zuteilung oder Ausübung 108 exakt, 17 ≤ 1 €, 13 durch Prämie in offener
Aktienbasis belegt, **19 offen**. Die Symbol-Zuordnung hatte 6 Fälle
fälschlich getrennt. Von den 19 hat keiner ein IB-Lot aus der Zeit vor Beginn
der Historie, einer eine Kapitalmaßnahme; bei 8 weichen nur die Optionen ab,
bei 11 Optionen und Aktien. Rest gemessen am IB-Ergebnisvolumen des
Basiswerts: 5 × unter 1 %, 8 × 1–10 %, 6 × über 10 %. Diese 19 sind noch nicht
einer konkreten Ursache zugeordnet.

**Entschieden 13.09.2026 (Planer, im Plan nachgezogen): (b).** Nicht als
Kompromiss, sondern weil (a) Information vernichtet: Aus (b) lässt sich (a)
jederzeit herstellen, indem die Prämie in die Basis geschoben wird — umgekehrt
ist das eigenständige Ergebnis der Option nicht mehr rekonstruierbar. Unter (a)
zeigte ausgerechnet die zugeteilte Option kein Ergebnis, und die Performance
einer automatisierten Optionsstrategie wanderte in eine spätere, diskretionäre
Aktienentscheidung, womöglich in ein anderes Jahr.

**Auflage:** Die in offenen Aktien geparkte Prämie wird **je Zuteilung als
eigener Wert gespeichert**, nicht nur beim Abgleich errechnet. Die Überleitung
zu IB schließt damit exakt, und die IB-Sicht bleibt für Abgleich,
Steuerexport und künftige Fragen ableitbar.

**Steuer:** vor AP-10 mit dem Steuerberater zu klären. (b) hält beide Wege
offen, (a) nur einen.

**Vor der Abnahme offen:** Die Überleitung muss exakt schließen, nicht
innerhalb einer Toleranz. Einzeln zuzuordnen sind deshalb die 19 offenen
Basiswerte **und** die 17 mit Abweichung bis 1 €.

**Stand der Einzelzuordnung (13.09.2026, pseudonymisiert B01–B36):**
- 639 Zuteilungen und Ausübungen *mit* Aktienlieferung tragen bei IB ein
  realisiertes Ergebnis von 0 — die Prämie wandert vollständig in die
  Aktienbasis. Das Muster ist damit an jeder einzelnen Zeile belegt.
- **6 offene Basiswerte** (B20, B27, B28, B30, B32, B36): Der Rest entspricht
  genau der Summe ihrer Zuteilungen und Ausübungen *ohne* Aktienlieferung —
  Ursache ist der fehlende Barausgleich (OF-25).
- **13 offene** (B18, B19, B21–B26, B29, B31, B33–B35) und **17 knappe**
  (B01–B17): Der Rest entspricht weder der Kommission der zugeteilten Optionen
  noch dem Barausgleich. Noch ohne Ursache; als Nächstes je Lieferung statt je
  Basiswert zu prüfen.
- **Die 17 knappen (B01–B17):** Der Rest liegt bei allen innerhalb einer
  Rundung je gelieferter Aktie — 14 × höchstens 0,0001 € je Aktie, 3 ×
  höchstens 0,005 €. Das spricht für eine Rundung, mit der IB die Prämie je
  Aktie in die Basis umlegt. Die exakte Rundungsregel ist noch nicht belegt.
- **B19 und B29** haben keine Aktienlieferung, gehören also zum Barausgleich,
  enthalten aber noch einen weiteren Anteil.

**Stand nach provisorischem Barausgleich (OF-25), 13.09.2026:** Basiswerte
ohne Zuteilung 127 exakt, 1 bis 1 €; mit Zuteilung oder Ausübung 114 exakt,
13 durch Prämie in offener Aktienbasis belegt, 19 bis 1 € (B01–B17, B19, B29),
**11 offen: B18, B21–B26, B31, B33–B35**. Alle 11 haben physische Lieferung;
IBs Lots ihrer Aktienschließungen verweisen auf die Lieferzeilen (41) und auf
gewöhnliche Käufe (6). Die Verknüpfung trägt also, die Ursache des Rests ist
noch nicht benannt.

**Re-Lauf 14.09.2026, mit dem echten, jetzt korrigierten Import und
Matching** (`werkzeuge/abgleich/golden_geldtest_fifopnl.py`, neu ins Repo
übernommen). Anders als oben **je schließender Ausführung**, nicht je
Basiswert aufsummiert — ein strengerer, feinerer Maßstab, die Zahlen sind
mit denen oben deshalb nicht direkt vergleichbar (Abweichungen können sich
über die Ausführungen eines Basiswerts hinweg aufheben, wenn je Basiswert
aufsummiert wird). Von 15.672 vergleichbaren, schließenden Ausführungen
(Kapitalmaßnahmen-`conid`s ausgeklammert, s. OF-27) treffen **14.612 genau
(±0,02 Lokalwährung), 93,2 %**. Aufgeschlüsselt:

| Anlageklasse/Ereignistyp/Underlying zuteilungsberührt | Trefferquote |
|---|---|
| OPT/`expiry`/nein | 228/228 — 100 % |
| OPT/`expiry`/ja | 5.557/5.558 — 100 % |
| OPT/`trade`/ja | 7.679/7.708 — 99,6 % |
| OPT/`trade`/nein | 617/621 — 99,4 % |
| OPT/`exercise`/ja | 233/259 — 90,0 % |
| OPT/`assignment`/ja | 268/881 — 30,4 % |
| STK/`trade`/ja | 4/175 — 2,3 % |
| STK/`assignment`/ja | 0/204 — 0 % |

**Korrektur einer ersten, zu pessimistischen Messung (17.09.2026).** Die
erste Fassung dieses Re-Laufs meldete 59,2 % und einen großen, ungeklärten
Rest auch bei unberührten Optionsgeschäften. Beides war ein Fehler des
Abgleichsskripts, nicht der Engine: Die Referenz `fifoPnlRealized` wurde je
`tradeID` aus der zuerst gelesenen Datei genommen. In den Exporten mit
`model="Independent"` schaltet IB aber alle Felder zum realisierten Ergebnis
ab (OF-21) — dort steht überall 0. Gemessen: 14.009 `tradeID`s kommen in
beiden Exportvarianten vor, und **in jedem einzelnen Fall** steht die 0 im
Modell-Export und der echte Wert im modellfreien. Das Skript liest die
Referenz jetzt ausschließlich aus modellfreien Zeilen (29.939 Modellzeilen
übergangen, keine Ausführung bleibt dadurch ohne Referenz).

**Damit derselbe Fehler nicht wiederkehren kann**, steht die Eigenschaft
seit AP-02m nicht mehr nur hier, sondern als Datenfeld am Importlauf:
`import_runs.realized_pnl_verfuegbar` ist falsch, sobald der Export
Modell-Attribute trägt (Plan §5, Vertrag AP-02 Regel 8). Ein Befund in einer
Textdatei wirkt nicht — genau das ist hier passiert.

**Damit bleibt genau ein großes Muster übrig — das schon entschiedene.**
Verfall und gewöhnlicher Optionshandel schließen praktisch vollständig
(99,4 % bis 100 %). Die Abweichungen sitzen bei Zuteilung, Ausübung und den
daraus entstandenen Aktien: `STK`/`assignment` 0 von 204, `STK`/`trade` 4 von
175, `OPT`/`assignment` 268 von 881, dazu 26 `exercise`-Zeilen, bei denen IB
ein realisiertes Ergebnis von **0** meldet, obwohl die Option erlischt. Das
ist dieselbe Prämie, die IB in die Aktienbasis verrechnet und das Matching an
der Option realisiert — **die Auflage aus der Entscheidung oben ist nach wie
vor nicht umgesetzt.**

**Rest außerhalb des Prämienmusters: 34 Ausführungen** (33 `trade`,
1 `expiry`) auf 18 `conid`s, alle mit einem IB-Wert ungleich 0.

**Das ist eine Verteilungs-, keine Betragsdifferenz — gemessen 17.09.2026.**
Bei **16 der 18 betroffenen `conid`s heben sich die Abweichungen exakt zu 0
auf** (±0,02): Über das Instrument gerechnet stimmt das realisierte Ergebnis
mit IB überein, nur die Zuordnung auf die einzelnen Schließungen ist eine
andere. Dazu passt: 27 der 34 Fälle haben auf derselben `conid`
**zeitgleiche Ausführungen**, und bei gleichem Zeitstempel entscheidet im
Matching die `exec_id` über die FIFO-Reihenfolge, während IB anders zuordnen
kann. Ausgeschlossen sind Teilschließungen (0 Fälle) und Ereigniszeilen als
Eröffnung (0).

**Gegenprobe zur Gleichstandsregel (17.09.2026): sie ist bereits erfüllt und
ändert nichts.** Der Plan hält fest, der FIFO-Gleichstand sei nach `tradeID`
aufsteigend aufzulösen, weil IBs Zuordnung derselben Ordnung folge. Gemessen:
`exec_id` **ist** die `tradeID` (AP-02a), und das Matching sortiert bei
gleicher Handelszeit genau danach. Die `tradeID`s sind 9- oder 10-stellig, in
**allen 34** Fällen sind die beteiligten jedoch gleich lang — lexikografische
und numerische Ordnung fallen damit zusammen. Ein Lauf mit erzwungen
numerischer Sortierung (nullgepolsterte `exec_id`) liefert dieselbe
Trefferquote, 14.612 von 15.672, **Differenz null Ausführungen**. Die Annahme
„IB folgt derselben Ordnung" ist damit für diese Daten **nicht bestätigt**;
die abweichende Zuordnung hat eine andere, noch unbekannte Ursache. Der
Plansatz sollte entsprechend abgeschwächt werden.

**Bewertung:** Kein Geld geht verloren oder entsteht; betroffen ist allein,
welchem Los eine Schließung zugerechnet wird. Für den Geldtest je Jahr und
Anlageklasse ist das folgenlos, für eine Leg-genaue Darstellung nicht. Eine
Vereinheitlichung der Reihenfolge bei Gleichstand wäre nur sinnvoll, wenn IBs
Regel dafür bekannt ist — sie ist es nicht, und geraten wird sie nicht
(Regel 10). Die zwei `conid`s ohne Ausgleich bleiben offen.

**Vor der nächsten Runde am Geldtest zu klären:** ob die schon
**entschiedene** Auflage („Prämie je Zuteilung als eigener Wert speichern“)
umgesetzt wird, bevor der kleine Rest weiter zerlegt wird — der große Teil
der Abweichungen geht nachweislich darin auf. Die Auflage braucht die
Verknüpfung Option ↔ Aktienlieferung (`assignment_links`) und gehört damit
zu AP-04, nicht zu AP-03.

## OF-25 · Barausgleich bei Zuteilung und Ausübung fehlt im Matching

**Befund aus dem Geldtest (13.09.2026); blockiert die Abnahme von AP-03.**
501 Zuteilungen und Ausübungen von Optionen erfolgen ohne Aktienlieferung —
barausgeglichene Optionen, etwa auf Indizes. Ihre Zeilen tragen `tradePrice =
0` und `proceeds = 0`, IB meldet aber ein realisiertes Ergebnis ungleich 0. Das
Matching schließt sie nach Vertrag Regel 7 zum Preis der Ereigniszeile, also
zu 0, und realisiert damit nur die Prämie; der Barausgleich fehlt. Bei 6
Basiswerten erklärt genau das den gesamten Rest.

**Offen:** In welchem Feld oder welcher Buchung der Ausgleichsbetrag steht
(`closePrice`, `mtmPnl`, eine Kassenbuchung am selben Tag oder nur implizit im
`fifoPnlRealized`). Erst dann lässt sich Regel 7 für barausgeglichene Optionen
fassen und in Tests gießen — ohne diese Kenntnis wäre jede Regel geraten.

**Geklärt 13.09.2026:** Bei **allen 501 Zeilen** entspricht die fehlende
Differenz genau `−quantity × multiplier × closePrice` (gleichbedeutend mit
`−mtmPnl`). Der Ausgleichsbetrag steht im `closePrice` der Ereigniszeile.
**Vorschlag für Vertrag Regel 7:** Eine Zuteilung oder Ausübung ohne
zugehörige Aktienlieferung schließt zum `closePrice`, nicht zum `tradePrice`.
Das erfordert, dass der Import `closePrice` an der Ausführung führt, und eine
feste Erkennung „ohne Lieferung" — bisher nur provisorisch über eine
Aktienzeile zur selben Zeit am selben Basiswert. Entscheidung nötig vor den
Tests.

**Gegenprobe 13.09.2026:** Mit dem Schluss zum `closePrice` stimmen alle 501
Schließungen centgenau mit IB; die centgenauen Optionsschließungen steigen von
14.040 auf 14.541. Die 6 Basiswerte B20, B27, B28, B30, B32 und B36 schließen
exakt, B19 und B29 bis auf höchstens 1 €. Die Regel ist damit belegt.

**Erkennung am Instrument (13.09.2026):** `SecurityInfo.settlementPolicyMethod`
trennt die beiden Fälle ohne Ausnahme — alle 639 Zuteilungen und Ausübungen
mit Aktienlieferung tragen `Delivery`, alle 501 ohne Lieferung tragen `Cash`.
`deliveryType` ist in Trade und SecurityInfo durchgehend leer. Die
provisorische Erkennung über eine Aktienzeile zur selben Zeit wird damit
überflüssig.

**Vorschlag, Entscheidung nötig:**
- Vertrag Regel 7: Eine Zuteilung oder Ausübung einer Option mit
  Abwicklungsart `Cash` schließt zum `closePrice` der Ereigniszeile; bei
  `Delivery` bleibt es beim Preis der Ereigniszeile. Fehlt die Abwicklungsart,
  bricht der Lauf ab — kein Raten.
- Import: `instruments` führt die Abwicklungsart, `executions` den
  `closePrice`. Das ist eine Schemaänderung, also eine Migration in der
  Nachbesserung von AP-02.
- Abnahmebasis: Fixtures und Tests dafür gehören in ein Vorbereitungs- oder
  Korrekturpaket des starken Modells — für den Import zu AP-02k, für das
  Matching zu AP-03.

**Entschieden 13.09.2026 (Nutzer): wie vorgeschlagen.** Benennung nach
Projektkonvention: `instruments.abwicklungsart` mit `lieferung` oder
`barausgleich`, `executions.schlusskurs`. Fehlt die Abwicklungsart, bricht
nicht der Import ab, sondern das Matching bei der betroffenen Zuteilung oder
Ausübung. Eingetragen in AP-02k (Regel 6, Tests 15–17) und in AP-03, Regel 7
(Vertrag). Die Tests für das Matching folgen als eigenes Korrekturpaket.

**Zu entscheiden:** Welche Methode führt das Journal?

- (a) **Wie IB:** Prämie in die Aktienbasis. Der Abgleich gegen IB wird exakt,
  eine zugeteilte Option zeigt aber kein eigenes Ergebnis.
- (b) **Wie bisher:** Ergebnis an der Option. Der Geldtest vergleicht dann je
  Basiswert statt je Anlageklasse und weist die in offenen Aktien steckende
  Prämie gesondert aus.

Zu bedenken: Für Strategie- und Kettenauswertung (AP-04, AP-05) ist die Prämie
Teil des Optionsergebnisses. Steuerlich (AP-10) muss die deutsche Behandlung von
Stillhalterprämien nicht IBs Methodik folgen; das ist eigens zu prüfen und nicht
aus IBs Zahlen abzuleiten.

**Nachtrag 13.09.2026:** Die ohne Modell gezogenen Exporte enthalten
Kapitalmaßnahmen auch auf der Ebene `CLOSED_LOT`, genau zwei (TC und ED). Beide
tragen `fifoPnlRealized = 0` — sie realisieren nichts, die Regel bleibt
ausnahmslos belegt. Eine erste, vorschnelle Vermutung, solche Zeilen stünden
für realisierende Maßnahmen, hat sich damit nicht bestätigt. Offen bleibt nur
der Fall einer Maßnahme mit Barausgleich; in den Daten kommt keine vor. Die
CLOSED_LOT-Zeile der TC-Maßnahme trägt eine eigene `transactionID`, die der
ED-Maßnahme dieselbe wie ihre DETAIL-Zeile.

**Abnahmebasis ergänzt (AP-03vb, 13.09.2026):** `tests/test_matching.py` prüft
jetzt beide Fälle — Barausgleich schließt zum `schlusskurs`, ein gesetzter
`schlusskurs` bei Lieferung wird ignoriert, fehlende Abwicklungsart und
fehlender `schlusskurs` bei Barausgleich brechen ab. Vier der fünf neuen Tests
schlagen gegen den jetzigen `engine/matching.py` erwartungsgemäß fehl; die
Nachbesserung ist Sache von AP-03.

## OF-26 · Identität einer OpenPosition mit `transactionID`, aber ohne `type`

AP-02k, Regel 4 definiert die Identität einer Sektionszeile mit ID über Konto,
`transactionID` **und** `type`. Die Regel ist an den CashTransactions gemessen,
wo `type` gesetzt ist; kein gemessener Export liefert eine `transactionID` auf
OpenPositions, und OpenPositions haben kein `type`-Feld — die Regel schweigt
über diese Kombination.

**Annahme:** `ingest/flex.py`, `_quell_id`: Fehlt `type`, bleibt der Typ-Teil
der Identität leer; die Identität einer solchen Zeile ist dann (Konto,
`transactionID`). Sollte ein künftiger Export `transactionID`s auf
OpenPositions tragen, ist die Regel dafür neu zu entscheiden — bis dahin
fallen offene Positionen über den Inhaltsschlüssel (Stichtag + `roh_json`),
wie es die Abnahmetests verlangen.

## OF-28 · Vertrag Regel 7 (Barausgleich/Lieferung) greift zu weit — bricht bei jeder physischen Zuteilung/Ausübung ab

**Befund 14.09.2026, beim Nacharbeiten von OF-27.** Der Bestandsabgleich
schloss 639 Ausführungen aus, weil ihr Instrument keine `abwicklungsart`
trägt und `_abwicklung_pruefen` (Vertrag Regel 7, OF-25) deshalb mit
`ValueError` abbricht. Genauer hingesehen: Das sind **nicht** irgendwelche
Optionen mit Datenlücke, sondern exakt die 639 **Aktienlieferungszeilen**,
die zu den 639 physisch gelieferten Zuteilungen/Ausübungen gehören (OF-25
hatte diese Zahl bereits als „alle 639 … mit Aktienlieferung" gemessen).

Beleg (über alle 9 Golden-Dateien, dedupliziert über `exec_id`):

| Anlageklasse | assignment/exercise-Zeilen | davon mit `abwicklungsart` |
|---|---|---|
| OPT | 1140 | 1140 (639 `lieferung`, 501 `barausgleich`) |
| STK | 639 | 0 |

**Ursache:** IB markiert bei einer physischen Zuteilung/Ausübung **zwei**
Ausführungszeilen mit demselben Ereigniscode in `notes` (Ep/Ex/A) — die
Optionszeile (die schließt) und die dazugehörige Aktienlieferung (die eine
Aktienposition eröffnet oder schließt). `abwicklungsart` kommt einzig aus
`SecurityInfo.settlementPolicyMethod` (OF-25) — ein Feld, das nur für
Optionen einen Sinn ergibt und bei Aktien im Export durchgehend leer ist,
auch wenn die conid selbst in `SecuritiesInfo` auftaucht (bei allen 165
betroffenen STK-conids ohne Barausgleichsbezug der Fall, plus 7 CASH-conids
ganz ohne `SecuritiesInfo`-Zeile).

`_abwicklung_pruefen` in `engine/matching.py` prüft aber jede Zeile mit
`ereignistyp in (assignment, exercise)` unabhängig von der Anlageklasse.
**Praktische Folge: `bilde_legs()` bricht bei jedem echten Konto mit
mindestens einer physisch gelieferten Zuteilung/Ausübung ab** — nicht nur
bei Datenlücken, sondern systematisch, weil die Aktienlieferungszeile per
Konstruktion nie eine `abwicklungsart` tragen kann. Die bisherige
Abnahmebasis (AP-03vb, `barausgleich*.json`) deckt diesen Fall nicht ab, weil
ihre Fixtures offenbar nur die Optionszeile der Zuteilung enthalten, nicht
die begleitende Aktienlieferung.

**Vorschlag, Entscheidung nötig:** Vertrag Regel 7 auf Optionsinstrumente
beschränken — `_abwicklung_pruefen` prüft `abwicklungsart` nur, wenn
`asset_class` der Ausführung `OPT` oder `FOP` ist. Die begleitende
Aktienlieferungszeile (Anlageklasse `STK`) nimmt an dieser Prüfung gar nicht
teil und wird wie eine gewöhnliche `trade`-Ausführung zu ihrem eigenen Preis
gematcht — ihr `ereignistyp` bleibt `assignment`/`exercise` (weiterhin
matchend, § MATCHENDE_EREIGNISTYPEN), nur die Barausgleich/Lieferung-Prüfung
entfällt für sie. Das ist noch nicht entschieden und noch nicht umgesetzt —
Korrekturpaket nötig (aendert_tests: ja), da die Abnahmebasis um einen
Fixture-Fall „Zuteilung mit Aktienlieferung, beide Zeilen" ergänzt werden
muss, den es bisher nicht gibt.

**Umgesetzt 14.09.2026 (AP-03vo, AP-03):** `_abwicklung_pruefen` prüft die
Abwicklungsart jetzt nur noch, wenn `asset_class` der Ausführung `OPT` oder
`FOP` ist; jede andere Anlageklasse (insbesondere die Aktienlieferungszeile)
matcht ohne diese Prüfung zu ihrem eigenen Ereigniszeilenpreis. Re-Lauf des
Bestandsabgleichs (`werkzeuge/abgleich/golden_bestandsabgleich_of23.py`)
danach: von 192 vergleichbaren `conid`s stimmen jetzt 180 überein (94 %,
zuvor 61 % mit den 639 fälschlich ausgeklammerten Aktienlieferungszeilen).
Keine der verbliebenen 1140 Optionszeilen fehlt eine `abwicklungsart` — die
Datenlücke, vor der Regel 7 ursprünglich schützen sollte, kommt in den
gemessenen Golden-Daten gar nicht vor.

## OF-27 · Re-Lauf nach OF-23: Bestandsabgleich mit echtem Import und echtem Matching

**Befund 13.09.2026, Re-Lauf nach der Nachbesserung von AP-03 (OF-23).**
Erstmals lief der Bestandsabgleich mit dem tatsächlichen, jetzt korrigierten
`ingest.flex.import_flex_file` und der tatsächlichen, jetzt korrigierten
`engine.matching.bilde_legs()` — nicht mit provisorisch angepassten
Abgleichsskripten wie zuvor (OF-21, vor der Nachbesserung von AP-02k). Die
`kapitalmassnahmen`-Eingabe wurde für diesen Lauf händisch aus
`flex_corporate_actions` (Gruppierung nach `actionID`) abgeleitet — die
eigentliche Ableitung ist laut AP-03vm ein eigenes, noch nicht begonnenes
Paket.

**Methodikfehler gefunden und im Re-Lauf-Skript korrigiert (kein
Produktionscode betroffen):** Zwei der Golden-Dateien decken denselben
Zeitraum ab (`…20260101_20260911_…a50fc…` und `…ee891…`, offenbar ein
erneuter Export desselben Statements). `flex_open_positions` dedupliziert
über `(konto, quell_schluessel)` je Datei, nicht über den Inhalt der Zeile —
beide Exporte lieferten dieselbe OpenPosition-Zeile doppelt, was den
IB-Bestand am jüngsten Stichtag durchgängig um den Faktor 2 überzeichnete
(105 von 105 gemeinsamen `conid`s exakt im Verhältnis 0,5). Für den Re-Lauf
wurde das Skript um eine inhaltsbasierte Deduplizierung ergänzt; ob
`_quell_id` für OpenPositions robuster gegen erneut exportierte, inhaltlich
identische Statements gemacht werden sollte, ist eine eigene Frage,
verwandt mit OF-26.

**Zwei Kapitalmaßnahmen ließen sich nicht ohne Raten in Transfer/Zugang
übersetzen** (Regel 10 — keine Annahme ohne Beleg):
- Eine `FI`-Maßnahme trägt 2 Abgang- und 2 Zugang-Zeilen unter derselben
  `actionID` (vermutlich zwei Optionsserien desselben Underlyings in einer
  Maßnahme). Für den Re-Lauf wurden Abgang und Zugang positional nach
  aufsteigender `conid` gepaart — eine **dokumentierte Annahme, nicht
  bestätigt**.
- Eine `ED`-Maßnahme trägt 4 Abgang- und 2 Zugang-Zeilen unter derselben
  `actionID` — keine plausible 1:1- oder 1:2-Paarung erkennbar. Für den
  Re-Lauf wurde sie ausgeklammert (keine `kapitalmassnahmen`-Zeile daraus
  abgeleitet). **Noch ohne Erklärung.**

**Ergebnis nach Korrektur des Dedup-Fehlers:** Von 273 `conid`s mit offener
Position bei uns oder bei IB am jüngsten Stichtag stimmen 167 exakt überein
(61 %). Von den 106 abweichenden `conid`s lassen sich 92 (87 %) auf eine
bereits bekannte, von OF-23 unabhängige Lücke zurückführen: 639 Ausführungen
(`assignment`/`exercise`) tragen an ihrem Instrument keine `abwicklungsart`
und wurden für diesen Lauf ausgeklammert, weil `bilde_legs()` dafür
erwartungsgemäß mit `ValueError` abbricht (Vertrag Regel 7, OF-25) — jede
dadurch nicht geschlossene Position bleibt bei uns fälschlich offen. Das ist
eine Datenlücke in der Stammdaten-Verschmelzung (`_stammsatz_verschmelzen`),
keine Folge dieser Nachbesserung, und noch ohne eigene Untersuchung.

**14 `conid`s bleiben ohne Zuordnung** — mutmaßlich (nicht bestätigt) unter
anderem die 4 `conid`s der ausgeklammerten `ED`-Maßnahme oben, dazu evtl.
weitere Ereignisarten, die nicht in `MATCHENDE_EREIGNISTYPEN` gematcht
werden. Nicht einzeln nachverfolgt — Aufwand für diesen Lauf nicht
gerechtfertigt.

**Kein Befund, der gegen die Kapitalmaßnahmen-Nachbesserung selbst spricht:**
Unter den `conid`s, die tatsächlich vergleichbar sind (nicht durch die beiden
oben genannten, unabhängigen Lücken betroffen), stimmt der Bestand in 167 von
172 Fällen (97 %); die 5 verbleibenden sind nicht auf `basis_ungeklaert`
zurückzuführen (kein Leg im ganzen Lauf trägt dieses Flag — die Golden-Daten
enthalten offenbar keinen Fall von `DI` ohne `costBasis`).

**Geldtest (realisiertes Ergebnis je Jahr/Anlageklasse gegen die
Jahressummen) wurde in diesem Re-Lauf NICHT durchgeführt** — eigener,
größerer Aufwand (u. a. FX-Umrechnung nach der in OF-23 entschiedenen
IB-Konvention, `FIFOPerformanceSummaryInBase` als Referenz über
überlappende Perioden hinweg dedupliziert). Bleibt offen; AP-03 ist damit
weiterhin nicht formal abgenommen.

**Nachtrag 14.09.2026, nach OF-28:** Die 639 ausgeklammerten Ausführungen
oben waren die Aktienlieferungszeilen physischer Zuteilungen, nicht eine
Datenlücke — s. OF-28. Mit der dortigen Korrektur (`_abwicklung_pruefen`
nur noch an Optionen) und demselben Skript ohne diese Ausklammerung stimmen
jetzt 180 von 192 vergleichbaren `conid`s überein (94 %). Die verbleibenden
12 sind weiterhin nicht einzeln zugeordnet — mutmaßlich unter anderem die
4 `conid`s der übersprungenen `ED`-Maßnahme (s. o.).

**Nachtrag 14.09.2026, die 12 verbleibenden `conid`s einzeln untersucht.**
Alle 12 sind nur bei uns offen, nie nur bei IB, und keins davon betrifft
`basis_ungeklaert`. **Kein Befund gegen `engine/matching.py`** — alle drei
Ursachen liegen in der händischen `kapitalmassnahmen`-Ableitung dieses
Re-Laufs, die laut AP-03vm ohnehin nur ein Behelf für die noch nicht
gebaute echte Ableitung ist:

1. **7 sind `CASH`-conids** (Währungspaare). `bilde_legs()` matcht ihre
   Trades wie jede andere Ausführung und eröffnet entsprechend Legs — IBs
   `OpenPositions` führt Währungspositionen aber offenbar anders (oder gar
   nicht) als gehandelte Instrumente. Ob `CASH`-Ausführungen vor
   `bilde_legs()` überhaupt herausgefiltert werden sollen, ist eine eigene,
   noch offene Entscheidung (verwandt mit dem Nachtrag zu OF-23 oben: „12
   CASH-Positionen … liegt außerhalb des Matchings“ — dort ging es um den
   Geldtest, nicht um den Bestand; ob dieselbe Ausnahme gilt, ist nicht
   automatisch übertragbar).
2. **1 `conid` (STK) trägt eine offensichtlich falsche, periodische Menge**
   (`…111,111…`). Ursache gefunden: die oben genannte, nicht bestätigte
   Annahme „Abgang/Zugang positional nach `conid` gepaart“ bei der einen
   uneindeutigen `FI`-Maßnahme (2 Abgang, 2 Zugang) hat hier eine
   Options-Abgangzeile (`alte_menge=9`) mit einer sachfremden Aktien-
   Zugangzeile (`neue_menge=1000`) verpaart — Faktor 1000/9. Die Annahme ist
   damit für diesen Fall **widerlegt**, nicht nur unbestätigt.
3. **1 weiterer `conid` (STK) trägt ein Phantom-Lot von 200 Stück ohne
   jede eigene Ausführung** — vollständig aus einer `DI`-Maßnahme mit
   `kosten_neu = 0` synthetisch eröffnet. Bei IB ist die Position am
   jüngsten Stichtag nicht (mehr) vorhanden. Naheliegende Erklärung
   (nicht geprüft): eine spätere Bewegung dieses Bestands steckt in der
   übersprungenen `ED`-Maßnahme oben, die genau deshalb keine plausible
   Paarung ergab.
4. **3 `conid`s (OPT) haben eine `expiry`-Zeile, deren Menge nicht zur
   eröffnenden Ausführung passt** (z. B. Eröffnung 1 Kontrakt, `expiry`
   2 bzw. 10 Stück) — bei allen dreien in unterschiedlichem Verhältnis,
   kein fester Faktor. Naheliegendste Erklärung: ein Optionskontrakt, dessen
   Lieferumfang durch eine Kapitalmaßnahme angepasst wurde, **ohne** dass
   IB dafür die `conid` wechselt (anders als die in AP-03vm behandelten
   Transfer-Fälle) — genau der Fall, für den OF-23 das noch nicht gesetzte
   `instruments.angepasst` vorgesehen hatte. **Nicht bestätigt, nicht
   weiter untersucht** — würde die Ableitung aus `flex_corporate_actions`
   um einen dritten Fall neben Transfer und reinem Zugang erweitern.

Keiner der vier Punkte ändert etwas am Befund oben: Unter den tatsächlich
vergleichbaren `conid`s ist die Kapitalmaßnahmen-Nachbesserung selbst ohne
Gegenbeleg. Alle vier bleiben offen, keiner wurde geraten oder verdeckt
gepatcht.

## OF-29 · Geldtest blockiert: `fxRateToBase` wird beim Import nicht geführt

**Befund 14.09.2026, beim Versuch, den Geldtest (letzter offener Punkt vor
der Abnahme von AP-03) anzugehen.** Der Geldtest vergleicht realisiertes
Ergebnis je Jahr/Anlageklasse gegen die Jahressummen der Kontoauszüge. Die
Kontoauszüge weisen in Basiswährung (EUR) aus; die gehandelten Instrumente
stehen praktisch durchgehend in Fremdwährung (USD, gemessen an allen
Golden-Instrumenten). Der bereits entschiedene Umrechnungsweg (OF-23,
„Entschieden 13.09.2026, getrennt nach Zweck“) braucht für den
IB-vergleichbaren Wert `fxRateToBase` **der schließenden Ausführung**.

**Dieses Feld führt `ingest/flex.py` derzeit nicht.** `fxRateToBase` steht
am rohen `Trade`-Element (bestätigt an den Golden-Exporten), aber
`_execution_zeile` übernimmt es nicht in die zurückgegebene Zeile, und
`executions` hat keine passende Spalte. Ohne dieses Feld lässt sich der
IB-vergleichbare Geldtest aus den persistierten Daten nicht rechnen — auch
nicht behelfsmäßig wie bei OF-27/OF-28, weil das Feld nirgends im Journal
ankommt, roh oder normalisiert.

**Vorschlag:** Eigenes, kleines Korrekturpaket für AP-02 (`aendert_tests:
ja`, `modell: stark`): `executions` um eine Spalte für `fxRateToBase`
ergänzen (Migration), `_execution_zeile` liest sie mit. Erst danach lässt
sich der Geldtest überhaupt versuchen — dieses Paket implementiert den
Geldtest selbst nicht, nur die dafür fehlende Datengrundlage.

**Nicht Teil dieses Fundes:** Ob `fifoPnlRealized`/`mtmPnl` (ebenfalls roh
vorhanden) zusätzlich gebraucht werden, ist beim eigentlichen Bau des
Geldtests zu klären, nicht hier — nicht geraten.

**Umgesetzt 14.09.2026 (AP-02l, AP-02):** `executions.buchungskurs` aus
`Trade.fxRateToBase` (Migration `e1f4a2c8b6d3`), `_execution_zeile` liest es
mit. Damit ist nur die Datengrundlage da — der Geldtest selbst (AP-03) ist
weiterhin nicht gebaut. Bleibt offen: FX-Umrechnung nach der IB-Konvention
anwenden, `FIFOPerformanceSummaryInBase` als Referenz über überlappende
Perioden hinweg dedupliziert einlesen, und ob `fifoPnlRealized`/`mtmPnl`
zusätzlich gebraucht werden.

## OF-30 · Wird AP-09 (TDP-Import) überhaupt noch gebraucht?

**Vorfrage vor allen Formatentscheidungen (15.09.2026, Nutzer).** Der
TDP-Import war als Ersatz gedacht, falls Flex nicht weit genug zurückreicht.
Deckt Flex die gesamte Kontohistorie ab, trägt TDP nichts bei — dann entfällt
AP-09 als Importpaket, und die Entscheidungen unten werden nicht gebraucht.

**Reichweitenprüfung, gemessen 15.09.2026** (alle Golden-Exporte des Kontos,
nur Zählwerte und Monate):

- Alle Exporte gehören zu einem einzigen Konto, `2022.xml` eingeschlossen.
- Frühester Trade: **04/2022**. Früheste Kassenbuchung ebenfalls **04/2022**,
  darunter drei Ein- oder Auszahlungen — das Konto beginnt in diesem Monat.
- **0 von 19.329 Closed Lots** tragen ein Eröffnungsdatum vor 04/2022. IB
  führt das echte Eröffnungsdatum am Lot unabhängig vom Exportzeitraum; kein
  vor 04/2022 eröffneter Bestand wurde je geschlossen.
- **Keine conid** beginnt mit einer Schließung (`openCloseIndicator = C`).
- Transfers: nur 2 interne Kassenübertragungen (2025). Kein Wertpapierbestand
  wurde von außen eingebucht.
- Die Bestände an allen fünf Stichtagen 2022–2026 schließen mit dem Matching
  ohne Abweichung (OF-21) — auch das spräche gegen einen unbekannten Vortrag.

**Befund: Flex deckt die gesamte Kontohistorie ab.** Die Lücke aus OF-21
(04/2023–12/2025) ist mit den Jahresexporten seit 13.09.2026 geschlossen.
Offen ist nur die Gegenprobe auf TDP-Seite (frühestes Handelsdatum im
TDP-Export); da das Konto erst 04/2022 beginnt, kann TDP für dieses Konto
keine früheren Buchungen enthalten.

**Vorschlag, Entscheidung Planer und Nutzer:** AP-09 als Importpaket
streichen. Quelle 1 (Jahres-Flex) ist bereits der bestehende AP-02-Import;
TDP bleibt höchstens unabhängige Zweitmeinung ohne gehärteten Parser. Die
Planänderung vom 15.09.2026 und der Anhang `AP-09-anhang-tdp-format.md`
wären dann entsprechend als Referenz zu kennzeichnen.

### Nur falls AP-09 doch gebraucht wird — entschieden 15.09.2026 (Nutzer)

1. **Fehlende `Contract Id`** (Aktienzeilen aus Zuteilung): aus der bereits
   aus Flex bekannten Instrumententabelle über Symbol und Anlageklasse
   füllen, wenn eindeutig; sonst mit leerem `conid` und Kennzeichen
   `conid_ungeklaert` importieren. Weder ablehnen noch still leer lassen.
2. **Fehlende Abwicklungsart:** Vertrag Regel 7 (AP-03) gilt nur für
   Qualitätsstufe A. Für Altdaten die Abwicklungsart aus den
   Flex-Instrumenten übernehmen, wo bekannt; sonst Kennzeichen
   `abwicklung_unbekannt` — die Zeile bleibt in `executions`, nimmt aber
   nicht an der Kettenbildung teil. Kein Abbruch.
3. **Ereigniszeilen** (gemessen, der Anhang lag falsch): `P` trägt echte
   Börsen (CBOE, CBOE2, SAPPHIRE) und ist ein Handel, wie OF-20.
   `Ep`/`Ex`/`A` tragen durchgehend `--`. **Regel: Ereigniszeile heißt
   `Exchange == '--'`**, nicht „`Notes` gefüllt“. Unbekannte Codes wie
   `IA`, `FP`, `L` müssen damit nicht bekannt sein.
4. **Konto:** konfigurierte Zuordnungstabelle TDP-Kennung → Kontonummer,
   explizit gepflegt. Nicht ableiten — die Kennung ist eine
   Anzeigeabkürzung ohne rechnerischen Bezug zur Kontonummer.
5. **„Gleiche ID, anderer Inhalt“:** verglichen werden `conid`, Richtung,
   Menge, Preis, Kommission, Währung und Ereignistyp — als `Decimal`, auf die
   geringere Genauigkeit beider Quellen gerundet. **Zeitstempel bleiben außen
   vor** (gemessen: 175 von 175 Zeilen weichen ab, TDP deutsche Ortszeit,
   Flex Kontozeitzone; der Versatz wechselt wegen verschiedener
   Umstellungstermine zwischen 6 und 5 Stunden). Bei Konflikt gewinnt Flex;
   die TDP-Zeile wird protokolliert, nicht geschrieben.

**Kleinere Punkte:** `Strike` ist bei Aktien `0,00000`, nicht leer.
`Transfer = True` wird mit klarem Fehler abgelehnt. Wie `FOP` in TDP
erscheint, bleibt offen, bis eine solche Zeile vorliegt — nicht erfunden.
Bestätigte Zuordnungen: `Conversion Rate` → `buchungskurs`, `Currency` →
Kommissionswährung, `Amount`/`Amount In Base` → nur `roh_json`.

**Folgen für die Dokumente, falls AP-09 bleibt:** Der Anhang ist in Punkt 3
(Ereigniserkennung) und beim `Strike` zu korrigieren; `AP-09.md` ist auf den
Anhang und den Modellsplit umzustellen (Parser gegen synthetische Fixtures:
günstiges Modell; Abnahme gegen Echtdaten: starkes Modell). Der Parser hängt
nicht von AP-03 ab, nur die Abnahme über Jahressummen.

## OF-31 · OptionApp-Export: darf `Open` leer sein?

Der Formatanhang (AP-13) regelt leere Zellen nur für `Close` und `Close Time`
(bei offenen Trades). Für `Open` steht „leer möglich: siehe unten“ — die
Verweisstelle behandelt aber nur die Schließung. In den Referenzexporten ist
`Open` stets gefüllt; ein leerer Fall wurde nie beobachtet.

**Annahme:** `ingest/optionapp.py`, `_zahlzelle`: Eine leere `Open`-Zelle wird
als `offen_preis = NULL` gebucht, nicht als Fehler. Das Schema trägt das Feld
als nullable. Sollte ein echter Export einen offenen Trade ohne Eröffnungspreis
liefern, ist neu zu entscheiden, ob das ein Defekt der Quelle ist (Abbruch) —
bis dahin geht kein Trade verloren.

## OF-32 · `tests/test_ingest_optionapp.py` verletzt I001, sobald der Parser existiert

Befund der AP-13-Teil-1-Umsetzung (18.09.2026): `ruff check . --no-cache`
schlägt nach Anlegen von `ingest/optionapp.py` mit `I001` in
`tests/test_ingest_optionapp.py:29` an — zwischen den First-party-Importen
steht eine Leerzeile. Ohne das Modul klassifiziert ruff
`from ingest.optionapp import …` nicht als First-party und meldet nichts;
deshalb war der Befund in AP-13p (ohne Modul) unsichtbar. Dieselbe Falle wie
in AP-02, dort nachträglich als I001-Falle dokumentiert.

Die Datei ist Abnahmebasis und für das Umsetzungspaket unveränderlich (Regel
1). Behebung braucht ein Korrekturpaket nach Regel 1a (`aendert_tests: ja`,
`locker`): die Leerzeile in Zeile 30 löschen — reine Formatierung, es ändert
sich keine Erwartung.

**Erledigt 18.09.2026 (AP-13pk).** Leerzeile entfernt, `ruff check .`
sauber, alle 149 Tests unverändert grün.

## OF-33 · AP-03: Vollständigkeitsprüfung gegen `FIFOPerformanceSummaryInBase`

**Befund 18.09.2026**, zweite monetäre Abnahmehälfte aus Plan §4
(„Vollständigkeit, je Jahr"). Details und Ergebnis stehen in `AP-03.md`
unter „Vollständigkeitsprüfung"; hier nur die Punkte, die über AP-03 hinaus
relevant sind.

**Fensterkaveat.** `FIFOPerformanceSummaryInBase` ist nur in Exporten ohne
`model`-Attribut gefüllt (OF-21). Von neun Golden-Exporten sind das fünf —
und deren Fenster sind **April–März, kein einziges ein Kalenderjahr**
(die eine Ausnahme: das jüngste, Januar–September 2026, ein Torso). Die
kalenderjahrgleichen Exporte (Januar–Dezember) tragen durchweg
`model="Independent"` und liefern eine leere Summary. Der Plan verlangt
„je Kalenderjahr" — das ist mit den vorliegenden Exporten nicht herstellbar,
nur je verfügbarem (Nicht-Kalenderjahr-)Fenster. Für eine echte
Kalenderjahr-Prüfung braucht es einen gezielten Neuexport ohne Modell mit
Januar–Dezember-Grenzen. Nicht blockierend für die Abnahme von AP-03 (die
Fensterprüfung genügt dafür), aber ein offener Verbesserungspunkt.

**CASH weicht in jedem Fenster um rund 100 % ab** — erwartungsgemäß und
bereits erklärt (OF-23-Nachtrag, OF-27): Devisenergebnis entsteht bei IB aus
dem Umtausch selbst, nicht aus einer realisierenden Ausführung mit
`fifoPnlRealized`. Diese Anlageklasse liegt außerhalb dessen, was ein
Vergleich über `fifoPnlRealized` prüfen kann — weder hier noch in einem
künftigen Kalenderjahr-Neuexport wird das anders sein, ohne einen eigenen
Ansatz für Devisenergebnisse.

**Methodische Notiz, falls diese Prüfung wiederverwendet wird:** Ein
direkter Vergleich des eigenen P&L-Ergebnisses gegen die Performance Summary
wäre von der bereits bezifferten Prämiendifferenz aus OF-24 dominiert
gewesen, nicht von echten Lücken (erste Fassung des Skripts, verworfen).
`golden_geldtest_vollstaendigkeit.py` vergleicht deshalb IBs eigenen
`fifoPnlRealized`-Wert, summiert über die von uns importierte
Ausführungsmenge, gegen IBs eigene Summary-Zahl — das isoliert fehlende
Ausführungen von der bekannten Bewertungsdifferenz.

## OF-34 · AP-04: „gleiche Seite" beim Zeitfenster-Fallback — aufgelöst

**Befund 18./19.09.2026, beim Bau von `engine/structures.py` (AP-04, Teil 1 —
Legs → Structures).** Schritt 2 der Erkennungsreihenfolge verlangt für den
Zeitfenster-Fallback „gleichem Underlying, gleicher Seite und vergleichbarer
Menge". Eine Structure aus gegenläufigen Legs (z. B. ein Vertical: ein Long-
und ein Short-Bein) hat per Definition keine einheitliche `side` — „gleiche
Seite" kann sich deshalb nicht auf die ganze entstehende Structure beziehen.

Erste, dokumentierte Annahme (18./19.09.2026): „gleiche Seite" gelte je
Leg-Paar mit identischem `side`. Nicht an den Golden-Daten prüfbar (keine
Ausführung dort braucht den Fallback) und im Nachhinein **falsch**.

**Aufgelöst 19.09.2026 (Nutzer, Plan präzisiert).** Der Plan trennt jetzt
ausdrücklich Strukturbildung (Block A) von Kettenbildung (Block B) — beide
hatten unterschiedliche Regeln, die vorher unter einer Nummerierung
vermischt waren. Block A, Schritt 2 verlangt **gegenläufige Richtungen**,
nicht gleiche: Der Fallback führt zwei getrennt ausgeführte Beine EINER
Structure zusammen (ein Long-Bein aus der einen Order, das Short-Bein aus
einer unmittelbar danach platzierten zweiten), nicht mehrere unabhängige,
gleichgerichtete Eröffnungen. `engine/structures.py` ist entsprechend
korrigiert (`_zeitfenster_clustern`: `richtung != anker.richtung` statt
`==`), Tests angepasst.

## OF-35 · AP-04 Teil 2: Kettenbildung — Stand nach der Planpräzisierung

**Befund 19.09.2026, beim Bau von `engine/chains.py`.** Ursprünglich drei
Punkte; nach Rückfrage beim Nutzer sind zwei davon aufgelöst, einer bleibt
in engerer Form bestehen.

**1. Futures-Roll: kein Zeitfenster, nur `exec_batch` (aufgelöst, enger
gefasst).** Frühere Annahme: dasselbe 3-Minuten-Fenster wie bei Optionen
gilt auch für Futures-Rolls. **Nutzer 19.09.2026:** falsch — Futures
verketten sich automatisch **nur** über einen gemeinsamen `exec_batch`
(„Roll in einer Order"). Eine Front-Monat-Schließung und eine
Back-Monat-Eröffnung am selben Handelstag **ohne** gemeinsamen `exec_batch`
sind höchstens ein Kandidat für eine manuelle Bestätigung, kein
automatischer Link — Futures sind ein seltener Fall, eine Heuristik dafür
brächte mehr Risiko als Nutzen. `engine/chains.py` ist entsprechend
umgesetzt (keine Zeitfenster-Funktion mehr für Futures). **Weiterhin offen:**
Die Kandidatenmarkierung selbst (Front-Monat-Schließung + Back-Monat-
Eröffnung ohne `exec_batch`, zur manuellen Bestätigung vorgeschlagen) ist
noch nicht gebaut — das braucht den Override-Mechanismus der
Persistenzschicht, der insgesamt noch aussteht.

**2. Options-Roll ohne OA-Referenz: doch erkannt (aufgelöst, Annahme
widerlegt).** Frühere Annahme: keine automatische Verkettung ohne
OA-Referenz. **Nutzer 19.09.2026:** falsch, und zwar folgenreich — ohne
Rollerkennung gäbe es für DAX und ESTX50 gar keine Ketten, und die
Roll-Degradationsauswertung (§1, erste der drei Kernfragen) wäre
unbeantwortbar. Zwei Wege, beide jetzt umgesetzt: **Roll in einer Order**
(dieselbe Combo-Ausführung schließt die alte und eröffnet die neue
Structure, erkennbar am gemeinsamen `exec_batch` — der Regelfall, weil
Rolls laut Nutzer üblicherweise in einer Order ausgeführt werden) und
**Roll in zwei Orders** (3-Minuten-Fenster, gleicher Basiswert, gleiche
Seite, vergleichbare Menge — die Expiry ist hier bewusst keine Bedingung,
ein Roll wechselt sie gerade). Golden-Sanity-Lauf danach: Chains sinken von
8.803 auf 7.009, mit Rollketten bis zu 14 Gliedern — genau das erwartbare
Bild für rollierte Index-Strategien.

**3. Die Golden-Referenzzahl „1.261 → 134" ist gestrichen, nicht nur
ungeklärt.** War zunächst als „Herkunft nicht identifizierbar" dokumentiert.
**Nutzer 19.09.2026, nach eigener Prüfung:** Die Zahl stammt aus einer
älteren Ad-hoc-Auswertung (Nico), deren Quelldatei und Methode nie
festgehalten wurden — auch die Größenordnung (DAX bis Ende Juni: 1.309
Zeilen, davon 1.157 ohne Ereignisse) trifft die 1.261 nicht genau. Als
Abnahmekriterium für das schwierigste Bauteil des Projekts ist eine Zahl
unbekannter Herkunft und Methode untauglich: Bei Abweichung wäre nicht
erkennbar, welche Seite falsch liegt. **Ersetzt durch drei Prüfungen (Plan
§6, AP-04, „Abnahme"):**

- *Externe Referenz, OA-Teil:* Kettenbildung stimmt für OA-geführte
  Positionen exakt mit dem OA-Trade-Export überein (Anzahl und
  Zusammensetzung) — eine von der Engine unabhängige Quelle. **Noch nicht
  durchgeführt:** Der reale Februar-2026-OA-Export (137 Trades) liegt nicht
  vor; `fixtures/golden/` enthält keine XLSX-Datei, nur die synthetischen
  AP-13p-Fixtures. Ohne die echte Datei ist dieser — der härteste und
  wichtigste — Abnahmenachweis nicht führbar.
- *Invarianten, gesamter Bestand:* geprüft und bestanden
  (`werkzeuge/abgleich/golden_ketten_invarianten.py`, 19.09.2026) — über
  die gesamte Golden-Historie (8.880 Structures, 7.009 Chains) liegt keine
  Structure in zwei Ketten, kein Nicht-Schlussglied einer Kette ist offen,
  jede Rollverknüpfung bleibt auf demselben Underlying, und die
  Ketten-Ergebnissumme stimmt exakt mit der unabhängig aufsummierten
  Struktur-Ergebnissumme überein (0 von 6.857 geprüften Ketten weicht ab).
- *Stichprobe, Nicht-OA-Teil (DAX/ESTX50):* noch nicht durchgeführt — dafür
  braucht es eine manuelle Durchsicht gerollter Ketten, eingefroren als
  Fixture.

