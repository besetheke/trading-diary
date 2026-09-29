---
titel: OA-Abgleich (engine/oa_abgleich.py)
modell: guenstig
status: fertig
abhaengig_von: AP-13v
---

# AP-13k · OA-Abgleich

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-13v). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag in `auftraege/AP-13v.md`. Lies ihn vollständig,
samt Abschnitt „Ablauf" — der ist verbindlich, kein Implementierungsdetail
zur freien Wahl.

## Worum es geht

Verknüpft importierte OA-Trades mit bereits gebildeten Ketten und
vergleicht das Ergebnis. Reine Funktion, kein Seiteneffekt, keine
Persistenz — die Zuordnung ist ein Nachweis/eine Auswertung, keine
Schreiboperation.

## Zu bauen

Ein einziges neues Modul: `engine/oa_abgleich.py`, mit den Dataclasses
und der Funktion `oa_abgleich()` nach Vertrag.

## Wo du abschreiben sollst statt neu zu erfinden

- **Baumuster**: `engine/campaigns.py`.
- **Auflösung von Leg-Signaturen ohne DB-Zugriff**: `werkzeuge/abgleich/
  golden_oa_abgleich.py`, Funktionen `_eigene_legs()`/`_referenz_legs()`
  — genau das Muster, nur als Produktionscode. Dieses Werkzeug bleibt
  unberührt, keine Abhängigkeit von `werkzeuge/` aus `engine/`.

## Die Stelle, an der erfahrungsgemäß geraten wird

Der Fingerabdruck vergleicht **nur** die Leg-Spezifikation
(Right/Strike/Expiry/Richtung als Menge), nicht die Entry Time — das ist
keine Vereinfachung, sondern eine bereits getroffene, dokumentierte
Entscheidung (`OFFENE_FRAGEN.md`, OF-53). Eine Abweichung im Fingerabdruck
verwirft die Zuordnung nicht — sie bleibt bestehen, nur mit
`erkennung="heuristik"` statt `"auto"`.

## Grenzen

- Kein Eingriff in `engine/chains.py`, `engine/structures.py`,
  `engine/matching.py`, `engine/campaigns.py`.
- Keine Persistenz, keine Migration, keine API, keine Oberfläche — die
  Übernahme von `Strategy`/`Status` in Kette/Struktur (neue Spalten) ist
  ein eigenes, noch nicht geschriebenes Paket.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_oa_abgleich.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `engine/oa_abgleich.py`.
