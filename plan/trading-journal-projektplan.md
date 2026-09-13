# Trading Journal — Projektplan

**Rolle dieses Dokuments:** Ausführungsgrundlage für Entwickler und Coding-Agenten.
Jedes Arbeitspaket ist so geschnitten, dass es isoliert bearbeitet, getestet und
abgenommen werden kann.

**Stand:** 05.09.2026 · **Version 7** — Strategien aus dem OptionApp-Export
übernommen, Verknüpfungsverfahren festgelegt. Grundlage: zwei
Trading-Diary-Pro-Exporte, zwei Activity-Flex-Exporte (3.971 bzw. 1.376
Ausführungen) und zwei OptionApp-Trade-Exporte. Verknüpfungsschlüssel am Überschneidungszeitraum
verifiziert

---

## 1. Zielbild

Ein lokales Trading-Journal in Anlehnung an Trading Diary Pro, zugeschnitten auf
ein gemischtes Portfolio aus Index-Optionen (BCS/BPS auf DAX, SPX, NDX, RUT,
ESTX50), Aktien und Futures über IBKR/Mexem.

**Kernunterschied zum Vorbild:** Analyseeinheit ist nicht der einzelne Round Turn,
sondern die Kette aus Eröffnung, n Rolls und Schließung — und darüber die
Kampagne, die zusammengehörige Ketten beider Marktseiten verbindet.

| Ebene | Beschreibung | Beispiel |
|---|---|---|
| Execution | einzelner Fill vom Broker | 1x SPX 5900 Call verkauft |
| Structure | vollständige Position zu einem Zeitpunkt | BCS 5900/5950 · 100 Aktien · 1 FDAX |
| Chain | Position über ihre gesamte Lebensdauer | Einzeltrade (0 Rolls) · Eröffnung → 3 Rolls → Verfall |
| Campaign | zusammengehörige Ketten beider Seiten | IC · BPS plus finanzierender BCS |

**Wichtig zum Begriff Kette:** eine Kette ist keine Sonderform für gerollte
Positionen. Jede Position ist eine Kette; die meisten haben die Länge 1. Ein
Einzelaktien-BPS, der eröffnet und geschlossen wird, ist eine Kette ohne Roll und
läuft in allen Auswertungen unverändert mit. Die Roll-Anzahl ist eine Kennzahl und
ein Filter, niemals ein Eintrittskriterium. In der Oberfläche heißt die Liste
deshalb **Positionen**, nicht Ketten.

Quer zu diesen Ebenen steht die **Strategie** (§1.3) — die eigentliche
Auswertungsdimension.

**Die drei Fragen, die das Tool beantworten muss** (Priorität in dieser Reihenfolge):

1. Wie viel kostet mich Rollen wirklich — brutto vs. netto, nach Anzahl Rolls?
2. Wie viel meiner Performance frisst Kommission, aufgeschlüsselt nach Index,
   Anlageklasse, Strategie, Laufzeit und Roll-Verhalten?
3. Welche Konfigurationen (Index, DTE bei Eröffnung, Delta, Breite, Roll-Politik,
   Gegenfinanzierung ja/nein) verdienen Geld, welche nicht?

Alles Weitere — Kalenderansicht, Equity-Kurve, Notizen, Tags, Screenshots — ist
Standardfunktionalität und nachgelagert.

### 1.1 Anlageklassen

| Klasse | Besonderheiten | Chain-Konzept |
|---|---|---|
| Optionen (OPT) | Multi-Leg, Rolls, Expiry, Assignment | ja — Roll-Kette |
| Optionen auf Futures (FOP) | wie OPT, anderer Multiplikator | ja |
| Futures (FUT) | Kontraktwechsel Front → Back, Tickwert | ja — `contract_roll` |
| Aktien (STK) | Tranchen, Splits, Dividenden, Kapitalmaßnahmen | nein, optional manuell |
| Cash/FX | Währungsumtausch, Zinsen | nein — nur Kostenrechnung |

Die Anlageklasse hängt am Instrument und ist in jeder Auswertung eine
Filterdimension. Sie ist zugleich die Grundlage für die steuerliche Trennung
(Aktien vs. Termingeschäfte, getrennte Verlusttöpfe) in AP-10.

**Instrumentenumfang (aus dem TDP-Export belegt):** Index-Optionen (SPX, DAX,
NDX, RUT, ESTX50), ETF-Optionen (SPY, QQQ, XSP), Einzelaktienoptionen (WDC, NOW,
GLW, DELL, NVDA, ASTS, ZS, PINS, AAPL, MDT, CRWD), Aktien, Futures. Zwei
Währungsräume (EUR/USD), Börsen unter anderem CBOE, CBOE2, EUREX, MEMX, ISE, PHLX.

**Kein Zusammenfassen wirtschaftlich gleicher Basiswerte.** SPX, SPY und XSP bilden
denselben Markt ab, tragen aber unterschiedliche Strategien. Eine Aggregation über
den Basiswert würde diese Unterscheidung zerstören. Auswertungen laufen deshalb
über die Strategie, nicht über den wirtschaftlichen Basiswert.

### 1.3 Strategie — die zentrale Auswertungsdimension

Weder Basiswert noch Anlageklasse erklären, warum eine Position existiert. Zwei
BPS auf SPY und XSP am selben Tag können zwei völlig verschiedene Verfahren sein.
Jede Structure trägt daher eine **Strategie-Kennung**.

**Herkunft der Positionen im Buch:**

| Quelle | Charakter | Zuordnung |
|---|---|---|
| OptionApp | 20 benannte Strategien (SPX, SPY, XSP, QQQ, RUT) | `orderReference` plus OA-Trade-Export, AP-13 |
| Options Roller | verwaltete Index-Rolls | über `roller_link` |
| Diskretionär | Einzelwerte, Einzelfallentscheidung | manuell, Vorbelegung nach Basiswerttyp |

**Namenskonvention:** Strategie-Kennungen müssen in Option Omega, OptionApp und
Journal dasselbe bezeichnen. Sie sind stabil, sprechend und werden nie
umbenannt — nur neu angelegt und alt gesetzt. Diese Konvention ist vor AP-01
festzulegen; sie später nachzuziehen bedeutet, die gesamte Historie neu zu
klassifizieren.

### 1.4 Ereignisarten

Nicht jede Zeile im Brokerdatenstrom ist ein Handel. Der TDP-Export zeigt
Tagesabschluss-Ereignisse (Verfall, Ausübung, Zuteilung), die im selben Zeitstempel
über mehrere Basiswerte hinweg gebucht werden — im Beispiel 29 Legs zu einem
Zeitpunkt über RUT, SPX, SPY und XSP. Jede Execution trägt deshalb einen
`ereignistyp`:

| Ereignistyp | Erkennung | Behandlung |
|---|---|---|
| `trade` | reguläre Börsenausführung | normales Matching |
| `expiry` | Ereigniscode, keine Börse | schließt Legs zu 0, kein Strukturaufbau |
| `exercise` | Ereigniscode | schließt Legs, ggf. Übergang in Basiswert |
| `assignment` | Ereigniscode plus Gegenbuchung im Basiswert | Kettenübergang Option → Aktie |

**Zuteilungen sind ein Kettenübergang, kein neuer Trade.** Im Beispiel entsteht
zeitgleich mit einem zugeteilten Put ein Aktienkauf über 100 Stück ohne
Kontraktkennung. Ohne explizite Verknüpfung steht später ein Optionsverlust ohne
Gegenstück und eine Aktienposition ohne Herkunft in der Auswertung.

