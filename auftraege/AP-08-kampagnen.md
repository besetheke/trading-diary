---
titel: Kampagnenansicht — Umsetzung (API + Oberfläche)
modell: guenstig
status: offen
abhaengig_von: AP-07l, AP-08l
aendert_tests: nein
---

# AP-08-kampagnen · Kampagnenansicht

Abnahmebasis (vom starken Modell, bereits eingecheckt): `tests/test_api_kampagnen.py`
— unveränderlich (Regel 1). Lies die Datei vollständig, sie ist der Vertrag.

## Worum es geht

Bestätigte Kampagnen (`campaigns`/`campaign_links`) sind bisher nur über die
CLI-Dateirundreise sichtbar. Dieses Paket macht sie **rein lesend** über die
API und eine neue Oberflächen-Seite sichtbar — genau wie AP-07l/AP-08l das für
Ketten gemacht haben. **Keine Neuberechnung der Kandidaten**: offene
(unbestätigte) Kandidaten bleiben bei der Datei-Rundreise (Plan, AP-08-Umfang,
Auflage zu AP-07l) — diese Ansicht zeigt nur, was bereits in den Tabellen
steht.

## Zu ändern

**Nur `api/app.py`:**

- `GET /kampagnen`: Liste aller `campaigns`-Zeilen, je mit
  `campaign_id, underlying, eroeffnet_am, beendet_am, netto_pnl_eur` (als
  Zeichenkette wie bei `/ketten`, Regel 5/13) und `anzahl_ketten`
  (Anzahl zugehöriger `campaign_links`). Optionaler Filter `underlying`.
  Antwortform `{"treffer": [...], "gesamt": N}`, sortiert nach
  `eroeffnet_am` absteigend (wie `/ketten`).
- `GET /kampagnen/{campaign_id}`: wie oben, zusätzlich `ketten`: Liste je
  verknüpfter Kette mit `chain_id, natur_schluessel, beziehungstyp,
  erkennung, bestaetigt_am`. Unbekannte `campaign_id` → 404. Nicht-numerische
  `campaign_id` → 422 (wie bestehende Routen mit `int`-Pfadparameter).
- Beide Routen vor der Rückfall-Route der Oberfläche einhängen (wie alle
  bisherigen API-Routen).
- Pydantic-v2-Modelle nach dem Muster der `/ketten`-Antwortmodelle.
- Rein lesend — keine Transaktion, kein Schreiben.

**Neu `ui/src/Kampagnen.tsx`:**

- Liste aller Kampagnen (Tabelle: Eröffnung, Basiswert, Ende, Ergebnis netto
  EUR, Anzahl Ketten), Filter nach Basiswert — Vorbild `Positionen.tsx`
  (ohne Sortierung/Spaltenwahl, das ist für dieses Paket kein Vertrag).
- Klick auf eine Zeile → Detailansicht (kann dieselbe Seite mit
  aufgeklapptem Bereich sein oder eine Unterseite `/kampagnen/:campaignId`)
  zeigt die verknüpften Ketten mit `beziehungstyp`/`erkennung` und einen
  Verweis auf `/positionen/:chainId`.
- Route `/kampagnen` in `ui/src/main.tsx` eintragen, Navigationslink
  „Kampagnen" neben „Positionen"/„Kalender". **Nicht** `/kampagnen` für die
  Oberflächenseite verwenden, falls das mit dem API-Pfad kollidiert — prüfe
  wie AP-08j2 das für den Kalender gelöst hat (API behält `/kampagnen`,
  die Seite bekommt bei Bedarf einen anderen Pfad, z. B. `/kampagnenliste`).
- `npm run build` danach, `ui/dist` aktuell halten.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, `journal/rebuild.py`,
`engine/campaigns.py`. Keine Berechnung offener Kandidaten. Kein Schreiben
(keine Bestätigung/Ablehnung aus der Oberfläche — das ist ein separates,
noch nicht beauftragtes Korrektur-Dialog-Paket).

**Hinweis zur Abstimmung mit paralleler Arbeit:** `api/app.py` wird zur
selben Zeit auch für die Equity-Kurve (AP-06, separates Paket) erweitert.
Bitte zuerst committen und kurz Bescheid geben, bevor an `api/app.py`
weitergearbeitet wird, um einen Merge-Konflikt zu vermeiden.

## Abnahme

`tests/test_api_kampagnen.py` grün, Gesamtsuite grün, `ruff check .` sauber,
`npm run build` fehlerfrei. `git diff --stat` ohne `tests/`/`fixtures/`.
