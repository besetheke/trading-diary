---
titel: Abnahmebasis für die Sichtbarkeit offener Campaign-Kandidaten
modell: stark
status: fertig
abhaengig_von: AP-05k
aendert_tests: ja
---

# AP-05s · Abnahmebasis für die Sichtbarkeit offener Campaign-Kandidaten

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-05sk (günstiges Modell).

Fachliche Grundlage: `auftraege/AP-05.md`, Abnahme — „Unklassifizierte
Kandidaten bleiben sichtbar; sie werden nicht still als `independent`
einsortiert." `engine.campaigns.campaign_kandidaten()` (AP-05k, fertig)
liefert die Kandidaten bereits berechnet; dieses Paket zählt, wie viele
davon noch **keine** gemeinsame Kampagnen-Klassifikation haben, und macht
das in `journal rebuild`/der CLI sichtbar — genau der erste, risikoarme
Ausschnitt von AP-05 (Sichtbarkeit), nicht die vollständige
Klassifikations-Persistenz (die zweite Hälfte, siehe „Ausdrücklich nicht
Teil dieses Pakets").

## Ausdrücklich nicht Teil dieses Pakets

**Das Schreiben einer Klassifikation** (Bestätigung oder Ablehnung eines
Kandidaten) — dafür ist offen, wie eine **Ablehnung** persistiert wird
(`OFFENE_FRAGEN.md`, OF-54). Dieses Paket liest nur, was `campaign_links`
bereits enthält, unabhängig davon, wie diese Zeilen dort hingekommen sind
— es trifft keine eigene Annahme über den künftigen Schreibweg und ist
davon unabhängig testbar.

## Worum es geht

Ein Kandidat (`CampaignKandidat` mit `kette_a`/`kette_b`) gilt als
**entschieden**, wenn beide Ketten bereits derselben `campaign_id`
zugeordnet sind (`campaign_links`) — unabhängig vom `beziehungstyp`. Sonst
gilt er als **offen**.

## Zu bauen

### `journal/campaigns_sicht.py`

```python
def offene_kandidaten_zaehlen(
    kandidaten: Iterable[CampaignKandidat],
    kampagnen_je_chain_id: Mapping[int, set[int]],
    chain_id_je_objekt: Mapping[int, int],  # id(Chain) -> chain_id
) -> int
```

Reine Funktion (Regel 6): kein DB-Zugriff. Für jeden Kandidaten: die
`chain_id` beider Ketten über `chain_id_je_objekt` (Python-Objektidentität,
wie in `journal.oa_persistenz` — dasselbe Muster, gleicher Grund:
`z.chain`/`kandidat.kette_a`/`kandidat.kette_b` sind dieselben Objekte,
die auch in `kette_je_schluessel` stehen, keine Kopien) auflösen, dann die
Mengen ihrer Kampagnen (`kampagnen_je_chain_id`) schneiden — nicht leer
heißt entschieden, sonst offen. Fehlt eine Kette in `chain_id_je_objekt`
(sollte nicht vorkommen), zählt sie als „keine Kampagne" — offen, nicht
Abbruch.

### `journal/rebuild.py`

- Import `engine.campaigns.campaign_kandidaten` und `journal.campaigns_sicht.
  offene_kandidaten_zaehlen`; `campaign_links`-Tabelle aus `journal.schema`
  importieren.
- Nach `_offene_kandidaten()` (Rollkandidaten), vor dem `return
  RebuildErgebnis(...)`: `campaign_links` lesen und zu
  `kampagnen_je_chain_id: dict[int, set[int]]` gruppieren (Schlüssel
  `chain_id`, Wert die Menge ihrer `campaign_id`s); `chain_id_je_objekt`
  aus `kette_je_schluessel` und `ketten_id_je_schluessel` bilden (wie in
  `journal.oa_persistenz.oa_werte_schreiben()`); `campaign_kandidaten
  (kette_je_schluessel.values())` aufrufen; `offene_kandidaten_zaehlen()`
  aufrufen.
- `RebuildErgebnis` um `campaign_kandidaten_offen: int = 0` erweitern
  (wie `kandidaten_offen`, nicht persistiert, jeder Lauf neu berechnet).
- `journal/cli.py`, `rebuild`-Zweig: Summenzeile um
  `{ergebnis.campaign_kandidaten_offen} offene Campaign-Kandidaten`
  ergänzen (Muster: `kandidaten_offen`).

## Wo du abschreiben sollst statt neu zu erfinden

- **Zählfeld, das nicht persistiert wird**: `RebuildErgebnis.kandidaten_offen`,
  `_offene_kandidaten()`.
- **Objektidentität statt Naturschlüssel-Neuberechnung**:
  `journal/oa_persistenz.py`, `oa_werte_schreiben()`.
- **CLI-Summenzeile erweitern**: `journal/cli.py`, bestehender
  `rebuild`-Zweig.

## Grenzen

- Kein Eingriff in `engine/campaigns.py`, `engine/chains.py`,
  `engine/structures.py`, `journal/schema.py`, `migrations/` — keine
  Schemaänderung, dieses Paket schreibt nichts.
- Kein Klassifikations-Dialog, kein Schreiben von `campaigns`/
  `campaign_links` — reine Anzeige (siehe „Ausdrücklich nicht Teil dieses
  Pakets").
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_campaigns_sicht.py` läuft vollständig grün, alle übrigen
  Tests bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt `journal/campaigns_sicht.py` (neu),
  `journal/rebuild.py`, `journal/cli.py`.
