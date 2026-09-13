# Abgleich gegen die Golden-Daten

Diese Skripte sind der Nachweis für die Abnahme von AP-03 (Plan §6, zwei
Hälften: Bestandsabgleich und Geldtest). Sie liegen im Repo, damit sich jede
Prüfung nach einer Nachbesserung unverändert wiederholen lässt — eine
Neufassung aus dem Gedächtnis kann sich unbemerkt unterscheiden.

**Regeln (CLAUDE.md, Regel 2):**

- Die Skripte lesen `fixtures/golden/`, schreiben nichts und legen keine
  Datenbank an; alles läuft im Speicher.
- Ausgegeben werden ausschließlich Zählwerte, Aufzählungswerte, relative
  Größenordnungen und Pseudonyme — keine Beträge, Titel, `conid`s oder
  Kontonummern. Das gilt auch für Fehlermeldungen.
- Nur Pakete des starken Modells führen sie aus.

**Provisorisch:** Solange der Import das echte Flex-Format nicht liest
(OF-19 bis OF-22), passen die Skripte ihn nur im eigenen Prozess an. Diese
Anpassungen sind Befund, nicht Lösung, und entfallen nach der Nachbesserung von
AP-02.

| Skript | Prüft |
|---|---|
| `golden_barausgleich.py` | Geldtest je schließender Ausführung und je Basiswert, mit und ohne Barausgleich (OF-24, OF-25) |
| `golden_lieferart.py` | Ob `settlementPolicyMethod` barausgeglichene von physischen Zuteilungen trennt (OF-25) |

Aufruf aus dem Projektverzeichnis:
`.venv\Scripts\python.exe werkzeuge\abgleich\<skript>.py`
