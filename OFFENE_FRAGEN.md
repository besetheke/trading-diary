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

**Teilweise geschehen (AP-06v, E2 — Nutzerfreigabe):** `metrics_by_chain`
wird in Tranche I minimal geformt (`chain_id` eindeutig auf `chains.chain_id`,
`netto_eur_wirtschaftlich`, `netto_eur_ib`), weil die Analyseschicht die
EUR-Werte in den Cache legt statt in `chains.netto_pnl_eur` — dort setzt sie
der Rebuild bei jedem Lauf auf `None` zurück, ein Wert wäre eine stille
Reihenfolge-Abhängigkeit (Rebuild vor Analytik). `chains.netto_pnl_eur`
bleibt dauerhaft leer (Plan §5 führt die Spalte; die Verankerung „leer nach
rebuild“ in `tests/test_rebuild.py` bleibt gültig, nur der Spaltenkommentar
wird korrigiert). Das Löschverhalten ist mitgeformt: `chain_id` trägt
`ON DELETE CASCADE` — verschwindet eine Kette im Rebuild, fällt ihre
Cache-Zeile mit ihr (der Rebuild bleibt von der Analytik unberührt; ohne
CASCADE liefe sein Löschen verschollener Ketten auf einen IntegrityError,
sobald einmal Kennzahlen gelaufen ist), Werte überlebender Ketten gelten
fort, bis der nächste Bericht sie neu schreibt. `metrics_daily` (Tranche IV)
und `metrics_by_campaign` (Tranche V) bleiben weiter offen.

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

## OF-36 · AP-04: OA-Abgleich durchgeführt — 92,4 %, fünf offene Abweichungen

