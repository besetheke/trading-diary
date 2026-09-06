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
