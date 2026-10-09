---
titel: Automatischer Abruf der Flex-Query — Umsetzung und Nachtlauf
modell: guenstig
status: offen
abhaengig_von: AP-02a2
aendert_tests: nein
---

# AP-02a2k · Umsetzung gegen die Abnahmebasis AP-02a2

Vertrag und Entscheidungen: `auftraege/AP-02a2.md` (vollständig lesen).
Maßgeblich sind die Tests in `tests/test_flex_abruf.py` (unveränderlich,
Regel 1).

## Zu bauen

1. **`ingest/flex_abruf.py`** (neu): `AbrufFehler`, `standard_transport`,
   `abrufen`, `statement_speichern` nach dem Vertrag; Konstanten `BASIS_URL`
   und ein Pfad `PROJEKTWURZEL` für die Prüfung des Ziels. Nur Standard-
   bibliothek (`urllib.request`, `xml.etree.ElementTree`, `hashlib`) — keine
   neue Abhängigkeit. Antworten mit `xml.etree` parsen (die Statements
   stammen von IBKR, nicht von Dritten; die Dateigröße bleibt klein).
2. **`journal/cli.py`:** Unterbefehl `abrufen` mit den Optionen aus dem
   Vertrag; liest `FLEX_TOKEN`, `FLEX_QUERY_ID`, `FLEX_ZIEL` aus der
   Umgebung. Die Ausgabezeile des Imports ist dieselbe wie bei `journal
   import`; bei `--rebuild` ruft der Befehl danach den Rebuild-Befehl auf
   (die Tests ersetzen `journal.cli.rebuild`).
3. **`nachtlauf.cmd`** (neu, Projektwurzel, Windows-Stapeldatei, nicht
   getestet — wird vom starken Modell gelesen und vom Nutzer erprobt):
   - liest Zugangsdaten aus `%USERPROFILE%\.trading-journal\flex.cmd`, falls
     vorhanden (setzt `FLEX_TOKEN`, `FLEX_QUERY_ID`, `FLEX_ZIEL`, optional
     `FLEX_BACKUP_ZIEL`); **keine Zugangsdaten in der Datei selbst**,
   - wechselt in das Projektverzeichnis, bricht ab, wenn `.venv` fehlt,
   - ruft `journal abrufen --rebuild` auf und schreibt die gesamte Ausgabe
     in `%USERPROFILE%\.trading-journal\logs\nachtlauf-JJJJMMTT.log`
     (außerhalb des Repositories),
   - bei Erfolg und gesetztem `FLEX_BACKUP_ZIEL`: `backup.cmd journal.db
     <Ziel>\journal-JJJJMMTT.db`, danach nur die 14 neuesten Dateien
     `journal-*.db` im Ziel behalten (ältere löschen),
   - gibt den Fehlercode des fehlgeschlagenen Schritts zurück, läuft strikt
     nacheinander (nie zwei Python-Prozesse gleichzeitig).
4. **`START.md`** (oder `README.md`): Abschnitt „Nächtlicher Abruf" mit den
   Umgebungsvariablen, dem Muster der Datei `flex.cmd` (ohne echten Token),
   einem Probelauf von Hand (`.venv\Scripts\python.exe -m journal abrufen
   --ziel …`) und dem Befehl zum **Einrichten** der Aufgabe als Beispiel
   (`schtasks /Create …`), **ohne** ihn auszuführen.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, am Schema, am Import
(`ingest/flex.py`). Keine neue Abhängigkeit, kein Dienst, kein Hintergrund-
prozess. **Der Token wird nirgends ausgegeben oder gespeichert**, auch nicht im
Protokoll von `nachtlauf.cmd` (kein `set` und kein `echo` der Variablen).

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Probelauf gegen die echte Gegenstelle macht der Nutzer mit seinem Token; das
starke Modell liest `nachtlauf.cmd` vor der Übergabe.
