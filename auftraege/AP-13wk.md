---
titel: Persistenz des OA-Abgleichs (journal/oa_persistenz.py)
modell: guenstig
status: fertig
abhaengig_von: AP-13w
---

# AP-13wk · Persistenz des OA-Abgleichs

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-13w: Migration und Schema sind bereits committet, Tests liegen in
`tests/test_rebuild_oa.py`). **Tests und Fixtures sind tabu** — fällt ein
Test, ist der Code falsch.

Maßgeblich ist der Vertrag in `auftraege/AP-13w.md`, Abschnitt „Zu bauen"
— er ist verbindlich, kein Implementierungsdetail zur freien Wahl.

## Worum es geht

`engine.oa_abgleich.oa_abgleich()` (AP-13k) rechnet bereits alles im
Speicher. Dieses Paket schreibt das Ergebnis in `chains`/`structures` und
bindet es in `journal rebuild` ein.

## Zu bauen

- `journal/oa_persistenz.py`, Funktion `oa_werte_schreiben()` — exakt
  nach Vertrag.
- Wiring in `journal/rebuild.py`: Baseline in `_struktur_zeile()`/
  `_kette_zeile()`, Aufruf in `_rebuild_laufen()`, zwei neue Zählfelder
  in `RebuildErgebnis`.
- `journal/cli.py`: die Summenzeile des `rebuild`-Befehls ergänzen.

## Wo du abschreiben sollst statt neu zu erfinden

- **Baumuster einer DB-schreibenden Anbindung**: `journal/rebuild.py`
  selbst — wie `_struktur_zeile()`/`_kette_zeile()` Werte zurückgeben und
  wie `update(...)`-Aufrufe an anderer Stelle in `_rebuild_laufen()`
  aussehen (z. B. `_overrides_anwenden()`).
- **Zählfeld, das nicht persistiert wird**: `RebuildErgebnis.kandidaten_offen`.
- **CLI-Summenzeile erweitern**: `journal/cli.py`, der bestehende
  `rebuild`-Zweig, Zeile mit `kandidaten_offen`.

## Grenzen

- Kein Eingriff in `engine/oa_abgleich.py`, `engine/chains.py`,
  `engine/structures.py`, `migrations/`, `journal/schema.py`.
- Keine API-, keine Oberflächenänderung.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_rebuild_oa.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `journal/oa_persistenz.py`
  (neu), `journal/rebuild.py`, `journal/cli.py`.
