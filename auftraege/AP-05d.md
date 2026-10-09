---
titel: Abnahmebasis Klassifikation der Campaign-Kandidaten (AP-05, Teil 2)
modell: stark
status: fertig
abhaengig_von: AP-05r, AP-05rk, AP-05sk
aendert_tests: ja
---

# AP-05d · Abnahmebasis: Klassifikation über eine Datei-Rundreise

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die
Umsetzung ist AP-05dk (günstiges Modell). Neue Testdatei
`tests/test_kampagnen_durchsicht.py` (26 Tests), keine bestehende Erwartung
wird geändert. Vorbild ist die Rollkandidaten-Durchsicht
(`journal/durchsicht.py`, AP-04d); gleiche Bauart, gleiche Sicherungen.

Plan AP-05: „Vorschläge werden nie automatisch übernommen. Eine getroffene
Klassifikation überlebt `rebuild`. Unklassifizierte Kandidaten sind sichtbar
und arbeitbar." Entscheidungen: `OFFENE_FRAGEN.md`, OF-54 und OF-71.

## Bausteine

1. **Migration + Tabelle `campaign_ablehnungen`** (Regel 3: nur über Alembic,
   neue Revision mit `down_revision = 'e5f2b8c4d7a1'`; Tabelle auch in
   `journal/schema.py`). Spalten: `chain_id_a`, `chain_id_b` (beide
   Fremdschlüssel auf `chains.chain_id`), `typ` (`ic` | `financing`, CHECK) —
   zusammen Primärschlüssel —, `notiz` (Text, null), `erstellt_am`
   (DateTime, nicht null). `chain_id_a` ist die früher eröffnete bzw. bei
   `financing` die Bestandskette (wie `CampaignKandidat.kette_a`). Die IDs
   sind **Kontosicht**-Ketten.
2. **`journal/kampagnen_durchsicht.py`** (neu): `kampagnen_ausschreiben(db_pfad,
   ziel)` → `KampagnenAusschreibErgebnis(gruppen, kandidaten)` und
   `kampagnen_urteile_einlesen(db_pfad, quelle, *, ueberschreiben=False,
   jetzt=None)` → `KampagnenEinleseErgebnis(neu_bestaetigt, neu_abgelehnt,
   kampagnen_neu, verknuepfungen_neu, unveraendert, geaendert,
   unentschieden)`.
3. **`journal/rebuild.py`** (Erweiterungen) und **`journal/campaigns_sicht.py`**.
4. **`journal/cli.py`**: `kampagnen-ausschreiben DATEI [--db]` und
   `kampagnen-einlesen DATEI [--ueberschreiben] [--db]`.

## Ausschreiben

- Quelle der Kandidaten: `bestand_berechnen` + `engine.campaigns`
  (`campaign_kandidaten`) — kein zweiter Lesepfad. Ketten werden über ihren
  Naturschlüssel (`_kette_schluessel`) auf die **Kontosicht**-Zeilen in
  `chains` abgebildet (`sicht = 'konto'` ausdrücklich filtern, nie eine andere
  Sicht). Fehlt eine Zeile: `ValueError` mit Hinweis auf `journal rebuild`.
- Nur **offene** Kandidaten: nicht, wenn beide Ketten eine gemeinsame
  Kampagne haben, und nicht, wenn das Paar (`chain_id_a`, `chain_id_b`, Typ)
  in `campaign_ablehnungen` steht.
- Gruppen nach `kette_a`; innerhalb einer Gruppe `financing` vor `ic`;
  `financing` nach Abstand aufsteigend, `ic` nach Überlappung absteigend
  (unbegrenzt = `None` zuerst), bei Gleichstand nach Schlüssel Kette B.
  Gruppen nummeriert nach dem ersten Auftreten.
- XLSX, Blätter `Kandidaten` und `Anleitung`; Kopf (21 Spalten, feste Reihenfolge)
  siehe `KOPF` in den Tests. `Kette A/B: beendet` leer, wenn offen;
  `Abstand Minuten` ganzzahlig gerundet; `Überlappung Tage` auf zwei Stellen
  gerundet, leer = unbegrenzt. `Typ Kette A`/`Typ Kette B` **vorbelegt**:
  `ic` → beide `ic_leg`; `financing` → A `ic_leg`, B `financing` (Annahme, in
  OF-71 festgehalten; vom Nutzer änderbar). `Entscheidung`, `Bemerkung` leer.
