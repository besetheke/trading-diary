---
titel: OA-Strategie und -Status in API und UI
modell: guenstig
status: fertig
abhaengig_von: AP-13wk
---

# AP-13x · OA-Strategie und -Status anzeigen

Direktes Umsetzungspaket, kein separates Vorbereitungspaket — reines
Durchreichen bereits berechneter/persistierter Werte, keine neue
Berechnung, also kein Regel-8-Test nötig (gleiches Muster wie AP-08fp).
**Tests, die es schon gibt, bleiben unverändert**, dies ergänzt nur
API-Antwortmodelle und UI-Darstellung.

## Worum es geht

`oa_strategie`/`oa_status`/`oa_erkennung` werden seit AP-13wk an Kette
und Struktur geschrieben, aber nirgends angezeigt — weder über die API
noch in der Oberfläche. Dieses Paket macht sie sichtbar, nach demselben
Muster wie AP-08fp (Preise).

## Zu bauen

### `api/app.py`

- `StrukturAntwort`/`KetteAntwort`: je drei neue Felder,
  `oa_strategie: str | None`, `oa_status: str | None`,
  `oa_erkennung: str | None`.
- `_struktur_als_dict()`: direkt aus der Zeile durchreichen
  (`s["oa_strategie"]` usw. — keine Berechnung).
- `_kette_als_dict()`: ebenso aus der Kettenzeile (`k["oa_strategie"]`
  usw.) — die Kette trägt diese Spalten bereits (AP-13w-Migration), sie
  müssen **nicht** über `_ketten_zuschuesse()` aus den Gliedern
  hergeleitet werden.

### `ui/src/api.ts`

- `Kette`- und `Struktur`-Interface: dieselben drei Felder,
  `string | null`.

### `ui/src/Positionen.tsx`

- Eine neue Spalte **„OA-Strategie"** zwischen „Endzustand" und „Preis
  auf" — Zelleninhalt `kette.oa_strategie ?? '—'`. Status/Erkennung
  bleiben der Detailansicht vorbehalten (Listenzeile nicht überladen).

### `ui/src/PositionDetail.tsx`

- In der Strukturkarte, nach „Erkennung" (der bestehenden,
  Brokerdaten-Erkennung): **„OA-Strategie"**, **„OA-Status"** — je
  `?? '—'`.
- **„OA-Erkennung"**, falls gesetzt, als kleiner Hinweis neben dem
  Status (z. B. `title`-Attribut „automatisch" bei `auto`, „unsicher,
  Fingerabdruck weicht ab" bei `heuristik`) — Regel 7: eine automatisch
  erzeugte Verknüpfung bleibt als solche erkennbar, nicht als stille
  Tatsache serviert. Kein eigenes UI-Element nötig, ein Tooltip reicht.

## Wo du abschreiben sollst statt neu zu erfinden

- **Exakt dasselbe Muster**: `git show <AP-08fp-Commit>` (Preise in
  Liste/Detail) — Durchreichen ohne Berechnung, `?? '—'` für leer,
  keine Kürzung nötig (Text, keine Zahl).

## Grenzen

- Keine Interpretation der Werte (kein Mapping `oa_status` → eigener
  Endzustand) — reine Anzeige, wie bisher in der Persistenz festgelegt.
- Keine Filterung/Sortierung nach den neuen Feldern.
- Kein Eingriff in `journal/oa_persistenz.py`, `journal/rebuild.py`,
  `engine/*`.

## Abnahme

- `ruff check .` sauber, `npm run build` (inkl. `tsc --noEmit`) läuft
  durch, Python-Suite unverändert grün.
- Ansicht mit erfundenen Daten geprüft (`tests/fixtures_rebuild.py`-Bestand
  reicht; OA-Felder bleiben dort `—`, da keine OA-Trades importiert —
  zusätzlich mit einem OA-Trade aus `tests/test_rebuild_oa.py`-Muster
  gegenprüfen, dass „SPX: IC" o. Ä. tatsächlich erscheint).
- `git diff --stat` zeigt ausschließlich `api/app.py`, `ui/src/api.ts`,
  `ui/src/Positionen.tsx`, `ui/src/PositionDetail.tsx`.
