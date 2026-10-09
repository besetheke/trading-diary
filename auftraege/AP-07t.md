---
titel: Abnahmebasis Tagesübersicht und Kalender der Lese-API
modell: stark
status: fertig
abhaengig_von: AP-07l
aendert_tests: ja
---

# AP-07t · Abnahmebasis: Tagesübersicht und Kalender (AP-07 Rest, zweiter Teil)

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-07tk (günstiges Modell). Neue Testdatei `tests/test_api_tage.py`
(17 Tests), keine bestehende Erwartung wird geändert.

Zweck: Das tägliche Journal braucht pro Handelstag die Frage „was ist heute
passiert?" und einen Monatsüberblick (Plan AP-08: Kalenderansicht). Die
Endpunkte lesen, was `journal rebuild` geschrieben hat; sie rechnen nichts
Neues.

## Entscheidungen (09.10.2026)

- **Nur Kontosicht** (`sicht = 'konto'`, jede Antwort nennt sie), wie die
  übrige Lese-API (OF-36).
- **Nur lesend, immer aktiv** (kein `mit_journal`-Schalter): Das Schema der
  Standard-API bleibt ausschließlich `get`.
- **Aufsummiert wird nur das Nötigste** und nie über Währungen: Das realisierte
  Ergebnis eines Tages ist die Summe der Strukturen, die an diesem Tag
  geschlossen wurden (`structures.geschlossen_am`), **je Währung**. Das ist
  dieselbe Art Ausnahme wie `struktur_summe_netto` je Kette in AP-07l;
  Geld bleibt Zeichenkette ohne stille Rundung (`format(x, "f")`).
- **Was ein „Tag" ist:** das Kalenderdatum der Zeitstempel (naiv, wie in der
  Datenbank), Tagesgrenze 00:00 bis 24:00.

## Endpunkte (verbindlich)

`GET /tage/{datum}` (`datum` = `JJJJ-MM-TT`, sonst 422) → `TagAntwort`:
`datum`, `sicht`, und vier Listen — leer, nie 404:

- `eroeffnet`: Ketten, die an dem Tag eröffnet wurden (`TagKetteAntwort`:
  `chain_id`, `natur_schluessel`, `underlying`, `asset_class`, `seite`,
  `anzahl_rolls`, `endzustand`, `eroeffnet_am`, `beendet_am`), nach
  Eröffnungszeit, dann `chain_id`.
- `beendet`: Ketten, die an dem Tag beendet wurden, nach `beendet_am`, dann
  `chain_id`.
- `rolls`: Kettenglieder vom Typ `roll`, deren Struktur an dem Tag eröffnet
  wurde (`chain_id`, `structure_id`, `underlying`, `sequenz`, `eroeffnet_am`).
- `realisiert`: je Währung (alphabetisch) `waehrung`, `sicht`,
  `anzahl_strukturen`, `brutto`, `kommission`, `netto` der an dem Tag
  geschlossenen Strukturen.

`GET /kalender?monat=JJJJ-MM` (`monat` fehlt oder ist ungültig → 422) →
`KalenderAntwort`: `monat`, `sicht`, `tage` — **nur Tage mit Ereignissen**,
aufsteigend; je Tag `datum`, `eroeffnet`, `beendet`, `rolls` (Anzahlen) und
`realisiert` (je Währung `waehrung`, `sicht`, `netto`).

## Grenzen

Kein Schreiben, keine Kettensicht, keine Kennzahlen (Trefferquote,
Kommissionsanteil), keine Umrechnung nach Euro, keine Journal-Texte (die
liefert AP-07j). Die Rückfall-Route der Oberfläche bleibt die letzte Route.

## Abnahme

`tests/test_api_tage.py` und alle bisherigen API-Tests grün, `ruff check .`
sauber. Gegen eine Wegwerf-Umsetzung geprüft: 50 von 50 grün (33 bestehende,
17 neue); ohne Umsetzung alle 17 rot.
