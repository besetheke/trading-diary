---
titel: "Analytik Tranche II: Kommissionsattribution (Abnahmebasis)"
paket: AP-06w
modell: stark
status: offen
abhaengig_von: AP-06vr
naechstes: AP-06wk
aendert: tests/test_kommissions_attribution.py (neu, nach Freigabe), analytics/kommission.py (neu, durch AP-06wk), journal/cli.py (durch AP-06wk), OFFENE_FRAGEN.md
aendert_tests: ja
---

# AP-06w · Analytik Tranche II — Kommissionsattribution (Abnahmebasis)

Vorbereitungspaket nach Plan §11.2: Das starke Modell schreibt Abnahmebasis
und Tests, bevor gebaut wird. **Es implementiert nichts** — die Umsetzung ist
AP-06wk (günstiges Modell). Nach Freigabe der Entscheidungen E1–E7 legt dieses
Paket `tests/test_kommissions_attribution.py` an (rot, allein wegen
`ModuleNotFoundError: No module named 'analytics.kommission'`).

Fachliche Grundlage: Plan §6 AP-06 — „Kommissionsattribution absolut und in
Prozent des Bruttoergebnisses, aufgeschlüsselt nach Index, Anlageklasse,
Strategie und Roll-Anzahl" — und §1 Kernfrage 2 („Wie viel meiner Performance
frisst Kommission …?"). Tranchierung siehe `auftraege/AP-06v.md`; Tranche I
(AP-06v/k/vk/vr) ist fertig.

## Datenlage (gemessen 04.10.2026 an journal.db, nur Zählwerte — Regel 2)

- 7.188 Ketten (Kettensicht), davon 6.842 abgeschlossen.
- Roll-Verteilung der abgeschlossenen: 0 → 5.730, 1 → 702, 2 → 233, 3+ → 177.
- Anlageklassen (Ketten): OPT 7.096, STK 56, CASH 26, FUT 8, FOP 2.
- 298 verschiedene Underlyings.
- Kommission abgeschlossener Strukturen: EUR −60.952,75 (966 Strukturen),
  USD −19.152,45 (7.886), Einzelstücke in CHF/GBP/PLN/SEK (12 Zeilen). Ein
  Währungsmix dieser Größe verbietet Rohsummen — die Attribution rechnet in
  EUR (wirtschaftliche Sicht, Tranche I E2/E4).
- **Die Strategie-Dimension ist heute leer:** `strategies` 0 Zeilen,
  `structures.strategy_id` 0 gesetzt, `chains.oa_strategie` 0 gesetzt.
  Gemessener Grund: `optionapp_trades` ist leer (0 Zeilen) — der OA-Trade-
  Export wurde nie in diese Datenbank importiert; `executions.oa_trade`
  trägt immerhin 7.844 Referenzen. Die Strategie-Gruppierung liefert bis zum
  OA-Import (AP-13 Teil 1 auf dieser DB) genau einen Bucket. Die Dimension
  wird trotzdem gebaut — sie ist strukturell, nicht optional.

## Zu bauen (durch AP-06wk)

Neues Modul `analytics/kommission.py`. Rein (P2/P3): keine Uhr, kein Netzwerk,
kein Zufall, **keine Schreibzugriffe** — die Attribution braucht keinen Cache
(Cache-Tabellen sind Tranche IV/V, OF-01), der Bericht schreibt nur eine CSV.

Reine Funktion `kommissions_attribution(...)` mit derselben
Eingangssignatur wie `kennzahlen_auswertung` (Zeilen als plain dicts mit den
Spaltennamen der Tabellen; Schlüsselwörter `sicht` und
`nur_qualitaetsstufe_a`). Datenklassen (frozen):

- `KommissionsGruppe`: `dimension` ('index' | 'anlageklasse' | 'strategie' |
  'roll_anzahl'), `schluessel` (Text), `sicht`, `anzahl_ketten`,
  `kommission_eur`, `brutto_eur`, `netto_eur` (Decimal, wirtschaftliche
  Sicht), `kommissionsanteil` (Decimal | None, 4 Stellen, HALF_UP),
  `anzahl_ketten_kurs_fehlt` (int).
