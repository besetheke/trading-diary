---
titel: Depot-Stichtag aus dem NAV-Tag und Einzelkonto-Grenze (R03, R04)
modell: stark
status: fertig
abhaengig_von: AP-17
aendert_tests: nein
---

# AP-17e · Review R03 und R04

## R03 Depot-Stichtag

`journal/depot_stichtag.py::aktueller_depot_stichtag`: Stichtag ist der jüngste `OpenPositions`-Tag. Ist der jüngste NAV-Tag
neuer und weist der NAV Aktien und Optionen **bekannt als 0** aus (Rohstoffe, Fonds, Anleihen leer oder 0), gilt der NAV-Tag als
Stichtag: ein leerer Abschnitt heißt dann leeres Depot, nicht „alter Bestand“. Fehlt der NAV oder ist er nicht eindeutig leer,
bleibt der Positions-Tag. Eingebaut in `/depot`, `analytics/titel.py`, `analytics/ib_abgleich.py`.

## R04 Einzelkonto-Grenze

`journal/rebuild.py::bestand_berechnen` bricht mit klarer Meldung ab, wenn die Ausführungen mehr als ein Konto enthalten
(Matching würde Käufe des einen gegen Verkäufe des anderen paaren). Es wird nichts verändert.

## Tests

`tests/test_einzelkonto_und_depotstichtag.py` (8): Abbruch ohne Änderung, Stichtag-Fälle A–F, `/depot` zeigt leeres Depot.
Volle Suite 1003 grün, ruff sauber.

## Nicht Teil dieses Pakets

Mehrkonto-Unterstützung (erst bei Bedarf).
