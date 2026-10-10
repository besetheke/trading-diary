---
titel: Kettensicht ohne Doppelzählung — Umsetzung (OF-68, Option A)
modell: guenstig
status: fertig
abhaengig_von: AP-04sx
aendert_tests: nein
---

# AP-04sy · Umsetzung gegen die Abnahmebasis AP-04sx

Fachliche Regeln und Begründung: `auftraege/AP-04sx.md` (Abschnitt „Neue Regel",
vier Punkte). Maßgeblich sind die Tests in `tests/test_kettensicht.py` — sie
sind unveränderlich (Regel 1). Schlägt einer fehl, ist der Code falsch; bei
fachlicher Unklarheit `OFFENE_FRAGEN.md` und Abbruch.

## Zu ändern

- `engine/kettensicht.py`: `kettensicht_legs` liefert die Kettensicht-Legs;
  Erkennung der umgeleiteten Ausführungen (`_umgeleitet`) bleibt unverändert.
  Modul-Docstring an die neue Regel anpassen (OF-52 „zählt doppelt" gilt nicht
  mehr; OF-68).
- `engine/matching.py`: **nur additiv**, Standardverhalten von `bilde_legs`
  bleibt bitgleich (alle Tests in `tests/test_matching.py` unverändert grün).
  Gebraucht werden zwei optionale Eingaben mit leerem Standardwert:
  - Ausführungen, die zwingend **eröffnen** (nie schließen), und
  - Kontrakte, deren Verfall vor der letzten Handelszeit des Eingabebestands
    liegt; für sie werden am Ende gegenläufige offene Lose FIFO gegeneinander
    geschlossen (früheres Los eröffnet, späteres schließt).
  Dafür führt der FIFO je Kontrakt zwei Bestände (Long/Short): eine Ausführung
  schließt das älteste Los der Gegenrichtung, sonst eröffnet sie.
  Mengenaufteilung und Kommissionsverteilung (`teilmengen`) wiederverwenden,
  nicht nachbauen — die Summe der Kommission muss in beiden Sichten exakt gleich
  sein (Regel 5).
- Ohne umgeleitete Ausführung gibt `kettensicht_legs` die Kontosicht-Legs
  unverändert zurück.

## Grenzen

- Kein Eingriff in `engine/structures.py`, `engine/chains.py`, `journal/`.
- Rein (Regel 6): „letzte Handelszeit" kommt aus den übergebenen
  Ausführungen, kein `datetime.now()`.
- Keine Änderung unter `tests/` oder `fixtures/`.

## Abnahme

- `pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`.
- **Nach der Umsetzung führt das starke Modell den Echtabgleich aus**
  (Kopie von `journal.db`, Rebuild): Brutto und Kommission je Sicht gleich,
  offene Legs gleich. Das ist nicht Teil dieses Auftrags.
