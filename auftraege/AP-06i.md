---
titel: Ergebnis loser Legs in Equity und Kapital (OF-78, Teil 1)
modell: guenstig
status: offen
abhaengig_von: AP-06e, AP-06g, AP-08f2
aendert_tests: nein
---

# AP-06i · Lose Legs ins Geld

Korrektur nach OF-78. Die Abnahmebasis hat das starke Modell bereits gelegt
(eigener Commit): `tests/test_equity_lose_legs.py` (6 Tests, reine Funktion)
und `tests/test_api_equity_lose_legs.py` (3 Tests, über Rebuild und API).
Beide sind **unveränderlich**; sie sind derzeit rot.

## Hintergrund

Im Echtbestand bleiben 185 abgeschlossene Aktien-Legs der Kontosicht ohne
Struktur (`legs.structure_id IS NULL`), meist Aktien aus Zuteilung oder
Ausübung, die die Kettenbildung nicht fortsetzen konnte. Die Equity-Kurve
summiert nur Strukturen — deren Ergebnis (rund −64.000 €) fehlt in jeder
Geldsumme. Das Geld muss vollständig sein, unabhängig davon, ob die
Kettenbildung das Leg einordnen kann (die Kettenbildung selbst ist ein
eigenes, späteres Paket des starken Modells).

## Entscheidungen

- **I1 Loses Leg** = Leg der Kontosicht mit `structure_id is None` und
  gesetzter `close_exec_id`. Offene lose Legs gehen nirgends ein.
- **I2 Betrag und Tag:** Betrag nach derselben Formel wie Strukturen,
  `analytics.kennzahlen._wirtschaftlich([leg], exec_je_id, mult_je_conid)` —
  keine zweite EUR-Rechnung. Vorher wie in `kennzahlen_auswertung`
  `bewerte_barausgleich` anwenden. Tag = Datum der `handelszeit` der
  schließenden Ausführung. `None` (Kurs fehlt) zählt als Mangel des Tages
  in `anzahl_lose_legs_kurs_fehlt`, nicht als 0 und nie still.
- **I3 Felder:**
  - `EquityTag`: neu `anzahl_lose_legs: int = 0`,
    `anzahl_lose_legs_kurs_fehlt: int = 0` (am Ende, mit Vorgabe — die
    bestehenden Tests bauen `EquityTag` ohne sie). `netto_eur` enthält Strukturen
    **und** lose Legs; `anzahl_strukturen` zählt weiter nur Strukturen.
  - `EquityMonat`: neu `lose_legs_eur: Decimal = Decimal("0.00")`,
    `anzahl_lose_legs: int = 0`, `anzahl_lose_legs_kurs_fehlt: int = 0`.
    `summe_netto_eur` enthält die losen Legs; `durchschnitt_netto_eur` und
    `trefferquote` bleiben Kennzahlen **nur über Strukturen** (Durchschnitt =
    Strukturanteil / `anzahl_strukturen`).
  - Ein Tag oder Monat entsteht auch, wenn nur lose Legs (oder nur ihr
    Mangel) beitragen.
- **I4 Qualitätsstufe:** Mit `nur_qualitaetsstufe_a` fällt ein loses Leg
  weg, wenn eine seiner beiden Ausführungen schlechter als A ist (wie
  `_qualitaetsstufe`: Minimum über die beteiligten Ausführungen).
- **I5 Zeitraum:** wie bei Strukturen (Tag der Schließung im Zeitraum).
- **I6 CSV unverändert** (`als_csv`: keine neue Spalte — `netto_eur` enthält
  die losen Legs bereits).
- **I7 API:** `EquityTagAntwort` und `EquityMonatAntwort` in `api/app.py` um
  die neuen Felder erweitern (Geld als Text über `_als_text`). Die oberste
  Ebene der Antwort bleibt unverändert (ein bestehender Test vergleicht sie
  vollständig). `GET /kapital` übernimmt die Equity-Tage bereits — dort ist
  nichts zu ändern; der Test prüft das nur.

## Umfang

Nur `analytics/equity.py` und `api/app.py`. `equity_bericht` liest die Legs
schon ohne Filter auf `structure_id`; es reicht, sie in `equity_auswertung`
auszuwerten.

## Ausdrücklich nicht Teil dieses Pakets

- Kettenbildung (`engine/chains.py`): warum die Legs lose bleiben — starkes
  Modell, später.
- Kalender, Tagesansicht, Kennzahlen je Kette, Oberfläche.
- Keine Änderung unter `tests/`, `fixtures/`, `engine/`, `ui/`.

## Abnahme

Die 9 neuen Tests grün, Gesamtsuite grün, `ruff check .` sauber,
`git diff --stat` nur `analytics/equity.py`, `api/app.py` und dieses
Auftragsdokument (Status). Vor Beginn und vor dem Commit
`git pull --ff-only`. Den Echtabgleich gegen IB (je Jahr) macht danach das
starke Modell.