---

## 2. Architekturprinzipien

Bindend. Abweichungen brauchen eine explizite Entscheidung, keine stille Umsetzung.

**P1 — Fakten und Meinungen strikt trennen.**
Brokerdaten sind unveränderlich und jederzeit neu importierbar. Notizen, Tags,
Kampagnen-Klassifikationen und manuelle Korrekturen liegen in getrennten Tabellen
und werden von einem Re-Import niemals überschrieben. Ein vollständiger Neuaufbau
der abgeleiteten Daten muss möglich sein, ohne dass eine Benutzereingabe verloren geht.

**P2 — Die Engine ist rein.**
Matching und Analytik sind deterministische Funktionen ohne Netzwerk, ohne Uhrzeit,
ohne Zufall. Gleiche Eingabe → bitgleiche Ausgabe.

**P3 — Jede Zahl ist rückverfolgbar.**
Zu jeder aggregierten Kennzahl muss sich per Drilldown die Menge der zugrunde
liegenden Executions anzeigen lassen.

**P4 — Berichtswährung EUR, Rechnung in Originalwährung.**
Beträge werden in Originalwährung gespeichert und erst in der Analyseschicht
umgerechnet. FX-Kurs und Kursdatum sind Teil des gespeicherten Ergebnisses.

**P5 — Identität vor Heuristik.**
Zusammengehörigkeit wird primär über Broker-Identifikatoren bestimmt
(`ibOrderID`, `tradeID`, `conid`), erst nachrangig über Zeitfenster. Jede
heuristisch erzeugte Verknüpfung ist als solche markiert und manuell korrigierbar.

**P7 — Ereignisse sind keine Trades.**
Verfall, Ausübung und Zuteilung werden vor dem Matching als eigene Ereignisart
klassifiziert und nehmen nicht an der zeitbasierten Strukturbildung teil. Eine
Struktur entsteht nie aus Zeilen mit `ereignistyp != 'trade'`.

**P6 — Datenqualität ist ein Feld, keine Annahme.**
Jeder Import trägt eine Qualitätsstufe. Auswertungen können auf belastbare
Zeiträume eingeschränkt werden. Altdaten dürfen Kennzahlen nicht stillschweigend
verwässern.

---

## 3. Technischer Stack und Betrieb

| Schicht | Wahl | Begründung |
|---|---|---|
| Sprache | Python 3.12 | bestehende Tools, ibapi, pricing.py wiederverwendbar |
| Persistenz | SQLite (WAL) + SQLAlchemy Core | Single-User, dateibasiert, backupfähig |
| Validierung | Pydantic v2 | Schemaverträge zwischen den Schichten |
| API | FastAPI | stabiler Vertrag, UI später austauschbar |
| Frontend | React + Vite + Recharts | Kalender/Drilldown-UX in Streamlit zu mühsam |
| Tests | pytest, pytest-cov | Golden-Tests als Abnahmekriterium |
| Migration | Alembic | Schemaänderungen nachvollziehbar |

**Betriebsort:** Trading-Server (Windows), dort wird auch entwickelt.
Die Datenbank liegt lokal, Sicherung auf Netzlaufwerk.

**Auflagen für den Betrieb auf dem Trading-Server:**
- Im Betrieb liefert FastAPI das gebaute Frontend als statische Dateien aus. Kein
  Node-Dev-Server während der Handelszeiten.
- Frontend-Builds und größere Neuberechnungen laufen außerhalb der Handelszeiten.
- Der nächtliche Import läuft über den Windows-Task-Scheduler, nicht als Dienst.
- Backup mit `VACUUM INTO` auf das Netzlaufwerk, kein Dateikopieren bei aktivem
  WAL. Täglich, mit Aufbewahrung der letzten 14 Stände.
- Ressourcenbudget: der Import darf nicht länger als fünf Minuten laufen und
  nicht mehr als einen Kern dauerhaft belasten.

---

## 4. Schichtenmodell und Verhältnis zum Options Roller

```
[Flex Query XML]   [Legacy-Auszüge 2022-2024]
        │                    │
        ▼                    ▼
  L1  Ingest  ──────────────────→ executions (immutable, idempotent, Qualitätsstufe)
        │
        ▼
  L2  Matching Engine   → legs → structures → chains → campaigns
        │                 (rein, deterministisch, golden-getestet)
        ▼
  L3  Analytics         → KPIs, Kommissionsattribution, FX, Roll-Analyse
        │
        ▼
  L4  API (FastAPI)     → read für Analytik, write für Journal und Klassifikation
        │
        ▼
  L5  UI (React)
```

### 4.1 Options Roller — geteilte Datenbank, getrennte Domänen

**Gemeinsam:** eine SQLite-Datei im WAL-Modus, ein Server, ein Backup.

**Getrennt:** die Chain-Tabellen. Der Roller führt vorwärtsgerichteten
Arbeitszustand — was er zu tun gedenkt, teilweise vor der Ausführung. Das Journal
rekonstruiert rückwärts aus abgerechneten Brokerdaten. Beide werden systematisch
abweichen (Teilfills, manuelle Eingriffe, verworfene Orders). Eine gemeinsame
Tabelle würde diese Abweichung zu einem Dauerkonflikt machen.

**Brücke:** Tabelle `roller_link` (roller_chain_id, journal_chain_id,
zugeordnet_am, methode). Damit wird **Absicht gegen Ergebnis** auswertbar — was
der Roller vorhatte gegen das, was abgerechnet wurde.

**Perspektive (AP-11):** Der Roller kennt im Moment des Aufsetzens die Absicht
einer Position — insbesondere ob ein BCS als IC-Seite oder als Gegenfinanzierung
eines BPS-Rolls gedacht ist. Diese Information am Entstehungsort abzugreifen ist
ungleich zuverlässiger als sie später zu rekonstruieren.

**Nebenläufigkeit:** WAL erlaubt gleichzeitiges Lesen und einen Schreiber.
Journal-Schreibvorgänge sind kurz und laufen nachts. Der Roller behält Vorrang;
jede Journal-Transaktion nutzt `busy_timeout` und darf im Konfliktfall abbrechen,
niemals blockieren.

---

## 5. Datenmodell (Skizze)

**Rohdaten (nie verändert)**
- `import_runs` — id, quelle (flex/legacy_pdf/legacy_csv), datei_hash, importiert_am,
  zeitraum_von, zeitraum_bis, **qualitaetsstufe** (A/B/C), zeilen_gesamt, zeilen_neu
