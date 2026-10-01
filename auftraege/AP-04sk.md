---
titel: Kettensicht-Zuordnung (engine/kettensicht.py)
modell: guenstig
status: fertig
abhaengig_von: AP-04s
---

# AP-04sk · Kettensicht-Zuordnung

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-04s). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag in `auftraege/AP-04s.md`, Abschnitt „Ablauf"
— er ist verbindlich, kein Implementierungsdetail zur freien Wahl. Lies
auch „Die Stelle, an der erfahrungsgemäß geraten wird" vollständig, bevor
du anfängst — der naheliegende erste Entwurf hat genau dort einen Fehler.

## Worum es geht

Baut aus den Kontosicht-Legs (`engine.matching.bilde_legs()`, bereits
vorhanden) die Kettensicht-Legs: dieselben Legs, plus für jede
„umgeleitete" Ausführung (OF-52, OF-36) eine eigene, neue Struktur-
Eröffnung — unter Wiederverwendung der bestehenden FIFO-Logik, nicht
durch eine neue.

## Zu bauen

Ein einziges neues Modul: `engine/kettensicht.py`, mit
`kettensicht_legs()` nach Vertrag.

## Wo du abschreiben sollst statt neu zu erfinden

- **FIFO nicht nachbauen**: ruf `engine.matching.bilde_legs()` auf einem
  eingeschränkten Ausführungspool auf, wie im Vertrag beschrieben.
- **Baumuster einer reinen Engine-Funktion über Legs**: `engine/chains.py`,
  `engine/structures.py` — keine DB, keine Uhrzeit, kein Zufall.

## Grenzen

- Kein Eingriff in `engine/matching.py`, `engine/structures.py`,
  `engine/chains.py`.
- Keine Migration, keine Persistenz, keine API, keine Oberfläche.
- Keine mehrstufigen Umleitungs-Kaskaden (Vertrag, „Grenzen").
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_kettensicht.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `engine/kettensicht.py`.
