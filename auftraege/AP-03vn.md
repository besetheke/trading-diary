---
titel: Nachtrag zur Abnahmebasis AP-03 - Kommissionen mit Nachkommastellen (OF-18)
modell: stark
status: fertig
abhaengig_von: AP-03vk
aendert_tests: ja
---

# AP-03vn · Kommissionen mit mehr als zwei Nachkommastellen

Nachtrag zur Abnahmebasis nach CLAUDE.md, Regel 1a. Es legt Tests und ein
Fixture neu an und implementiert nichts. Die Nachbesserung von
`engine/matching.py` ist Sache von AP-03.

## Anlass

Das Review von AP-03 hat gezeigt (OF-18): `_kommission_verteilen` rundet auch
den letzten Kommissionsanteil auf den Cent. Hat die gebuchte Kommission mehr
als zwei Nachkommastellen, geht die Summe über die Legs nicht mehr auf; eine
ungeteilte Ausführung wird ohne jede Aufteilung still gerundet. In den
Golden-Exporten betrifft das 78 % bzw. 61 % aller Ausführungen.

Die Abnahmebasis aus AP-03v enthält kein Fixture mit solchen Kommissionen,
deshalb lief AP-03 trotz des Fehlers grün.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren:

- **Neues Fixture** `fixtures/synthetisch/kommission_nachkommastellen.json`
  mit drei Fällen: eine ungeteilte Ausführung, eine Aufteilung auf zwei
  Schließungen, eine Short-Position mit offenem Rest.
- **Drei neue Tests** am Ende von `tests/test_matching.py`:
  `test_ungeteilte_gebrochene_kommission_bleibt_exakt`,
  `test_gebrochene_kommission_letzte_teilmenge_traegt_den_exakten_rest`,
  `test_gebrochene_kommission_summe_je_conid_ist_exakt`. Jeder Erwartungswert
  trägt seinen Rechenweg. Die Tests prüfen jedes Leg einzeln und nicht nur die
  Summe, denn beim Short-Fall heben sich zwei Rundungsfehler in der Summe
  zufällig auf.

Bestehende Tests und Fixtures bleiben unverändert.

## Umzusetzen

1. Fixture und Tests wie oben.
2. `auftraege/AP-03.md`, Vertrag Regel 5: präzisieren, dass die gebuchte
   Kommission nie gerundet wird — gerundet werden nur die Anteile vor der
   letzten Teilmenge, die letzte trägt den exakten Rest.
3. `OFFENE_FRAGEN.md`: OF-18 fortschreiben.

## Abnahme

- Die drei neuen Tests **schlagen gegen den jetzigen `engine/matching.py`
  fehl** — genau an den Stellen, die OF-18 beschreibt. Das ist gewollt: Sie
  sind die Abnahme für die Nachbesserung von AP-03. `check.cmd` ist bis dahin
  rot.
- Gegen eine unabhängig aus dem Vertrag geschriebene Referenz bestehen alle
  Tests von `tests/test_matching.py`.
- Alle übrigen Tests der Suite bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in `tests/test_matching.py`,
  dem neuen Fixture, `auftraege/AP-03.md` und `OFFENE_FRAGEN.md`. Kein Code
  unter `engine/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Änderung an `engine/matching.py`. Die Korrektur dort macht AP-03 gegen
diese Tests.