- `executions` — **exec_id (PK) = `tradeID` aus dem Flex-Export**, **transaction_id**
  (Feld `transactionID`, sekundär, für Abstimmung mit dem Broker), konto, conid,
  symbol, sec_type, expiry,
  strike, right, side, menge, preis, waehrung, multiplikator, kommission,
  kommission_waehrung, handelszeit, **ib_exec_id**, **exec_batch** (erste zwei
  Segmente der ib_exec_id — Gruppierungsschlüssel für Combo-Legs),
  **ib_order_id** (nur Teilfills desselben Kontrakts), **order_reference** (Rohwert),
  **oa_trade**, **oa_leg** (opak), **oa_rolle**, **oa_order**, boerse,
  **ereignistyp** (trade/expiry/exercise/assignment), **ereignis_code** (Rohwert
  der Quelle, z. B. Ep/Ex/A/P), roh_json, import_run_id, qualitaetsstufe

  **Schlüsselgleichheit über Quellen hinweg (gemessen):** die Spalte
  `Transaction ID` im Trading-Diary-Pro-Export trägt denselben Wert wie das Feld
  **`tradeID`** in IB Flex — im Überschneidungszeitraum 175 von 175 Treffern,
  null Treffer gegen `transactionID`. Der Namensgleichklang zwischen der
  TDP-Spalte und dem Flex-Feld `transactionID` ist irreführend; entscheidend ist
  die Messung. Damit sind Altbestand ab 2022 und laufende Flex-Importe ohne
  Dublettenrisiko zusammenführbar, auch bei überlappenden Zeiträumen.
  Nicht zu verwechseln mit `Contract Id` (= conid, Instrument) und `ID`
  (TDP-intern, ohne Aussagekraft).

  **Vollständigkeit (gemessen über drei Exporte, 19.425 Zeilen):** `tradeID` ist
  lückenlos gefüllt und vollständig eindeutig, auch auf allen 5.944
  Ereigniszeilen für Verfall, Ausübung und Zuteilung. Eine fehlende `tradeID` ist
  daher kein zu behandelnder Normalfall, sondern ein Abbruchgrund: der Import
  bricht mit Nennung der Zeile ab, statt auf einen Ersatzschlüssel auszuweichen.
- `strategies` — strategy_id (PK, sprechende Konvention), name, quelle
  (optionapp/roller/diskretionaer), aktiv_ab, aktiv_bis, beschreibung,
  backtest_referenz
- `assignment_links` — option_exec_id, stock_exec_id, erkennung, bestaetigt_am
- `instruments` — conid (PK), symbol, underlying, **asset_class** (OPT/FOP/FUT/STK/CASH),
  expiry, strike, right, multiplikator, tickwert, waehrung
- `corporate_actions` — id, conid, typ (Split/Reverse/Merger/Spinoff), stichtag,
  faktor, roh_json

**Qualitätsstufen:** A = Flex-XML mit Order-IDs und conids · B = strukturierter
Auszug ohne Order-IDs · C = aus PDF extrahiert, nur Betrag und Kommission belastbar.

**Behandlung von Kapitalmaßnahmen**

IB bucht Kapitalmaßnahmen nicht als Faktor auf derselben `conid`, sondern als
Abgang auf der alten und Zugang auf einer neuen. Für den Bestand genügt das; für
die Geldrechnung nicht — ein Abgang, der wie ein Verkauf zu null gebucht wird,
erzeugt einen Scheinverlust in Höhe der Anschaffungskosten und später einen
Scheingewinn in gleicher Höhe.

- Offene Lots **wandern** auf die neue `conid`. Anschaffungskosten,
  Eröffnungsausführung und Eröffnungszeitpunkt bleiben erhalten. Realisiert wird
  nichts.
- Alte und neue `conid` gehören zur selben Kette. Die Maßnahme erscheint als
  Ereignis im Zeitstrahl der Detailansicht, damit kein Instrumentenwechsel
  unerklärt bleibt.
- **Angepasste Optionskontrakte** tragen ein Kennzeichen am Instrument. Nach einem
  Split ist der Lieferumfang nicht standardisiert; ohne Markierung vergleicht die
  Analytik Strikes und Multiplikatoren, die nicht vergleichbar sind.
- **Reine Zugänge:** IBs Kostenangabe wird übernommen, wo eine vorliegt. Meldet IB
  null, wird das Lot mit `basis_ungeklaert` gekennzeichnet und der Fall in
  `OFFENE_FRAGEN.md` eingetragen — eine stillschweigende Nullbasis erzeugt beim
  späteren Verkauf einen Scheingewinn in voller Höhe und ist über AP-10 steuerlich
  relevant.

**Währungsumrechnung**

Maßgeblich ist `fxRateToBase` an der jeweiligen Ausführung — IBs eigener
Buchungskurs. Er steht an jeder Zeile, braucht keine externe Kursquelle und wird
mit Bezugszeitpunkt gespeichert (P4). Beim Abgleich gegen IBs Summen weisen
Abweichungen dadurch auf die Rechnung hin, nicht auf die Kursmethodik.
Basiswährung ist EUR; die EUR-Zeilen tragen durchgehend den Kurs 1.

**Abgeleitet (jederzeit neu berechenbar)**
- `legs` — leg_id, conid, open_exec_id, close_exec_id, menge, matching_methode,
  brutto_pnl, kommission_gesamt, offen_ja_nein
- `structures` — structure_id, **asset_class**, **strategy_id**, typ (BCS/BPS/Vertical/Single/
  Stock/Future/Custom), underlying, expiry, short_strike, long_strike, breite,
  menge, eroeffnet_am, geschlossen_am, dte_bei_eroeffnung, status, brutto_pnl,
  kommission, netto_pnl, waehrung, **erkennung** (order_id/heuristik/manuell)
- `chains` — chain_id, underlying, asset_class, seite (Call/Put/n.a.),
  eroeffnet_am, beendet_am, anzahl_rolls, endzustand
  (Verfall/Geschlossen/Assigned/Offen), netto_pnl_eur
- `chain_links` — chain_id, structure_id, sequenz, verknuepfungstyp
  (open/roll/close/adjust), erkennung
- `campaigns` — campaign_id, underlying, eroeffnet_am, beendet_am, netto_pnl_eur
- `campaign_links` — campaign_id, chain_id, **beziehungstyp**
  (ic_leg/financing/contract_roll/independent), erkennung, bestaetigt_am

**Benutzerdaten (überleben jeden Rebuild)**
- `journal_entries` — id, scope_typ (campaign/chain/structure/tag), scope_id, text,
  erstellt_am, geaendert_am
- `tags`, `entity_tags`
- `attachments` — id, scope_typ, scope_id, dateipfad, mime, erstellt_am
- `chain_overrides`, `campaign_overrides` — manuelle Korrekturen der Erkennung
- `roller_link` — Brücke zum Options Roller
- `fx_rates` — datum, waehrung, kurs_eur, quelle

**Materialisiert (Cache, verwerfbar)**
- `metrics_daily`, `metrics_by_chain`, `metrics_by_campaign`

---

## 6. Arbeitspakete

Jedes Paket: Ziel → Ausgang → Abnahme. Fertig ist ein Paket erst, wenn die
Abnahmekriterien maschinell überprüfbar erfüllt sind.

### AP-00 · Flex-Konfiguration ⚠ weitgehend erledigt
**Ziel:** Datenzugang klären. Ergebnis liegt vor, siehe §6.1.
**Erledigt:** Flex-Export reicht bis April 2022, Query-Typ Activity Flex.
Ausführungsebene vollständig, Ausführungs-ID als quellenübergreifender Schlüssel
bestätigt, Gruppierungsschlüssel für Combo-Orders gefunden.
**Verbleibend:**
1. Flex-Query nach §6.2 anpassen; Closed Lots einmal mit größerem Zeitraum
   gegentesten.
2. Prüfen, ob OptionApp `orderReference` künftig als Träger der Strategie-Kennung
   befüllen kann. Nicht mehr blockierend für AP-04, aber wertvoll für AP-12.
3. Strategie-Namenskonvention nach §1.3 festlegen.
4. Flex Web Service Token für den automatisierten Abruf einrichten.

#### 6.1 Befunde aus dem Referenz-Flex-Export

Grundlage: Activity-Flex-Export 01.04.2022–31.03.2023, 3.971 Ausführungen
(3.768 Optionen, 201 Aktien, 2 Cash), ausschließlich USD.

**Gruppierungsschlüssel für Combo-Legs ist `ibExecID`.** Format
`<batch>.<order>.<leg>.<fill>`; die ersten beiden Segmente bilden den Schlüssel.

