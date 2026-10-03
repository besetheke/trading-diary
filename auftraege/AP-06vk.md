---
titel: "Regel 3 am Echtbestand: Mengenvorzeichen und Leg-Anteile (AP-06vk)"
paket: AP-06vk
modell: stark
status: fertig
abhaengig_von: AP-06k
aendert: analytics/kennzahlen.py, OFFENE_FRAGEN.md (OF-62, OF-63, OF-64)
---

# AP-06vk · Korrekturpaket nach CLAUDE.md, Regel 1a

Der erste Echtlauf von `journal kennzahlen` auf `journal.db` (03.10.2026,
32.475 Ausführungen, 7.188/7.183 Ketten je Sicht) machte Regel 3
(wirtschaftliche EUR-Sicht) unplausibel: Summe −75.877.878 EUR bei einem
Handelsergebnis von +210.144 (Instrumentenwährung) und +183.905 EUR in der
IB-Sicht. Zwei Befunde, beide durch Handrechnung an Einzelketten belegt:

## Befund 1 — Mengenvorzeichen (OF-13 gilt auch hier)

AP-03, Regel 1: „Die Richtung kommt aus `side`, die Stückzahl aus
`abs(menge)`; das Vorzeichen von `menge` wird nicht ausgewertet — die Quelle
führt es uneinheitlich." Regel 3 multiplizierte trotzdem
`side-Vorzeichen × preis × menge`. IB Flex trägt das Seitenvorzeichen
zusätz­lich in der Menge (SELL = negativ) — die Doppelverwendung kippte jeden
Verkaufscashflow. Handrechnung Kette 7184 (SPX-BPS):
`SELL 5,82 × menge −1 × mult 100` ergab −582 statt +582; die Kettenzeile
−728,23 EUR statt +296,38 EUR.

## Befund 2 — Geldwert ist der Leg-Anteil, nicht die Gesamtausführung

Bei Teilablösungen (AP-03, Regel 5: eine Ausführung wird anteilig auf Legs
verteilt — 607 Ketten je Sicht betroffen) und Assignments steht in
`legs.menge` der zugeordnete Anteil. Die erste Fassung wertete je Leg die
**ganze** Ausführung. Handrechnungen:

- Kette 9533 (DAX, Kurs 1): exec `SELL 262,30 × menge 40` speist zwei Legs
  mit je menge 10 — +52.460 wurden doppelt gezählt; wirtschaftlich −52.406
  statt −4.866 (= netto bei Kurs 1).
- Kette 9215 (MELI, Assignment): leg menge 5 gegen exec menge 100 —
  +163.959 EUR statt +1.157 EUR.

## Die Korrektur

`analytics/kennzahlen.py::_wirtschaftlich` rechnet jetzt **je Leg-Seite**
(open und close) mit `leg.menge`: `side-Vorzeichen × preis × abs(leg.menge)
× multiplikator + anteilige Kommission`, multipliziert mit dem buchungskurs
der Ausführung dieser Seite. Die Kommission läuft — wie Regel 3 es sagt —
mit dem Kurs *derselben Ausführung*, anteilig nach
`leg.menge / abs(exec.menge)` (ohne Rundung: die Anteile summieren sich
exakt zur Ausführungskommission zurück). `_beteiligt` bleibt für
`eur_kurs_fehlt` und die Qualitätsstufe unverändert; sein Docstring nennt
die Regel-3-Annahme nicht mehr.

## Warum die Abnahmebasis unberührt grün blieb

Die Testwelt von `tests/test_kennzahlen.py` testet durchgängig „alle Mengen
je Leg 1" und je Ausführung 1 — dort sind Ausführungs- und Leg-Menge
identisch, und die Handrechnungen (K1: 67.60, K5: 82.80) gelten unter
beiden Modellen exakt. Alle 19 Tests bleiben grün, die Gesamtsuite ebenso,
`ruff check .` sauber.

## Abnahme am Echtbestand (03.10.2026)

- Kette 7184: 296,38 / 296,66 / Effekt −0,28 (centgenau die Handrechnung).
- Kette 9533: wirtschaftlich = IB = netto = −4.866,00, Effekt 0,00.
- Kette 9215: wirtschaftlich = IB = 1.157,18, Effekt −0,00.
- Summen Kettensicht: wirtschaftlich +166.890,77, IB +183.904,96,
  aggregierter Währungseffekt −17.013,87 (vorher −496.657 durch die
  Doppelzählungen).
- Ketten mit |wirtschaftlich/IB| ≥ 3: 87 von 6.841 (vorher 6.214);
  verbleibende Fälle sind lange Roll-Ketten mit echten USD-Kurssprüngen
  (0,83–1,04).
