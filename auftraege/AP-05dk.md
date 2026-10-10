---
titel: Klassifikation der Campaign-Kandidaten — Umsetzung (AP-05, Teil 2)
modell: guenstig
status: fertig
abhaengig_von: AP-05d
aendert_tests: nein
---

# AP-05dk · Umsetzung gegen die Abnahmebasis AP-05d

Vertrag und Regeln: `auftraege/AP-05d.md` (lies ihn vollständig). Maßgeblich
sind die Tests in `tests/test_kampagnen_durchsicht.py` (unveränderlich,
Regel 1).

## Zu bauen

1. **Migration + Tabelle** `campaign_ablehnungen` (Alembic-Revision mit
   `down_revision = 'e5f2b8c4d7a1'`, Tabelle in `journal/schema.py`).
   Keine bestehende Migration ändern (Regel 3).
2. **`journal/kampagnen_durchsicht.py`** nach dem Vorbild von
   `journal/durchsicht.py` (Aufbau, Schutz der Zieldatei, „erst prüfen, dann in
   einer kurzen Transaktion schreiben", Abbruch ohne Teilzustand). Lesen und
   Rechnen über `bestand_berechnen` und `engine.campaigns.campaign_kandidaten`.
   **Alle Nachschlagen in `chains` filtern ausdrücklich auf `sicht = 'konto'`.**
3. **`journal/rebuild.py`:** Ketten aus `campaign_links` und
   `campaign_ablehnungen` zu den gesicherten Ketten (neben den Overrides);
   Kampagnen-Zeiten nachziehen; abgelehnte Paare an
   `offene_kandidaten_zaehlen` übergeben. **`journal/campaigns_sicht.py`:**
   optionaler Parameter `abgelehnt` (Standard leer).
4. **`journal/cli.py`:** `kampagnen-ausschreiben` und `kampagnen-einlesen`
   (Ausgabeformate wie in den Tests: „Ausgeschrieben nach …: N Gruppen, M
   Kandidaten"; „Einlesen …: N neu bestätigt, …"; Fehler „Ausschreiben
   fehlgeschlagen:" / „Einlesen fehlgeschlagen:" auf stderr, Rückgabe 1).

## Bei der Gelegenheit (kleine Härtung, kein Verhaltenswechsel)

`journal/durchsicht.py` schlägt Naturschlüssel in `structures` und `chains`
ohne Sichtfilter nach; es funktioniert nur, weil die Zeilen zufällig in der
passenden Reihenfolge zurückkommen. Dort `sicht = 'konto'` ergänzen
(`_gruppen_bilden` und `_urteile_schreiben`). Die bestehenden Tests müssen
unverändert grün bleiben.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`. Datenbank nur lesend,
außer im Einlesen (kurze Transaktion, Regel 9). Decimal, kein float.

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`;
Migration läuft auf einer leeren Datenbank. Den Echtlauf auf einer Kopie von
`journal.db` macht anschließend das starke Modell.