| Kandidat | Eignung | Beleg |
|---|---|---|
| `ibExecID`-Präfix | **tauglich** | 768 von 778 Mehr-Leg-Zeitstempeln lösen sich in genau ein Präfix auf; kein Präfix über mehr als einen Basiswert oder Zeitstempel; Gruppen bis 6 Legs |
| `ibOrderID` | untauglich | 0 von 778 Mehr-Leg-Zeitstempeln teilen eine ID; gruppiert nur Teilfills desselben Kontrakts |
| `orderReference` | leer | in der Historie nicht befüllt |
| `volatilityOrderLink` | leer | nicht befüllt |
| `brokerageOrderID` | lückenhaft | 847 von 2.797 Zeilen |
| Zeitstempel allein | untauglich | 10 Fälle mit mehreren Orders im selben Sekundenwert |

**Weitere Feldbefunde:**
- **`tradeID`** entspricht der Spalte `Transaction ID` im Trading-Diary-Pro-Export
  (175 von 175 Treffern im Überschneidungszeitraum, null gegen `transactionID`).
  `tradeID` ist damit der Primärschlüssel der Tabelle `executions`. Das Feld
  `transactionID` wird sekundär mitgeführt, taugt aber nicht als Brücke zum
  Altbestand.
- Alle 1.376 Buchungen des Februar-Exports erscheinen mit identischer `tradeID` in
  der Jahresdatei. Die Dublettenerkennung über überlappende Zeiträume ist belegt.
- `openCloseIndicator` ist bei 3.243 von 3.971 Zeilen leer und trägt sonst nur „C".
  Unbrauchbar — eigene Zuordnung nach AP-03 zwingend.
- `fifoPnlRealized` steht auf Ausführungs- und Symbolebene durchgehend auf null.
  Das realisierte Ergebnis muss selbst berechnet werden.
- `notes` trägt die Ereigniscodes Ep (550), A (348), P (266), Ex (8) —
  deckungsgleich mit dem TDP-Export.
- `ibExecID` fehlt bei Ereigniszeilen. Unkritisch: diese nehmen nach P7 ohnehin
  nicht an der Strukturbildung teil.
- Der Zeitraum 2022/23 besteht fast vollständig aus Einzelaktienoptionen (FSLY,
  UPST, EBAY, KSS, DAL, PYPL, STNE, INTC). Der Golden-Test-Datensatz mit den
  134 DAX-Ketten liegt in einem späteren Zeitraum.

**Befunde aus dem zweiten Referenzexport (Februar 2026, 1.376 Ausführungen,
1.350 Optionen, 24 Aktien, 2 Futures, EUR und USD):**

**OptionApp schreibt eine strukturierte `orderReference`.** Format:
`OptionsApp: Trade <n>, Leg <n>, <Rolle> <n>` mit den Rollen `Open Order`,
`Close Order` und `Profit Target`. Damit liefert die Quelle die Kettenidentität
direkt — für diese Positionen ist keine Heuristik nötig.

| Merkmal | Wert |
|---|---|
| Ausführungen mit strukturierter Referenz | 653 von 1.376 |
| distinct OA-Trades / Orders | 137 / 188 |
| Rollen | Open Order 434, Close Order 207, Profit Target 12 |
| OA-Trades mit 2 Orders / 3 Orders | 70 / 3 |
| OA-Trades über mehr als einen Handelstag | 20 |
| OA-Trades mit mehr als einer Expiry (gerollt) | 27 |
| Abdeckung SPX / DAX | 609 von 818 / 29 von 180 |

**Fallstricke beim Parsen der Referenz:**
- **Order-Nummern sind nicht global eindeutig.** Drei Nummern erscheinen unter
  zwei verschiedenen OA-Trades und Basiswerten. Schlüssel ist das Paar
  (OA-Trade, OA-Order), niemals die Order-Nummer allein.
- **`Leg` ist nicht die Spread-Seite.** 76 von 149 Leg-Gruppen enthalten Calls und
  Puts gemischt; eine Leg-Nummer kann Öffnung und Schließung überspannen. Das Feld
  wird als opake Kennung gespeichert und nicht semantisch ausgewertet.
- **Generische Werkzeugnamen sind keine Kennungen.** `ActivityMonitor` (84),
  `OptTrader` (18), `OptionChain` (7) stammen aus TWS-Werkzeugen und tragen keine
  Gruppierungsinformation. Sie müssen erkannt und verworfen werden, sonst entstehen
  Phantomketten.
- **Strukturen sind nicht auf zwei Legs beschränkt.** OptionApp handelt auch
  Drei-Leg-Gebilde (Call-Spread plus einzelner Put). Die Typisierung in AP-04 muss
  n-Leg-Strukturen zulassen.

**Sektionsbefunde:** Open Positions (135) liefern Kostenbasis und unrealisiertes
Ergebnis. Cash Transactions (43) decken Zinsen, Quellensteuer, Dividenden,
Gebühren und Einzahlungen ab — Grundlage für E8. Corporate Actions und Transfers
sind aktiviert, im Berichtsmonat aber leer. Securities Info (712) liefert die
Instrumentenstammdaten. **Closed Lots fehlt noch** und ist nachzuaktivieren.

**Befunde aus dem OptionApp-Trade-Export (178 Trades, Zeitraum um August 2026):**

Spalten: `Entry Time`, `Strategy`, `Name`, `Strikes`, `Quantity`, `Open`, `Close`,
`Stops`, `Profit`, `Close Time`, `Status`.

- **20 benannte Strategien** liegen vor: `XSP: IF7` (34), `SPY: IF7` (31),
  `RUT: IC` (16), `SPX: IC +Vo/n` (12), `SPX: FKK10` (10), `SPX: DD 5/7` (8),
  `SPX: DC 0/1`, `SPX: ORB L PBF`, `SPX: Dawn`, `SPX: DC 1/2 We` (je 7),
  `QQQ: DC14/28`, `SPX: ORB L IF` (je 6) und weitere. E13 ist damit inhaltlich
  beantwortet — die Konvention existiert bereits und wird übernommen, nicht neu
  erfunden.
- `XSP: IF7` und `SPY: IF7` sind dieselbe Strategie auf zwei Instrumenten. Das
  belegt E10: eine Zusammenfassung der Basiswerte hätte genau die interessante
  Auswertung zerstört, nämlich den Vergleich beider Umsetzungen.
- **`Status` liefert den Endzustand:** EXPIRED (93), CLOSED (50),
  PARTIALLY STOPPED (24), EXPIRED estimated (8), STOPPED (2), UNMANAGED (1).
  Teilstopps hätte die Engine aus den Rohdaten kaum erkannt.
- **Abdeckung:** nur SPX, SPY, XSP, QQQ und RUT. DAX, ESTX50, Futures und die
  diskretionären Einzelwerte sind nicht enthalten und bekommen ihre Strategie über
  den Roller-Link oder manuell.

**Verknüpfung OA-Export ↔ Flex-Ketten**

- **Primär:** die Nummer in eckigen Klammern im Feld `Name` gegen `oa_trade`.
- **Sekundär, Absicherung:** `Entry Time` sekundengenau plus die vollständige
  Leg-Spezifikation aus `Strikes` (Richtung, Menge, Typ, Strike, Expiry je Leg).
  Weicht der Fingerabdruck vom Nummerntreffer ab, ist das ein Fehlerfall und
  keine stille Entscheidung.
