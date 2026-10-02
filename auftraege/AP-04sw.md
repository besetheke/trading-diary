---
titel: Persistenz der Kettensicht (sicht-Feld, Migration, Wiring)
modell: stark
status: fertig
abhaengig_von: AP-04sk
---

# AP-04sw · Persistenz der Kettensicht

**Kein Vorbereitungspaket mit separater Umsetzung.** Durchgehend vom
starken Modell gebaut — begründet unten unter „Warum kein
Umsetzungspaket".

## Worum es geht

Die zweite Hälfte von AP-04s (Plan §5, „Zwei Sichten"): `sicht` als
Pflichtfeld in `legs`/`structures`/`chains`/`chain_links`, Wiring von
`engine.kettensicht.kettensicht_legs()` in `journal rebuild`, und die
Absicherung, dass keine bestehende Abfrage (API, `journal/durchsicht.py`,
Tests) die beiden Sichten vermischt.

## Gebaut

- **Migration** `migrations/versions/b7f4e2a8c1d5_ap04sw_sicht_feld.py`:
  `sicht` (Text, `server_default='konto'`, Check `IN ('konto','kette')`)
  auf allen vier Tabellen. `natur_schluessel` ist an `structures`/`chains`
  jetzt nur noch zusammen mit `sicht` eindeutig
  (`uq_{structures,chains}_natur_schluessel_sicht`). Hoch- und
  Herunterstufen gegeneinander getestet.
- `journal/schema.py` entsprechend erweitert.
- **`journal/rebuild.py`**: `_struktur_zeile()`/`_kette_zeile()` nehmen
  jetzt `sicht` entgegen. Neue Funktion `_sicht_schreiben()` kapselt die
  komplette Struktur-/Ketten-/Leg-/Kettenglied-Schreiblogik für **eine**
  Sicht (Naturschlüssel-Abgleich jetzt je Sicht gefiltert) und wird in
  `_rebuild_laufen()` zweimal aufgerufen: einmal mit `matching.legs`
  (Kontosicht, unverändertes Verhalten), einmal mit
  `kettensicht_legs(...)` (neu, `sicht='kette'`, kein Override-Schutz —
  Grenze von AP-04s). `RebuildErgebnis.legs/structures/chains/
  chain_links` behalten ihre bisherige Bedeutung (Kontosicht-Zählung,
  Rückwärtskompatibilität); vier neue `*_kette`-Felder kommen hinzu.
  Overrides/OA-Abgleich/Campaign-Sichtbarkeit laufen unverändert nur auf
  der Kontosicht.
- **`api/app.py`**: `/ketten` filtert jetzt grundsätzlich auf
  `sicht='konto'` — die einzige Stelle, die mehrere Zeilen liefern könnte;
  die Detail-Routen holen ohnehin per Primärschlüssel.
- **`journal/durchsicht.py`**: unverändert in der Logik, aber durch die
  Migration abgesichert — siehe Befund 1.

## Drei Befunde, erst beim tatsächlichen Durchlauf sichtbar (nicht beim Entwurf)

1. **Fünf bestehende Testdateien griffen ungefiltert auf `structures`/
   `chains`/`chain_links` zu** und erwarteten implizit „genau eine Zeile
   je Naturschlüssel" — das war wahr, bis es zwei Sichten gab.
   `tests/test_rebuild.py` (`_zeilen()`), `tests/test_rebuild_oa.py`
   (`_kette_zeile()`, `_struktur_zeilen()`), `tests/test_campaigns_sicht.py`
   (`_chain_ids()`), `tests/test_api_lesen.py` (eine Inline-Abfrage),
   `tests/test_durchsicht.py` (eine Inline-Abfrage) ergänzt um
   `sicht='konto'`. **Keine Erwartung geändert** — nur die Abfrage
   korrigiert, die jetzt mehrdeutig wäre. `_zeilen()`/`_kette_zeile()`
   filtern automatisch, wo die Tabelle eine `sicht`-Spalte hat, damit die
   rund 35 Aufrufer in `test_rebuild.py` selbst unverändert bleiben.
2. **Synthetische Zuteilungs-Fortsetzungen fehlten.** `bilde_chains()`
   legt sie erst nach der Strukturbildung an; `bestand_berechnen()` holt
   sie seit AP-04d nach, meine erste Fassung von `_sicht_schreiben()`
   nicht — `KeyError` bei jeder Zuteilung mit zwei Legs. Behoben durch
   eine gemeinsame Funktion `_struktur_je_schluessel_mit_synthetischen()`,
   jetzt von beiden Stellen genutzt (keine zweite Kopie der Logik).
3. **Die API hätte ohne Filter sofort doppelt so viele Ketten gezeigt** —
   genau das Risiko, das Plan §5 ausdrücklich ausschließt („keine Abfrage
   liefert Zeilen aus beiden Sichten").

## Warum kein Umsetzungspaket

Dieser Umbau berührt den gemeinsamen Lesepfad (`bestand_berechnen()`,
auch von `journal/durchsicht.py` genutzt), drei Module und fünf
Bestandstests gleichzeitig — eine Schnittstelle zu bestehenden Systemen,
keine Fleißarbeit gegen einen fertigen Vertrag. Alle drei Befunde oben
wurden ausschließlich durch tatsächliches Ausführen gefunden, nicht durch
Lesen des Vertrags — ein als Vertrag weitergereichtes Umsetzungspaket
hätte dieselben drei Fallstricke ohne Sicherheitsnetz wiederholt.

## Grenzen

- Kein Override-Mechanismus für die Kettensicht (wie AP-04s/AP-04sk).
- Keine API-Route für die Kettensicht — nur Persistenz, keine
  Oberfläche.
- Kein Eingriff in `engine/*`.

## Abnahme

- `tests/test_rebuild_kette.py` (neu, 7 Tests): Pflichtfeld in jeder
  Tabelle, Rückwärtskompatibilität der bestehenden `RebuildErgebnis`-Felder,
  die eigentliche Wirkung (Vorgang B ist in der Kontosicht einbeinig, in
  der Kettensicht zweibeinig), die erlaubte Jahresabgrenzungs-Abweichung,
  Abgleich-statt-Neuanlage über zwei Läufe, `journal/durchsicht.py`
  bleibt eindeutig, `/ketten` liefert nur die Kontosicht.
- Volle Suite grün (inklusive der fünf angepassten Bestandsdateien),
  `ruff check .` sauber.
- `git diff --stat`: `api/app.py`, `journal/rebuild.py`,
  `journal/schema.py`, `migrations/versions/
  b7f4e2a8c1d5_ap04sw_sicht_feld.py`, `tests/test_rebuild_kette.py` (neu),
  plus die fünf oben genannten Testdateien (nur Abfrage-Filter, keine
  Erwartung geändert).
