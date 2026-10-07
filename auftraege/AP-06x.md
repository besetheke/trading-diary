---
titel: Abnahmebasis Barausgleich in der wirtschaftlichen EUR-Rechnung (OF-69)
modell: stark
status: fertig
abhaengig_von: AP-06v, AP-06w
aendert_tests: ja
---

# AP-06x · Abnahmebasis: Zuteilung und Ausübung bei Barausgleich in EUR

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-06xk (günstiges Modell). Neue Testdatei `tests/test_eur_barausgleich.py`
(10 Tests), keine bestehende Erwartung wird geändert.

## Fehler (OF-69)

Bei Zuteilung/Ausübung einer Option mit Barausgleich (SPX, XSP, RUT, …) trägt
die Ereigniszeile den Preis 0, der Abrechnungskurs steht in `schlusskurs`
(OF-25). `engine/matching.py` rechnet damit richtig; die wirtschaftliche
EUR-Rechnung (`analytics/kennzahlen.py::_wirtschaftlich`,
`analytics/kommission.py::_eur_teile`) nahm den Preis 0 und bewertete nur die
Prämie. Wirkung auf den Echtbestand (Kopie, 07.10.2026): Summe netto EUR
198.895 statt 163.546, „Währungseffekt" in den Barausgleich-Ketten −149 statt
Zehntausenden, Kommissionsanteile je Strategie verzerrt.

## Regel

Eine Ausführung mit `ereignistyp` `assignment` oder `exercise`, deren
Instrument `abwicklungsart = 'barausgleich'` trägt, wird mit ihrem
`schlusskurs` bewertet statt mit dem `preis`. Alles andere bleibt beim `preis`
(Handel auch bei gesetztem `schlusskurs`; Lieferung; Aktienzeilen). Fehlt der
`schlusskurs` bei Barausgleich: `ValueError`, der die Ausführung nennt.

Die Eingabezeilen tragen dafür zusätzlich `ereignistyp` und `schlusskurs`
(Ausführungen) und `abwicklungsart` (Instrumente). Fehlen die Schlüssel (alte
Tests), gilt das bisherige Verhalten.

## Abnahme

`tests/test_eur_barausgleich.py` grün (Handrechnung im Modul-Docstring), alle
übrigen Tests unverändert grün, `ruff check .` sauber. Gegen eine
Wegwerf-Umsetzung geprüft: ohne sie schlagen 7 von 10 Tests fehl, mit ihr
laufen alle grün.
