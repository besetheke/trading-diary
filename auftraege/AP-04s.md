---
titel: Abnahmebasis für die Kettensicht-Zuordnung (erster Ausschnitt, engine)
modell: stark
status: fertig
abhaengig_von: AP-04
aendert_tests: ja
---

# AP-04s · Abnahmebasis für die Kettensicht-Zuordnung

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-04sk (günstiges Modell).

Fachliche Grundlage: Plan §5, „Zwei Sichten auf dieselben Ausführungen",
und §6, AP-04s. Die Grundsatzentscheidung „Ausführung zählt doppelt" ist
in `OFFENE_FRAGEN.md`, OF-52, bereits getroffen.

**Bewusst risikoarm zugeschnitten — erster Ausschnitt, wie schon bei
AP-13 (v/w getrennt).** Dieses Paket liefert nur die **Engine-seitige
Zuordnung** (die zweite Leg-Zuordnung über dieselben Ausführungen). Kein
`sicht`-Feld, keine Migration, keine Persistenz, kein `journal rebuild`
— das ist ein eigenes, noch nicht begonnenes Folgepaket. Erst wenn die
Zuordnung selbst steht und geprüft ist, lohnt sich die (große) Migration
über `legs`/`structures`/`chains`/`chain_links`.

## Die Grundsatzentscheidung (OF-52) — zur Erinnerung

Eine Ausführung, die laut OA ihren **eigenen** Vorgang eröffnen sollte
(`oa_rolle = 'Open Order'`), aber vom kontoweiten FIFO-Abgleich (AP-03)
als Schließung eines **anderen** Vorgangs verbraucht wurde (206 von
5.598 Ausführungen, OF-36): Sie **zählt doppelt** — sie schließt den
alten Vorgang (Kontosicht, unverändert) **und** eröffnet den eigenen
(Kettensicht, neu).

## Zu bauen

Ein einziges neues Modul: `engine/kettensicht.py`, mit einer Funktion:

```python
def kettensicht_legs(
    konto_legs: Iterable[Leg],
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
    kapitalmassnahmen: Iterable[Mapping] = (),
) -> tuple[Leg, ...]
```

Nimmt die bereits gebildeten Kontosicht-Legs (`engine.matching.bilde_legs()`,
unverändert) und liefert die Kettensicht-Legs — eine Obermenge mit
gezielten Ergänzungen/Entfernungen (siehe Ablauf). **Kein Eingriff** in
`engine/matching.py`, `engine/structures.py`, `engine/chains.py` — die
Kettensicht speist beide anschließend **unverändert**, nur mit diesem
anderen Leg-Satz als Eingabe (derselbe Aufruf, zweimal: einmal mit
Kontosicht-Legs, einmal mit Kettensicht-Legs).

## Ablauf (verbindlich)

1. **Umgeleitete Ausführungen erkennen.** Eine Ausführung `E` ist
   umgeleitet, wenn: `E.ereignistyp == 'trade'` **und**
   `E.oa_rolle == 'Open Order'` **und** `E.oa_trade` gesetzt **und** `E`
   als `close_exec_id` eines Kontosicht-Legs `L` auftritt **und** die
   eröffnende Ausführung von `L` (`executions[L.open_exec_id]`) ein
   anderes `oa_trade` trägt (oder keines).
2. **Freie Ausführungen bestimmen.** Frei ist jede Ausführung, die in der
   Kontosicht eine **offene** (nie geschlossene) Eröffnung ist
   (`open_exec_id` eines Legs mit `close_exec_id is None`).
3. **Je umgeleiteter Ausführung `E`**: einen eingeschränkten
   Ausführungspool bilden — alle Ausführungen mit demselben `oa_trade`
   und demselben `conid` wie `E`, plus `E` selbst, **aber nur, wenn sie
   frei sind** (Schritt 2) oder `E` selbst sind. `engine.matching.
   bilde_legs()` auf diesem Pool aufrufen (Wiederverwendung, kein Nachbau
   der FIFO-Logik) und daraus das Leg mit `open_exec_id == E` übernehmen
   — das ist die neue, eigene Struktur-Eröffnung von `E`s Vorgang.
