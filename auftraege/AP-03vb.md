---
titel: Barausgleich bei Zuteilung und Ausübung (OF-25)
modell: stark
status: offen
abhaengig_von: AP-03vn, AP-02
aendert_tests: ja
---

# AP-03vb · Barausgleich bei Zuteilung und Ausübung

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ergänzt die Abnahmebasis um die
Barausgleich-Regel aus AP-03.md, Vertrag Regel 7 (OF-25), die dort seit dem
13.09.2026 als „noch nicht Teil der Abnahmebasis" vermerkt ist.
**Implementiert wird nichts** — die Nachbesserung von `engine/matching.py`
macht danach AP-03.

## Anlass

Der Geldtest (OF-24/OF-25) zeigte: 501 Zuteilungen und Ausübungen im
Golden-Export werden bar abgerechnet. IB bucht sie mit Ereigniszeilenpreis
0.00; der tatsächliche Abrechnungskurs steht in `closePrice` (jetzt
`executions.schlusskurs`, AP-02 Regel 6). Das Matching kennt diese
Unterscheidung noch nicht — es schließt jede Zuteilung/Ausübung zum
Ereigniszeilenpreis, was bei Barausgleich das Ergebnis um den vollen
Abrechnungsbetrag verfälscht.

Entschieden (13.09.2026): Bei `abwicklungsart='barausgleich'` schließt die
Ereigniszeile zum `schlusskurs`, bei `'lieferung'` bleibt es beim
Ereigniszeilenpreis — die Prämie steht dort in der Aktienbasis, nicht an der
Option (OF-24). Fehlt die Abwicklungsart, ist Barausgleich gegen Lieferung
nicht entscheidbar; kein Standardwert.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Drei neue Fixtures** unter `fixtures/synthetisch/`:
  `barausgleich.json` (conid 500020 barausgleich, conid 500021 lieferung als
  Kontrollgruppe mit gesetztem, aber zu ignorierendem `schlusskurs`),
  `barausgleich_fehlende_abwicklungsart.json`,
  `barausgleich_fehlender_schlusskurs.json`.
- **`fixtures/synthetisch/ereigniszeile_kein_trade.json`**: am Instrument
  conid 500011 (trägt die einzige Ausübung dieser Datei) wird
  `abwicklungsart: "lieferung"` ergänzt. Ohne dieses Feld bräche der neue
  Check die bestehende Ausübung ab; am Ergebnis ändert sich nichts.
- **`tests/test_matching.py`**: `DEZIMALFELDER` um `schlusskurs` ergänzt
  (sonst bleibt der Wert eine Zeichenkette statt `Decimal`, Regel 5). Fünf
  neue Tests am Ende der Datei:
  `test_barausgleich_schliesst_zum_schlusskurs`,
  `test_barausgleich_ereigniszeilenpreis_waere_das_falsche_ergebnis`,
  `test_lieferung_ignoriert_gesetzten_schlusskurs`,
  `test_fehlende_abwicklungsart_bei_ausuebung_bricht_ab`,
  `test_barausgleich_ohne_schlusskurs_bricht_ab`. Der Moduldocstring erhält
  einen Nachtrag, der den Anlass und die Fixture-Änderung erklärt.

Bestehende Tests bleiben in ihren Erwartungen unverändert.

## Umzusetzen

Nichts an `engine/matching.py`. Nachbesserung ist Sache von AP-03.

## Abnahme

- Die vier neuen Tests, die den Barausgleich selbst betreffen
  (`test_barausgleich_schliesst_zum_schlusskurs`,
  `test_barausgleich_ereigniszeilenpreis_waere_das_falsche_ergebnis`,
  `test_fehlende_abwicklungsart_bei_ausuebung_bricht_ab`,
  `test_barausgleich_ohne_schlusskurs_bricht_ab`) schlagen gegen den
  jetzigen `engine/matching.py` fehl. Das ist gewollt — Nachweis, dass die
  Abnahmebasis die Lücke tatsächlich zeigt. `test_lieferung_ignoriert_
  gesetzten_schlusskurs` darf schon jetzt grün sein: Für `lieferung` ändert
  sich nichts, der Test ist eine Regressionssicherung für die Nachbesserung.
- Alle 61 bisherigen Tests bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_matching.py`, den drei neuen Fixtures und der einen Zeile in
  `ereigniszeile_kein_trade.json`. Kein `engine/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung im Matching. Keine Änderung an `ingest/` oder `journal/`.