- **Nicht als Fremdschlüssel verwenden.** `Name` ist ein frei editierbares
  Textfeld mit Nutzereinträgen („prüf EXIT Condition", „D25/25 VIX-0.3"). Ein
  Feld, das ein Mensch bearbeitet, trägt keinen stabilen Schlüssel.
- **Entschieden:** die Klammernummer ist die **Trade**-Nummer. Gemessen am
  Überschneidungszeitraum Februar 2026: 66 von 66 OA-Trades matchen gegen
  `Trade` in der `orderReference`, null gegen `Leg`, null gegen `Order`. Die
  Nummer ist damit der Primärschlüssel der Verknüpfung, der Fingerabdruck dient
  der Absicherung.

#### 6.2 Soll-Konfiguration der Flex-Query

**Sektion Trades**
- Detailebene **Execution** — die einzige, die gebraucht wird.
- **Modelle aus der Abfrage entfernen — Voraussetzung für alles Weitere.**
  IB deaktiviert sämtliche Realized-P/L-Abschnitte und -Felder, sobald Modelle
  einbezogen sind. Alle bisherigen Exporte tragen `model="Independent"`; deshalb
  blieb Closed Lots trotz gesetztem Schalter leer und `fifoPnlRealized` stand
  durchgehend auf null — auch schon 2022. Das Konto ohne Modellauswahl abfragen.
- Detailebene **Closed Lots**: nach Entfernen der Modelle verfügbar. Dient als
  Zweitmeinung, nicht als Abnahmegrundlage — der Bestandsabgleich in AP-03 ist
  aussagekräftiger.
- Abschnitt **Realized and Unrealized Performance Summary in Base** aktivieren.
  Liefert das realisierte Ergebnis je Basiswert und Anlageklasse in Basiswährung,
  mit bereits verrechneten Kommissionen. Grundlage der monetären Abnahmehälfte in
  AP-03. Wie IB den Berichtszeitraum dieses Abschnitts abgrenzt, zeigt erst der
  erste Export und ist dann festzuhalten.
- Sektionen **Cash Transactions** und **Corporate Actions** auf die Detailebene
  beschränken. Der Importer filtert zusätzlich selbst auf
  `levelOfDetail == "DETAIL"`, damit eine neu angelegte Abfrage keine stille
  Doppelzählung verursacht.
- Ebenen **Order**, **Symbol Summary** und **Asset Class Summary** abschalten.
  Sie gruppieren nichts Brauchbares und verdreifachen die Dateigröße.
- Pflichtfelder: `tradeID`, `transactionID`, `ibExecID`, `ibOrderID`,
  `orderReference`, `conid`, `symbol`, `underlyingSymbol`, `underlyingConid`,
  `assetCategory`, `multiplier`, `strike`, `expiry`, `putCall`, `buySell`,
  `quantity`, `tradePrice`, `proceeds`, `ibCommission`, `ibCommissionCurrency`,
  `currency`, `fxRateToBase`, `netCash`, `dateTime`, `orderTime`, `exchange`,
  `notes`, `openCloseIndicator`, `cost`, `mtmPnl`.

**Zusätzlich zu aktivierende Sektionen**

| Sektion | Zweck |
|---|---|
| Open Positions | Bestandsabgleich an den Periodengrenzen; ohne sie lassen sich offene Legs nicht validieren |
| Cash Transactions | Zinsen, Gebühren, Dividenden — Grundlage für E8 und die Aktien-Ergebnisrechnung |
| Corporate Actions | Splits und Kapitalmaßnahmen; ersetzt die manuelle Pflege aus E6 |
| Transfers | Positionsübertragungen, falls vorhanden |
| Financial Instrument Information | conid-Stammdaten, Multiplikator, Basiswert-conid |

**Reihenfolgeunabhängigkeit des Imports**

Stammdaten aus `SecuritiesInfo` und `Instruments` tragen das Periodenende ihrer
Quelldatei. Ein bestehender Datensatz wird nur überschrieben, wenn die neue Quelle
jünger ist. Damit ist die Importreihenfolge beliebig — eine Bedienanweisung
„erst Historie, dann Laufendes" wäre eine Fehlerquelle, die man in einem Jahr
vergisst. Bewegungsdaten sind davon nicht betroffen: sie sind unveränderlich und
werden bei Schlüsselkollision verworfen, nicht überschrieben.

**Abrufmodus**
- Format XML, Basiswährung EUR, `fxRateToBase` aktiviert.
- Ein Abruf umfasst höchstens 365 Tage. Historie jahresweise abrufen
  (2022/23, 2023/24, 2024/25, 2025/26), danach rollierend.
- Flex Web Service mit Token für den automatisierten nächtlichen Abruf.
  Der Token gehört nicht ins Repository.

### AP-01 · Fundament
**Ziel:** Repo, Toolchain, Schema, Testinfrastruktur.
**Ausgang:** Lauffähiges Skelett, Alembic-Initialmigration, `CLAUDE.md` mit den
Guardrails aus §7, CI-Task für `pytest` und `ruff`, WAL-Konfiguration,
Backup-Skript.
**Abnahme:** `make test` grün auf leerem Datenbestand. Schema entspricht §5.
Backup-Skript erzeugt eine konsistente Kopie auf dem Netzlaufwerk bei laufendem
Schreibzugriff.

### AP-02 · Ingest Flex Query
**Ziel:** Flex-XML → `executions`, idempotent, alle Anlageklassen.
**Ausgang:** CLI `journal import <datei>`; Instrument-Normalisierung inkl.
`asset_class`; Reporting über neue und übersprungene Zeilen.
**Abnahme:** Doppelter Import derselben Datei erzeugt null neue Zeilen. Zwei
überlappende Dateien erzeugen die Vereinigungsmenge ohne Duplikate. Unbekannte
Feldwerte oder unbekannte Anlageklassen führen zu einem Fehler, nicht zu stillem
Verwerfen.

### AP-03 · Leg-Matching
**Ziel:** Executions → geschlossene und offene Legs mit realisiertem P&L, über
alle Anlageklassen.
**Ausgang:** FIFO-Matching pro conid; Teilschließungen korrekt aufgeteilt;
Kommission anteilig zugeordnet; Multiplikator und Tickwert je Anlageklasse
korrekt angewandt; Kapitalmaßnahmen aus `corporate_actions` angewandt, bevor
gematcht wird.
**Abnahme — zwei Hälften, beide erforderlich:**

*Strukturell, Bestandsabgleich.* Der rekonstruierte Bestand stimmt an mehreren
Stichtagen über die gesamte Historie mit den offenen Positionen von IB überein.
Jede verbleibende Abweichung ist einzeln einer konkreten Ursache zugeordnet —
benanntes Papier, benanntes Datum, benannte Kapitalmaßnahme. Eine
Ursachenkategorie ohne Zuordnung der Einzelfälle gilt nicht als Erklärung.

**Der Stichtag richtet sich nach dem Buchungstag (`reportDate`), nicht nach dem
Handelstag.** Damit lösen sich Verfälle am Stichtag und Ausführungen, die im alten
Jahr gehandelt und im neuen gebucht wurden, ohne Sonderregel auf. Eine frühere
Fassung dieses Plans sah stattdessen die Konvention vor, am Stichtag verfallende
Optionen pauschal als offen zu zählen; das traf die Wirkung, aber nicht die
Ursache und erzeugte an Stichtagen, an denen Verfall und Buchung zusammenfallen,
16 beziehungsweise 34 neue Abweichungen. Die Regel ist ersatzlos gestrichen.

