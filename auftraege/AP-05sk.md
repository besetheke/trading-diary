---
titel: Sichtbarkeit offener Campaign-Kandidaten (journal/campaigns_sicht.py)
modell: guenstig
status: offen
abhaengig_von: AP-05s
---

# AP-05sk · Sichtbarkeit offener Campaign-Kandidaten

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-05s). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag in `auftraege/AP-05s.md`, Abschnitt „Zu bauen"
— er ist verbindlich, kein Implementierungsdetail zur freien Wahl.

## Worum es geht

`engine.campaigns.campaign_kandidaten()` (AP-05k) rechnet bereits alles im
Speicher. Dieses Paket zählt, wie viele Kandidaten noch keine gemeinsame
Kampagne haben, und macht die Zahl in `journal rebuild`/der CLI sichtbar
— reine Anzeige, kein Schreiben.

## Zu bauen

- `journal/campaigns_sicht.py`, Funktion `offene_kandidaten_zaehlen()` —
  exakt nach Vertrag.
- Wiring in `journal/rebuild.py`: Aufruf in `_rebuild_laufen()`, ein
  neues Zählfeld in `RebuildErgebnis`.
- `journal/cli.py`: die Summenzeile des `rebuild`-Befehls ergänzen.

## Wo du abschreiben sollst statt neu zu erfinden

- **Baumuster einer reinen Zählfunktion über Kandidaten**:
  `journal/rebuild.py`, `_offene_kandidaten()`.
- **Objektidentität statt Naturschlüssel-Neuberechnung**:
  `journal/oa_persistenz.py`, `oa_werte_schreiben()` — genau dasselbe
  Muster (`{id(v): k for k, v in ...}`), hier nur zum Lesen statt
  Schreiben.
- **CLI-Summenzeile erweitern**: `journal/cli.py`, der bestehende
  `rebuild`-Zweig, Zeile mit `kandidaten_offen`/`oa_zugeordnet`.

## Grenzen

- Kein Eingriff in `engine/campaigns.py`, `engine/chains.py`,
  `engine/structures.py`, `journal/schema.py`, `migrations/`.
- Kein Klassifikations-Dialog, kein Schreiben von `campaigns`/
  `campaign_links`.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_campaigns_sicht.py` läuft vollständig grün, alle übrigen
  Tests bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `journal/campaigns_sicht.py`
  (neu), `journal/rebuild.py`, `journal/cli.py`.
