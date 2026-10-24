# Journal für das Paper-Konto

Stand 24.10.2026. Das Paper-Konto des Rollers (`DU…`) liegt **nicht** im echten Journal (`journal.db`, Konto `U8…`). Der Import lehnt
ein fremdes Konto ab (Einzelkonto-Grenze). Wer die Roller-Trades auf Paper mit den Journal-Kennzahlen sehen will, nimmt dieselbe Software
mit einer **eigenen Datenbank**:

| | echtes Journal | Paper-Journal |
|---|---|---|
| Datenbank | `journal.db` | `%USERPROFILE%\.trading-journal\paper\journal-paper.db` |
| Port | 8000 | 8001 |
| Zugangsdaten | `%USERPROFILE%\.trading-journal\flex.cmd` | `…\paper\flex-paper.cmd` |
| Nachtlauf | `nachtlauf.cmd` | `werkzeuge\paper\nachtlauf-paper.cmd` |

## Einrichtung (einmalig)

1. **Flex-Abfrage für das Paper-Konto anlegen** (IB Kontoverwaltung → Berichte → Flex-Abfragen), mit denselben Sektionen wie für das echte
   Konto (Trades, Open Positions, Cash Transactions, NAV, Corporate Actions, Transfers, Securities Info). Token und Query-ID notieren.
   *Das kann nur der Nutzer tun.*
2. `.\werkzeuge\paper\Einrichten-Paper.ps1` — legt Ordner und Datenbank an (Migration) und eine Vorlage `flex-paper.cmd`.
3. In `flex-paper.cmd` Token und Query-ID eintragen (die Datei nie weitergeben).
4. Aufgabenplanung: `werkzeuge\paper\nachtlauf-paper.cmd` nachts, wie beim echten Journal.
5. `.\werkzeuge\paper\Schnellstart-Paper.ps1` startet das Paper-Journal auf Port 8001 (zeigt den Roller-Dienst auf Port 8600).

## Hinweise

- Die Roller-Orders tragen die `orderRef` `R3|…`; im Paper-Journal erscheinen sie als normale Ausführungen und werden wie im echten Journal zu
  Strukturen und Ketten verknüpft.
- Die Paper-Fills sind von IB simuliert; Kennzahlen daraus sagen etwas über den Ablauf, nicht über Fill-Qualität am echten Markt.
- Steuer-Seiten des Paper-Journals sind bedeutungslos (Paper hat keine steuerliche Wirkung).
- Das echte Journal wird durch nichts hier verändert.