*Monetär, Jahressummen.* Das selbst berechnete realisierte Ergebnis stimmt je
Kalenderjahr und je Anlageklasse mit den Jahressummen der Kontoauszüge überein.
Diese Hälfte ist unverzichtbar: der Bestandsabgleich prüft, **welche** Positionen
offen sind, nicht **wie viel Geld** entstanden ist. Falscher Multiplikator, schief
verteilte Kommission bei Teilschließungen und ein FX-Kurs vom falschen Tag lassen
die Positionszahlen unberührt und entwerten trotzdem jede spätere Auswertung.

*Closed Lots entfallen.* Über sechs Exporte hinweg liefert das Konto keine
Lot-Ebene, `fifoPnlRealized` steht durchgehend auf null. Beide Abnahmehälften
kommen ohne aus.

*Reihenfolge:* Jahresexporte ziehen, Kapitalmaßnahmen anwenden, Bestandsabgleich
wiederholen, Jahressummen prüfen. Keine Abnahme vor diesem Durchlauf.
Ein Aktiensplit im Testdatensatz wird korrekt verarbeitet. Mindestens 35 Tests.

### AP-04 · Structure- und Chain-Erkennung ⚠ Kernstück
**Ziel:** Legs → Positionen → Ketten.

**Erkennungsreihenfolge (P5, P7):**
0. **Vorfilter:** Zeilen mit `ereignistyp != 'trade'` werden aus der
   Strukturbildung ausgeschlossen und getrennt verarbeitet. Ohne diesen Schritt
   verklebt ein Zeitfenster die Tagesabschlussbuchungen zu Phantomstrukturen —
   im Referenzexport 29 Legs über vier Basiswerte im selben Zeitstempel.
0a. **Höchste Priorität, OptionApp-Referenz:** trägt die Ausführung eine
   strukturierte `orderReference`, liefert sie die Kette (OA-Trade), die
   Strukturaktion (OA-Trade plus OA-Order) und die Rolle (Open/Close/Profit
   Target) direkt. Keine Heuristik, keine Zeitfenster. Generische Werkzeugnamen
   sind zu verwerfen, siehe §6.1.
1. **Primär, Ausführungsidentität:** ohne OA-Referenz gruppieren Legs mit gleichem
   `ibExecID`-Präfix (erste zwei Segmente) zu einer Structure. Eine
   Combo-Ausführung, die gleichzeitig Legs schließt und öffnet, ist ein Roll.
   Belege in §6.1.
1a. **Teilfills:** mehrere Ausführungen desselben Kontrakts mit gleicher
   `ibOrderID` werden vor der Strukturbildung zu einer Leg-Position verdichtet.
   `ibOrderID` gruppiert **keine** Combo-Legs und darf dafür nicht verwendet werden.
2. **Sekundär, Zeitfenster:** fehlt die `ibExecID` oder wurde in getrennten Orders
   gehandelt, gilt ein Fenster von **3 Minuten** bei gleichem Underlying, gleicher
   Seite und vergleichbarer Menge (Abweichung höchstens 20 %). Alle Werte
   konfigurierbar. **Gleicher Basiswert und gleiche Expiry sind Pflichtbedingung,
   nicht Feinschliff:** im Referenzexport liegen am 03.09. um 17:20:42 acht Legs
   sekundengleich — ein Iron Condor auf SPY und einer auf XSP, zwei getrennte
   Orders. Sekundengleichheit belegt keine gemeinsame Order.
2a. **Zuteilung:** ein `assignment` auf eine Option und die zeitgleiche
   Gegenbuchung im Basiswert werden über `assignment_links` verbunden. Die Kette
   setzt sich in der entstandenen Aktienposition fort, bis diese geschlossen ist.
3. **Futures:** Schließung Front-Monat und Eröffnung Back-Monat auf dasselbe
   Underlying wird als `contract_roll` behandelt.
4. **Aktien:** keine automatische Kettenbildung. Tranchen bleiben eigenständige
   Structures und können manuell zu einer Campaign gebündelt werden.

**Ausgang:** Chain-Aufbau, Override-Mechanismus, `journal rebuild`-Kommando.
**Abnahme:** Golden-Test gegen den bekannten Referenzdatensatz — 1.261
Transaktionen führen zu 134 Chains, davon 66 BCS und 68 BPS. Abweichungen sind zu
erklären, nicht wegzuparametrisieren. Jede Chain trägt aus, ob sie über Order-ID
oder Heuristik gebildet wurde. Manuelle Overrides überleben ein vollständiges
`rebuild`.
**Zusätzliche Pflichttests:** Ein Zeitstempel mit mehr als 20 Ereigniszeilen über
mehrere Basiswerte erzeugt null Strukturen. Eine zugeteilte Option und die daraus
entstandene Aktienposition liegen in derselben Kette. Ein Verfall schließt die
betroffenen Legs zu null, ohne eine Folgeposition zu erzeugen. Generische
`orderReference`-Werte erzeugen keine Kette. Zwei OA-Trades, die dieselbe
Order-Nummer tragen, bleiben getrennte Ketten. Eine Struktur mit drei Legs wird
als solche erkannt und nicht auf zwei Legs zurechtgestutzt.

### AP-05 · Campaign-Erkennung und Klassifikation
**Ziel:** Zusammengehörige Ketten beider Marktseiten gruppieren.

**Kandidatenregeln (Vorschlag, keine Automatik):**
- **IC-Kandidat:** gleiches Underlying, gleiche Expiry, gegenläufige Seiten, beide
  Ketten gleichzeitig offen, keine zwischenzeitliche Schließung.
- **Financing-Kandidat:** neue Kette auf der Gegenseite, eröffnet im zeitlichen
  Umfeld eines Rolls der Bestandskette, gleiches Underlying.

**Kernpunkt:** Die Unterscheidung zwischen geplanter IC-Seite und
Gegenfinanzierung ist eine Absichtsfrage und aus den Daten nicht entscheidbar. Das
System schlägt vor, der Nutzer klassifiziert einmal, die Entscheidung wird in
`campaign_links.beziehungstyp` persistiert und ist ab dann bindend.

**Ausgang:** Vorschlagsliste, Klassifikations-Dialog, Persistenz.
**Abnahme:** Vorschläge werden nie automatisch übernommen. Eine getroffene
Klassifikation überlebt `rebuild`. Unklassifizierte Kandidaten sind in der UI
sichtbar und arbeitbar.

### AP-06 · Analytik
**Ziel:** Kennzahlen auf allen vier Ebenen, filterbar nach Anlageklasse und
Datenqualitätsstufe.
**Umfang:** Netto-P&L und Trefferquote je Ebene · Kommissionsattribution absolut
und in Prozent des Bruttoergebnisses, aufgeschlüsselt nach Index, Anlageklasse,
Strategie und Roll-Anzahl · Roll-Degradationskurve (Ergebnis nach 0, 1, 2, 3+
Rolls) · Wirkung von Gegenfinanzierungen auf das Kampagnenergebnis ·
Equity-Kurve und Drawdown · Aufschlüsselung nach Index, Seite, DTE-Band, Breite ·
FX-Umrechnung nach P4.
**Abnahme:** Jede Kennzahl bietet Drilldown bis auf Execution-Ebene. Jede
Auswertung lässt sich auf Qualitätsstufe A einschränken. Die
Roll-Degradationsauswertung reproduziert die bekannte Aussage, dass Ketten ohne
Roll am besten abschneiden.

