---
titel: Abnahmebasis des OA-Parsers erweitert - Trade mit einem Leg (OF-67)
modell: stark
status: fertig
abhaengig_von: AP-13pn
aendert_tests: ja
---

# AP-13pp · Trade mit nur einem Leg

Korrekturpaket nach CLAUDE.md, Regel 1a (`aendert_tests: ja`, `modell: stark`),
**implementiert nichts**. Die Parsernachbesserung ist AP-13t (günstiges Modell).

## Befund (OF-67)

Der echte Import des Gesamtexports (`journal import-optionapp`, 05.10.2026)
brach ab: `Zeile … (Trade …): 'Strikes' zerfällt in 1 Legs, erwartet sind zwei
bis vier (Anhang)`. Der Gesamtexport enthält unter 1.383 ausgeführten Trades
einen mit **einem** Leg (SPX, CLOSED). Die Untergrenze „zwei Legs" stammte aus
den ersten Referenzexporten (244 Trades) und war eine Beobachtung, keine Regel;
Plan §6.1 kennt n-Leg-Strukturen, die Strukturtypen kennen `Single`.

Vorab geprüft (nur Zählwerte): Mit der Grenze 1–4 läuft der **gesamte** Import
in eine temporäre Datenbank durch — 5.358 Trades, 4.391 Legs, keine weitere
Zeile scheitert. Es ist also genau diese eine Stelle.

## Was dieses Paket festlegt (nichts Bestehendes geändert)

- Ein Trade darf ein bis vier Legs tragen; die **Obergrenze vier bleibt**.
- Neue Fixtures `oa_ein_leg.xlsx` (Trade 5301) und `oa_fuenf_legs_defekt.xlsx`
  (Trade 5401, Gegenprobe), erzeugt aus `fixtures/optionapp/erzeugen.py`
  (nur die zwei neuen Dateien; die bestehenden Fixtures byteweise unverändert).
- Zwei neue Tests am Ende von `tests/test_ingest_optionapp.py`, keine bestehende
  Assertion geändert. Vertragstext AP-13p (Vertrag 5) und Anhang berichtigt.

## Prüfung der Abnahmebasis (vor der Abgabe)

Ohne Änderung rot allein an `test_trade_mit_einem_leg_wird_gelesen`
(`ValueError … zerfällt in 1 Legs`); gegen eine Wegwerf-Grenze `1 <= len(teile)
<= 4` 33/33 grün; danach zurückgesetzt.
