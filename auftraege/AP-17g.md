---
titel: Roll-Kosten in der Oberfläche und festgeschriebene Abhängigkeiten (M01, M08)
modell: stark
status: teilweise
abhaengig_von: AP-17
aendert_tests: nein
---

# AP-17g · Teil 1 des Ausbaus aus dem Review

## M08 Abhängigkeiten festschreiben

`requirements-lock.txt` (Journal und Roller, `pip freeze` vom 18.10.2026, ohne `ibapi`, das aus `C:\TWS` kommt).
`setup.cmd` und `Deploy.ps1` installieren zuerst den festen Stand; fehlt die Datei, gilt wie bisher die offene Mindestversion.
Test: `tests/test_abhaengigkeiten_fest.py` (exakte Versionen, deckt `pyproject.toml` ab, Skripte nutzen die Datei).

## M01 Roll-Kosten und Kommission

`GET /roll-kosten-auswertung?sicht=kette|konto&nur_a=…` (`api/roll_kosten.py`) reicht `analytics.kommission` und
`analytics.degradation` unverändert weiter (EUR, Dezimal-Texte). Seite `/roll-kosten` („Roll-Kosten“ im Journal-Menü):
Ergebnis nach 0/1/2/3+ Rolls (Anzahl, Summe, Ø netto, Trefferquote, Ketten ohne Kurs, beide Modi `belegt` und
`belegt_bestaetigt`), Abdeckung samt offenen Rollkandidaten, Kommission nach Roll-Anzahl, Strategie, Basiswert, Anlageklasse;
beide Sichten ausdrücklich benannt. Test: `tests/test_api_roll_kosten.py`.

## Offen (OF-102)

Drilldown von jeder Zeile auf die gezählten Ketten/Positionen: die Rechenkerne liefern bisher nur Summen, keine Kettenlisten.
Dafür müssten sie die Ketten-IDs je Gruppe mitgeben (eigener Auftrag). Außerdem Browser-Smoke-Test und Restore-Probe (M08),
Vorabprüfung aller Downloads vor dem Stoppen der Dienste. M02–M07 folgen.
