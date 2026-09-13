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

**Währung (entschieden, Plan):** Maßgeblich ist `fxRateToBase` an der
jeweiligen Ausführung — IBs eigener Buchungskurs, mit Bezugszeitpunkt
gespeichert (P4). Basiswährung ist EUR; die EUR-Zeilen tragen den Kurs 1.

**Nachtrag 13.09.2026:** Die ohne Modell gezogenen Exporte enthalten
Kapitalmaßnahmen auch auf der Ebene `CLOSED_LOT`, genau zwei (TC und ED). Beide
tragen `fifoPnlRealized = 0` — sie realisieren nichts, die Regel bleibt
ausnahmslos belegt. Eine erste, vorschnelle Vermutung, solche Zeilen stünden
für realisierende Maßnahmen, hat sich damit nicht bestätigt. Offen bleibt nur
der Fall einer Maßnahme mit Barausgleich; in den Daten kommt keine vor. Die
CLOSED_LOT-Zeile der TC-Maßnahme trägt eine eigene `transactionID`, die der
ED-Maßnahme dieselbe wie ihre DETAIL-Zeile.
