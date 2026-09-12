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