- `KommissionsErgebnis`: `sicht`, `gruppen` (Tupel), `anzahl_ketten_gesamt`
  (inklusive offener und mangelbehafteter — die Abdeckung muss sichtbar
  bleiben).

### Regeln

1. **Sicht.** Nur 'kette' oder 'konto'; jede Gruppe trägt ihre Sicht. Wie
   Tranche I (E1) laufen die strategischen Fragen über die Kettensicht; der
   Berichtsparameter `--sicht` bleibt.
2. **Nur abgeschlossene Ketten** (`beendet_am` nicht leer) tragen Summen —
   offene haben noch keine endgültige Kommission. Sie zählen in
   `anzahl_ketten_gesamt`.
3. **EUR nach Regel 3 von Tranche I** (wirtschaftlich, OF-62-Konvention):
   je beteiligter Ausführung Kommission × buchungskurs, anteilig nach
   Leg-Menge (AP-03, Regel 5). Fehlt ein Kurs der Kette: kein Wert, keine
   Summe, kein stiller Kurs 1 — die Kette zählt in
   `anzahl_ketten_kurs_fehlt` der Gruppen, denen ihr Schlüssel entspricht.
4. **Gruppierungsschlüssel.**
   - `index` = `chains.underlying` — kein Zusammenfassen wirtschaftlich
     gleicher Werte (§1.1: SPX/SPY/XSP bleiben getrennt);
   - `anlageklasse` = `chains.asset_class`;
   - `strategie` = `chains.oa_strategie`, sonst der Bucket '(ohne)';
     `structures.strategy_id` und die Sammelkennung E13/E14 bleiben
     unberührt (noch offen);
   - `roll_anzahl` = '0' | '1' | '2' | '3+' als Text.
5. **kommissionsanteil** = |`kommission_eur`| / |`brutto_eur`|, 4 Stellen
   HALF_UP, `None` wenn `brutto_eur` = 0. Kernfrage 2 ist ein
   Größenverhältnis; die Vorzeichen beider Summen stehen als eigene Felder
   daneben (E3).
6. **Determinismus.** Gruppen sortiert nach (dimension, schluessel)
   aufsteigend, Textvergleich — '3+' liegt damit hinter '2'.
7. **Drilldown ohne Id-Listen.** Jede Gruppe nennt `anzahl_ketten`; die
   beitragenden Ketten sind über den Kettensicht-Bericht (chain_id →
   structures → legs → executions) vollständig aufdröselbar. Ketten-Id-
   Listen ins CSV zu schreiben wäre unleserlich groß und veraltet beim
   nächsten Lauf (API-Endpunkte dafür sind AP-07-Rest).
8. **Keine stillen Rundungen.** Der Anteil entsteht einmal am Ende aus den
   Summen, nie aus gerundeten Zwischenwerten; Beträge werden geführt, wie
   sie rechnerisch entstehen (Regel 5).

### Bericht und CLI

`journal kennzahlen` erhält `--kommission <datei>`: schreibt die Gruppen
aller vier Dimensionen als **eine** CSV mit den Spalten `dimension`,
`schluessel`, `sicht`, `anzahl_ketten`, `kommission_eur`, `brutto_eur`,
`netto_eur`, `kommissionsanteil`, `anzahl_ketten_kurs_fehlt`. Geldbeträge
als Text mit Punkt (Decimal, kein float), `None` als leere Zelle — wie im
Tranche-I-CSV.

## Testwelt (tests/test_kommissions_attribution.py; alle Erwartungen von Hand)

Weiterverwendung der K-Welt aus `tests/test_kennzahlen.py` (K1 USX
geschlossen Stufe A, K2 DAX EUR, K3 offen, K4 Kursfehler, K5 Stufe B), plus:

- **K6 NDX, 1 Roll, 2 Strukturen** (je wie K1: Preise 120/80/60/30,
  Multiplikator 10, Kommission −2 je Ausführung, Kurse 0.90/0.95),
  `oa_strategie = 'NDX: IC-Test'` auf der Kette. Hand: je Struktur
  brutto_eur 75.00, Kommission −7.40; Kette brutto 150.00, Kommission
  −14.80, netto 135.20.