### AP-07 · API
**Ziel:** FastAPI-Schicht über Analytik und Benutzerdaten.
**Ausgang:** Read-Endpunkte für alle Ansichten; Write-Endpunkte für Journal, Tags,
Overrides und Kampagnen-Klassifikation; OpenAPI-Schema.
**Abnahme:** Contract-Tests gegen das OpenAPI-Schema. Kein Endpunkt liefert
Zahlen, die nicht aus L3 stammen.

### AP-08 · UI
**Ziel:** Bedienbares Frontend, im Betrieb statisch ausgeliefert.
**Umfang:** Dashboard (Equity, Monatsübersicht, Kommissionsanteil) ·
**Positionsliste** (alle Ketten, unabhängig von der Roll-Anzahl) mit Filtern nach
Strategie, Anlageklasse, Basiswert, Roll-Anzahl und Qualitätsstufe ·
Kampagnenansicht · Detailansicht mit Roll-Zeitstrahl und Gegenseiten-Verknüpfung ·
Kalenderansicht · Journal-Editor · Korrektur-Dialoge für Chain, Campaign und
Strategiezuordnung.
**Abnahme:** Jede Ansicht erreicht ihre Daten ausschließlich über die API. Die
Positionsliste zeigt Einzeltrades ohne Roll gleichrangig neben gerollten Ketten.
Die Detailansicht zeigt alle Structures einer Kampagne in zeitlicher Ordnung mit
Einzel-P&L und kumuliertem Ergebnis.

### AP-09 · Legacy-Import ab April 2022
**Ziel:** Historie erschließen. Quellenpriorität nach Ergebnis von AP-00:

1. **Jahresweise Flex- oder Activity-Statements** aus dem Broker-Portal →
   Qualitätsstufe A oder B. Kein neuer Parser nötig, AP-02 wird wiederverwendet.
2. **Trading-Diary-Pro-Vollexport** → Qualitätsstufe B. Struktur ist bekannt
   (24 Spalten, deutsches Zahlenformat mit Komma als Dezimaltrenner und Punkt als
   Tausendertrenner, Datumsformat `TT.MM.JJJJ hh:mm:ss`, Ereigniscodes in der
   Spalte `Notes`, `Contract Id` = conid, `Account` als Kurzkennung). Kettenbildung
   über die Zeitfenster-Heuristik, nicht über Order-IDs.
3. **PDF-Kontoauszüge** → Qualitätsstufe C, nur wenn 1 und 2 ausfallen. Keine
   automatische Chain-Bildung aus C-Daten. Layoutvarianten je Jahr einzeln testen.

**Abnahme:** Jahressummen aus dem Import stimmen mit den Jahresendsalden der
Auszüge überein. Die Qualitätsstufe jeder Zeile ist in der Auswertung sichtbar und
filterbar. Bei Nutzung von Quelle 2: Überlappungszeitraum mit Flex-Daten wird
importiert und beide Quellen werden auf Abweichungen verglichen, bevor die
Altdaten übernommen werden.

### AP-10 · Steuerliche Auswertung
**Ziel:** Trennung nach Aktien und Termingeschäften, Vorbereitung Anlage KAP.
**Abnahme:** Getrennte Töpfe je Anlageklasse, Jahresabgrenzung nach
Zuflussprinzip, Export als CSV. Keine steuerliche Beratung im Tool, nur
nachvollziehbare Aufbereitung.

### AP-11 · Absichtserfassung im Options Roller
**Ziel:** Der Roller schreibt beim Aufsetzen einer Position die Absicht mit
(IC-Seite, Gegenfinanzierung, Neueröffnung) und füllt `roller_link`.
**Abnahme:** Neue Positionen erscheinen im Journal mit vorbelegter
Kampagnenklassifikation, die der Nutzer nur noch bestätigen muss.

### AP-12 · Erwartung gegen Realität
**Ziel:** Je Strategie die im Option-Omega-Backtest erwartete Verteilung gegen das
im Journal realisierte Ergebnis stellen.
**Umfang:** Import der Backtest-Ergebnisse je Strategie-Kennung; Gegenüberstellung
von erwartetem und realisiertem Ergebnis, Trefferquote und Verlustverteilung;
Zerlegung der Differenz in Kommission, Slippage, Roll-Entscheidungen und Timing.
**Voraussetzung:** stabile Strategie-Kennungen nach §1.3 in allen drei Systemen.
**Abnahme:** Für mindestens eine Strategie liegt eine nachvollziehbare Zerlegung
der Abweichung vor, deren Einzelposten sich zur Gesamtdifferenz aufaddieren.

### AP-13 · OptionApp-Abgleich
**Ziel:** Den OA-Trade-Export einlesen und mit den Ketten verknüpfen, um Strategie,
Endzustand und ein zweites Ergebnis als Referenz zu erhalten.
**Umfang:** Parser für den Export (deutsches Zahlenformat, `Profit` mit
Währungszeichen, `Strikes` als Leg-Spezifikation) · Fingerabdruck-Verknüpfung nach
§6.1 · Übernahme von `Strategy` und `Status` in Kette und Strukturen · Abgleich des
OA-Ergebnisses gegen das selbst berechnete.
**Abnahme:** Für den Testzeitraum sind mindestens 95 % der OA-Trades eindeutig
einer Kette zugeordnet. Nicht zugeordnete Trades erscheinen in einer Fehlerliste,
werden nie stillschweigend verworfen. Abweichungen zwischen OA-Ergebnis und
eigener Berechnung sind erklärbar (typischerweise Kommissionsbehandlung).
Der Endzustand aus `Status` überschreibt nie eine aus Brokerdaten abgeleitete
Tatsache, sondern ergänzt sie.

---

## 7. Guardrails für ausführende Entwickler und Agenten

Gehört in die `CLAUDE.md` des Repos.

1. Schemaänderungen nur über eine Alembic-Migration, nie durch direktes Editieren.
2. Engine-Module (L2, L3) importieren weder `requests`, `datetime.now()` noch
   Zufallsquellen. Zeit kommt als Parameter herein.
3. Keine stillen Rundungen. Geldbeträge als `Decimal`, nie als `float`.
4. Kein Überschreiben von `executions`, keine Löschung von Benutzerdaten.
5. Automatisch erzeugte Verknüpfungen werden dem Nutzer als Vorschlag präsentiert,
   nie als Tatsache gespeichert. `erkennung` ist Pflichtfeld.
6. Neue Kennzahlen brauchen einen Test mit einem von Hand nachgerechneten
   Erwartungswert, nicht mit dem Ergebnis der eigenen Implementierung.
7. Bei Unklarheit im Fachlichen: Annahme im Code dokumentieren und in
   `OFFENE_FRAGEN.md` eintragen — nicht raten und weitermachen.
8. Der Options Roller hat Vorrang. Keine langlaufenden Schreibtransaktionen,
   `busy_timeout` gesetzt, im Konfliktfall abbrechen statt blockieren.
9. Ein Arbeitspaket ist erst fertig, wenn seine Abnahmekriterien erfüllt sind.

---

## 8. Reihenfolge und Meilensteine

| Meilenstein | Inhalt | Ergebnis |
|---|---|---|
| M0 | AP-00 | Datenlage geklärt, Flex-Query vollständig |
| M1 | AP-01, AP-02 | Rohdaten vollständig und reproduzierbar in der DB |
| M2 | AP-03, AP-04 | Ketten korrekt erkannt, Golden-Test grün |
| M3 | AP-05, AP-06 | Die drei Kernfragen aus §1 per CLI beantwortbar |
| M4 | AP-07, AP-08 | Bedienbares Tool |
| M5 | AP-09 bis AP-13 | Historie, Steuer, Absichtserfassung, OptionApp-Abgleich |

