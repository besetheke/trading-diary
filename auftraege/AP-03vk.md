---
titel: Korrektur der Abnahmebasis AP-03 - Preisfaktor bei Futures (OF-14)
modell: stark
status: fertig
abhaengig_von: AP-03v
aendert_tests: ja
---

# AP-03vk · Preisfaktor bei Futures

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ändert zwei Test-Erwartungen der
Abnahmebasis aus AP-03v und läuft deshalb unter dem Profil `locker`.
Implementiert wird nichts — `engine/matching.py` entsteht erst in AP-03.

## Anlass

AP-03v hat festgelegt: Bei `FUT` und `FOP` schlägt ein gesetzter `tickwert`
den `multiplikator` und gilt als Geldwert eines vollen Punkts. Das ist in sich
stimmig, belegt das Feld aber mit einer Bedeutung, die sein Name nicht hergibt.

Der Fehlerfall, den das öffnet: Beim ES ist der Multiplikator 50, die
Tickgröße 0,25 und der echte Tickwert 12,50. Trägt jemand dort 12,50 ein, weil
das Feld „Tickwert" heißt, rechnet das Matching mit 12,50 statt 50 — jeder
Futures-P&L wäre still um den Faktor 4 falsch, und kein Test schlüge an.

**Entschieden (OF-14, Variante a):** `multiplikator` trägt bei allen
Anlageklassen den Preisfaktor, bei Futures also den Punktwert. `tickwert` ist
eine Berichtsgröße und geht nicht in den P&L ein. IB liefert `tickwert` nicht;
der Tickwert ist aus Multiplikator und Tickgröße ableitbar, nicht umgekehrt.
Der Vertrag in `auftraege/AP-03.md`, Regel 3, ist bereits angepasst.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren. Eine unabhängige Gegenprobe gegen eine Referenz
nach Variante (a) hat gezeigt, dass genau diese beiden Tests betroffen sind;
alle übrigen 55 bestehen unverändert.

- `tests/test_matching.py`, **`test_futures_tickwert_hat_vorrang_vor_dem_multiplikator`**:
  umbenennen in `test_futures_tickwert_geht_nicht_in_den_pnl_ein`. Neue
  Erwartung `(18010.0 - 18000.0) * 2 Kontrakte * 5 = 100.00`, Rechenweg als
  Kommentar. Der Test bleibt scharf, weil das Fixture den Tickwert 25
  weiterhin setzt — er muss ignoriert werden.
- `tests/test_matching.py`, **`test_futures_multiplikator_allein_waere_das_falsche_ergebnis`**:
  umbenennen in `test_futures_tickwert_als_faktor_waere_das_falsche_ergebnis`.
  Die Gegenprobe kehrt sich um: `brutto_pnl != Decimal("500.00")`, Rechenweg
  `(10.0 * 2 * 25) = 500.00` als Kommentar.
- `tests/test_matching.py`: der Kommentarblock über den Futures-Tests darf die
  neue Regel beschreiben.
- `tests/test_matching.py`, **ein neuer Test** `test_fehlender_multiplikator_bricht_ab`:
  Vertrag Regel 3 verlangt einen `ValueError` unter Nennung des `conid`, wenn
  `multiplikator` fehlt. Die Testdaten entstehen im Test, indem aus dem
  geladenen Fall `futures_tickwert` bei conid 500004 `multiplikator` auf `None`
  gesetzt wird — `tickwert` bleibt 25 und darf nicht einspringen. Kein neues
  Fixture.
- `fixtures/synthetisch/futures_tickwert.json`: **nur das Feld `beschreibung`**,
  weil es die alte Regel nennt. Alle Zahlen bleiben unverändert; sie machen den
  Test erst scharf.

Die übrigen Tests bleiben unberührt, auch die beiden anderen Futures-Tests
(`test_futures_ohne_tickwert_gilt_der_multiplikator`,
`test_futures_kommission_wird_voll_zugeordnet`) und
`test_futures_beide_positionen_sind_geschlossen`.

## Umzusetzen

1. Die oben genannten Änderungen an `tests/test_matching.py` und am Feld
   `beschreibung`.
2. `journal/schema.py`: ein Kommentar an `instruments.tickwert`, dass das Feld
   eine Berichtsgröße ist und nicht in den P&L eingeht; der Punktwert steht in
   `multiplikator`. **Nur der Kommentar, keine Schemaänderung, keine Migration.**
3. `OFFENE_FRAGEN.md`: OF-14 als umgesetzt vermerken.

## Abnahme

- `check.cmd` läuft grün; `tests/test_matching.py` überspringt sich weiterhin,
  weil `engine/matching.py` nicht existiert.
- `git diff --stat` zeigt Änderungen ausschließlich in `tests/test_matching.py`,
  `fixtures/synthetisch/futures_tickwert.json`, `journal/schema.py` und
  `OFFENE_FRAGEN.md`.
- Der Diff an `futures_tickwert.json` betrifft nur die Zeile `beschreibung`.
- Die zwei geänderten und der neue Test tragen ihren Rechenweg im Kommentar.
- Kein Code unter `engine/`, keine Migration, keine Änderung an `plan/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung des Matchings. Keine Tickgröße im Schema — sollte sie je
gebraucht werden, ist das eine eigene Entscheidung mit eigener Migration.
