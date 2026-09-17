---
titel: FIFO-Gleichstand einfrieren (OF-24)
modell: stark
status: fertig
abhaengig_von: AP-03vo
aendert_tests: ja
---

# AP-03vp · Verhalten bei FIFO-Gleichstand festnageln

Korrekturpaket nach CLAUDE.md, Regel 1a — **kein Lückennachweis, sondern eine
Einfrierung.** Dieses Paket ändert nichts am Verhalten und deckt keinen Fehler
auf; es hält den heutigen Stand fest, damit er nicht unbemerkt wandert. Die
neuen Tests sind deshalb ausnahmsweise **sofort grün**, und das ist der Zweck.

## Anlass

Der Geldtest (OF-24) lässt 34 Ausführungen auf 20 Instrumenten übrig, bei
denen das Matching einer Schließung ein anderes Los zurechnet als IB. Bei
16 der 20 Instrumente heben sich die Beträge exakt auf: Je Instrument stimmt
das realisierte Ergebnis mit IB überein, nur die Verteilung auf die einzelnen
Schließungen ist eine andere. Es geht kein Geld verloren und es entsteht
keines.

Gemeinsames Merkmal: 27 der 34 Fälle haben auf derselben `conid`
**zeitgleiche Ausführungen**. Bei gleicher Handelszeit entscheidet im
Matching die `exec_id` — die laut AP-02a die `tradeID` ist — in aufsteigender
Ordnung, welches Los zuerst geschlossen wird.

**IBs eigene Regel für diesen Gleichstand ist unbekannt.** Die naheliegende
Annahme, IB folge derselben `tradeID`-Ordnung, ist gemessen **nicht**
bestätigt: In allen 34 Fällen sind die beteiligten `tradeID`s gleich lang,
lexikografische und numerische Ordnung fallen also zusammen, und ein Lauf mit
erzwungen numerischer Sortierung liefert exakt dieselbe Trefferquote
(14.612 von 15.672, Differenz null). Eine andere Reihenfolge zu wählen wäre
geraten (Regel 10) — also bleibt es bei der heutigen, und sie wird geprüft
statt stillschweigend vorausgesetzt.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Eine neue Fixture** `fixtures/synthetisch/fifo_gleichstand.json`: zwei
  Eröffnungen mit identischer Handelszeit auf derselben `conid` (G1 zu 5,00,
  G2 zu 7,00), danach eine Schließung (G3 zu 9,00).
- **Zwei neue Tests** am Ende von `tests/test_matching.py`:
  `test_fifo_gleichstand_wird_nach_exec_id_aufgeloest` und
  `test_fifo_gleichstand_andere_reihenfolge_waere_ein_anderes_ergebnis`.

Bestehende Tests bleiben unverändert.

## Vertrag (Präzisierung zu AP-03.md, Regel 2)

Bei **gleicher Handelszeit** bestimmt die `exec_id` in aufsteigender Ordnung
die FIFO-Reihenfolge. Das war schon immer so — die Sortierung lautet
`(handelszeit, exec_id)` —, stand aber nirgends als geprüfte Zusage. Ändert
sich diese Reihenfolge, ändern sich Zuordnung und ausgewiesenes Ergebnis je
Leg, ohne dass die Summe je Instrument sich bewegt. Genau das sollen die
beiden Tests sichtbar machen.

## Abnahme

- Beide neuen Tests sind grün, ohne dass `engine/` angefasst wird.
- Alle übrigen Tests bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_matching.py` und der neuen Fixture.

## Ausdrücklich nicht Teil dieses Pakets

Keine Änderung der Reihenfolge. Keine Angleichung an IB — deren Regel ist
unbekannt. Keine Aussage zu den vier Instrumenten, deren Abweichungen sich
nicht aufheben (rund 71 Einheiten, davon 70,94 PLN auf einem einzigen); die
sind in `AP-03.md` beziffert.