- Schutz wie bei den Rollkandidaten: vorhandene Zieldatei → `FileExistsError`;
  Ziel im Projektverzeichnis außerhalb von `fixtures/golden/` → `ValueError`
  (Wort „Projektverzeichnis" in der Meldung).

## Einlesen (alles prüfen, dann in einer kurzen Transaktion schreiben)

- `Entscheidung`: `ja`/`j` bestätigt, `nein`/`n` lehnt ab, leer =
  unentschieden; alles andere (auch Wahrheitswerte, Zahlen) → `ValueError`
  (Meldung enthält „Entscheidung"). Unbekannter Schlüssel → `ValueError`
  (enthält „Schlüssel").
- **Bestätigung** (nur Typen `ic_leg`, `financing`, `contract_roll`,
  `independent`, sonst `ValueError` mit „Typ"): beide Ketten müssen denselben
  Basiswert haben.
  - Keine der beiden Ketten in einer Kampagne → neue `campaigns`-Zeile,
    beide Ketten verknüpfen.
  - Genau eine in einer Kampagne → die andere kommt in diese Kampagne.
    Das gilt auch **innerhalb derselben Datei** (zwei Zeilen mit einer
    gemeinsamen Kette ergeben eine Kampagne).
  - Beide in derselben Kampagne mit denselben Typen → `unveraendert`.
  - Beide in **zwei verschiedenen** Kampagnen (auch aus der Datei) →
    `ValueError` („Kampagnen"), nichts wird zusammengeführt oder geschrieben.
  - Hat eine Kette in der Kampagne schon einen anderen Typ: aus der Datei
    selbst → `ValueError` („Typ"); aus der Datenbank → `ValueError`, mit
    `ueberschreiben=True` wird der Typ geändert (`geaendert`).
  - `campaign_links`: `erkennung = 'manuell'`, `bestaetigt_am = jetzt`.
    `campaigns.underlying`, `eroeffnet_am` (früheste Eröffnung der Ketten) und
    `beendet_am` (leer, solange eine Kette offen ist, sonst die späteste
    Schließung) werden aus den Ketten (Kontosicht) gesetzt.
- **Ablehnung:** Zeile in `campaign_ablehnungen`. Steht das Paar schon in
  derselben Kampagne → `ValueError` („Kampagne"); keine Ablehnung löscht je
  eine Verknüpfung.
- **Widerspruch zu früher:** Bestätigung eines gespeicherten abgelehnten
  Paares → `ValueError` („widerspricht"); mit `ueberschreiben=True` wird die
  Ablehnung gelöscht und bestätigt (`geaendert`). Dasselbe Paar in einer
  Datei erst `nein`, dann `ja` → immer `ValueError`.
- Bricht irgendetwas ab, steht danach nichts Neues in der Datenbank.
- Zweites Einlesen derselben Datei ändert nichts (`bestaetigt_am` bleibt).

## Rebuild

- **Ketten mit Klassifikation werden nie gelöscht** (Regel 4): Die Ketten in
  `campaign_links` und in `campaign_ablehnungen` zählen wie die der
  Overrides zu den gesicherten (Fremdschlüssel!). Ohne das bräche der
  Rebuild ab, sobald eine klassifizierte Kette verschwindet.
- **Kampagnen-Zeiten nachziehen:** `underlying`, `eroeffnet_am`, `beendet_am`
  jeder Kampagne werden bei jedem Rebuild aus ihren Ketten neu bestimmt
  (wie oben). `netto_pnl_eur` bleibt unberührt.
- **`campaign_kandidaten_offen`** zählt abgelehnte Paare nicht mit:
  `offene_kandidaten_zaehlen(..., abgelehnt=())` bekommt einen optionalen
  Parameter (Standard leer, die bestehenden Tests bleiben unverändert grün):
  Menge von Tripeln (`chain_id_a`, `chain_id_b`, Typ).

## Ausdrücklich nicht Teil dieses Pakets

Übersetzung der Klassifikation in die Kettensicht (wie bei den Overrides erst
bei Bedarf der Auswertung „Wirkung der Gegenfinanzierung", AP-06), die
Kampagnen-Kennzahlen, ein Dialog in der Oberfläche (AP-08).

## Abnahme

`tests/test_kampagnen_durchsicht.py` grün, alle bisherigen Tests unverändert
grün, `ruff check .` sauber, `alembic upgrade head` auf einer leeren
Datenbank. Gegen eine Wegwerf-Umsetzung geprüft: 26 von 26 grün, die
benachbarten Rebuild-, Durchsicht- und Kampagnen-Tests (104) ebenso; ohne
Umsetzung ist die Datei rot (ImportError).