**M0 ist weitgehend erledigt.** Die Auswertung des Referenzexports hat den
Gruppierungsschlüssel geliefert (§6.1) und die Soll-Konfiguration festgelegt
(§6.2). Offen sind nur noch die Anpassung der Query und die Strategie-Konvention.

**Startfreigabe:** AP-01, AP-02 und AP-03 sind nicht von den offenen
Entscheidungen E12 bis E14 abhängig und können sofort beginnen. AP-00 läuft
parallel, es ist Portalarbeit ohne Programmieranteil. Trifft `orderReference`
später ein, genügen Re-Import und `rebuild` — die Struktur ändert sich nicht.

**M2 ist der Risikopunkt.** Vor M2 lohnt keine Arbeit an der UI.

---

## 9. Entscheidungsstand

**Entschieden**

- **E1 — Options Roller:** geteilte Datenbank und geteiltes Deployment, getrennte
  Domänenmodelle, Brücke über `roller_link`. Begründung in §4.1.
- **E2 — Roll-Definition:** primär Order-Identität, sekundär 3-Minuten-Fenster.
  Gegenfinanzierung und IC über die Campaign-Ebene (AP-05).
- **E3 — Datenumfang:** ein Konto, Historie ab April 2022, Vorgehen abhängig von
  AP-00. Anlageklassen: Optionen, Futures, Aktien.
- **E4 — Betrieb:** lokal auf dem Trading-Server, Sicherung auf Netzlaufwerk,
  Auflagen in §3.

- **E6 — Kapitalmaßnahmen:** vorrangig aus der Flex-Sektion Corporate Actions
  (§6.2). Manuelle Pflegetabelle nur noch als Rückfallebene für Vorgänge, die
  Flex nicht ausweist.
- **E7 — Futures-Kettenlogik:** Kontraktwechsel gilt als Fortsetzung derselben
  Kette, mit ausweisbarer Trennung je Kontrakt.
- **E8 — Zinsen und Finanzierungskosten:** separat ausgewiesen, nicht in die
  Trade-P&L eingerechnet.

- **E9 — Historienquelle:** Trading-Diary-Pro-Vollexport ab 2022 ist verfügbar und
  ersetzt den PDF-Parser. Zusammenführung mit Flex-Daten über die Ausführungs-ID.
- **E10 — Basiswerte:** kein Zusammenfassen von SPX/SPY/XSP. Stattdessen
  Strategie als Auswertungsdimension (§1.3). Backtest-Abgleich als AP-12.
- **E11 — Einzelwerte:** laufen gleichrangig mit. Eine Kette der Länge 1 ist der
  Normalfall, kein Sonderfall. Getrennt betrachtet wird per Filter, nicht per
  Modell.

**Offen**

- **E12 — `orderReference`:** vollständig beantwortet. In der Historie 2022/23
  leer, im aktuellen Betrieb von OptionApp strukturiert befüllt (§6.1). Für
  OA-Positionen ist damit auch die Kettenidentität gelöst; für den übrigen Bestand
  greift der `ibExecID`-Präfix.
- **E13 — Strategie-Namenskonvention:** die 20 OptionApp-Strategien werden
  übernommen, die Verknüpfung läuft über die OA-Trade-Nummer (§6.1). Offen bleibt
  allein eine Sammelkennung für den nicht von OptionApp gesteuerten Teil des Buchs
  — rund 61 % der Ausführungen.
- **E14 — Diskretionäre Trades:** eigene Strategie-Kennung je Vorgehen (z. B.
  „Einzelwert BPS opportunistisch") oder eine Sammelkennung? *Default:*
  Sammelkennung, verfeinerbar über Tags.

---

## 11. Arbeitsteilung zwischen Modellen

Die Abnahmekriterien in §6 sind maschinell prüfbar. Damit lässt sich der Großteil
der Umsetzung an ein günstigeres Modell vergeben, ohne die Qualität an der
Modellwahl aufzuhängen. Verifikation ersetzt Vertrauen.

### 11.1 Zuordnung

| Paket | Modell | Begründung |
|---|---|---|
| AP-00 | Mensch | Portalarbeit, keine Programmierung |
| AP-01 | stark | setzt Schema und Regeln für alle folgenden Pakete |
| AP-02, AP-03 | günstig | eng umrissen, hart testbar |
| AP-04, AP-05 | stark | Urteilsfragen, Mehrdeutigkeit, echte Kontodaten als Golden-Test |
| AP-06 | stark | Kennzahlendefinitionen müssen stimmen |
| AP-07 bis AP-10 | günstig | Fleißarbeit gegen feste Verträge |
| AP-11 bis AP-13 | stark | Schnittstellen zu bestehenden Systemen |

Die Trennung fällt mit der Datenschutzgrenze zusammen: die Pakete beim
Drittanbieter kommen mit synthetischen oder verfremdeten Fixtures aus. Echte
Kontodaten verlassen die Pakete beim starken Modell nicht.

### 11.2 Arbeitsmuster

1. Starkes Modell schreibt Abnahmetests und Fixtures für ein Paket.
2. Günstiges Modell implementiert, bis die Tests grün sind.
3. Diff-Review durch das starke Modell am Paketende, nicht zwischendurch.

### 11.3 Zusätzliche Guardrails für die `CLAUDE.md`

10. **Tests, Fixtures und Abnahmekriterien sind unveränderlich.** Kein Modell
    ändert sie, um grün zu werden. Schlägt ein Test fehl, ist der Code falsch oder
    die Anforderung unklar — im zweiten Fall Eintrag in `OFFENE_FRAGEN.md` und
    Abbruch, keine Anpassung des Tests.
11. Golden-Test-Fixtures mit echten Kontodaten liegen in einem eigenen Verzeichnis
    und werden nur von Paketen beim starken Modell gelesen.

### 11.4 Einbindung in Claude Code

Z.AI stellt einen Anthropic-kompatiblen Endpunkt bereit, kein Proxy nötig. Eine
eigene Settings-Datei statt globaler Umgebungsvariablen, damit das reguläre
`claude` unangetastet bleibt und beide Modelle parallel laufen können.

`.claude/settings-guenstig.json` im Projektverzeichnis:

```json
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "<api-key>",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "<flash-modell>",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "<hauptmodell>",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "<hauptmodell>",
    "API_TIMEOUT_MS": "3000000"
  }
}
```

Start über `claude --settings .claude/settings-guenstig.json`, auf Windows
gekapselt in einer `dev-guenstig.cmd`. Ein zweites `dev-stark.cmd` ohne Override
startet das reguläre Setup.

**Betriebshinweise:**
- Modellbezeichnungen und Endpunkt beim Anbieter verifizieren, sie ändern sich
  häufig. Die aktuelle Anbieterdokumentation ist maßgeblich, nicht dieses Dokument.
- Bei alternativen Endpunkten die Tool-Search-Funktion deaktiviert lassen; die
  Kompatibilität ist nicht überall vollständig.
- Der API-Schlüssel gehört nicht ins Repository. Settings-Datei in `.gitignore`.
- Abrechnung: für Massenarbeit ist ein Flatrate-Coding-Plan planbarer als
  Token-Abrechnung.

---

## 12. Was das Projekt bewusst nicht ist

Kein Multi-Broker-Import. Kein Live-Positionsmonitor — das leistet das bestehende
Dashboard. Kein Backtester. Kein Mehrbenutzersystem. Keine Steuerberatung. Jede
dieser Grenzen später zu öffnen ist möglich; sie jetzt offen zu halten kostet Zeit
ohne Gegenwert.
