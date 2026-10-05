---
titel: Parsernachbesserung - Produktcode in der Leg-Grammatik (OF-66)
modell: guenstig
status: offen
abhaengig_von: AP-13pn
---

# AP-13s · Parsernachbesserung: Produktcode

Umsetzungspaket nach Plan §11.2, Schritt 2, gegen die Abnahmebasis AP-13pn
(`tests/test_ingest_optionapp.py`, fünf neue Tests am Ende). **Tests und
Fixtures sind tabu** — fällt ein Test, ist der Code falsch.

## Zu bauen

Ausschließlich in `ingest/optionapp.py`: `LEG_MUSTER` so erweitern, dass vor dem
Recht **optional** ein Produktcode stehen darf — drei bis sechs Großbuchstaben,
danach genau ein Leerzeichen. Beispiele, die zerlegt werden müssen:

- `-1xODAP P23000 (260918)` → Short, Menge 1, Put, Strike 23000, 18.09.2026
- `2xODAC C24500 (260918)` → Long, Menge 2, Call, Strike 24500
- `1xP22900 (260918)` → wie bisher (ohne Code)

Der Code bekommt **keine** eigene Spalte und keinen eigenen Gruppenwert in
`_legs_zerlegen()` — er darf die Gruppen `vorzeichen, menge, right, strike,
verfall` nicht verschieben (nicht-erfassende Gruppe `(?:...)`). Der Rohwert `roh`
bleibt der ganze Ausschnitt samt Code.

Nicht ändern: `GEPLANTER_LEG_MUSTER`, die Fehlermeldung (die Aussage „über
N Legs ausnahmslos stabil" kann stehenbleiben), alles andere im Parser.

## Grenzen

- Keine Änderung an Tests, Fixtures, `fixtures/optionapp/erzeugen.py`.
- Keine Lockerung darüber hinaus: Kleinbuchstaben, ein anderes Recht als `C|P`
  oder ein Code ohne folgendes Leerzeichen müssen weiter abbrechen.
- **Regel 2:** Nichts unter `fixtures/golden/` lesen. Der echte Gesamtexport wird
  vom starken Modell/Nutzer geladen, nicht hier.

## Abnahme (AP-13s)

- `tests/test_ingest_optionapp.py` 31/31 grün, Gesamtsuite grün,
  `ruff check .` sauber.
- `git diff --stat`: ausschließlich `ingest/optionapp.py`.
