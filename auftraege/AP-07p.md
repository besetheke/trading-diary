---
titel: Praemien an Struktur und Kette, eine Rechnung statt drei
modell: guenstig
status: offen
abhaengig_von: AP-07pv
---

# AP-07p · Prämien an Struktur und Kette

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-07pv). **Tests, Fixtures und Migration sind tabu** — fällt ein Test,
ist der Code falsch.

Maßgeblich ist der Vertrag P1–P8 in `auftraege/AP-07pv.md`, samt dem
Abschnitt „Die drei Entscheidungen, die nicht beim Umsetzer liegen".

## Worum es geht

Die Positionsliste zeigt kein Wort davon, zu welchem Preis eröffnet und
geschlossen wurde. Die Größe existiert aber schon **zweimal** im Code —
in `journal/durchsicht.py` und in einem Abgleichswerkzeug. Dieses Paket
macht daraus **eine** Rechnung, speichert das Ergebnis an der Struktur und
reicht es durch die Lese-API.

## Zu bauen

1. `journal/preise.py` — die Berechnung, einmal (P1–P3).
2. `journal/rebuild.py` — schreibt `eroeffnungspreis` und `schlusspreis` in
   die beiden Spalten, die die Migration bereits angelegt hat.
3. `journal/durchsicht.py` — gibt seine eigene Fassung auf und ruft die
   gemeinsame Funktion.
4. `api/app.py` — die zwei Felder an Struktur und Kette (P7, P8).

## Wo du abschreiben sollst statt neu zu erfinden

- **Die Rechnung selbst** steht heute in `journal/durchsicht.py` als
  `_nettopraemie()` — sie ist richtig und geprüft. Verschiebe sie, statt
  sie neu zu schreiben, und passe nur die Rundung nach P3 an.
- **Das Schreiben der Spalten**: `_struktur_zeile()` in
  `journal/rebuild.py` füllt bereits `netto_pnl` und `waehrung` aus Legs
  und Ausführungen (AP-04v, Vertrag 10a/11) — dieselbe Stelle, dieselben
  Daten.
- **Das Durchreichen in der API**: die vorhandenen Geldfelder der Struktur
  zeigen, wie ein `Decimal` zur Zeichenkette wird (`_als_text`).

## Die drei Stellen, an denen erfahrungsgemäß geraten wird

1. **Leg-Menge, nicht Ausführungsmenge** (P1). Eine Ausführung kann mehrere
   Legs bedienen; wer ihre Menge nimmt, zählt doppelt. Genau daran ist
   schon einmal etwas zerbrochen (AP-04pk).
2. **Offen bleibt leer** (P2). Eine offene Struktur bekommt keinen
   Schlusspreis von `0` — das sähe aus wie ein Rückkauf zum Nulltarif und
   wäre in der Liste nicht von einem echten Nullpreis zu unterscheiden.
3. **Die Schreibweise ist festgelegt** (P3): acht Stellen runden, dann
   überzählige Nullen weg, aber **mindestens zwei** behalten. `40` wird zu
   `40.00`, nicht zu `40`; `26/3` zu `8.66666667`. Die Tests prüfen die
   Zeichenkette, nicht den Zahlenwert.

## Grenzen

- **Kein Eingriff in `engine/`** und keine neue Migration — beides steht
  bereits.
- **`werkzeuge/abgleich/` nicht anfassen und nicht ausführen** (Regel 2).
  Dass dort eine dritte Kopie der Rechnung liegt, ist bekannt; sie zieht
  das starke Modell nach.
- Keine Darstellung in der Oberfläche, keine Kennzahl, keine Umrechnung.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf temporären Datenbanken.

## Abnahme

- Die neun neuen Tests (fünf in `tests/test_rebuild.py`, vier in
  `tests/test_api_lesen.py`) sind grün, die gesamte Suite ebenfalls.
- `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `journal/preise.py`,
  `journal/rebuild.py`, `journal/durchsicht.py`, `api/app.py` und
  `OFFENE_FRAGEN.md`.
