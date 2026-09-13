---
titel: Korrektur der Abnahmebasis AP-02 - echtes Flex-Format (OF-19, OF-20, OF-22)
modell: stark
status: offen
abhaengig_von: AP-02a
aendert_tests: ja
---

# AP-02k · Abnahmebasis des Imports auf das echte Flex-Format

Korrekturpaket nach CLAUDE.md, Regel 1a. Es stellt Fixtures und Tests des
Flex-Imports auf das Format um, das IB tatsächlich liefert, und legt Tests für
drei Befunde aus dem Golden-Lauf an. **Implementiert wird nichts** — die
Nachbesserung von `ingest/flex.py` macht danach AP-02 gegen diese Tests.

Golden-Daten brauchst du dafür nicht: Das echte Schema steht vollständig unten.
Es enthält nur Attributnamen, Formen und Aufzählungswerte, keine Inhalte.

## Anlass

Der Golden-Lauf vom 12./13.09.2026 (OF-19 bis OF-22) hat gezeigt: Der Import
liest keine einzige echte Ausführung. Die synthetischen Fixtures bilden ein
Format ab, das IB nicht liefert, und alle Tests laufen gegen dieses Format
grün. Mit provisorisch korrigiertem Import stimmen die Bestände des Matchings
an echten Daten dagegen fast vollständig mit IB überein — der Fehler liegt vor
dem Matching.

## Das echte Format

Gemessen an sechs Exporten 2022–2026.

| Element | Ebene (`levelOfDetail`) | Zeitfelder |
|---|---|---|
| `Trade` | `EXECUTION` | `dateTime` als `JJJJMMTT;HHMMSS`; `orderTime` ebenso oder leer; **kein `tradeTime`** |
| `CashTransaction` | `DETAIL`; ältere Exporte zusätzlich `SUMMARY` (Tagesaggregate der DETAIL-Zeilen) | `dateTime` als `JJJJMMTT;HHMMSS` **oder nur** `JJJJMMTT` |
| `CorporateAction` | `DETAIL`; älter zusätzlich `SUMMARY` | `dateTime` in beiden Formen |
| `OpenPosition` | `SUMMARY` | `reportDate` als `JJJJMMTT` |
| `Transfer` | `TRANSFER` | `dateTime` als `JJJJMMTT;HHMMSS` |
| `FlexStatement` | — | `fromDate`, `toDate` als `JJJJMMTT`; `whenGenerated` als `JJJJMMTT;HHMMSS`; dazu `period` |

Weiter gemessen:

- `FlexStatement` hat **kein** `currency`, `OpenPosition` **kein** `markValue`.
- `notes` ist eine durch `;` getrennte Liste von Codes. Vorkommende Werte:
  leer, `Ep`, `Ex`, `A`, `P`, `IA`, `L`, `IA;P`, `FP;P`.
- Jede DETAIL-Zeile der CashTransactions trägt eine `transactionID`. Dieselbe
  ID kommt als Paar `Broker Interest Paid` / `Broker Interest Received` vor;
  die Kombination aus `transactionID` und `type` ist eindeutig.

## Fachliche Regeln (vom Nutzer bestätigt)

1. **Zeitformen.** `JJJJMMTT;HHMMSS` ergibt den Zeitpunkt. `JJJJMMTT` ohne
   Uhrzeit ergibt 00:00:00 — eine dokumentierte Annahme, keine Information
   der Quelle. Jede andere Form bricht mit genanntem Feld ab. Die Handelszeit
   einer Ausführung kommt aus `dateTime`; `tradeTime` wird nicht gelesen.
2. **Codes in `notes`.** `Ep`, `Ex` und `A` bestimmen den Ereignistyp, auch
   als Teil einer Liste. `P`, `IA`, `FP` und `L` sind Zusatzkennzeichen einer
   gewöhnlichen Ausführung und ergeben `trade`. `ereignis_code` trägt den
   Rohwert von `notes`. Jeder andere Code bricht mit genanntem Code ab (OF-08);
   zwei Ereigniscodes in einer Liste brechen ebenfalls ab.
3. **Ebenen je Sektion.** Trades: nur `EXECUTION`. CashTransactions und
   CorporateActions: `DETAIL` wird gebucht, `SUMMARY` wird nicht gebucht, aber
   gezählt und im Importergebnis ausgewiesen. OpenPositions: nur `SUMMARY`.
   Transfers: nur `TRANSFER`. Jede andere Ebene und ein fehlendes
   `levelOfDetail` brechen mit genannter Sektion und Ebene ab. Das gilt
   ausdrücklich auch für Trade-Zeilen einer Closed-Lot-Ebene: Sie sollen
   sichtbar stoppen, nicht still als Ausführungen landen. Ihre Verarbeitung
   ist ein eigenes Paket, sobald ein echter Export mit Closed Lots vorliegt.
4. **Identität einer Sektionszeile mit ID.** Zwei Zeilen sind dieselbe Buchung,
   wenn Konto, `transactionID` und `type` übereinstimmen. Zweimal dieselbe
   Kombination in einer Datei bricht ab. Zeilen ohne ID behalten den
   bisherigen Inhaltsschlüssel (OF-09).
