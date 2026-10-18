---
titel: Stabile Strukturbildung und Live-Ende aus gematchten Legs (R06, R07)
modell: stark
status: fertig
abhaengig_von: AP-17
aendert_tests: nein
---

# AP-17f · Review R06 und R07

## R06 Reihenfolge-Unabhängigkeit (`engine/structures.py`)

- Alle Arbeits-Legs und die Zeitfenster-Gruppen werden mit einem **vollständigen Schlüssel** sortiert:
  Zeit, Basiswert, Verfall, Recht, Strike, Richtung, Menge, Eröffnungs-ID, Schließungs-ID. Die Ergebnisliste der Strukturen
  trägt als letzten Schlüssel die Exec-IDs. Permutationen der Eingabe liefern identische Strukturen und Naturschlüssel.
- **Festgelegte Regel für Mehrdeutigkeit** (nur Ersatzweg Zeitfenster): passen mehrere offene Cluster, bekommt das Bein den mit den
  wenigsten Beinen seiner eigenen Richtung, bei Gleichstand den früheren. Vier gleichzeitige Legs (2 Long, 2 Short) ergeben so
  zwei Paare statt 3 + 1. Der Ersatzweg bleibt ein Vorschlag (`erkennung = heuristik`); die Paarung innerhalb gleichzeitiger
  Legs ist nach Strike-Reihenfolge festgelegt, nicht „bewiesen“. Siehe OF-101.

## R07 Ende der Live-Eröffnung (`analytics/backtest.py::_live_laden`)

Eröffnung (Fingerabdruck) und Ende kommen aus getrennten Mengen: eröffnet wird per Trade (kein Schließungs-Leg), das Ende laut
`legs.close_exec_id` der eröffnenden Ausführungen sowie laut späteren Ereignissen mit derselben OA-Nummer. Verfall, Zuteilung und
Ausübung (auch ohne OA-Nummer) erreichen die Ausstiegsanalyse; ein Rückkauf innerhalb des Eröffnungsfensters zählt nicht mehr als
Eröffnungsbein.

## Tests

`tests/test_structures_reihenfolge.py` (3), `tests/test_backtest_live_ende.py` (6: Rückkauf, Verfall mit/ohne OA-Nummer,
Teilschließung, schneller Roundtrip, offen). Bestehende Tests unverändert.

## Nicht Teil dieses Pakets

Anzeige mehrdeutiger Zuordnungen als Arbeitsliste (M04); Barausgleich als eigene Ursache (zählt wie Verfall als „nicht Trade“).
