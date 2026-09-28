---
titel: Korrektur der Abnahmebasis AP-05v - Financing-Fixtures sind zugleich IC-Kandidaten (OF-51)
modell: stark
status: fertig
abhaengig_von: AP-05v
aendert_tests: ja
---

# AP-05vk · Financing-Tests von IC entkoppeln

Korrekturpaket nach CLAUDE.md, Regel 1a. Es ändert drei benannte
Test-Erwartungen in `tests/test_campaigns.py` und läuft deshalb unter
`locker`. Es ändert **nichts** an `auftraege/AP-05v.md` oder
`engine/campaigns.py` — beide sind korrekt.

## Der Befund (OF-51, gemeldet vom günstigen Modell bei AP-05k)

Die vertragstreue Implementierung von `engine/campaigns.py` scheiterte an
den drei Financing-Tests. Ursache: Die Fixtures in
`_gerollte_kette()`/`test_financing_kandidat_*` gaben der Gegenkette
(`call`) versehentlich **dieselbe Expiry** wie das letzte Glied der
Bestandskette (bzw. wie die Put-Kette im Fall ohne Roll) — damit erfüllte
jedes der drei Testpaare **zugleich** alle vier Bedingungen des
IC-Kandidaten (Vertrag 4): gleicher Basiswert, gegenläufige Seiten, gleiche
Expiry am letzten Glied, überlappende Intervalle. Insbesondere
`test_financing_kandidat_ohne_roll_kein_kandidat` ist wortwörtlich der
Lehrbuch-IC aus Entscheidung 1 — `assert ... == ()` widerspricht dem
eigenen Vertrag.

Das günstige Modell hat das von Hand nachgerechnet (nicht mit der
Prädikatfunktion der eigenen Implementierung), zwei mögliche
Kunstgriffe benannt und **beide als vertragsfremd verworfen**, statt
einen davon einzubauen — genau richtig nach Regel 1/1a/10.

## Die Korrektur

Einzige Änderung: Die Expiry der Gegenkette (`call`) in den drei
Financing-Tests wird von der Expiry der Bestandskette **entkoppelt**, nach
demselben Isolationsmuster wie im IC-Block (jeder Test sperrt genau eine
Bedingung). Gewählt: `date(2026, 11, 20)` — verschieden von der
Roll-Zielexpiry `2026-10-16` (`_gerollte_kette`s hartcodierte
`conid_neu`-Expiry) und von `2026-09-18` (Expiry im Fall ohne Roll).

**Ausdrücklich freigegeben, nur diese drei Stellen:**

- `test_financing_kandidat_erkannt`: `call`s `expiry=date(2026, 10, 16)` →
  `date(2026, 11, 20)`.
- `test_financing_kandidat_ausserhalb_fenster_kein_kandidat`: dieselbe
  Änderung.
- `test_financing_kandidat_ohne_roll_kein_kandidat`: `call`s
  `expiry=date(2026, 9, 18)` → `date(2026, 11, 20)`.

Die Prüflogik ändert sich nicht: Jeder Test prüft weiterhin exakt dieselbe
Financing-Bedingung wie zuvor benannt (erkannt/außerhalb Fenster/ohne
Roll) — es ändert sich nur, dass die Fixtures die IC-Bedingung nicht mehr
nebenbei miterfüllen.

## Abnahme

- Alle 9 Tests in `tests/test_campaigns.py` grün.
- `ruff check .` sauber, gesamte Suite grün.
- `git diff` zeigt unter `tests/` ausschließlich die drei genannten
  Expiry-Werte in `tests/test_campaigns.py`; `engine/campaigns.py`
  unverändert gegenüber der AP-05k-Umsetzung.
