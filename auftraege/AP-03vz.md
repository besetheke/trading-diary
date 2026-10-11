---
titel: Kapitalmaßnahmen aus den Flex-Rohzeilen ableiten und anwenden; Faktoren an den Legs
modell: stark
status: fertig
abhaengig_von: AP-03vm, AP-02
aendert_tests: nein
---

# AP-03vz (und AP-03vz2) · Kapitalmaßnahmen im Rebuild

Behebt Befund 1 aus OF-79: Ticker-Wechsel und Zusammenlegungen (UNG, SMCI,
CHPT, VERU, PARA → PSKY) standen nicht in den Handelsdaten; ihre Aktien blieben
auf der alten `conid` offen, die späteren Verkäufe unter dem neuen Namen als
Leerverkäufe (37 offene Aktien-Legs ohne Gegenstück bei IB).

Die Engine konnte Transfers schon (AP-03vm); es fehlte die **Ableitung** aus
`flex_corporate_actions` nach `corporate_actions` — vorgesehen seit OF-23, nie
gebaut. Umsetzung durch das starke Modell (Cline im Creditlimit); die Tests
schrieb ich vor der Umsetzung (`tests/test_kapitalmassnahmen.py`, 22 Tests,
`tests/test_kapitalmassnahmen_eur.py`, 8 Tests, alle von Hand gerechnet).

## AP-03vz · Ableitung (`journal/kapitalmassnahmen.py`)

Rein: `kapitalmassnahmen_ableiten(zeilen)`; Hülle:
`kapitalmassnahmen_befuellen(verbindung)`, vom Rebuild vor dem Rechnen
aufgerufen. Sie **ergänzt** `corporate_actions` um fehlende Maßnahmen (Schlüssel
Konto, Aktion, alte und neue `conid`) — keine Zeile wird überschrieben oder
gelöscht (Regel 4), von Hand eingetragene bleiben, wiederholbar.

Regeln (Regel 10 — nichts wird geraten, Uneindeutiges wird mit Grund gemeldet):
Gruppen nach (Konto, `actionID`); gleiche Zeile aus zwei Exporten zählt einmal;
Optionszeilen werden übersprungen; **ein Abgang und ein Zugang auf
verschiedenen `conid`s = Transfer**; ein einzelner Zugang nur mit Kostenangabe;
alles andere (Ausbuchung, mehrere Zeilen derselben `conid`, …) wird gemeldet.

Echtbestand: 11 Aktionen → **6 Transfers** (UNG 1:4, SMCI 10:1, CHPT 1:20, VERU
1:10, PARA→PARA.CSH 1:1, PARA.CSH→PSKY 100→39,0741), übersprungen: die
Optionsanpassungen (SMCI, FAST), die Dividendenrechte (WKL, DI ohne Kosten, ED).

## AP-03vz2 · Faktoren an den Legs (Folgefehler, am Echtlauf gefunden)

Nach einer Maßnahme steht `legs.menge` in **neuen** Stücken, die Ausführung noch
mit Menge und Preis der **alten**. Alles, was Preis × Leg-Menge aus der Ausführung
neu rechnet, lieferte falsche Werte: Im ersten Echtlauf kippte die Equity von
+102.335 € auf −282.232 €. Die Datenbank wurde sofort aus der Sicherung
wiederhergestellt (Integritätsprüfung in Ordnung), die Ableitung kurz
abgeschaltet.

Behebung: Das Matching speichert je Leg `open_faktor` und `close_faktor`
(neue ÷ alte Menge der durchlaufenen Maßnahmen, mehrere multiplizieren sich, 1
ohne Maßnahme; nicht Teil der Gleichheit von `Leg`). Migration `b9d3e5a7c1f4`
(neue Spalten, Standard 1). Mit Preis ÷ Faktor und Ausführungsmenge × Faktor
rechnen jetzt: `analytics/kennzahlen.leg_seiten` (EUR-Werte, Kommissionsanteil),
`analytics/kommission`, `journal/preise` („Preis auf/zu"). Die Lese-Hüllen von
Equity, Kennzahlen und Kommission lesen die Faktoren mit.

## Nachweis

Gesamtsuite grün, `ruff check .` sauber. Echtlauf (Sicherung davor, Migration,
Rebuild): 6 Maßnahmen angewendet; **offene Aktien-Legs ohne Gegenstück bei IB:
37 → 0**; offener Bestand gegen IB: alle 138 Instrumente gleich. Equity
(Journal, EUR) 102.335 → 88.385. Gegen IBs realisiertes Ergebnis (aus den
Jahresdateien, 77.854 €): Abweichung **28.942 → 14.992 €**; die betroffenen
Paare gleichen sich aus (SMCI +10, UNG −50, VERU −384 €).

## Offen (OF-80)

Der Barteil einer Fusion (`TC` mit `proceeds`, PARA.CSH → PSKY: 913,89 USD) wird
nicht als realisiert gebucht; Ausbuchung verfallener Rechte (`ED`) und
Optionsanpassungen sind nicht modelliert; vier Optionen sind trotz Verfall noch
offen (Verfallszeile fehlt).
