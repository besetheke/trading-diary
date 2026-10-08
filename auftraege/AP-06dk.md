---
titel: Roll-Degradation — Umsetzung (AP-06 Tranche III)
modell: guenstig
status: offen
abhaengig_von: AP-06d
aendert_tests: nein
---

# AP-06dk · Umsetzung gegen die Abnahmebasis AP-06d

Verhalten, Entscheidungen E1–E8 und Schnittstellen: `auftraege/AP-06d.md`.
Maßgeblich sind die Tests in `tests/test_degradation.py` (unveränderlich,
Regel 1).

## Zu bauen

1. **`analytics/degradation.py`** (neu): die reine Auswertung, die CSV und die
   Hülle. Die Auswertung ruft `kennzahlen_auswertung(...)` (Tranche I) auf und
   gruppiert deren Ketten — **keine zweite EUR-Rechnung**. Netto je Kette ist
   `netto_eur_wirtschaftlich`; Ketten ohne Kurs haben dort `None`. Quoten über
   die vorhandene Hilfsfunktion `_quote` (oder einen gleichwertigen Import).
   Decimal, kein float; Geldbeträge in der CSV mit zwei, Quoten mit vier
   Stellen, `None` als leere Zelle.
2. **Hülle `degradations_bericht`**: liest die Zeilen der **Kettensicht**
   lesend, mit denselben Spalten wie `kennzahlen_bericht` — **auch**
   `executions.ereignistyp`, `executions.schlusskurs` und
   `instruments.abwicklungsart` (OF-69), und zusätzlich aus `chain_links`
   `sequenz`, `verknuepfungstyp`, `erkennung`. Sie darf **nichts schreiben**
   (`kennzahlen_bericht` schreibt `fx_rates`/`metrics_by_chain` — das gehört
   nicht hierher). Den lesenden Teil nach Möglichkeit mit
   `kennzahlen_bericht`/`kommissions_bericht` teilen, nicht kopieren.
3. **`journal/rebuild.py::offene_rollkandidaten(db_pfad) -> int`**: gibt
   dieselbe Zahl zurück wie `RebuildErgebnis.kandidaten_offen`, ohne etwas zu
   schreiben. Die Rechnung steckt in `bestand_berechnen` und
   `_offene_kandidaten`; die ID-Zuordnungen kommen aus den vorhandenen
   Kontosicht-Zeilen. Sie darf die abgeleiteten Tabellen nicht verändern (der
   Test prüft das). Laufzeit am Echtbestand: höchstens so lang wie `rebuild`
   selbst, besser kürzer — keinen vollständigen Rebuild mit Rücknahme bauen,
   wenn sich ein lesender Weg über `bestand_berechnen` anbietet.
4. **`journal/cli.py`**: Option `--degradation DATEI` an `kennzahlen`
   (Ausgabezeile `Degradation nach <Datei>: <n> Gruppen`). Die Prüfung
   `--sicht konto` zusammen mit `--degradation` geschieht **vor** jeder
   Ausgabe: stderr-Meldung mit dem Wort „Kettensicht", Rückgabe 1, keine
   Datei, auch nicht die Kennzahlen-CSV.

## Grenzen

Keine Änderung an `tests/`, `fixtures/`, `engine/`, den bestehenden Berechnungen
in `analytics/kennzahlen.py` und `analytics/kommission.py` (nur Wiederverwendung)
und am Schema (keine Migration). Keine Heuristik, die Kandidaten ausschließt.

## Abnahme

`pytest` grün, `ruff check .` sauber, `git diff --stat` ohne `tests/`. Den
Echtlauf auf einer Kopie von `journal.db` macht anschließend das starke Modell
(Referenz: OF-70).