Handwerte ohne Stufenfilter (Kettensicht):

- `index`: DAX → 1 Kette, −8.00 / 100.00 / 92.00, Anteil 0.0800;
  NDX → K6, −14.80 / 150.00 / 135.20, Anteil 14.80/150 = 0.0987;
  USX → K1+K5 (K4 zählt als kurs_fehlt 1), −14.60 / 165.00 / 150.40,
  Anteil 14.60/165 = 0.0885.
- `anlageklasse`: OPT → K1, K2, K5, K6: Kommission −7.40−8.00−7.20−14.80 =
  −37.40, Brutto 75+100+90+150 = 415.00, Netto 377.60, Anteil
  37.40/415 = 0.0901 (0.09012…), kurs_fehlt 1 (K4).
- `strategie`: '(ohne)' → K1, K2, K5: −22.60 / 265.00 / 242.40, Anteil
  0.0853, kurs_fehlt 1; 'NDX: IC-Test' → K6: 0.0987.
- `roll_anzahl`: '0' → K1, K2, K5: −22.60 / 265.00, 0.0853, kurs_fehlt 1;
  '1' → K6: 0.0987.
- Mit `nur_qualitaetsstufe_a=True` fällt K5 weg: OPT → K1, K2, K6:
  −7.40−8.00−14.80 = −30.20 / 75+100+150 = 325.00, Anteil 30.20/325 =
  0.0929 (0.09292…); USX → nur K1: 0.0987; DAX 0.0800; NDX unverändert
  0.0987.
- `anzahl_ketten_gesamt` = 6 (K1–K6) in jeder Konfiguration.

## Entscheidungen (vom Nutzer zu prüfen)

- **E1 — Kettensicht als Auswertungssicht** wie Tranche I; `--sicht konto`
  bleibt als Berichtsparameter.
- **E2 — Strategie-Schlüssel ist `oa_strategie` mit Bucket '(ohne)'**;
  `strategy_id`/E13/E14 bleiben außen vor. Heute ein Bucket, bis der
  OA-Import läuft.
- **E3 — Anteil als Betragsverhältnis** |Kommission|/|Brutto| (None bei
  Brutto 0); Vorzeichen stehen in den Summenfeldern daneben.
- **E4 — Nur abgeschlossene Ketten in Summen**; offene und kursfehlende
  Ketten zählen und sind über `anzahl_ketten_gesamt` beziehungsweise
  `anzahl_ketten_kurs_fehlt` ausgewiesen.
- **E5 — Roll-Gruppen '0'/'1'/'2'/'3+'** als Text, sortierbar hinter '2'.
- **E6 — Eine CSV für alle vier Dimensionen** statt vier Dateien.
- **E7 — Kein neuer Cache, keine Migration:** die Attribution ist eine
  reine Auswertung; Cache-Tabellen bleiben Tranche IV/V (OF-01).

## Grenzen

Keine Roll-Degradation (Tranche III), keine Equity-Kurve/Drawdown (IV), keine
Campaign-Ebene (V). Keine Aufschlüsselung nach Seite, DTE-Band oder Breite
(Kernfrage 3, eigener Schnitt). Keine API-Endpunkte (AP-07-Rest), keine UI
(AP-08-Rest). Keine Kommissionsaufschlüsselung je Bein oder je Ausführung —
Aggregationsebene ist die Kette. Keine Zeitzonen-Logik (OF-04). Keine
Änderung an `analytics/kennzahlen.py` oder dessen Abnahmebasis.

## Abnahme

Nach Freigabe E1–E7: `pytest tests/test_kommissions_attribution.py` rot nur
wegen `ModuleNotFoundError: No module named 'analytics.kommission'`; übrige
Suite grün. Nach AP-06wk: die Datei grün, Gesamtsuite grün, `ruff check .`
sauber, `git diff --stat` zeigt nur die genannten Dateien. Jeder
Erwartungswert ist von Hand gerechnet und am Test begründet (Regel 8).

