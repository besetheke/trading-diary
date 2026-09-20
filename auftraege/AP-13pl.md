---
titel: Abnahmebasis erweitern - Close und Close Time als '-' bei laufenden Trades (OF-37)
modell: stark
status: fertig
abhaengig_von: AP-13pk
aendert_tests: ja
---

# AP-13pl · `Close` und `Close Time` als `-`

Korrekturpaket nach CLAUDE.md, Regel 1a, und Vorbereitungspaket nach Plan
§11.2: Dieses Paket erweitert die Abnahmebasis des OptionApp-Parsers um einen
Fall, den die Referenzexporte aus §6.1 nicht enthielten. **Es implementiert
nichts.** Die Umsetzung ist danach AP-13q (günstiges Modell).

## Der Befund (OF-37)

`ingest/optionapp.py` bricht an zwei von drei realen OA-Exporten ab:

> `'Close Time' folgt nicht dem Format JJJJ/MM/TT hh:mm:ss: '-'`

Gemessen über alle drei realen Exporte — nur Zählwerte und
Aufzählungswerte, keine Kontodaten (Regel 2):

| Datei | Datenzeilen | `Close`/`Close Time` beide `-` | zugehöriger `Status` |
|---|---|---|---|
| 2026-01 | 268 | 187 | 179 × `CANCELED`, 8 × `RUNNING` |
| 2026-02 | 66 | 0 | — |
| 2026-08 | 178 | 24 | 24 × `PARTIALLY STOPPED` |

**Drei Befunde, die den Vertrag festlegen:**

1. **`Close` und `Close Time` tragen den Strich immer gemeinsam.** In 211
   betroffenen Zeilen gibt es keine einzige, in der nur eine der beiden
   Spalten `-` trägt. Ein einseitiger Strich ist damit kein beobachteter
   Zustand.
2. **Beide Spalten brechen ab**, nicht nur eine. `Close Time` fällt zuerst
   auf (`_zeitwert`, Zeile 303), `Close` würde unmittelbar danach in
   `_zahlzelle` an `Decimal('-')` scheitern (Zeile 318). Wer nur `_zeitwert`
   repariert, verschiebt den Abbruch um fünfzehn Zeilen.
3. **`-` heißt „noch nicht geschlossen"** — dieselbe Bedeutung wie bei der
   bereits vertraglich geregelten Spalte `Stops` (Vertrag 3: `-` heißt „kein
   Stop"). Die Quelle benutzt den Strich durchgehend als „gibt es nicht",
   nicht als Zahl und nicht als Datum.

Vertrag 8 (AP-13p) sah für `Close`/`Close Time` bisher nur „gefüllt" oder
„leer" vor. Das war an den beiden Referenzexporten gemessen richtig — sie
enthielten ausschließlich abgeschlossene Trades. Der reale Bestand kennt
einen dritten Fall.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Ein neues Fixture** `fixtures/optionapp/oa_laufend.xlsx`, erzeugt durch
  eine Ergänzung in `fixtures/optionapp/erzeugen.py`. Drei Zeilen, je eine
  je beobachtetem Status, alle mit `Close = "-"` **und** `Close Time = "-"`:
  - `[3001]`, Status `CANCELED`
  - `[3002]`, Status `RUNNING`
  - `[3003]`, Status `PARTIALLY STOPPED` — diese Zeile trägt zusätzlich
    einen gesetzten Stop (`Stops = "14.4"`), damit der Test belegt, dass
    `stop_wert` vom Strich in `Close` unberührt bleibt.

  Werte frei erfunden, wie bei den vier bestehenden Fixtures. Strikes,
  Mengen und `Profit` folgen der Grammatik aus
  `auftraege/AP-13-anhang-oa-format.md`.

- **Zwei neue Tests** in `tests/test_ingest_optionapp.py`:
  - `test_strich_in_close_und_close_time_heisst_offen` — alle drei Trades
    werden gebucht, `schluss_preis is None` und `schluss_zeit is None`, die
    Rohwerte von `Status` bleiben erhalten.
  - `test_strich_laesst_uebrige_felder_unberuehrt` — an `[3003]`:
    `stop_wert == Decimal("14.4")`, `profit` und `offen_preis` sind gelesen,
    die Legs sind vollständig angelegt.

- **Eine Ergänzung an Vertrag 8** in `auftraege/AP-13p.md` — ein Satz, der
  den Strich neben „leer" stellt und auf dieses Paket verweist. Der übrige
  Vertrag bleibt Wort für Wort unverändert.

**Nicht freigegeben:** Die bestehenden vier Fixtures und die 16 bestehenden
Tests bleiben unangetastet. Insbesondere bleiben `oa_standard.xlsx` und
damit die Erwartung „vier Trades, elf Legs" unverändert — der neue Fall
bekommt eine eigene Datei, gerade damit keine bestehende Erwartung
verschoben wird.

## Vertrag an die Umsetzung (AP-13q)

1. **`-` in `Close` und `Close Time` wird wie „leer" behandelt:**
   `schluss_preis` und `schluss_zeit` bleiben `None`, der Trade wird
   gebucht. Kein Abbruch.
2. **Nur der exakte Strich**, nach `strip()`. Jeder andere unlesbare Wert
   bricht weiterhin mit Nennung des Gefundenen ab — der Vertrag wird um
   einen benannten Wert erweitert, nicht um eine allgemeine Nachsicht.
   `"--"`, `"n/a"` oder ein leerer Punkt sind weiterhin Fehler.
3. **Beide Spalten**, nicht nur `Close Time`.
4. **Kein Statusbezug.** Die Behandlung hängt am Zellwert, nicht am
   `Status`. Der Parser leitet aus `CANCELED` nichts ab; Vertrag 9 gilt
   unverändert (Rohwert speichern, nicht abbilden).
5. **Der Rest von Vertrag 8 bleibt:** eine leere Zelle bedeutet weiterhin
   dasselbe.

## Abnahme

- Die zwei neuen Tests sind rot, solange `ingest/optionapp.py` unverändert
  ist, und grün, sobald der Vertrag erfüllt ist.
- Die 16 bestehenden Tests bleiben unverändert und grün.
- `fixtures/optionapp/erzeugen.py` erzeugt alle fünf Fixtures
  reproduzierbar.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_ingest_optionapp.py`, `fixtures/optionapp/erzeugen.py`,
  `fixtures/optionapp/oa_laufend.xlsx` und `auftraege/AP-13p.md`.
  **Kein `ingest/`.**

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung im Parser. Keine Änderung an der Behandlung von `Status`.

**Nebenbefund, nicht Teil dieses Pakets:** Die realen Exporte enthalten den
Statuswert `EXPIRED (estimated)` (Februar 1 ×, August 8 ×), der in den
Referenzexporten nicht vorkam. Vertrag 9 deckt ihn bereits ab — Rohwert
speichern, nicht abbilden —, es besteht also kein Defekt. Erwähnt, damit
niemand ihn später für einen hält.
