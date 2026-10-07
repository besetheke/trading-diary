---
titel: Abnahmebasis Overrides (bestätigte Rolls) auch in der Kettensicht (OF-61)
modell: stark
status: fertig
abhaengig_von: AP-04sw, AP-04sy
aendert_tests: ja
---

# AP-04sz · Abnahmebasis: `chain_overrides` in der Kettensicht

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-04szk (günstiges Modell). Neue Testdatei
`tests/test_rebuild_overrides_kette.py` (7 Tests), keine bestehende
Erwartung wird geändert.

## Entscheidung (OF-61)

Ein Override ist eine Aussage über das reale Geschehen („diese Struktur setzt
jene Kette fort"). Der Nutzer gibt sie **einmal, in der Kontosicht**, wo seine
Listen stehen. Die Kettensicht **übernimmt** sie, sie bekommt keine eigenen
Overrides.

## Regel

1. Nach dem Anwenden in der Kontosicht wird jeder **bestätigte** Override in
   die Kettensicht übersetzt: Struktur und Kette der Kontosicht werden über
   ihren **Naturschlüssel** (`structures.natur_schluessel`,
   `chains.natur_schluessel`) auf die Zeilen derselben Schlüssel in der
   Kettensicht abgebildet.
2. Existieren beide Schlüssel in der Kettensicht, wird der Override dort wie
   in der Kontosicht angewandt (Struktur in die Zielkette hängen, Erkennung
   `manuell`, Reihenfolge und Kennzahlen der Kette nachziehen, leer gewordene
   Kette entfällt) — `chain_links` mit `sicht = 'kette'`.
3. Fehlt einer der beiden Schlüssel in der Kettensicht (sie hat dort andere
   Strukturen, wo Ausführungen umgeleitet sind, OF-68), wird der Override
   dort **nicht** angewandt und gezählt. Das ist kein Fehler.
4. **Abgelehnte** Urteile ändern die Kettensicht nicht und werden nirgends
   gezählt (Rollkandidaten sind ein Kontosicht-Konzept).
5. `chain_overrides` selbst bleibt unverändert (Regel 4). Die Kontosicht-Zähler
   `overrides_angewandt`/`overrides_verwaist` behalten ihre Bedeutung.
6. `RebuildErgebnis` bekommt zwei neue Zähler mit Standardwert 0:
   `overrides_kette_angewandt`, `overrides_kette_ohne_entsprechung`. Die
   Ausgabe von `journal rebuild` ändert sich nicht.
7. Nicht geändert: Die OA-Werte werden danach wie bisher geschrieben.

## Bekannte Grenze

Die Überlappung (Kettensicht-Struktur enthält die Eröffnungen der
Kontosicht-Struktur, ohne gleichen Schlüssel) wird bewusst **nicht** aufgelöst.
Das wäre Raten; solche Overrides zählen unter „ohne Entsprechung". Sollte die
Zahl am Echtbestand relevant werden, folgt ein eigenes Paket.

## Abnahme

`tests/test_rebuild_overrides_kette.py` grün, alle bisherigen Tests
unverändert grün, `ruff check .` sauber. Gegen eine Wegwerf-Umsetzung
geprüft: ohne sie schlagen 5 von 7 Tests fehl, mit ihr laufen alle grün.
