---
titel: Schluesselkorrektur exec_id auf tradeID
modell: stark
status: offen
abhaengig_von: AP-02
aendert_tests: ja
---

# AP-02a · Schlüsselkorrektur

Korrekturpaket. Es ändert Test-Erwartungen und läuft deshalb unter dem Profil
`locker`. Das ist der einzige zulässige Weg, eine bestehende Test-Erwartung zu
ändern — siehe CLAUDE.md, Regel 1.

## Anlass

In AP-01 wurde `transactionID` als Primärschlüssel der Tabelle `executions`
angelegt, weil §6.1 des Plans das so auswies. Diese Angabe war falsch. Die
Messung am Überschneidungszeitraum ergibt: die Spalte `Transaction ID` im
Trading-Diary-Pro-Export entspricht dem Flex-Feld **`tradeID`** — 175 von 175
Treffern, null Treffer gegen `transactionID`. Der Namensgleichklang ist
irreführend.

Ohne Korrektur hätten Altbestand ab 2022 und laufende Flex-Importe in AP-09
keine gemeinsamen Schlüssel. Jede Buchung des Überschneidungszeitraums läge
doppelt in der Datenbank.

## Ausdrücklich freigegebene Änderungen an Tests

Nur diese, keine weiteren:

- `tests/test_ingest_flex.py`: die Erwartungen auf `transactionID`-Werte werden
  auf die entsprechenden `tradeID`-Werte umgestellt. Betroffen sind unter anderem
  die Prüfung um Zeile 83 und der Block um Zeile 93 bis 95. Prüfe die ganze Datei
  auf weitere Vorkommen.
- **Die Fixtures bleiben unverändert.** Die `tradeID`-Werte stehen bereits darin.
  Ändert sich eine Datei unter `fixtures/`, ist das ein Fehler.
- `tests/test_ingest_flex.py`: die drei unter „Abnahme" verlangten neuen Tests
  dürfen ergänzt werden. Ihre Testdaten entstehen im Test selbst (`tmp_path`),
  weil `fixtures/` tabu ist. Bestehende Tests bleiben bis auf die oben genannten
  Erwartungen unberührt; kein Umbau, keine Abschwächung.

Die Prüflogik der Tests bleibt gleich. Es ändert sich nur, welches Feld als
Schlüssel erwartet wird. Wenn du feststellst, dass ein Test dadurch inhaltlich
schwächer würde, melde das, statt ihn abzuschwächen.

## Umzusetzen

1. **Migration:** `exec_id` trägt künftig den Wert aus `tradeID`. Neue Spalte
   `transaction_id` für das Feld `transactionID`, sekundär, nicht eindeutig
   erzwungen, dient der Abstimmung mit dem Broker.
2. **Mapping in `ingest/flex.py`** entsprechend umstellen.
3. **Harte Prüfung statt stillem Ausweichen — nur für `executions`:** fehlt einer
   Trades-Zeile die `tradeID`, bricht der Import mit Nennung der betroffenen
   Zeile ab. Begründung: über drei Exporte mit zusammen 19.425 Zeilen ist
   `tradeID` lückenlos und eindeutig, auch auf allen 5.944 Ereigniszeilen. Eine
   fehlende `tradeID` wäre ein Defekt des Exports und soll auffallen, nicht
   kompensiert werden.
   **Die Quellschlüssel der Sektionszeilen bleiben unverändert**
   (`_quell_schluessel_vergeben` in `ingest/flex.py`): `tx:<id>`, sonst
   `inhalt:<sha256>#<n>`. Der Inhalts-Hash ist dort kein Ersatz für die
   `exec_id`, sondern der einzige Schlüssel von Zeilen ohne ID — `OpenPositions`
   tragen gar keine. Fällt er weg, bricht der Sektionsimport und die
   Dublettensicherung aus OF-09.
4. **Reihenfolgeunabhängiger Upsert der Stammdaten:** Datensätze aus
   `SecuritiesInfo` und die Instrumentenstammdaten tragen das Periodenende ihrer
   Quelldatei. Ein bestehender Datensatz wird nur überschrieben, wenn die neue
   Quelle jünger ist. Die Importreihenfolge muss dadurch beliebig sein.
   Bewegungsdaten sind nicht betroffen: sie bleiben unveränderlich und werden bei
   Schlüsselkollision verworfen.

## Abnahme

- `pytest` und `ruff check .` laufen sauber.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_ingest_flex.py`, `ingest/`, `migrations/`, Modelldefinitionen und
  `OFFENE_FRAGEN.md` (OF-09 und OF-10 fortschreiben, OF-11 schließen).
  **Keine Änderung unter `fixtures/`.**
- Ein Test belegt, dass eine Zeile ohne `tradeID` den Import abbricht.
- Ein Test belegt, dass ein Import älterer Stammdaten nach neueren die neueren
  nicht überschreibt, und dass die umgekehrte Reihenfolge dasselbe Ergebnis
  liefert.
- Ein Test belegt, dass dieselbe Buchung aus zwei überlappenden Quelldateien
  genau einmal in `executions` landet.

## Ausdrücklich nicht Teil dieses Pakets

Kein Leg-Matching, keine Strukturbildung, keine Erweiterung des Importumfangs.
Nur die Schlüsselumstellung und der reihenfolgeunabhängige Upsert.