5. **Importergebnis.** `ImportErgebnis` erhält das Feld
   `summenzeilen_uebersprungen` (Anzahl nicht gebuchter SUMMARY-Zeilen).

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Alle Dateien unter `fixtures/flex/`** auf das echte Format umstellen:
  - an Trades `tradeTime` durch `dateTime` in echter Form ersetzen;
  - `orderTime` und die `dateTime` der Sektionen in echte Form bringen;
  - `whenGenerated` in echte Form bringen;
  - an jeder Zeile `levelOfDetail` gemäß Tabelle setzen;
  - `FlexStatement.currency` und `OpenPosition.markValue` entfernen.

  **Inhaltlich bleibt jede Datei gleich:** dieselben Zeilen, IDs, Beträge,
  Mengen, Codes und Zeitpunkte, nur in echter Schreibweise. Mindestens eine
  CashTransaction erhält die reine Datumsform, damit sie abgedeckt ist.
- `fixtures/flex/activity_doppelte_buchungs_id.xml`: Die zweite Zeile erhält
  die Art der ersten (`Dividends`). Nur so prüft sie nach Regel 4 weiter den
  Abbruch. Der Test `test_duplicate_transaction_id_within_file_fails_and_writes_nothing`
  bleibt unverändert.
- `fixtures/flex/README.md`: auf das echte Format und die Regeln hier
  aktualisieren.
- `tests/test_ingest_flex.py`, **`test_unclassified_event_code_p_is_stored_as_unbekannt`**:
  umbenennen in `test_partial_execution_code_p_is_a_trade`. Erwartung: Die
  Zeile ist vorhanden, `ereignistyp == "trade"`, `ereignis_code == "P"`. Der
  Moduldocstring zu `P` wird entsprechend berichtigt.
- `tests/test_ingest_flex.py`, die Hilfen der AP-02a-Tests (`STATEMENT_RUMPF`,
  `TRADE_RUMPF`, `STAMMSATZ_RUMPF`, `_trade`) und die dort übergebenen
  Zeitwerte: echte Form, `levelOfDetail`, `dateTime`. **Erwartungen
  unverändert.**
- `tests/test_ingest_flex_sektionen.py`, Hilfe `_neuabruf`: Der ersetzte
  `whenGenerated`-Wert erhält echte Form. **Erwartungen unverändert.**
- **Neue Datei `tests/test_ingest_flex_format.py`** mit diesen Tests; Testdaten
  im Test (`tmp_path`) oder als neue Dateien unter `fixtures/flex/`:
  1. `test_datetime_with_semicolon_is_the_trade_time`
  2. `test_trade_without_datetime_aborts` — auch wenn ein `tradeTime` vorhanden ist
  3. `test_date_only_cash_booking_gets_midnight`
  4. `test_unknown_time_form_aborts_with_named_field`
  5. `test_modifier_codes_are_trades` — `IA`, `L`, `IA;P`, `FP;P`
  6. `test_event_code_inside_a_list_sets_the_event_type`
  7. `test_unknown_code_inside_a_list_aborts_with_named_code`
  8. `test_two_event_codes_abort`
  9. `test_summary_cash_rows_are_counted_not_booked` — DETAIL und SUMMARY in
     einer Datei; gebucht nur DETAIL; `summenzeilen_uebersprungen` stimmt
  10. `test_unknown_or_missing_level_aborts` — unter anderem eine Trade-Zeile
      mit Closed-Lot-Ebene
  11. `test_same_transaction_id_with_different_type_are_two_bookings` — Paar
      Zins gezahlt/erhalten; erneuter Import legt nichts doppelt an
  12. `test_open_positions_summary_and_transfer_level_are_accepted`

  Jeder Test nennt im Docstring die Regel aus diesem Auftrag, die er belegt.

Bestehende Tests außerhalb der oben genannten Stellen bleiben unberührt.

## Umzusetzen

1. Fixtures und Tests wie oben.
2. `auftraege/AP-02.md`: Die Regeln 1–5 als Vertrag an die Nachbesserung
   eintragen.
3. `OFFENE_FRAGEN.md`: OF-19, OF-20 und OF-22 fortschreiben; die Annahme zur
   reinen Datumsform (Regel 1) vermerken.
4. **Schema-Abgleich:** Vor Abschluss jedes neue oder geänderte Fixture
   maschinell gegen die Tabelle „Das echte Format" prüfen — Attributnamen,
   Zeitformen, Ebenen — und das Ergebnis im Abschluss melden. Genau dieser
   Schritt hat gefehlt, als die ursprünglichen Fixtures entstanden.

## Abnahme

- Gegen den jetzigen `ingest/flex.py` schlagen die umgestellten und die neuen
  Tests fehl, wo die Befunde es erwarten. Das ist gewollt; `check.cmd` ist bis
  zur Nachbesserung von AP-02 rot.
- Tests ohne Bezug zum Import-Format (Schema, Backup, Decimal, WAL, Matching)
  bleiben grün.
- Der Schema-Abgleich aus Schritt 4 ist gemeldet und ohne Befund.
- `git diff --stat` zeigt Änderungen ausschließlich unter `fixtures/flex/`, in
  `tests/test_ingest_flex.py`, `tests/test_ingest_flex_sektionen.py`,
  `tests/test_ingest_flex_format.py`, `auftraege/AP-02.md` und
  `OFFENE_FRAGEN.md`. Kein `ingest/`, keine Migration.

## Ausdrücklich nicht Teil dieses Pakets

- keine Änderung an `ingest/flex.py`;
- keine Verarbeitung von Closed Lots;
- kein Befüllen von `corporate_actions` für das Matching — Kapitalmaßnahmen
  sind ein eigenes Paket (OF-15, OF-21);
- keine Prüfung des Vorzeichens von `quantity` (OF-13).
