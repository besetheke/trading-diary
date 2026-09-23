---
titel: Abnahmebasis fuer die Praemien an Struktur und Kette (AP-07p)
modell: stark
status: fertig
abhaengig_von: AP-07l
aendert_tests: ja
---

# AP-07pv · Abnahmebasis für die Prämien

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-07p (günstiges Modell).

## Warum

Die Positionsliste zeigt das Ergebnis, aber nicht den Preis, zu dem
eröffnet und geschlossen wurde (Nutzer, 22.09.2026: „Die Übersichtsliste
hat z. B. keine Preise"). An diesen beiden Zahlen erkennt man einen Vorgang
wieder — und an ihnen unterscheidet man einen Roll von einem
Wiedereinstieg, wofür die Stichprobe dieselben Werte brauchte (OF-41).

**Und es gibt sie schon zweimal.** `journal/durchsicht.py` und
`werkzeuge/abgleich/golden_ketten_stichprobe.py` rechnen dieselbe Größe,
jede für sich. Eine dritte Kopie in der Lese-API liefe absehbar
auseinander. Dieses Paket führt sie zusammen.

## Die drei Entscheidungen, die nicht beim Umsetzer liegen

**1. Die Prämie gehört an die Struktur, nicht in die API.** Sie hängt an
Legs und Ausführungen — genau an dem, was der Rebuild zur Hand hat, wenn er
`netto_pnl` und `waehrung` füllt (AP-04v, Vertrag 10a/11). Dort berechnet
und gespeichert, reicht die API sie nur durch, wie jeden anderen Betrag.
Pro Anfrage zu rechnen hieße, die Liste über Legs und Ausführungen zu
verbinden — langsamer und eine Rechnung mehr an einer Stelle, wo laut
AP-07lv nichts gerechnet wird.

**2. Je Kontrakt, nicht je Position.** Ein Preis ist nur vergleichbar, wenn
er von der Stückzahl unabhängig ist: „für 2,40 verkauft" sagt etwas, „für
24,00 verkauft" nur zusammen mit der Menge. Geteilt wird durch
`structures.menge` — die kleinste verdichtete Beinmenge
(`engine.structures`, Regel 10).

**3. Acht Nachkommastellen, ausdrücklich.** Gemessen am echten Bestand
tragen Ausführungspreise bis zu acht Stellen (von 32.475 Zeilen: 16.894 mit
zwei, 39 mit drei, 18 mit vier, 12 mit fünf, 2 mit acht). Bei Menge 1 — dem
Regelfall — ist die Prämie damit exakt. Nur die Division kann einen Rest
lassen, und das auch nur bei ungleichen Beinmengen; bei gleichen kürzt sich
die Menge heraus. Ohne festgelegte Tiefe schnitte `Decimal` still bei 28
Stellen ab, und das wäre eine Rundung ohne Namen (Regel 5).

## Ausdrücklich freigegebene Änderungen

Nur diese, keine weiteren.

- **Migration `d4f8b2c6a913`** und die Ergänzung in `journal/schema.py`:
  `structures.eroeffnungspreis` und `structures.schlusspreis`, beide
  entleerbar.
- **Fünf neue Tests** in `tests/test_rebuild.py`, **vier** in
  `tests/test_api_lesen.py`. Kein bestehender Test wird geändert.

## Vertrag an die Umsetzung (AP-07p)

### Die Größe

- **P1 · Berechnung.** Je Leg: Menge der **Leg** × Preis der zugehörigen
  Ausführung, **Verkauf positiv, Kauf negativ**. Die Summe über alle Legs
  geteilt durch `structures.menge`. Für `eroeffnungspreis` zählt die
  eröffnende Ausführung jeder Leg, für `schlusspreis` die schließende.
  Die Leg-Menge, nicht die der Ausführung: Eine Ausführung kann mehrere
  Legs bedienen.
- **P2 · Offen heißt leer.** Ist die Struktur nicht geschlossen, bleibt
  `schlusspreis` leer. **Keine Null** — die sähe aus wie ein Rückkauf zum
  Nulltarif.
- **P3 · Schreibweise.** Auf acht Nachkommastellen kaufmännisch gerundet
  (`ROUND_HALF_UP`), danach überzählige Nullen entfernt, **mindestens
  zwei** Nachkommastellen bleiben stehen. Aus 40 wird `40.00`, aus −20
  `-20.00`, aus 26/3 `8.66666667`.
- **P4 · Probe.** Für eine geschlossene Struktur gilt
  `(eroeffnungspreis + schlusspreis) × menge × multiplikator = brutto_pnl`.
  Die Tests prüfen das; stimmt es nicht, ist eine der beiden Rechnungen
  falsch.

### Wo sie steht

- **P5 · Eine Stelle, nicht drei.** Lege die Berechnung in ein eigenes
  Modul (`journal/preise.py`) und benutze sie aus `journal/rebuild.py`.
  **`journal/durchsicht.py` gibt seine eigene Fassung auf** und ruft
  dieselbe Funktion — seine Tests sichern ab, dass sich dabei nichts
  ändert. Das Abgleichswerkzeug unter `werkzeuge/abgleich/` **rührst du
  nicht an** (Regel 2, es liest Golden-Daten); das ziehe ich nach.
- **P6 · Kein Eingriff in `engine/`.** Die Prämie ist abgeleitet wie
  `netto_pnl` und entsteht beim Schreiben, nicht beim Rechnen der Ketten.

### In der Lese-API

- **P7 · Struktur:** die Felder `eroeffnungspreis` und `schlusspreis`,
  Zeichenkette oder leer — wie jeder Betrag (AP-07lv, Entscheidung 1).
- **P8 · Kette:** dieselben zwei Felder, gefüllt aus dem **ersten** und dem
  **letzten** Glied. Nur Durchreichen, kein Rechnen: Endet die Kette auf
  einer offenen Struktur, ist `schlusspreis` leer.

## Abnahme

- Die neun neuen Tests sind grün, alle übrigen bleiben es;
  `ruff check .` sauber.
- `journal rebuild` läuft über den echten Bestand durch.
- `git diff --stat` der Umsetzung zeigt `journal/preise.py`,
  `journal/rebuild.py`, `journal/durchsicht.py`, `api/app.py` und
  `OFFENE_FRAGEN.md` — **kein `tests/`, kein `engine/`, kein
  `werkzeuge/`**, keine weitere Migration.

## Ausdrücklich nicht Teil dieses Pakets

Keine Darstellung in der Oberfläche — die kommt mit AP-08f. Keine
Kennzahl, keine Umrechnung, keine Kettensicht.
