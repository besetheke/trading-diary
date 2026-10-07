---
titel: Gemeinsame Leg-Seiten-Zerlegung für die EUR-Rechnung (Refactoring)
modell: guenstig
status: offen
abhaengig_von: AP-06xk
aendert_tests: nein
---

# AP-06xr · Das Duplikat der EUR-Rechnung beseitigen

Reine Umformung, **kein Verhalten ändert sich**. Grund: `_wirtschaftlich`
(`analytics/kennzahlen.py`) und `_eur_teile` (`analytics/kommission.py`)
enthalten dieselbe Zerlegung doppelt — Kursprüfung, Ausführung nachschlagen,
Seitenvorzeichen, Multiplikator, Kommissionsanteil nach Leg-Menge. Fehler
an dieser Stelle müssen heute zweimal behoben werden (OF-69 wurde nur
durch eine gemeinsame Vorstufe an einer Stelle möglich).

## Zu tun

1. In `analytics/kennzahlen.py` eine gemeinsame Funktion anlegen, die für eine
   Leg-Liste je Leg-Seite (Eröffnung, Schließung) die Bestandteile liefert:
   Ausführung, Vorzeichen der Seite, vorzeichenlose Leg-Menge, Multiplikator,
   Kommissionsanteil (Kommission × Leg-Menge / Gesamtmenge der Ausführung),
   Buchungskurs. Sie enthält alle bisherigen Prüfungen unverändert:
   Kursfehlen → `None` für die ganze Kette (E4), unbekannte Ausführung,
   unbekannte Seite, fehlendes Instrument, Menge 0 — mit **denselben
   Fehlertexten** (die Tests prüfen sie).
2. `_wirtschaftlich` und `_eur_teile` nutzen sie. **Jede der beiden Funktionen
   behält ihre eigene Rechenformel** (`_wirtschaftlich`: (Prämie + Kommission)
   × Kurs je Seite; `_eur_teile`: Brutto und Kommission getrennt × Kurs).
   Nicht zu einer Formel verschmelzen: Decimal-Rundung an der 28. Stelle
   würde sonst die Berichtssummen im letzten Zeichen verschieben.
3. `analytics/kommission.py` importiert aus `analytics/kennzahlen.py` (wie
   bisher `STUFEN_RANG`, `bewerte_barausgleich`).

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, `journal/`,
`analytics/steuer.py`. Kein neues Verhalten, keine neuen Parameter an den
öffentlichen Funktionen. Decimal, kein float.

## Abnahme

- `pytest` grün (alle Tests unverändert), `ruff check .` sauber,
  `git diff --stat` ohne `tests/`.
- Nachweis der Verhaltensgleichheit: Das starke Modell lässt danach
  `journal kennzahlen … --sicht kette` und `--sicht konto` auf einer Kopie
  von `journal.db` laufen; die Ausgabezeile „Summe netto EUR" muss
  **Zeichen für Zeichen** gleich bleiben (beide Sichten, Stand 07.10.2026:
  `163546.1955046522250138549223`).