4. **Verbrauchte freie Ausführungen aus der Kontosicht entfernen.** Findet
   Schritt 3 eine Schließung `F` (eine zuvor freie Ausführung), entfällt
   `F`s ursprüngliches Kontosicht-Leg (das offene) aus der Kettensicht —
   `F` schließt jetzt `E`s Struktur, nicht mehr sich selbst als
   unrealisierte Eröffnung.
5. **Kein freier Schließer gefunden.** Die neue Struktur bleibt offen
   (`close_exec_id = None`, `brutto_pnl = None`) — **keine
   mehrstufige Neuzuordnung**, keine Kaskade über eine dritte,
   unbeteiligte Ausführung (Grenzen).
6. Rückgabe: alle unveränderten Kontosicht-Legs (abzüglich der in Schritt
   4 entfallenen) plus die neuen Legs aus Schritt 3.

## Die Stelle, an der erfahrungsgemäß geraten wird

**Schritt 2/4 ist keine Nebensächlichkeit, sondern der Kern.** Eine erste,
naive Fassung (nur „Kontosicht-Legs plus ein neues Leg für `E`") verwendet
die gefundene Schließung `F` **zweimal innerhalb derselben Sicht** — einmal
in ihrem alten, jetzt überholten Kontosicht-Leg (offen, nie realisiert),
einmal als Schließung von `E`s neuer Struktur. Das ist kein „doppelt" im
Sinne von OF-52 (das gilt nur für die ursprünglich umgeleitete Ausführung
`E`, **über zwei verschiedene Sichten**), sondern ein Fehler **innerhalb
einer** Sicht. Nur eine zuvor **freie** (unrealisierte) Ausführung darf
umgewidmet werden, und ihr altes (offenes) Leg muss dabei entfallen.

**Wenn keine freie Ausführung existiert**, bleibt die neue Struktur
offen — das ist die bewusst gewählte, konservative Grenze dieses Pakets
(siehe „Grenzen"), keine zu behebende Lücke.

## Wo du abschreiben sollst statt neu zu erfinden

- **FIFO-Matching wiederverwenden, nicht nachbauen**: `engine.matching.
  bilde_legs()` — dieses Paket ruft es zweimal auf (einmal implizit schon
  geschehen für `konto_legs`, einmal für den eingeschränkten Pool je
  umgeleiteter Ausführung), niemals eine eigene FIFO-Schleife schreiben.
- **`Leg`-Felder**: `engine/matching.py`, Dataclass `Leg`.

## Grenzen

- **Keine Kaskaden über mehr als eine Stufe.** Schließt die gefundene
  freie Ausführung `F` selbst wieder eine DRITTE, an anderer Stelle
  benötigte Struktur, wird das nicht aufgelöst — `F` zählt hier als
  „verfügbar", Punkt. Mehrstufige Umleitungen (in der echten Historie
  bisher nicht beobachtet, OF-36 spricht von „genau einem" fehlenden
  Bein je Fall) sind ein möglicher Gegenstand eines späteren
  Korrekturpakets, nicht dieses hier.
- Kein Eingriff in `engine/matching.py`, `engine/structures.py`,
  `engine/chains.py`.
- Keine Migration, keine Persistenz, keine API, keine Oberfläche, kein
  `sicht`-Feld — eigenes Folgepaket.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_kettensicht.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- Mindestens ein Test zeigt die **eigentliche Wirkung**: Ein Vorgang, dem
  in der Kontosicht (`bilde_structures()` auf den unveränderten Legs) ein
  Bein fehlt, hat in der Kettensicht (`bilde_structures()` auf
  `kettensicht_legs()`) die vollständige Struktur.
- `git diff --stat` zeigt ausschließlich `engine/kettensicht.py`.