**Befund 19./20.09.2026.** Der reale OptionApp-Export lag inzwischen vor
(`fixtures/golden/Trades_2026-02_OA.xlsx`, 66 Trades, Zeitraum 30.01.–
27.02.2026) — der erste der drei AP-04-Abnahmeprüfungen (Plan §6, „Externe
Referenz, OA-Teil") konnte damit erstmals laufen:
`werkzeuge/abgleich/golden_oa_abgleich.py`.

**Vorab korrigierte Annahme: Vergleichsbasis ist das erste Kettenglied,
nicht das letzte.** Die XLSX zeigt keine Roll-Historie — nur eine
Momentaufnahme je Trade. Gemessen: Der Vergleich gegen das **erste**
Kettenglied trifft in 61 von 66 Fällen (92,4 %), gegen das letzte nur in 55
von 66 (83,3 %). Die Datei bildet also die **Eröffnungs**-Legs ab, nicht den
finalen Zustand nach etwaigen Rolls.

**Ergebnis: 61 von 66 OA-Trades (92,4 %) stimmen in Anzahl und
Zusammensetzung der Legs exakt mit dem ersten Kettenglied überein.** Kein
`oa_trade` fehlt in den Flex-Ausführungen (0 von 66), keiner bildet mehr als
eine Kette (0 von 66) — die Kettenidentität selbst (Schritt 0a) ist damit
strukturell bestätigt.

**Fünf Abweichungen, klares Muster, Ursache noch nicht bewiesen.** In allen
fünf Fällen fehlt bei uns **genau ein** Bein gegenüber der Referenz — nie
eines zu viel. Untersucht: Bei drei der fünf existiert unter demselben
`oa_trade`, aber anderer `oa_order`, eine Ausführung mit `oa_rolle =
'Close Order'`, zeitlich 36 bis 142 Minuten nach der ersten Eröffnung — ein
plausibler, aber **nicht bewiesener** Kandidat für das fehlende Bein (etwa
eine mehrstufige Eröffnung, bei der ein Bein aus Liquiditätsgründen in einer
zweiten, separaten Order nachgereicht wurde). Bei den übrigen zwei gibt es
unter demselben `oa_trade` gar keine Ausführung mit anderer `oa_order` — das
fehlende Bein taucht in den Flex-Daten unter dieser Nummer nicht auf.

**Klarstellung, die die Interpretation einschränkt (Nutzer, 19.09.2026): OA
rollt nicht selbst — jeder Roll läuft manuell über TWS.** Die
`oa_trade`-Nummer ist damit die vom Nutzer in OA gepflegte Kettenreferenz,
kein von OA ausgeführter Mechanismus. Für `engine/chains.py` ändert das
nichts (`_rolls_verketten()` — Schritt 1/2 — läuft bereits über **alle**
Structures, OA-referenzierte eingeschlossen, nicht nur über die ohne
`oa_trade`; verifiziert am Code). Für die fünf Abweichungen bedeutet es aber:
Das „Close Order"-Muster ist **kein** Hinweis auf einen fehlgeschlagenen
Roll-Mechanismus (den gibt es innerhalb von OA gar nicht), sondern müsste,
falls es die Erklärung ist, eine mehrstufige **Eröffnung** sein — nicht
geraten, sondern am nächsten OA-Export oder durch gezielte Nachfrage zu
klären.

**Nicht Teil dieses Fundes:** Endzustand-Übereinstimmung (XLSX-`Status` vs.
Ketten-`endzustand`) wurde ebenfalls gemessen, aber verworfen — die
Kreuztabelle zeigt, dass OAs Status-Vokabular (`CLOSED`/`EXPIRED`/`STOPPED`)
nicht 1:1 auf unseren Endzustand (`Geschlossen`/`Verfall`/`Assigned`)
abbildbar ist (z. B. 17 von 23 `EXPIRED`-Trades enden bei uns mit `Verfall`,
6 mit `Assigned` — plausibel bei einem Spread, dessen eines Bein verfällt,
während das andere zugeteilt wird, aber ein geratenes Mapping wäre hier
Regel-10-widrig). Kein Teil der 92,4-%-Zahl.

**Für die Abnahme von AP-04:** Der OA-Abgleich ist durchgeführt, aber noch
nicht „exakt" im Sinne des Plans (66 von 66). Die fünf Abweichungen sind
benannt, nicht erklärt — vor einer Abnahme zu klären, nicht wegzuparametrisieren.

**Ursache gefunden 21.09.2026 — kontoweite Verrechnung über OA-Trades
hinweg. Eine Entscheidung steht aus (Nutzer).** Die frühere Vermutung (eine
nachgereichte zweite Order) war falsch. In allen fünf Fällen existiert die
Ausführung des „fehlenden" Beins: gleiche OA-Tradenummer, gleiche
`oa_order`, `oa_rolle = 'Open Order'`, in derselben Sekunde wie die übrigen
Beine. Sie eröffnet aber keine Leg — **der FIFO-Abgleich hat sie als
Schließung einer gegenläufigen Position im selben Kontrakt verbraucht, die
ein anderer OA-Trade 0,2 bis 119 Stunden vorher eröffnet hatte.** In allen
fünf Fällen: andere OA-Tradenummer, Gegenrichtung, gleiche `conid`, Menge 1.

Das ist kein Engine-Fehler, sondern der Plan: AP-03 legt „FIFO-Matching pro
conid" fest, und IB verrechnet genauso — kontoweit, je Kontrakt. OA bucht
dagegen je Trade und führt beide Beine weiter. Auf Brokerebene gibt es das
Bein nicht; in OA gibt es es.

**Umfang über die gesamte Historie:** 206 von 5.598 Ausführungen mit
`oa_rolle = 'Open Order'` (3,7 %) hat der FIFO-Abgleich als Schließung
verbraucht, **ausnahmslos** gegen eine Position eines *anderen* OA-Trades.
184 OA-Trades sind betroffen, 58 Fälle 2025, 148 im Jahr 2026 — steigend.

**Folge für den OA-Abgleich (Februardatei):** 61 exakt, 5 durch kontoweite
Verrechnung erklärt, **0 unerklärt.** `golden_oa_abgleich.py` weist die
Kategorie jetzt eigens aus.

**Folge darüber hinaus — das ist die eigentliche Frage:** Für diese 184
Trades verschiebt sich das Ergebnis zwischen OA-Trades. Ein Trade verliert
ein Bein, ein anderer wird durch eine fremde Ausführung früher geschlossen.
Die Kettensumme stimmt (Invariante 4 hält), die Zuordnung je Trade nicht —
und genau die braucht die Frage „wie schneidet Strategie X ab".

**Nicht entschieden, nicht geraten (Regel 10).** Drei Wege:

1. **Brokersicht bleibt, Abnahmekriterium wird präzisiert.** Die Engine
   bleibt bei FIFO pro conid; das OA-Kriterium lautet „exakt, außer bei
   kontoweiter Verrechnung — diese Fälle werden gelistet". Folge: Die
   Ergebnisse je Strategie sind für 184 Trades verzerrt.
2. **Zuordnung nach OA-Trade vor FIFO.** Tragen beide Ausführungen eine
   OA-Referenz, schließt eine Eröffnung nie die Position eines anderen
   Trades. Folge: weicht vom IB-FIFO ab; die angenommene Geldprüfung aus
   AP-03 (je Schließung gegen `fifoPnlRealized`) bricht für diese Fälle und
   müsste über ein Korrekturpaket neu gefasst werden.
3. **Zwei Schichten.** Legs bleiben IB-FIFO (Brokerwahrheit, Geldprüfung
   unverändert); darüber eine Zuordnungsschicht nach Absicht, auf der
   Strukturen, Ketten und Strategieauswertung aufsetzen. Folge: sauberste
   Trennung, aber das meiste Bauwerk.

### Entschieden 22.09.2026: Weg 3 — zwei Sichten

Der Nutzer wählt beide Sichten nebeneinander: **eine für Kontoführung und
Steuer, eine für die Kette.** Das entspricht dem, was die OptionsApp selbst
tut (Netto- gegen Bruttoposition) und was oben als Weg 3 stand.

- **Kontosicht (netto)** — FIFO je `conid` kontoweit, wie IB. Maßgeblich
  für Geld: Sie trägt die Abnahme aus AP-03 und speist allein die
  steuerliche Auswertung (AP-10). **Ist gebaut.**
- **Kettensicht (brutto)** — Zurechnung je Vorgang. Beantwortet die
  Strategiefrage und trägt die Roll-Degradation. **Eigenes Paket, fällig
  vor AP-06.**

**Getrennt gehalten, umschaltbar gezeigt.** Die beiden Sichten sind nicht
zwei Darstellungen derselben Zahlen, sondern zwei Zuordnungen derselben
Ausführungen: Die Kettensicht braucht eine eigene Zuordnung innerhalb des
Vorgangs, sonst bliebe das kontoweit ausgeglichene Bein verschwunden.
Deshalb getrennte Speicherung, keine Vermischung, und **jede Zahl trägt,
aus welcher Sicht sie stammt**. Eine Summe über beide Sichten gibt es nicht.

**Offen für das spätere Paket, bewusst noch nicht entschieden:** Wie die
Kettensicht mit einem Bein umgeht, das in ihrem Vorgang nie geschlossen
wird, weil der Broker es kontoweit ausgeglichen hat. OA hat dafür eigene
Regeln (Stop, Verfall); ob wir sie übernehmen oder solche Fälle offen und
sichtbar lassen, ist zu klären, wenn das Paket geschnitten wird — nicht
jetzt zu raten.

Ausformuliert für den Plan in
`auftraege/AP-07-vorschlag-zwei-sichten-und-vorziehen.md`, §5.

## OF-37 · AP-13-Parser: `Close Time = '-'` bei laufenden/abgebrochenen Trades nicht vorgesehen

**Befund 19./20.09.2026, beim ersten Einlesen echter OA-Exporte.**
`ingest/optionapp.py` bricht an `Trades_2026-01_OA.xlsx` und
`Trades_2026-08_OA.xlsx` ab: `'Close Time' folgt nicht dem Format
JJJJ/MM/TT hh:mm:ss: '-'`. Gemessen über alle drei realen Exporte:

| Datei | Zeilen | `Close`/`Close Time` = `-` | zugehöriger `Status` |
|---|---|---|---|
| 2026-01 | 268 | 187 | 179 × `CANCELED`, 8 × `RUNNING` |
| 2026-02 | 66 | 0 | — |
| 2026-08 | 178 | 24 | 24 × `PARTIALLY STOPPED` |

Der Anhang (`AP-13-anhang-oa-format.md`) und AP-13p sahen für `Close`/
`Close Time` nur „gefüllt" oder „leer" vor (offener Trade), gemessen an den
beiden Referenzexporten aus §6.1, die ausschließlich abgeschlossene Trades
enthielten. Der reale Bestand zeigt einen dritten Fall: `-` bedeutet „noch
nicht geschlossen" — analog zur bereits bekannten `Stops`-Spalte, wo `-`
„kein Stop" heißt (Anhang, Eigenheit 2) — bei den Status `CANCELED`,
`RUNNING` und `PARTIALLY STOPPED` (ein teilweise gestoppter Trade hat
offenbar noch keine einheitliche Schlusszeit für den Gesamttrade).

**Nicht behoben, nicht geraten.** Betrifft nur die Januar- und
August-Datei, nicht die für den OA-Abgleich (OF-36) verwendete
Februar-Datei. Braucht ein Korrekturpaket nach Regel 1a an der
AP-13p-Abnahmebasis (`aendert_tests: ja`): ein Fixture-Fall mit `Close Time
= '-'`, ein Test, der `schluss_zeit = None` statt eines Abbruchs erwartet —
dieselbe Behandlung wie bei `Stops`. Umsetzung danach wie bei AP-13 Teil 1
beim günstigen Modell.

## OF-38 · Verwaister Override: Löschen einer Execution scheitert am FK der Legs (AP-04v)

**Befund 20.09.2026, bei der Umsetzung von AP-04p.**
`tests/test_rebuild.py::test_verwaister_override_wird_gezaehlt_und_nicht_geloescht`
setzt einen Override, löscht danach die Ausführung, auf der die Struktur
beruhte, per nacktem `DELETE FROM executions` — und ruft dann `rebuild()`.
Das DELETE scheitert zwingend am Fremdschlüssel:

- Nach Vertrag 15 schreibt der Rebuild `legs` vollständig aus
  `MatchingErgebnis.legs` — für das volle Fixture sind das 10 Zeilen,
  darunter die offene Aktien-Leg mit `open_exec_id = 'A2'` (verlangt von
  `test_grundlauf_schreibt_die_erwarteten_zeilen`:
  `legs == 10` und `zuordnung['A1']`).
- `legs.open_exec_id` verweist mit `NO ACTION` auf `executions.exec_id`
  (Initialmigration; `PRAGMA foreign_key_list(legs)` verifiziert), und
  `journal/db.py` setzt `PRAGMA foreign_keys=ON`.

Derselbe Codepfad (volles Fixture → Rebuild) muss die A2-Leg also schreiben
und darf sie zugleich nicht geschrieben haben — ohne Änderung an Test oder
Migration nicht erfüllbar. AP-04v wurde ohne Referenzimplementierung
committet („Dieses Paket implementiert die Persistenz nicht"), der Test lief
daher vermutlich nie grün. Die Verwaist-Logik selbst ist in Ordnung: Mit
realistischer Import-Rücknahme (Execution mitsamt ihrer Legs-Zeile gelöscht,
nachgestellt gegen eine migrierte Datenbank) erfüllt die Umsetzung jede
Assertion des Tests — `overrides_verwaist == 1`, `overrides_angewandt == 0`,
`chain_overrides` unangetastet, Struktur `A2` bleibt override-gesichert
stehen, die leer gewordene `k:A2` wird gelöscht.

**Nicht behoben, nicht geraten** (Plan §11.3, Guardrail 10: Eintrag und
Abbruch statt Testanpassung durch das günstige Modell). Zwei Korrekturen
lägen beim starken Modell:

1. **Migration:** `ON DELETE CASCADE` auf `legs.open_exec_id` /
   `legs.close_exec_id` (und konsequenterweise
   `assignment_links.option_exec_id` / `assignment_links.stock_exec_id`) —
   Abgeleitetes stirbt mit seinen Rohdaten, passend zu „jederzeit neu
   berechenbar". Der Test bliebe unverändert; empfohlen.
2. **Test:** Das DELETE in `test_verwaister_…` um das Mitlöschen der
   abhängigen `legs`-Zeile ergänzen — entspricht dem im Test zitierten
   Vorgang („fehlerhafter Import zurückgenommen") auch ohne CASCADE.

Die Umsetzung von AP-04p ist abgesehen davon vollständig: alle übrigen
Tests aus `tests/test_rebuild.py` grün, Gesamtsuite und `ruff check .`
sauber.

**Aufgelöst 20.09.2026 durch AP-04vk — Variante 2, nicht die empfohlene
Variante 1.** Der Fehler steckte im Testaufbau, nicht im Schema. Eine
Kaskade hätte das Schema geändert, damit ein schlecht geschriebener Aufbau
ausführbar wird; sie brächte zudem nichts, weil produktiv niemand
Ausführungen löscht (Regel 4) und der nächste `rebuild()` eine verwaiste
Leg ohnehin entfernt — `legs` wird vollständig neu geschrieben. Der
Testaufbau löscht jetzt die abhängige `legs`-Zeile mit, wie es eine
zurückgenommene Fehleinspielung täte. **Keine Assertion wurde geändert**,
die Prüflogik ist unverändert. Alle 16 Tests aus `tests/test_rebuild.py`
laufen grün.

Die Diagnose des günstigen Modells war in jedem Punkt zutreffend, und das
Vorgehen — Widerspruch beweisen, eintragen, Test nicht anfassen, abbrechen
— war genau richtig.

## OF-39 · `methode = 'zuteilung'` bildet auf `erkennung = 'order_id'` ab

**Annahme, dokumentiert 20.09.2026 (Regel 10).** Vertrag 12 aus AP-04v
listete für `structures.erkennung` nur `oa`, `exec_batch` und
`zeitfenster`. `engine/chains.py` erzeugt aber die synthetische Struktur
des Zuteilungsübergangs mit `methode = 'zuteilung'` (Zeile 156) — ein
vierter Wert, den der Vertrag überging. Das ist eine Lücke der
Abnahmebasis, keine der Umsetzung.

Die Umsetzung bildet ihn auf `order_id` ab. **Begründung:** Die Spalte
kennt nur `order_id`/`heuristik`/`manuell`, also kein `auto`. Eine
Zuteilung ist eine vom Broker gebuchte Tatsache (`ereignistyp =
'assignment'`), kein aus zeitlicher Nähe gezogener Schluss — `heuristik`
wäre also falsch. Dieselbe Begründung trägt bereits die Attribution auf
der Kettenseite: `chain_links.erkennung` steht für denselben Übergang auf
`auto` (AP-04).

**Wo es unsauber bleibt:** `order_id` behauptet wörtlich eine Ordernummer,
die es hier nicht gibt. Das Vokabular der Spalte stammt aus AP-01 und
unterscheidet nur zwei Herkünfte, wo es fachlich drei gibt (belegt durch
Ordernummer, belegt durch Brokerereignis, erschlossen). Solange nichts
davon abhängt, ist das folgenlos; sobald eine Auswertung nach
Belegqualität filtert, gehört das Vokabular erweitert — dann über eine
Migration, nicht über eine Umdeutung.

## OF-40 · AP-13-Parser: nicht ausgeführte Trades und eine zweite Exportvariante

**Befund 21.09.2026.** Nach AP-13q liest der Parser die Februardatei
vollständig, die Januar- und Augustdatei aber nicht. Gemessen (nur Formen
und Zählwerte): `Profit` als Zahl statt deutschem Text (Januar, alle 268
Zeilen), `Stops` leer (Januar 50), `Stops` mit zwei zeilengetrennten Werten
(Januar 3, August 31 — nur bei Trades mit drei oder vier Legs), `Open = '-'`
(Januar 179) und `Strikes` ohne Leg-Grammatik (Januar 207 Ausschnitte).

Entscheidend: **Alle 207 Grammatikabweichungen gehören zu `CANCELED`- oder
`RUNNING`-Trades** — Abbruchgründe bzw. geplante Legs mit Restlaufzeit
statt Verfallsdatum. Über alle 1.114 Legs ausgeführter Trades hält die
Grammatik ausnahmslos. Die Januardatei ist eine zweite Exportvariante,
keine defekte Datei.

**Geregelt durch AP-13pm (Abnahmebasis, Vertrag 14–18)**, Umsetzung AP-13r
beim günstigen Modell. Ein Trockenlauf mit genau diesen Regeln liest alle
drei Exporte vollständig; ohne Legs bleiben exakt die 179 `CANCELED`- und
8 `RUNNING`-Trades.

**Zwischenfall, Regel 2:** Beim ersten Lauf von `golden_oa_abgleich.py`
über die Januar- und Augustdatei hat die unbehandelte Parsermeldung zwei
OA-Tradenummern, einen Profit- und zwei Stopwerte in die Konsolenausgabe
geschrieben. Das Skript fängt Parserfehler jetzt ab und nennt nur noch das
betroffene Feld.


## OF-41 · Das Drei-Minuten-Fenster erkennt Rolls unzuverlässig (AP-04, Stichprobe)

**Erste Durchsicht durch den Nutzer, 21.09.2026.** Die dritte
AP-04-Abnahmeprüfung (Stichprobe, Nicht-OA-Teil) liegt beurteilt vor:
20 Nummern, davon 12 gerollte Ketten mit mindestens einem nur erschlossenen
Glied, 8 ausschließlich über die Order-Nummer belegte und 10 Paare der
Gegenprobe.

| Block | Urteil |
|---|---|
| Belegt (`exec_batch`) | **8 von 8 richtig** |
| Heuristik (Zeitfenster) | 6 richtig, **5 falsch**, 1 ohne Urteil |
| Gegenprobe (nicht verkettet) | 4 richtig, **4 falsch**, 2 unklar |

**Der belegte Weg trägt.** Kein einziger Fehler — das deckt sich damit, dass
Rolls üblicherweise als eine Order ausgeführt werden (Nutzer, 19.09.2026).

**Das Zeitfenster trägt nicht.** Es irrt in beide Richtungen:

- *Falsch verkettet:* In drei Fällen war die neue Position ein
  **Wiedereinstieg nach einem Profit Target**, kein Roll („Trade wurde nur
  nach einem PT als re-entry gestartet"), in einem weiteren eine schlichte
  Neueröffnung („Kein Roll – open"). Schließen und kurz darauf neu eröffnen
  sieht in den Brokerdaten genauso aus wie ein Roll.
- *Roll übersehen:* Beide Paare im Abstand von 3 bis 30 Minuten waren echte
  Rolls — das Fenster ist zu eng. Zwei der drei Fälle „alt schon
  fortgesetzt" ebenfalls: `_rolls_verketten()` vergibt die Fortsetzung an
  den ersten passenden Kandidaten und verbaut sich damit den richtigen.

Die Mengenregel (±20 %) sieht dagegen brauchbar aus: 3 von 4 richtig, zweimal
mit dem Hinweis „Pos gesplitted". Ein Fall der Gegenprobe zielt auf die
Strukturbildung, nicht auf die Verkettung („Offensichtlicher Trade falsch
gebaut") und ist gesondert zu prüfen.

**Nicht entschieden (Regel 10).** Die Stichprobe ist zu klein für einen
Schluss auf die Grundgesamtheit, und das Urteil erging ohne die Preise — ohne
sie ist ein Roll von einem Wiedereinstieg kaum zu unterscheiden. Deshalb
zweite Runde: `Stichprobe_Ketten_v2.xlsx` trägt Eröffnungs- und Schlusspreis
je Glied (Nettoprämie je Kontrakt, geprüft gegen das Bruttoergebnis: 142 von
142 stimmen exakt), übernimmt die bisherigen Urteile und vergrößert den
Heuristik-Block auf 25 Ketten.

**Was danach zu entscheiden ist:** Nach Regel 7 sind automatisch erzeugte
Verknüpfungen ohnehin Vorschläge, keine Tatsachen. Bestätigt die zweite
Runde das Bild, liegt es nahe, Zeitfenster-Verknüpfungen wie die
Futures-Rolls zu behandeln — als Kandidaten zur Bestätigung statt als Kette.
Das betrifft die Roll-Degradation unmittelbar und ist eine Planfrage, keine
stille Korrektur.

### Zweite Runde, mit Preisen (21.09.2026) — bestätigt, und die Ursache wird sichtbar

43 Nummern, alle beurteilt:

| Block | richtig | falsch | unklar |
|---|---|---|---|
| Belegt (`exec_batch`) | 8 | **0** | 0 |
| Heuristik (Zeitfenster) | 12 | **10** | 3 |
| Gegenprobe (nicht verkettet) | 3 | **4** | 3 |

**Die Menge ist der wunde Punkt, nicht die Zeit.** Sechs von neun
Bemerkungen nennen sie: „Pos gesplitted" (zweimal), „Zeit stimmt, Anzahl
nicht" (zweimal), „Spread erweitert", „Anzahl Pos nicht richtig
(gesplittet?)". Ein Roll ist im Bestand **keine Eins-zu-eins-Nachfolge**
einer Struktur durch eine andere: Positionen werden geteilt, zusammengelegt,
erweitert, teilweise gerollt. Das Kettenmodell unterstellt genau diese
Eins-zu-eins-Nachfolge. Deshalb prüft die Mengenregel eine Gleichheit, die
es nicht gibt, und scheitert in beide Richtungen.

**Der Befund, der schwerer wiegt als jede Fehlerquote (Nutzer, 21.09.2026):**
„Retrospektiv ist es nicht mehr so einfach zu erkennen, was gerollt wurde."
Ist die Absicht im Nachhinein selbst für den Händler nicht sicher
rekonstruierbar, gibt es für den heuristischen Teil **keine belastbare
Wahrheit** — weder für ein Abnahmekriterium noch als Lernmaterial für ein
Modell. Das ist keine Eigenschaft der Engine, sondern der Datenlage: Der
Broker zeichnet Ausführungen auf, keine Absichten.

**Erwogen und verworfen: ein gelerntes Modell.** Der Gedanke lag nahe, die
Erkennung aus den Bestätigungen lernen zu lassen statt Schwellen von Hand
zu setzen. Dagegen sprechen drei Dinge, keines davon algorithmischer Natur:
Das Material ist dünn und unsicher (43 Urteile, sechs davon „unklar"), ein
darauf trainiertes Modell erbt diese Unsicherheit und verbirgt sie hinter
einem Punktwert, und AP-06 verlangt Drilldown bis zur Ausführung — eine
Zahl, die niemand aufdröseln kann, erfüllt das nicht. Wo Lernen sich lohnen
würde: **Kandidaten sortieren**, damit die wahrscheinlichsten zuerst zur
Bestätigung kommen. Als Arbeitserleichterung, nicht als Wahrheitsquelle.
Zurückgestellt, bis genug bestätigte Fälle vorliegen.

**Entschieden (Nutzer, 21.09.2026):** Nur belegte Verknüpfungen bilden
Ketten; Zeitfenster-Treffer werden Kandidaten zur Bestätigung. Ausformuliert
im Plan, §6, AP-04, Block B. Die eigentliche Abhilfe liegt vorn, nicht
hinten: AP-11 schreibt die Absicht beim Aufsetzen mit.

## OF-42 · Strukturbildung: eine Order über mehrere Verfallstermine

**Befund 21.09.2026, aus der Stichprobe (Nr. 39, „Offensichtlicher Trade
falsch gebaut").** Block A, Regel 1 fasst alle Legs mit gleichem
`ibExecID`-Präfix zu einer Struktur zusammen — ohne Bedingung an die Expiry.
Der beanstandete Fall ist eine `Custom`-Struktur mit vier Put-Legs über
**zwei Verfallstermine**, alle aus einer einzigen Combo-Order.

**Gemessen über den gesamten Bestand:** 382 der 8.880 Strukturen umfassen
mehr als einen Verfallstermin, sämtlich als `Custom` klassifiziert.

| Herkunft | Anzahl | Einordnung |
|---|---|---|
| OA-Referenz (`methode = 'oa'`) | 245 | **unbedenklich** — OA bucht solche Trades selbst so (Diagonalen, Doppeldiagonalen); der Referenzexport bestätigt die Form |
| `exec_batch`, Order hat nur eröffnet | 80 | plausibel eine echte Diagonale |
| `exec_batch`, Order hat zugleich Legs geschlossen | **57** | **verdächtig** — das ist das Bild eines in einer Order gebündelten Rolls |

**Die Lücke liegt zwischen Block A und Block B.** Block B, Regel 1 erkennt
den Roll daran, dass eine Combo-Order gleichzeitig schließt und eröffnet.
Block A hat die eröffnende Seite dieser Order aber vorher schon zu **einer**
Struktur verschmolzen — auch wenn sie zwei Verfallstermine umfasst. Wo die
neue Position selbst wieder aus zwei Terminen besteht, ist nicht mehr
unterscheidbar, was Fortsetzung und was eigenständige Position ist.

**Nicht entschieden, nicht geraten (Regel 10).** Die Mehrterminigkeit allein
ist **kein** Fehlerkennzeichen — 245 Fälle sind extern bestätigt. Zu klären
ist nur, ob die 57 Fälle mit gleichzeitiger Schließung anders zu schneiden
sind. Denkbare Wege: die eröffnende Seite einer schließenden Combo-Order nach
Verfallstermin trennen, oder es beim heutigen Schnitt belassen und den Fall
als Kandidat kennzeichnen. Beides berührt Block A und damit die
Strukturbildung, nicht nur die Verkettung — ein eigener Auftrag, erst nach
der Entscheidung zur Kettenidentität.

**Nebenbefund zur Mengenwahrnehmung.** Zwei weitere Stichprobenhinweise
zielen nicht auf einen Fehler, sondern auf einen Unterschied im Bild: Nr. 26
(„Anzahl Pos nicht richtig (gesplittet?)") ist eine Vertikale über 31
Kontrakte, aus Teilfills verdichtet (Block A, Regel 1a); Nr. 41 („Spread
erweitert") sind zwei getrennte Zehnerpositionen sieben Stunden auseinander.
Die Engine rechnet beides regelkonform. Für die Anzeige heißt das: Teilfills
und Aufstockungen müssen sichtbar bleiben, sonst wirkt eine korrekte Menge
falsch (AP-08).

## OF-43 · Zwei Annahmen der Durchsicht, und ein Fehler im Zuschnitt von AP-04dv

**Nachgetragen 22.09.2026 durch das starke Modell.** Das Umsetzungspaket
AP-04d hat zwei Annahmen dokumentiert, konnte sie aber nicht hierher
schreiben: Die Abnahme in AP-04dv verlangte, der Diff dürfe ausschließlich
`journal/durchsicht.py`, `journal/rebuild.py` und `journal/cli.py` zeigen.
Damit hat **mein** Auftrag genau den Eintrag verboten, den Regel 10
vorschreibt. Das Paket hat sich richtig verhalten und die Annahmen in den
Modul-Docstring geschrieben; dort sucht sie später niemand.

**Lehre für künftige Abnahmebasen:** Die Diff-Zusage nennt ab jetzt immer
`OFFENE_FRAGEN.md` mit. Sie ist kein Umsetzungsartefakt, sondern die Stelle,
an der Ungeklärtes sichtbar bleibt.

### Annahme 1 · Preise je Kontrakt werden auf den Cent gerundet

Die Nettoprämie je Kontrakt entsteht durch Teilung durch die Strukturmenge
und kann nicht-terminierend sein (Menge 3 etwa). `Decimal` schnitte dann
still auf 28 signifikante Stellen ab — eine Rundung ohne Namen, die Regel 5
gerade verbietet. Gerundet wird deshalb ausdrücklich auf den Cent mit
`ROUND_HALF_UP`, wie `engine.matching` es für Ergebnis und Kommission
ebenfalls tut.

**Was daran offen bleibt:** Bei sehr kleinen Prämien ist der Cent grob —
eine Option zu 0,005 wird zu 0,01 oder 0,00. Folgenlos, solange die Spalte
nur der Anschauung dient und nie zurückgelesen wird (so der Vertrag). Wird
sie je Rechengrundlage, gehört die Genauigkeit vorher festgelegt.

### Annahme 2 · Dieselbe Zeile zweimal in einer Datei

Der Vertrag schweigt dazu, weil das Ausschreiben solche Dateien nie erzeugt
— von Hand eingefügte Zeilen könnten es. Behandelt wird die Datei
sequenziell: Die zweite Zeile mit demselben Urteil zählt als unverändert,
eine widersprechende fällt unter die Widerspruchsregel (Vertrag 14) und
bricht ohne `--ueberschreiben` ab. Das ist die vorsichtige Auslegung: keine
stille Entscheidung darüber, welche der beiden Zeilen gilt.

## OF-44 · AP-07l: drei kleine Annahmen an der Lese-API

**Eingetragen 22.09.2026 (Regel 10).** Der Vertrag aus AP-07lv lässt drei
Punkte offen; alle drei sind in `api/app.py` umgesetzt:

1. **`limit` hat keine Untergrenze.** Vertrag 4 nennt Vorgabe 50 und
   Höchstwert 500 und verlangt 422 für negative Werte; über `limit = 0`
   schweigt er. **Annahme:** mindestens 1 (`Query(ge=1)`) — eine Anfrage,
   die garantiert nichts zurückliefert, ist kein sinnvoller Grenzfall.
2. **Gleichstand im Drilldown.** Vertrag 7 ordnet „nach `handelszeit`
   aufsteigend"; bei gleicher Handelszeit (am Fixture Z3/Z4, beide
   15:00:00) fehlt eine Regel. **Annahme:** zweitsortiert nach `exec_id`
   aufsteigend — deterministisch, ohne fachliche Aussage.
3. **Richtung des Gleichstands in der Kettenliste.** Vertrag 4 sortiert
   `eroeffnet_am` absteigend und nennt `chain_id` als Zweitkriterium, aber
   keine Richtung. **Annahme:** aufsteigend — die natürliche Lesart einer
   Nummer als Sekundärkriterium.

**Abgenommen 22.09.2026 (Review durch das starke Modell).** Alle drei
Annahmen sind übernommen — sie sind eng, begründet und ohne fachliche
Folgen. Die Lücken lagen im Vertrag, nicht in der Umsetzung.

**Geprüft am echten Bestand** (7.183 Ketten, 9.203 Strukturen), über die
Konsolenausgabe hinaus nur Zählwerte und Laufzeiten (Regel 2):

- **Kein einziger `float` im JSON.** Rekursiv über alle Antworten gesucht —
  Entscheidung 1 hält nicht nur im Test, sondern über die Leitung.
- **Ergebnissumme stimmig:** 7.021 Ketten tragen eine, 162 nicht — und
  diese 162 sind **ausnahmslos** die offenen. Genau das verlangt
  Entscheidung 4; ein Feld, das immer leer bliebe, hätte kein Test bemerkt.
- **Jede Kette hat genau eine Währung.** Der gemischte Fall aus
  Entscheidung 3 kommt im echten Bestand nicht vor — er entsteht erst durch
  einen Override. Die Regel bleibt richtig, ist aber bis dahin theoretisch.
- **Laufzeiten für eine Oberfläche brauchbar:** Liste 20–350 ms, Einzelabruf
  und Drilldown 15–20 ms, Blättern bis Versatz 6.000 unter 100 ms.

**Nebenbefund, nicht dringend:** Starlette meldet beim Testclient, dass
`httpx` zugunsten von `httpx2` veraltet ist. Betrifft nur die Tests, nicht
die Auslieferung; beim nächsten Anfassen der Abhängigkeiten zu erledigen.

## OF-45 · AP-08l: drei Entscheidungen an der Naht zwischen API und Oberfläche

**Eingetragen 22.09.2026 (Regel 10).** Der Vertrag aus AP-08lv lässt drei
Punkte offen; alle drei sind in `api/app.py` umgesetzt:

1. **Wo `ui/dist` standardmäßig gesucht wird.** Vertrag 1 sagt „neben dem
   Projektverzeichnis“ — wörtlich genommen (Modul- oder Arbeitsverzeichnis)
   fände jeder Testlauf die einmal gebaute Oberfläche des
   Projektverzeichnisses, und `test_ohne_gebaute_oberflaeche_bleibt_die_api_nutzbar`
   wäre nach dem ersten `npm run build` rot: Der Normalzustand „frisch
   geklont, ohne Build“ (Vertrag 4) wäre nicht mehr prüfbar. **Annahme:** Der
   Standardbauort hängt an der Datenbankdatei (`ui/dist` in ihrem Verzeichnis),
   nicht am Modul- und nicht am Arbeitsverzeichnis. Im Betrieb (Datenbank im
   Projektverzeichnis, `uvicorn` von dort gestartet) ist dasselbe Verzeichnis
   gemeint; liegt die Datenbank woanders, bleibt die Wurzel bei der API und
   sagt, was fehlt.
2. **`ui_verzeichnis` angegeben, aber nicht vorhanden.** Der Vertrag regelt
   „angegeben und vorhanden“ und „ohne Angabe“; der Rest schweigt.
   **Annahme:** wie fehlend behandelt (404 mit Hinweis) — kein stiller
   Rückfall auf einen anderen Ort, der etwas Ungewolltes enthalten könnte.
3. **Kein ASGI-Server in den Abhängigkeiten.** Die Abnahme verlangt
   `npm run dev` gegen eine echte API auf localhost:8000, aber `pyproject.toml`
   nennt (zu Recht, solange nur der Testclient fragt) keinen Server — und
   steht diesem Paket nicht als Änderung zu. **Annahme:** `uvicorn` wird bei
   Bedarf in die Umgebung installiert; seine Aufnahme in die
   Abhängigkeiten ist eine Betriebsentscheidung für den Trading-Server (§3),
   nicht Teil dieses Pakets.

**Umsetzungshinweis (22.09.2026).** Das Projektverzeichnis liegt auf einem
laufwerkgebundenen Cloud-Volume (Google Drive). `npm install` bricht dort
beim Entpacken mit `EBADF`/`EPERM` ab, und das Volume verweigert auch
Junctions auf lokale Platten. Bauen funktioniert so: Quellen nach
`C:\td-build\ui` kopieren, dort `npm install` und `npm run build`, danach
`ui/dist` ins Projekt zurückkopieren — `.gitignore` nimmt `ui/dist` und
`node_modules` ohnehin nicht auf. Ein Umzug des Projekts auf ein lokales
Laufwerk macht den Umweg überflüssig.


## OF-46 · `uvicorn` war nicht deklariert (Fund im Review von AP-08l)

**Befund 22.09.2026.** `uvicorn` steckte im virtuellen Umfeld, stand aber in
keiner Abhängigkeitsliste. Auf einem frisch geklonten Rechner wäre die
Anwendung nach `pip install -e .` nicht startbar gewesen — FastAPI bringt
keinen Server mit.

Die Lücke lag in den Abnahmebasen AP-07lv und AP-08lv: Sie nannten `fastapi`

## OF-58 · AP-10: Jahresgrenze der steuerlichen Auswertung ohne Zeitzonen (naiv, wie gespeichert)

Die steuerliche Auswertung (AP-10) legt das Zuflussjahr mit dem Jahr der
`handelszeit` der schließenden Ausführung fest — naiv, wie der Import die
Zeiten speichert (Anschluss an OF-04, das dieselbe Frage für die Engine
entschieden hat). Geschäfte kurz vor Mitternacht einer Jahrgrenze können so
im anderen Jahr landen, als eine um UTC (IB handelt in Amerika-typischen
Zeiten meist gegen 22:30 MEZ — die Grenzfälle sind selten, aber existieren).
Nicht geraten, sondern bewusst geparkt: Eine Zeitzonen-Migration wäre eine
eigene Datenmigration über alle `handelszeit`-Spalten mit eigener
Abnahmebasis; sie ändert Daten, nicht den Vertrag von AP-10. Bis dahin gilt
wie bei OF-04: naiv wie gespeichert, dokumentiert in
auftraege/AP-10v.md (Entscheidung 2, Regel 3).

## OF-59 · AP-10: EUR-Ausweis der Steuerzahlen über den Buchungskurs — die wirtschaftliche Sicht bleibt offen

AP-10 weist jede Topfzeile zusätzlich als `netto_eur_ib` aus: netto ×
`buchungskurs` der schließenden Ausführung. Das ist die Sicht, die auch IB
seinen Reports zugrunde legt (ein Kurs je Buchungstag), und damit die
einzige, die gegen IB prüfbar ist. Die steuerlich möglicherweise gebotene
Sicht — Kurs je Zahlungsstrom, d. h. Eröffnung und Schließung jeder Leg
einzeln umgerechnet — ist eine andere Zahl und mit dem Steuerberater zu
klären; sie bewusst nicht geraten. Zwei Konsequenzen sind dokumentiert:

1. Fehlt der Buchungskurs einer Schließung, bleibt die EUR-Spalte für diese
   Leg leer, `eur_kurs_fehlt` zählt den Mangel und die Fehlerliste benennt
   ihn (`buchungskurs_fehlt`) — kein stiller Kurs 1, auch nicht bei
   EUR-Instrumenten (AP-10v, Regel 6).
2. Bei Zuteilung/Ausübung kann die Journa-Zahl von der IB-Zahl abweichen,
   weil die geparkte Prämie (OF-24-Auflage) noch nicht gebaut ist. AP-10
   exportiert deshalb nur die Journa-Sicht-Komponenten; die
   IB-Paritätbarkeit folgt mit OF-24, nicht hier.

und `httpx`, aber nicht den Server, der beides ausliefert. Nachgetragen als
Laufzeitabhängigkeit.

**Lehre, dieselbe wie bei OF-43:** Eine Abnahmebasis muss nicht nur sagen,
was der Code tun soll, sondern auch, was nötig ist, damit er läuft. Beides
ist Vertrag.


## OF-47 · AP-07p: Prämie der Kette bei gleicher `sequenz` zweier Glieder

**Befund.** Vertrag P8 (AP-07pv) füllt `eroeffnungspreis` und
`schlusspreis` der Kette aus dem **ersten** und **letzten** Glied, sagt aber
nicht, welches Glied bei gleicher `sequenz` in `chain_links` meint. Das
Schema erzwingt keine Eindeutigkeit — der Primärschlüssel ist
(chain_id, structure_id), nicht (chain_id, sequenz).

**Annahme:** Aufsteigend nach `(sequenz, structure_id)`: Das erste Glied
ist die kleinste, das letzte die größte Paarung. Die Engine vergibt
Sequenzen je Kette fortlaufend, Gleichstand ist nicht beobachtet; die Regel
folgt dem Determinismus-Muster von OF-44 (Gleichstand entscheidet eine
aufsteigende Nummer). Ort: `api/app.py`, `_ketten_zuschuesse()`.

**Offen:** Ob die Engine Sequenzen je Kette jemals doppelt vergibt — falls
ja, wäre eine garantiert eindeutige Vergabe in `engine.chains` das bessere
Mittel als eine Verregelung des Gleichstands.

## OF-48 · P4 aus AP-07pv galt nicht allgemein — mein Fehler im Vertrag, nicht in der Umsetzung

**Befund im Review von AP-07p, 27.09.2026.** Die Abnahme des Pakets nannte
als Probe: `(eroeffnungspreis + schlusspreis) × menge × multiplikator =
brutto_pnl`, geprüft an einer Stichprobe von 200 Strukturen mit einer
gefundenen, vertragsgerecht erklärten Abweichung. Ich habe die Probe am
gesamten Bestand wiederholt: **406 von 9.041 geschlossenen Strukturen
(4,5 %) weichen ab.** Bei 355 davon sind die Beinmengen sogar gleich — ein
Ratio-Effekt (ungleiche Mengen je Bein) scheidet als Haupterklärung damit
aus. 400 der 406 betreffen Optionen; ihre schließenden Beine enden
überwiegend per Zuteilung, Ausübung oder Verfall statt per Handel.

**Ursache, keine Fehlfunktion:** `brutto_pnl` bewertet bei Zuteilung,
Ausübung und Verfall über die Barausgleichsregel (AP-03vb, OF-25) — eine
andere Grundlage als der rohe Ausführungspreis, den `eroeffnungspreis`/
`schlusspreis` nach Vertrag P1 konsequent abbilden. Beide Zahlen sind für
sich richtig; sie beschreiben nur nicht dieselbe Größe, sobald ein Bein
nicht per `trade` schließt.

**Aufgelöst:** `auftraege/AP-07pv.md`, P4, um die Einschränkung ergänzt
(nur für ausschließlich per `trade` geschlossene Strukturen) und der
Befund dort mit den Zahlen hinterlegt. Kein Code geändert — die Prämien
sind korrekt, so wie P1 sie verlangt.

**Nebenbefund zum Vorgehen:** Bei der Untersuchung habe ich zunächst mit
einer fehlerhaften SQL-Abfrage (falscher Multiplikator-Bezug) gearbeitet
und dabei kurz reale Ausführungs-Kennungen und Dollarbeträge aus
`journal.db` in die Analyse gedruckt, bevor ich auf reine Zählwerte
umgestellt habe. `journal.db` liegt nicht unter `fixtures/golden/` und
Regel 2 nennt wörtlich nur dieses Verzeichnis — aber sie enthält echte
Kontodaten aus den Flex-Exporten, und dem Sinn der Regel nach hätte ich von
Anfang an so vorgehen sollen wie die Abgleichsskripte unter
`werkzeuge/abgleich/`: nur Zählwerte, Kategorien und Verhältnisse, nie
Rohwerte. Für künftige Diagnosen an `journal.db` gilt dieselbe Disziplin
wie für `fixtures/golden/`.

## OF-49 · Financing-Kandidat: 24-Stunden-Fenster als Annahme, nicht gemessen bestätigt

**Annahme, dokumentiert 27.09.2026 beim Zuschnitt von AP-05v (Regel 10).**
Der Plan nennt für den Financing-Kandidaten „im zeitlichen Umfeld eines
Rolls", ohne Zahl. Gemessen am echten Bestand (nur Zählwerte, Regel 2):

| Fenster | Kandidatenpaare |
|---|---|
| 1 Stunde | 161 |
| 6 Stunden | 351 |
| 24 Stunden | 518 |
| 72 Stunden | 1.029 |
| 1 Woche | 2.193 |

Kein natürlicher Sprung, der eine Grenze nahelegt — die Zahl wächst
durchgehend mit der Fensterbreite. Gewählt: **24 Stunden** (ein
Handelstag), als plausibelste Lesart von „im Umfeld", benannt als
`FINANCING_FENSTER` in `engine/campaigns.py`.

**Unterschied zum Rollkandidatenfenster (OF-41):** Dort bestätigte eine
Nutzer-Stichprobe die gewählten 30 Minuten nachträglich. Für das
Financing-Fenster gibt es diese Bestätigung noch nicht — die 24 Stunden
sind eine Annahme, keine gemessene Tatsache. Da Financing-Kandidaten
laut Plan ohnehin nur Vorschläge sind, über die der Nutzer entscheidet
(„Vorschläge werden nie automatisch übernommen"), ist das Risiko einer zu
groben Schätzung begrenzt: ein zu enges Fenster verbirgt echte Kandidaten,
ein zu weites erzeugt zusätzliche, die der Nutzer verwirft. Sobald ein
Klassifikationsdialog existiert und Entscheidungen vorliegen, sollte das
Fenster anhand dieser Entscheidungen überprüft werden — analog zur
Stichprobe, die das Rollkandidatenfenster bestätigt hat.

## OF-50 · Rollkandidaten: eine bereits belegte Struktur bekommt nie einen zweiten Kandidaten

**Befund 27.09.2026, bei der Kreuzprobe der Stichprobe gegen die heutige
Kandidatenliste** (`werkzeuge/abgleich/golden_stichprobe_kreuzprobe.py`,
Nachweis für die dritte AP-04-Abnahmeprüfung). Die Prüfung nimmt jeden vom
Nutzer bestätigten Roll aus den beiden Stichprobenrunden und sucht ihn in
der heutigen Kandidatenliste. Ergebnis:

| | Anzahl |
|---|---|
| bestätigte Rolls geprüft | 10 |
| davon als Kandidat gefunden | 7 |
| davon **fehlt** als Kandidat | **3** |
| nicht eindeutig auf Structures rückführbar (Messgrenze, siehe unten) | 6 |

Alle drei fehlenden Fälle haben **dieselbe Ursache**: Die schließende
Struktur war zum Zeitpunkt der Schließung bereits per `exec_batch` (belegte
Order-Fortsetzung) mit einer *anderen* Struktur verknüpft.
`rollkandidaten()` schließt eine Struktur, die schon belegt fortgesetzt
ist, vollständig von der Kandidatenliste aus (`engine/chains.py`, Vertrag 5
aus AP-04k: „Was belegt ist, wird nicht gefragt"). Bestätigt der Nutzer
aber einen **zweiten**, unbelegten Roll **derselben** Struktur — ein
Teil-Roll über zwei Orders, bei dem ein Teil der Position in einer
Combo-Order und der Rest separat rollt —, gibt es dafür heute **keinen**
Kandidaten. Nicht, weil er außerhalb des Zeitfensters läge oder die
Mengenregel griffe, sondern weil die Struktur als „schon erledigt" gilt,
sobald irgendeine belegte Fortsetzung existiert.

**Aufgelöst 27.09.2026, durch direkte Klärung mit dem Nutzer anhand seiner
Brokerhistorie.** Die drei Fälle einzeln geprüft:

- **Nr. 40** (Fall 1, Größenveränderung): Vom Nutzer bestätigt als **kein**
  Roll — „neue Position unabhängig von der ersten". Die tatsächliche
  Fortsetzung von `alt` ist die bereits belegte (gleiche Menge, gleicher
  Zeitstempel); der Gegenprobe-Kandidat war eine andere, 71 Sekunden
  später eröffnete, unabhängige Position.
- **Nr. 42:** Vom Nutzer bestätigt als **kein** Roll — ebenfalls „neue
  Position unabhängig von der ersten" (andere Strikes).
- **Nr. 43:** Erinnerung des Nutzers („Anzahl beim Rollen erhöht") passt
  nicht zu den Struktur-Daten — belegtes Ziel und Kandidat tragen beide
  dieselbe Menge, keine Erhöhung feststellbar. Weder bestätigt noch
  widerlegt; auf **„Unklar"** gesetzt.

**Wichtiger Grundsatz vom Nutzer für künftige Fälle:** „Wenn ein Trade zur
gleichen Sekunde eröffnet wird, wenn ein anderer geschlossen wird, dann ist
das sehr wahrscheinlich ein Rollvorgang." Genau das ist der Fall, den
`exec_batch` (Block B, Regel 1) erfasst — die drei hier untersuchten
„fehlenden" Kandidaten lagen alle **nicht** bei Abstand null, sondern
71 Sekunden bis 30 Minuten danach, und stellten sich als unabhängige
Positionen heraus, nicht als zweite Rollziele.

**Urteile in `Stichprobe_Ketten_v2.xlsx` nachgetragen** (Nr. 40, 42 auf
„Richtig" — korrekterweise kein Roll; Nr. 43 auf „Unklar"), mit Bemerkung
und Datum. Die Kreuzprobe erneut gelaufen:

| | Anzahl |
|---|---|
| bestätigte Rolls geprüft | 7 |
| davon als Kandidat gefunden | **7** |
| davon fehlt als Kandidat | 0 |

**Kein Korrekturbedarf an `rollkandidaten()`.** Der Ausschluss „was belegt
ist, wird nicht gefragt" (AP-04k, Vertrag 5) hat sich in allen drei
untersuchten Fällen als korrekt erwiesen — es gab keinen echten zweiten
Roll, den er übersehen hätte. Die ursprüngliche Vermutung „echte Lücke,
Teil-Roll über zwei Orders" hat sich unter genauerer Prüfung nicht
bestätigt.

**Zur Messgrenze der Kreuzprobe:** 6 der 22 in den beiden Stichproben als
„richtig" markierten Nummern ließen sich nicht eindeutig auf heutige
Structures zurückführen (Auflösung über Basiswert + exakten
Eröffnungszeitpunkt; mehrdeutig oder ohne Treffer). Das ist eine Grenze der
Rückführungsmethode, keine Aussage über die Engine.

**Für die AP-04-Abnahme:** Die dritte Prüfung („kein bestätigter Roll der
Stichprobe fehlt in der Kandidatenliste") gilt damit als **bestanden**.
Siehe `auftraege/AP-04.md` für den aktualisierten Abnahmestand.

## OF-51 · AP-05v widerspricht sich: Die Financing-Fixtures sind zugleich IC-Kandidaten, die Tests bestreiten das

**Befund 27.09.2026 bei der Umsetzung AP-05k.** Die vertragstreue
Implementierung von `engine/campaigns.py` scheitert an genau drei der
neun Tests in `tests/test_campaigns.py` — den drei Financing-Tests mit
Leer- bzw. Genau-eins-Erwartung. Nachrechnung der vier Vertrag-4-
Bedingungen von Hand (absichtlich nicht mit der Prädikatfunktion der
Implementierung) zeigt: **Alle drei Paare erfüllen alle Bedingungen des
IC-Kandidaten** — gleicher Basiswert, gegenläufige Seiten, am letzten
Glied gesetzte und identische Expiry, überlappende Intervalle nach
Entscheidung 1.

| Test | Paar (Kurzfassung) | IC nach Vertrag 4 | Test erwartet |
|---|---|---|---|
| `test_financing_kandidat_erkannt` | gerollte DAX-Put-Kette (letztes Glied: Expiry 16.10.) + Call-Vertikale Expiry 16.10., 2 h nach dem Roll eröffnet | ja | genau 1 Kandidat: `financing` |
| `test_financing_kandidat_ausserhalb_fenster_kein_kandidat` | dasselbe Paar, 30 h Abstand → financing nein | ja | `()` |
| `test_financing_kandidat_ohne_roll_kein_kandidat` | zwei ungerollte, offene DAX-Vertikalen, beide Expiry 18.09., Put 10:00 / Call 11:00 | ja | `()` |

Der dritte Fall ist der Lehrbuch-IC nach Entscheidung 1: zwei offene,
gegenläufige Ketten gleicher Expiry mit versetzten Eröffnungen — genau
die „rückwirkende Klassifikation", für die der Intervallvergleich
gewählt wurde. `assert ... == ()` ist mit Vertrag 4 nicht gleichzeitig
erfüllbar. Auffällig ist das Muster im IC-Block: Der einzige
IC-positive Test (`test_ic_kandidat_erkannt`) öffnet beide Ketten zum
identischen Zeitpunkt; alle IC-negativen Tests sperren je genau eine
Bedingung.

**Zwei Regeln würden die Suite grün machen — beide sind vertragsfremd:**
(a) IC nur bei identischem `eroeffnet_am` — widerspricht Entscheidung 1
ausdrücklich („zeitliche Überlappung, nicht ‚beide jetzt offen'"), und
fachlich werden Condor-Flügel praktisch nie im selben Moment eröffnet;
(b) IC nur bei Eröffnungsabstand innerhalb eines Fensters — ein solches
Fenster steht in keinem Vertrag. Eine Umsetzung, die eine davon
einbaut, wäre grün und trotzdem falsch. Deshalb Abbruch statt Trick
(CLAUDE.md Regel 1, 1a, 10).

**Vermutliche Ursache:** Die Financing-Fixtures wurden mit der Expiry
des letzten Roll-Glieds (16.10.) gebaut, damit der Roll-Kontext stimmt
— dabei übersehen, dass die Gegenkette dieselbe Expiry trägt und damit
die IC-Bedingung miterfüllt. Im IC-Block ist das Vergleichsmuster sauber
gesetzt (jeder Test sperrt genau eine Bedingung), im Financing-Block
fehlt diese Isolierung.

**Vorgeschlagene Auflösung — Korrekturpaket** (`aendert_tests: ja`,
`modell: stark`, nach Regel 1a): In den drei Financing-Tests die Expiry
der Gegenkette von der Expiry des letzten Glieds der Bestandskette
abweichen lassen. Dann prüft jeder Test weiterhin genau die
Financing-Regel, und alle Erwartungen stimmen, ohne dass am Vertrag
etwas zu ändern wäre. Alternative: die Erwartungen erweitern (`erkannt`:
2 Kandidaten, `financing` vor `ic`; die beiden Leerfälle: je 1 `ic`) und
dokumentieren, dass IC und Financing sich pro Paar nicht ausschließen —
das änderte aber Testnamen und Aussageabsicht. Erstere Variante ist
empfohlen; sie hält die Isolierung bei, die der IC-Block vorlebt.

**Stand:** `engine/campaigns.py` liegt vor, ist vertragstreu (Vertrag
1–7 aus `auftraege/AP-05v.md` Punkt für Punkt geprüft) und
`ruff`-sauber; alle übrigen Tests laufen grün. Die Datei bleibt
uncommittet und das Paket offen, bis die Basis korrigiert ist — danach
kann die Umsetzung mit Testlauf und Commit in einem Zug fertigstellen.

## OF-52 · AP-04s: Wie behandelt die Kettensicht ein Bein, dessen Schließung eigentlich einem anderen Vorgang gehört (Nutzerentscheidung)

Beim Zuschnitt von AP-04s (Kettensicht) zeigte sich eine Stelle, die der
Plan offenlässt: Bei den 206 Ausführungen aus OF-36 eröffnet eine
Ausführung offiziell einen neuen OA-Vorgang (B), wurde aber von der
kontoweiten FIFO-Verrechnung tatsächlich zur Schließung eines anderen,
älteren Vorgangs (A) auf demselben Conid verwendet. Für die Kettensicht
sollte B sein eigenes eröffnetes Bein bekommen — aber dann fehlt A eine
Schließung, obwohl real längst realisiert.

**Zwei Wege standen zur Wahl:**

1. Kettensicht folgt strikt den OA-Trade-Tags — A bleibt ohne Schließung
   „offen“, kein Ergebnis für dieses Bein.
2. Dieselbe Ausführung zählt doppelt: sie schließt A **und** eröffnet B
   gleichzeitig — beide Rollen sind für dasselbe reale Ereignis wahr.

**Entscheidung des Nutzers (28.09.2026): Weg 2 — Ausführung zählt
doppelt.** Jeder Vorgang bekommt ein vollständiges Ergebnis; das
entspricht der ursprünglichen Planformulierung „sonst bliebe das Bein
verschwunden“.

**Konsequenz für den Zuschnitt von AP-04s:** Die Kettensicht braucht eine
eigene, vorgangsbezogene FIFO-Zuordnung zusätzlich zur bestehenden
kontoweiten (Kontosicht). Eine Ausführung kann in dieser Zuordnung
gleichzeitig als Schließung eines Beins in Vorgang A und als Eröffnung
eines Beins in Vorgang B auftreten — pro Sicht ein eigener, in sich
vollständiger Satz von Legs/Strukturen/Ketten, `sicht` als Pflichtfeld,
nie in einer Abfrage gemischt (CLAUDE.md-Anschlussregel aus der
Zwei-Sichten-Entscheidung, siehe `auftraege/AP-07-vorschlag-zwei-sichten-und-vorziehen.md`).
Die konkrete Abnahmebasis (Vertrag, Tests, Fixtures) schreibt AP-04s
selbst; hier ist nur die Grundsatzentscheidung festgehalten.

## OF-53 · AP-13v: Der Fingerabdruck des OA-Abgleichs verzichtet auf die Entry Time

Plan §6.1 beschreibt die Absicherung der Verknüpfung als „Entry Time
sekundengenau plus die vollständige Leg-Spezifikation". `auftraege/AP-13-
anhang-oa-format.md`, Punkt 4 (bereits committet, aus einem früheren
AP-13p-Paket) widerspricht dem scheinbar: „Zeitstempel nicht zum Abgleich
verwenden. Das Format ist ein drittes neben TDP und Flex, und die Zeitzone
ist ungeprüft. Die Verknüpfung stiftet ausschließlich die Klammernummer."
`journal/schema.py` hält an `optionapp_trades.entry_zeit` dieselbe Warnung
fest.

**Auflegung, keine Annahme wider den Plan:** Beide Aussagen sind
vereinbar, wenn man den Fingerabdruck aus §6.1 auf seinen zweiten
Bestandteil reduziert — die vollständige Leg-Spezifikation (Richtung,
Menge, Typ, Strike, Expiry je Leg) — und die Entry Time weglässt, weil sie
laut der bereits getroffenen, committeten Entscheidung des AP-13p-Pakets
nicht vergleichbar ist. `engine/oa_abgleich.py` (AP-13v/AP-13k) vergleicht
deshalb nur die Leg-Signaturen als Menge, nicht die Zeit. Die Nummer bleibt
der alleinige Primärschlüssel (§6.1, „Entschieden"); der Fingerabdruck ist
weiterhin nur Absicherung — eine Abweichung verwirft die Zuordnung nicht,
sondern markiert sie als `erkennung="heuristik"` statt `"auto"` (Regel 7).
**Annahme:** `engine/oa_abgleich.py`, Modul-Docstring.

## OF-54 · AP-05: Wie persistiert eine abgelehnte Campaign-Kandidatur?

Für einen **bestätigten** IC- oder Financing-Kandidaten ist der Weg klar:
`campaigns`-Zeile anlegen (oder eine bestehende erweitern), dann für jede
der beiden Ketten eine `campaign_links`-Zeile mit `beziehungstyp`,
`erkennung = 'manuell'`, `bestaetigt_am`.

Unklar ist die **Ablehnung** — der Nutzer sieht einen Kandidaten
(z. B. zwei Ketten, die zufällig wie ein IC aussehen, aber inhaltlich
nichts miteinander zu tun haben) und will das dauerhaft festhalten, wie
bei Rollkandidaten `chain_overrides.urteil = 'abgelehnt'` es tut — sonst
taucht derselbe Kandidat bei jedem `journal rebuild` erneut als „offen"
auf. `campaign_links.beziehungstyp` kennt zwar den Wert `'independent'`,
aber die Zeile verlangt einen `campaign_id` (Primärschlüssel-Teil,
Fremdschlüssel auf `campaigns`) — für eine abgelehnte **Paarung** zweier
Ketten ist unklar, ob das heißt: (a) beide Ketten bekommen je eine eigene
Singleton-Kampagne mit `beziehungstyp = 'independent'`, oder (b) es
braucht eine eigene Tabelle nach dem Muster von `chain_overrides` — mit
den zwei Ketten-IDs und dem Kandidatentyp als Schlüssel, ohne
`campaign_id` — analog zur Rollkandidaten-Ablehnung.

**Nicht geraten**, weil beide Lösungen das Datenmodell auf Dauer
unterschiedlich prägen (Singleton-Kampagnen tauchen in jeder
Kampagnenliste auf; eine eigene Ablehnungstabelle nicht). Vorerst gebaut:
nur die **Sichtbarkeit** offener Kandidaten (`AP-05s`) — reine Lesefunktion,
ohne Schreiben, betrifft diese Frage nicht. Die Persistenz von
Bestätigung/Ablehnung ist ein eigenes, noch nicht begonnenes Paket, das
diese Frage vorher klären muss.

## OF-55 · AP-13vk2: Fingerabdruck verglich Vorzeichen gegen Betrag (Menge) — behoben

Beim Nachweis der AP-13-Abnahme (`werkzeuge/abgleich/
golden_oa_abgleich_verknuepfung.py` gegen `fixtures/golden/
Trades_2026-02_OA.xlsx`) fand sich, dass `engine.oa_abgleich`s Fingerabdruck
(seit AP-13vk, Menge als Teil der Leg-Spezifikation) am echten Bestand
**0 von 66** statt der erwarteten ~61 von 66 Treffer erzielte — eine
Regression, die die rein erfundenen Tests von AP-13vk nicht zeigen
konnten.

**Ursache:** `executions.menge` trägt bei IBs Flex-Import das Vorzeichen
von `quantity` unverändert (negativ bei Sell, `ingest/flex.py`); OAs
`Strikes`-Spalte meldet je Leg nur den **Betrag** — die Richtung steht
separat im führenden Minus des Leg-Tokens (`_legs_zerlegen()`). Der
Fingerabdruck verglich also faktisch Vorzeichen gegen Betrag. Die
AP-13vk-Testfixtures hatten das nicht aufgedeckt, weil sie
`executions.menge` immer positiv konstruiert haben, unabhängig von
`side` — anders als die echten Daten.

**Behoben:** `engine/oa_abgleich.py`, `_eigene_legs()` vergleicht jetzt
`abs(menge)`. Neuer Test `test_signierte_ausfuehrungsmenge_zaehlt_
trotzdem_als_treffer` (`tests/test_oa_abgleich.py`) mit einer signierten
Ausführungsmenge, Regel 1a (Korrekturpaket, nur diese eine Erweiterung).
Nachgemessen: wieder 61 von 66 auto, 5 von 66 heuristik — deckungsgleich
mit dem unabhängigen `golden_oa_abgleich.py` (92,4 % exakt ohne Menge,
vor AP-13vk).

## OF-56 · AP-13vk2: Ergebnisabgleich verglich OA-Profit gegen Brutto statt Netto — behoben

Bei derselben Golden-Messung war die zweite Abnahmegröße auffällig: der
Ergebnisabgleich (`ergebnis_eigen = chain.brutto_pnl`) traf bei nur 1 von
66 Trades auch nur näherungsweise (± kleines Toleranzband). Eine Messung
gegen das **Netto**-Ergebnis (`chain.brutto_pnl + chain.kommission_
gesamt`) traf dagegen bei 36 von 66 (11 exakt, 25 im Ein-Dollar-Band) —
OAs `Profit`-Spalte ist erkennbar bereits kommissionsbereinigt, wie in
jedem Trading-Journal üblich, nicht der Bruttoerlös vor Kosten.

**Behoben:** `engine/oa_abgleich.py`, `oa_abgleich()` — `ergebnis_eigen`
jetzt `chain.brutto_pnl + chain.kommission_gesamt`. Neuer Test
`test_ergebnisabgleich_vergleicht_netto_nicht_brutto` mit von Hand
gerechnetem Beispiel (Regel 8: 120,00 + (−3,00) = 117,00).

**Nicht vollständig gelöst — siehe OF-57:** Auch gegen Netto bleiben 29
von 66 (44 %) ohne Erklärung im Toleranzband. Die AP-13-Abnahme („Abweichungen
... sind erklärbar") ist damit **noch nicht erfüllt** — `auftraege/
AP-13.md` bleibt deshalb bewusst `offen`, trotz 100 % Abdeckung und leerer
Fehlerliste.

## OF-57 · AP-13: 29 von 66 Ergebnisabweichungen (Netto) bleiben nach OF-56 unerklärt

Nach der Netto-Korrektur (OF-56) bleibt eine erhebliche unerklärte
Restmenge. Eine erste, grobe Auffälligkeit (gemessen, nicht verifiziert):
Ketten mit Endzustand **Verfall** sind unter den unerklärten Fällen
deutlich überrepräsentiert (19 von 33 Verfall-Fällen unerklärt, aber nur
6 von 25 „Geschlossen"-Fällen) — kein sauberer Auslöser (auch „Geschlossen"
hat unerklärte Fälle, auch „Verfall" hat erklärte), aber ein Hinweis, der
an OF-25/OF-48 erinnert (Barausgleichsregel: die Engine bewertet manche
Schließungsarten wirtschaftlich anders als die rohe Ausführung/Prämie).

**Nicht geraten, nicht weiterverfolgt** — das bräuchte eine eigene,
sorgfältige Untersuchung wie OF-48, keinen Schnellschuss innerhalb eines
Vorbereitungspakets. Bis dahin bleibt AP-13s dritte Abnahmegröße
(„Abweichungen erklärbar") offen; die ersten beiden (Abdeckung ≥ 95 %,
Fehlerliste) sind mit OF-55/OF-56 klar erfüllt (100 % Abdeckung, 0
Fehler, gemessen an `Trades_2026-02_OA.xlsx`).

## OF-60 · fx_rates: Tageskurs-Regel „letzte Ausführung des Tages" ist eine Annahme

Der Plan (§5) nennt `fx_rates` als Kursquelle der Analyseschicht, aber ohne
Regel, welcher Kurs an einem Tag mit mehreren verschiedenen
`fxRateToBase`-Werten gilt (AP-06v, Entscheidung E3).

**Annahme (AP-06v, Regel 11):** Kennzahlen rechnen niemals aus `fx_rates`,
sondern je Ausführung mit deren eigenem `buchungskurs` (wirtschaftliche
Sicht). `fx_rates` ist eine verwerfbare Materialisierung für Inspektion und
spätere Tranchen: je (datum, waehrung ≠ EUR) der `buchungskurs` der letzten
Ausführung des Tages (max `handelszeit`, Gleichstand größte `exec_id`),
`quelle = 'abgeleitet_letzte_ausfuehrung'` — als abgeleitet gekennzeichnet,
damit sie niemand mit einer echten Kursquelle verwechselt (Nutzerfreigabe
E3). Anlage: `analytics/kennzahlen.py`
(`fx_tageskurse`, `kennzahlen_bericht`).

**Offen:** (a) Ob Tranche IV (Equity-Kurve/metrics-Cache) stattdessen einen
Tagesendkurs oder -durchschnitt braucht — dann Regel 11 dort erweitern und
`quelle` unterscheiden. (b) Ob `fxRateToBase` an echten Tagen überhaupt
streut — beim ersten echten Datenbestand messen und hier nachtragen.

## OF-61 · Kettensicht: Wie kommen Overrides (bestätigte Rolls) hinein?

AP-04sw wendet `chain_overrides` bewusst nur in der Kontosicht an — Grenze
von AP-04s („kein Override-Schutz" für die Kettensicht). Bestätigte Rolls
existieren in der Kettensicht also nicht. Die Abnahme von AP-06 (Plan §6)
verlangt die Roll-Degradation aber „wahlweise nur auf belegten Ketten oder
auf belegten plus bestätigten" und nennt in beiden Fällen die Abdeckung —
die bestätigte Variante ginge mit der Freigabe von E1 in AP-06v sonst still
verloren.

**Entschieden (Nutzerfreigabe E1, AP-06v):** Tranche I startet mit der
dokumentierten Einschränkung. Vor Tranche III ist ein kleines Nachziehpaket
„Overrides auch in der Kettensicht anwenden" zu bauen — erst dann darf die
Degradationsvariante „belegte plus bestätigte" als erfüllt gelten.

**Nicht geraten:** Ob Overrides je Sicht angewandt werden (eigene
Zuordnungen für Ketten der Kettensicht) oder bestätigte Kontosicht-Rolls auf
die Ketten der Kettensicht abgebildet werden, ist eine Designfrage mit
unterschiedlichen Folgen für Naturschlüssel-Abgleich und Verwaisung — erst
mit echten Roll-Kandidaten entscheidbar. Dazugehört die Abdeckungs-Angabe:
umgeleitete Beine ohne freien Schließer bleiben offene Ketten (AP-04s-Grenze)
und fallen aus den abgeschlossenen Kennzahlen heraus; die Degradation in
Tranche III muss das ausweisen.

## OF-62 · Regel 3 (wirtschaftliche Sicht): Mengenvorzeichen und Leg-Anteile am Echtbestand

Der erste Echtlauf (03.10.2026) machte die wirtschaftliche EUR-Sicht
unplausibel (−75,9 Mio EUR bei +210 k Handelswährung). Zwei Befunde, beide
handgerechnet: IB Flex trägt das SELL-/BUY-Vorzeichen zusätzlich in der
Menge — Regel 3 wertete es doppelt (AP-03, Regel 1 / OF-13 gilt auch hier);
und bei Teilablösungen/Assignments ist `legs.menge` der Anteil der Kette an
der Ausführung, nicht deren Gesamtmenge (AP-03, Regel 5).

**Behoben (AP-06vk):** `_wirtschaftlich` rechnet je Leg-Seite mit
`leg.menge` und vorzeichenloser Menge; die Kommission läuft anteilig mit dem
Kurs der jeweiligen Seite. Die Abnahmebasis (alle Mengen je Leg 1) bleibt
unberührt grün; Handrechnungen Kette 7184/9533/9215 stimmen centgenau.
Künftig gilt: Wer Regel 3 ändert, muss die drei Echtlauf-Ketten als
Regression im Blick behalten (bis ein dauerhafter Test existiert).

**Nachtrag (AP-06vr, 03.10.2026):** Der dauerhafte Regressionstest existiert
— `tests/test_kennzahlen_regression.py` (eigene Datei, Abnahmebasis bleibt
eingefroren), drei Welten nach den Handrechnungsketten 7184/9533/9215:
Vorzeichen, Teilablösung, Assignment. Festgehalten ist auch die dabei
gemessene Mengen-Konvention des Bestands: `legs.menge` vorzeichenlos
(21.000 von 21.000 Zeilen positiv, `engine/matching.py` speichert `abs`),
`executions.menge` mit IB-Flex-Vorzeichen (SELL negativ, 16.244 Zeilen) —
nur so ist der Kommissionsanteil `leg.menge/|exec.menge|` vorzeichenlos
korrekt. Wer eine der beiden Konventionen „vereinheitlicht", kippt Regel 3
und wird von genau diesem Test erwischt.

## OF-63 · Schema-Drift: journal.db trug oa_*-Spalten ohne Migration

Am 03.10.2026 brach `alembic upgrade head` auf `journal.db` mit
`CircularDependencyError` — `structures` hatte die Spalten
`oa_strategie/oa_status/oa_erkennung` bereits (alle NULL, ohne das
CHECK `ck_structures_oa_erkennung`), obwohl `alembic_version` auf
`d4f8b2c6a913` stand und `chains` die Spalten nicht hatte. Ein
Migrationsrest scheidet aus (das CHECK fehlte); die Ursache ist aus dem
Repo nicht rekonstruierbar.

**Behoben (03.10.2026):** Backup
(`backups/journal_2026-10-03_pre_e5f2b8c4d7a1.sqlite`, `VACUUM INTO`),
`DROP COLUMN` der drei driftenden Spalten (0 Zeilen betroffen), danach
`a3e8f1c9d426 → b7f4e2a8c1d5 → e5f2b8c4d7a1` regulär; Null-Drift-Beweis
durch Spalten-/Constraint-/FK-Vergleich gegen eine frisch migrierte Leerd-DB
(einziger Unterschied: FK-Nummerierungsreihenfolge, semantisch bedeutungslos).

**Offen:** Die Ursache des Drifts ist unbekannt. Beobachtung: Nach jedem
manuellen Schema-Eingriff außerhalb der Migrationen gilt
`alembic current` allein nicht mehr als Drift-Freiheits-Beweis — der
Schema-Vergleich gegen eine frische Head-DB (wie oben) ist der zuverlässige
Check und sollte nach auffälligen Ereignissen wiederholt werden.

## OF-64 · Betriebsrisiko: journal.db liegt auf dem Google-Drive-Volume

Beim ersten Echtlauf brach der Commit des Kontosicht-Berichts mit
`sqlite3.OperationalError: disk I/O error` ab (nach 46 s Rechnung, DB
gesund, kein WAL-Rest, 11 GB frei); der Wiederholungslauf war sofort grün.
`journal.db` liegt unter `G:\Meine Ablage\#Code#\Trading Diary` — ein
Cloud-Sync-Volume. Der Sync-Client fasst die wachsende DB (164→171 MB durch
den ersten Bericht) genau beim Commit an; WAL-/SHM-Memory-Mapping und
Datei-Upload konkurrieren. Der Plan (§3) sieht die Arbeits-DB ohnehin lokal
und nur das Backup (`VACUUM INTO`) aufs Netzlaufwerk.

**Offen (Nutzerentscheidung):** Arbeits-DB auf ein lokales Laufwerk
verschieben (Startskripte und `JOURNAL_DB` entsprechend anpassen) oder das
betriebliche Risiko akzeptieren und nur die Häufigkeit flüchtiger
Commit-Fehler beobachten. Ein Wiederholungslauf nach einem `disk I/O error`
ist bis dahin die dokumentierte Erste-Hilfe.

**Entschieden (vertagt, Nutzer 04.10.2026):** Der Betrieb läuft vorerst
weiter auf dem Google-Drive-Volume; die Entscheidung fällt später. Erste
Hilfe bleibt der Wiederholungslauf nach einem `disk I/O error`. Neu zu
bewerten spätestens, wenn (a) ein Commit mehrfach hintereinander scheitert,
(b) andere Schreibfehler auftreten (`database is locked`, `database disk
image is malformed`) oder (c) Tranche IV die Datenbank deutlich häufiger
schreibt (Equity-Kurve, `metrics_daily`).

**Zweitbeobachtung 04.10.2026:** Betroffen ist nicht nur SQLite. Ein
`git commit` blieb beim Objekt-Rename hängen (`.git/objects/…/tmp_obj_*`
ließe sich nicht umbenennen — Sync hält die Datei fest); der sofortige
Wiederholungslauf war grün. Auch im Git-Betrieb gilt: nach kryptischem
Fehler einmal wiederholen, bevor man sucht.



## OF-65 · OA-Gesamtexport: Er ersetzt die Monatsdateien, und eine Fortschreibung ist nicht definiert

**Befund 04.10.2026**, beim Prüfen von `fixtures/golden/Trades_2026-10-04_16-02-17_all.xlsx`
(Gesamtexport der OptionApp, Blatt `Trades`, elf Spalten wie im Anhang). Nur
Zählwerte, Regel 2.

- **5.358 Trades**, alle mit Eröffnung 2026, 5.358 eindeutige Klammernummern.
  Status: CANCELED 3.975, EXPIRED 671, CLOSED 570, PARTIALLY STOPPED 51,
  STOPPED 40, EXPIRED (estimated) 36, RUNNING 14, UNMANAGED 1.
- **Die drei Monatsdateien sind Teilmengen**: Januar 268 von 268 enthalten,
  Februar 66 von 66, August 178 von 178. Inhaltlich identisch sind aber nur
  Februar 66 von 66 und August 177 von 178 — **Januar 0 von 268**: Die
  Januar-Trades haben sich seit dem Monatsexport verändert (laufend →
  abgeschlossen).
- **Folge:** Der Parser bricht bei „gleiche Nummer, abweichender Inhalt" ab
  (AP-13, Vertrag 10). Wer die Monatsdateien *und* den Gesamtexport lädt, läuft
  in genau diesen Abbruch. **Regel für jetzt: nur den Gesamtexport laden, nie
  die Monatsdateien daneben.**
- **Offen:** Wie schreibt man einen späteren, neueren Gesamtexport fort, wenn
  laufende Trades inzwischen abgeschlossen sind? „Überschreiben" widerspricht
  dem Parser (keine stille Entscheidung); „nur Neue laden" lässt Status und
  Ergebnis veralten. Gebraucht wird eine ausdrückliche Fortschreibungsregel
  (z. B. nur Trades mit Status RUNNING aktualisieren, nie abgeschlossene).
  Nicht geraten; eigenes Paket, bevor ein zweiter Gesamtexport geladen wird.

## OF-66 · OA-Gesamtexport: Ein DAX-Trade mit Eurex-Produktcode in der Leg-Grammatik

Der Gesamtexport enthält **eine** Zeile (CLOSED, Strategie `DAX: BPS`), deren
`Strikes` nicht der Grammatik `[-]<Menge>x<C|P><Strike> (<JJMMTT>)` folgt: Vor
dem Recht steht ein Produktcode, Form `[-]<n>x<CODE> <P|C><Strike> (<JJMMTT>)`
(Eurex-Optionsprodukt, vier Buchstaben). Der Parser bricht daran ab (richtig
nach AP-13, Vertrag 5: Abweichung = Defekt der Quelle, nicht raten).

Zwei Dinge dazu:

1. **OA handelt inzwischen auch DAX.** Die Annahme „OA-Export enthält nur
   SPX/SPY/XSP/QQQ/RUT" (Plan §6.1) gilt für 2026 nicht mehr. Damit wird die
   Strategie-Dimension auch für einen Teil des DAX-Bestands möglich — relevant
   für die DAX-Kommissionsfrage (AP-06).
2. **Der Parser braucht eine Grammatikerweiterung** (optionaler Produktcode,
   der nicht in die Leg-Identität eingeht; Strike/Expiry/Recht/Richtung/Menge
   bleiben maßgeblich). Das ist ein Korrekturpaket an der Abnahmebasis von
   AP-13 (Regel 1a, `aendert_tests: ja`, stark), danach eine Parsernachbesserung
   durch das günstige Modell — dasselbe Muster wie AP-13pl/q und pm/r.
   **Bis dahin lässt sich der Gesamtexport nicht laden** (Abbruch an dieser
   einen von 5.358 Zeilen, ohne etwas zu schreiben).

## OF-67 · OA-Gesamtexport: Trade mit nur einem Leg

Der echte Import (05.10.2026) brach an Zeile 2599 ab: `'Strikes' zerfällt in 1
Legs, erwartet sind zwei bis vier`. Unter 1.383 ausgeführten Trades des
Gesamtexports gibt es einen mit einem Leg. Die Untergrenze „zwei" war eine
Beobachtung der ersten Referenzexporte (Anhang), keine fachliche Regel.
**Behoben über AP-13pp (Abnahmebasis) und AP-13t (Parser)**; die Grenze lautet
jetzt ein bis vier. Vorab mit einer Wegwerf-Grenze gegen eine temporäre
Datenbank geprüft: Der gesamte Import läuft danach durch (5.358 Trades, 4.391
Legs), keine weitere Zeile scheitert. Lehre: Meine Vorprüfung von OF-66 hat nur
die Leg-Grammatik je Ausschnitt gemessen, nicht die Anzahl je Zelle; künftig
gleich ein Probeimport in eine temporäre Datenbank statt einzelner Prüfwerte.

## OF-68 · Kettensicht: Summen weichen von der Kontosicht ab (Folge von OF-52)

Echtlauf 05.10.2026: Die Nettosumme der Kettensicht liegt rund 32.000 EUR
(etwa 16 %) neben der Kontosicht (198.895 EUR). Plan §5 verlangt gleiche
Summen. Rund 82 % der Differenz erklären die 205 umgeleiteten Ausführungen:
Nach der OF-52-Entscheidung („Ausführung zählt doppelt") schließt eine solche
Ausführung den alten Vorgang und eröffnet zugleich den eigenen; ihr Geldfluss
wird zweimal gebucht, real nur einmal bezahlt. Die OA-Sicht lässt den alten
Vorgang dagegen bis zu seinem eigenen Ende laufen. Die Empfehlung zu OF-52 war
in diesem Punkt falsch gewichtet (Invariante nicht geprüft).

**Bis zur Entscheidung:** Geld- und Kommissionsfragen auf der Kontosicht
(`--sicht konto`); die Kettensicht gilt nur als Strategieansicht ohne
belastbare Summe.

**Optionen (Entscheidung steht aus):**

- **A — Alter Vorgang bleibt offen.** Die umgeleitete Ausführung eröffnet nur
  den neuen Vorgang; der alte läuft bis zu seinem eigenen Ende (wie OA).
  Summen stimmen. Ändert die OF-52-Entscheidung, Korrekturpaket
  (`aendert_tests: ja`, stark) plus Umsetzung.
- **B — Abstimmungszeile.** Variante bleibt, die Doppelzählung wird im Bericht
  als eigene Zeile ausgewiesen. Kein Eingriff in Tests, aber Summen je Gruppe
  bleiben verzerrt.

**Folgepaket:** AP-13z (OA-Strategie auch in die Kettensicht schreiben) erst
nach der Entscheidung. Verwandt: OF-52, OF-61.

**Entscheidung (06.10.2026): Option A.** Abnahmebasis AP-04sx (Tests
berichtigt, Regel 1a), Umsetzung AP-04sy. Zusatzregel „Verfall": Nach dem
Verfall werden gegenläufige offene Lose gegeneinander geschlossen, sonst
blieben 189 Legs offen (13.639 USD brutto). Vorab an einer Kopie von
`journal.db` mit einer Wegwerf-Umsetzung geprüft: realisiertes Brutto,
Kommission und offene Legs in beiden Sichten identisch. **Bekannte Grenze:**
Bei ITM-Verfall wird das innere Ergebnis nicht auf die beiden Vorgänge
aufgeteilt (Summe stimmt, Zuordnung je Kette nicht). Die EUR-Summe ist nach
der Umsetzung nachzurechnen.

**OF-68 behoben (06.10.2026, AP-04sy, Commit 2a8fb88).** Echtabgleich an einer
Kopie von `journal.db`: realisiertes Brutto 244.622,27 und Kommission
−82.311,20 in beiden Sichten gleich, offene Legs 294 = 294, **Summe netto EUR in
beiden Sichten identisch** (198.895,02). Die Kettensicht hat 17.343, die
Kontosicht 17.345 Legs (zwei Legs weniger durch die Verfallszusammenführung).

## OF-69 · Wirtschaftliche EUR-Rechnung ignoriert den Abrechnungskurs bei Barausgleich

Beim Nachrechnen der Kommissionsanteile je Strategie (07.10.2026) fiel auf, dass
Kette 9091 (Short Put, zugeteilt) in den Legs −959 USD zeigt, in der
wirtschaftlichen EUR-Rechnung aber +333 EUR. Ursache: Bei Barausgleich trägt
die Zuteilungszeile den Preis 0, der Abrechnungskurs steht in `schlusskurs`
(OF-25); `engine/matching.py` nutzt ihn, `analytics/kennzahlen.py` und
`analytics/kommission.py` nicht. Meine Abnahmebasis von AP-06v/06w hat den
Fall nicht abgedeckt (kein Zuteilungsfall mit Barausgleich in der Testwelt).

Auswirkung am Echtbestand (Kopie): Summe netto EUR **198.895 → 163.546**;
IB-basierte Summe unverändert 182.402. Die Barausgleich-Ketten (3.777) haben
danach einen „Währungseffekt" von −149 insgesamt; der verbleibende Effekt
(−18.856) liegt fast vollständig in den 319 Ketten mit Aktienbein (Lieferung +
STK) und ist dort ein echter Kurseffekt der Haltedauer. Unberührt: Steuer
(AP-10), Legs, USD-Werte, alle Brutto/Netto-Spalten in Kontraktwährung.
Alle bisher genannten Kommissionsanteile je Strategie mit Zuteilungen
(`Default`, `FKK10`) waren verzerrt und sind zu verwerfen.
**Behebung:** AP-06x (Abnahmebasis, fertig), AP-06xk (Umsetzung, Auftrag fehlt noch).

**OF-61 entschieden (07.10.2026):** Overrides werden einmal in der Kontosicht
gegeben und per Naturschlüssel in die Kettensicht übersetzt; fehlt dort einer
der beiden Schlüssel (umgeleitete Ausführungen), zählt der Override als „ohne
Entsprechung" und wird nicht geraten. Abnahmebasis AP-04sz, Umsetzung AP-04szk.
Am Echtbestand gibt es derzeit 0 bestätigte Overrides; die Wirkung zeigt sich
erst, wenn die 677 offenen Rollkandidaten durchgesehen werden. Die Degradation
in Tranche III muss weiterhin ausweisen, wie viele Ketten wegen fehlender
Entsprechung nicht erfasst sind.

## OF-70 · Roll-Degradation (AP-06 Tranche III): Entscheidungen und erster Echtlauf

Entscheidungen E1–E8 stehen in `auftraege/AP-06d.md` (Kettensicht, Gruppen
0/1/2/3+, Modi `belegt` und `belegt_bestaetigt`, Abdeckung, offene Kandidaten
gehen nie ein, aber ihre Ketten werden nicht ausgeschlossen). Abnahmebasis
AP-06d, Umsetzung AP-06dk.

**Erster Echtlauf (Wegwerf-Umsetzung auf einer Kopie von `journal.db`,
08.10.2026, 5:50 Minuten, nur zur Einordnung):**

| Rolls | Ketten | Summe netto EUR | Ø je Kette | Trefferquote |
|---|---|---|---|---|
| 0 | 5.935 | +224.411 | +37,81 | 70,4 % |
| 1 | 674 | −10.646 | −15,80 | 64,4 % |
| 2 | 233 | +10.492 | +45,03 | 60,5 % |
| 3+ | 177 | −60.710 | −343,00 | 53,1 % |

Die Trefferquote fällt monoton mit der Roll-Anzahl; die Plan-Aussage „Ketten
ohne Roll schneiden am besten ab" gilt für Summe und Trefferquote. Der
Durchschnitt ist **nicht** monoton (Gruppe 2 liegt über Gruppe 0 und 1):
Zwei Rolls sind häufig ein geplanter Zyklus, drei und mehr sind überwiegend
Rettungsversuche. Ketten mit Rolls sind nicht zufällig gewählt — wer rollt,
hatte meist schon ein Problem; die Kurve zeigt den Zusammenhang, nicht die
Wirkung des Rollens.

**Abdeckung:** alle 7.019 abgeschlossenen Ketten sind zugelassen (derzeit
0 bestätigte Overrides, deshalb sind beide Modi gleich); Rollverknüpfungen
1.894, offene Kandidaten 677 → 73,7 %. Die 677 sind Kandidaten**paare**, bei
Mehrdeutigkeit werden mehrere Fortsetzungen je schließender Position
angeboten; die Roll-Abdeckung ist deshalb eine **Untergrenze**. Sie steigt,
sobald die Rollkandidaten durchgesehen sind.

**Bekannt:** Die Kettensicht hat 56 Rollverknüpfungen weniger als die
Kontosicht (1.972 gegen 2.028); Ursache offen (vermutlich andere
Strukturbildung bei umgeleiteten Ausführungen, OF-68) — zu untersuchen, bevor
die Kurve als endgültig gilt.

## OF-71 · AP-05: Kandidatenregeln nach der Praxis; Ablehnung und Bestätigung offen

Nutzerangaben (08.10.2026): Spreads auf beiden Seiten werden oft dauerhaft
gehalten und einzeln gerollt (DAX meist freitags, etwa 7 DTE), auch unsymmetrisch
— wirtschaftlich ein Iron Condor, auch wenn die Seiten getrennt aufgesetzt
sind; ein IC in einem Trade ist bereits eine Kette und braucht keinen
Kandidaten. Gegenfinanzierung meist innerhalb weniger Minuten; zu Beginn werden
oft beide Seiten gerollt oder nach einem Take Profit neu aufgesetzt.

Messung am Echtbestand (Kopie, 08.10.2026, nur Zählwerte): bisher 3.755
Kandidaten (IC 3.237, Financing 518). Financing nach Abstand: ≤5 min 62, ≤15 min
34, ≤1 h 65, ≤6 h 190, ≤24 h 167; davon 26 mit einer eigenen Vorgängerkette
derselben Seite ≤15 min vorher (Doppel-Roll/Wiedereinstieg). IC: 604 mit
Eröffnungsabstand ≤5 min; Überlappung <1 Tag 2.435, 1–7 Tage 402, >7 Tage 400.

**Entschieden (Nutzerfreigabe „wie vorgeschlagen"):**
1. IC über irgendein Glied mit gleicher Expiry statt über die letzte Expiry.
2. Doppel-Roll-Filter (15 Minuten, einschließlich) beim Financing.
3. Ranggrößen `abstand`/`ueberlappung` am Kandidaten; die Durchsicht sortiert.
→ Abnahmebasis AP-05r, Umsetzung AP-05rk. Danach (neues Paket, AP-05d):
Persistenz der Entscheidung und Durchsicht-Datei.

**Noch zu entscheiden bzw. empfohlen für AP-05d:** Ablehnung als eigene Tabelle
(OF-54, Empfehlung b); Bestätigung legt eine Kampagne an oder ergänzt eine
bestehende, bei zwei verschiedenen Kampagnen benannter Abbruch (kein
automatisches Zusammenführen); `ic_leg` für beide Ketten, bei Financing
`financing` für die neue Kette und der Typ der Bestandskette in der Datei
vorbelegt und änderbar; Altbestand vor 2026 nicht erzwungen, AP-11 liefert die
Absicht künftig an der Quelle.

**Vorbehalt des Nutzers:** Die Praxis ist Routine und nie hundertprozentig
stringent (Delta 10 aufsetzen, bei 2 EUR Take Profit, neu aufsetzen, auf beiden
Seiten; rollen, wenn nötig, notfalls finanzieren). Wie viel Erkenntnis aus der
Kampagnen-Klassifikation entsteht, wird nach dem ersten Einsatz bewertet. Die
Kernfragen (Kosten, Rolls, Strategien) hängen nicht daran.

**AP-05d (09.10.2026):** Persistenz der Klassifikation als Datei-Rundreise
(`kampagnen-ausschreiben`/`kampagnen-einlesen`), Abnahmebasis AP-05d, Umsetzung
AP-05dk. Entscheidungen aus OF-54/OF-71 umgesetzt: Ablehnung in eigener Tabelle
`campaign_ablehnungen`, keine automatische Zusammenführung zweier Kampagnen,
Typ je Kette in der Datei vorbelegt. **Annahme (Regel 10):** Bei einem
Financing-Kandidaten ist die Bestandskette mit `ic_leg` vorbelegt, die neue
Kette mit `financing`; `contract_roll` und `independent` sind eintragbar. Ob
das der Absicht des Nutzers entspricht, zeigt sich beim ersten Durchgehen.
Die Klassifikation hängt an **Kontosicht**-Ketten; eine Übersetzung in die
Kettensicht folgt erst, wenn die Kampagnen-Auswertung (AP-06) sie braucht.

## OF-72 · Durchsicht der Rollkandidaten: Naturschlüssel ohne Sichtfilter

Beim Lesen von `journal/durchsicht.py` (09.10.2026) fiel auf, dass
`_gruppen_bilden` und `_urteile_schreiben` Naturschlüssel in `structures` und
`chains` ohne `sicht = 'konto'` nachschlagen. Seit AP-04sw gibt es jeden
Schlüssel zweimal. Es funktioniert nur, weil die Zeilen in der Reihenfolge des
Unique-Index (Naturschlüssel, Sicht) zurückkommen und die Kontosicht zuletzt
steht — ein Wegwerf-Lauf mit einer Bestätigung und anschließendem Rebuild
(`overrides_angewandt 1`, `verwaist 0`) bestätigt, dass es heute richtig läuft.
Der vorhandene Test prüft das nur schwach. **Behebung:** kleine Härtung in
AP-05dk (Sichtfilter ergänzen, bestehende Tests unverändert grün).

## OF-73 · Reihenfolge: zuerst der MVP mit dem täglichen Journal

Entscheidung des Nutzers (09.10.2026): Das Ausfüllen der Listen (Rollkandidaten
AP-04d, Campaign-Kandidaten AP-05d) wird zurückgestellt, bis der MVP stabil
läuft und das tägliche Journal mit den Basisfunktionen benutzbar ist. Die
Werkzeuge dafür sind gebaut und abgenommen (`kandidaten-*`, `kampagnen-*`) und
warten. Der MVP-Schnitt (Plan M4): AP-07 Rest und AP-08 Rest in dieser
Reihenfolge — **AP-07j** (Notizen, Tags, Tagesjournal; `scope_typ = 'tag'` ist
der Handelstag), danach Tagesübersicht und Kennzahlen-Endpunkte, dann die
Oberfläche dazu (AP-08j). Die Rest-Analytik (Equity/Drawdown, DTE-Band, Breite)
folgt danach.

## OF-74 · Automatischer Abruf: Protokoll des Flex Web Service nicht gegen die Gegenstelle erprobt

Der Abruf (AP-02a2/AP-02a2k) folgt dem Flex Web Service in Version 3 nach
meiner Kenntnis der IBKR-Dokumentation: zweistufig (`SendRequest` liefert
`ReferenceCode` und `Url`, `GetStatement` liefert das Statement oder meldet mit
`ErrorCode 1019`, dass es noch erzeugt wird). Basisadresse
`https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService`.
**Annahme (Regel 10):** Die Fehlercodes außer 1019 werden nicht gedeutet, nur
benannt; ein erneuter Abruf bei Ratenbegrenzung ist Sache des nächsten
Nachtlaufs. Die Abnahme ist gegen erfundene Antworten erfolgt; **der erste
echte Abruf mit dem Token des Nutzers ist die Probe.** Weicht die echte
Antwort ab (anderes Element, andere Adresse), ist das ein kleiner
Korrekturauftrag am Transport bzw. an `BASIS_URL`, nicht an der Logik.
Noch beim Nutzer: Flex-Query nach §6.2 anpassen, Token im IBKR-Portal anlegen.
