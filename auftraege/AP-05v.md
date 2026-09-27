---
titel: Abnahmebasis fuer Campaign-Kandidaten (engine/campaigns.py)
modell: stark
status: offen
abhaengig_von: AP-04
aendert_tests: ja
---

# AP-05v · Abnahmebasis für Campaign-Kandidaten

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-05k (günstiges Modell).

Fachliche Grundlage: Plan §6, AP-05, Abschnitt „Kandidatenregeln (Vorschlag,
keine Automatik)". Dieses Paket baut nur die **Erzeugung** der beiden dort
genannten Kandidatentypen — reine Berechnung über bereits gebildete Ketten,
kein Klassifikationsdialog, keine Persistenz, keine API. Das ist bewusst so
geschnitten: Genau in dieser Form wurden die Rollkandidaten aus AP-04k
zuerst gebaut, bevor die Durchsicht (AP-04d) und später eine Oberfläche
draufsetzten.

## Die drei Entscheidungen, die nicht beim Umsetzer liegen

**1. „Gleichzeitig offen" heißt zeitliche Überlappung, nicht „beide jetzt
offen".** Der Plan verlangt „beide Ketten gleichzeitig offen, keine
zwischenzeitliche Schließung". Eine Kette schließt per Definition genau
einmal — es gibt kein Wiederöffnen (`Chain.beendet_am` ist gesetzt oder
nicht, ein Zwischenzustand existiert nicht). „Keine zwischenzeitliche
Schließung" ist damit automatisch erfüllt, sobald man **Zeitintervalle**
vergleicht: `[eroeffnet_am, beendet_am oder unbegrenzt)`. Zwei Ketten sind
IC-Kandidat, wenn diese Intervalle sich überschneiden — unabhängig davon,
ob beide heute noch offen sind. Das erlaubt auch die rückwirkende
Klassifikation abgeschlossener Kampagnen, nicht nur die Live-Beobachtung.

**2. Verglichen wird die aktuelle Seite der Kette, nicht ihre Historie.**
Eine Kette kann über Rolls die Expiry wechseln. „Gleiche Expiry" beim
IC-Kandidaten bezieht sich auf das **letzte Glied** (`glieder[-1]`) —
den Zustand, der gerade gilt. Rechte/Seite kommen aus `Chain.seite`, das
ist bereits über die gesamte Kette gebildet (Call/Put/n.a.) und wird
unverändert übernommen.

**3. Das Financing-Zeitfenster ist 24 Stunden, als Annahme markiert.**
Der Plan nennt „im zeitlichen Umfeld eines Rolls", ohne Zahl. Gemessen am
echten Bestand (nur Zählwerte, Regel 2): 161 Kandidatenpaare bei 1 Stunde,
351 bei 6, 518 bei 24, 1.029 bei 72, 2.193 bei einer Woche — kein
natürlicher Sprung, der eine Grenze nahelegt. **24 Stunden** (ein
Handelstag) ist die plausibelste Lesart von „im Umfeld" und wird als
Annahme in `OFFENE_FRAGEN.md` festgehalten, nicht stillschweigend gesetzt
— anders als beim Rollkandidatenfenster gibt es hier noch keine
Nutzer-Stichprobe, die den Wert bestätigt. Der Wert ist ein benannter
Modulwert, keine Zahl im Code.

**Größenordnung, zur Einordnung:** Bei 24 Stunden ergeben sich rund 500
Financing- und rund 3.240 IC-Kandidatenpaare über die gesamte Historie.
Das ist bewusst großzügig — die Kandidatenliste behauptet nichts (Plan §6,
Block B, Regel 5 gilt sinngemäß: ein Vorschlag ist keine Tatsache); eine
spätere Oberfläche muss filtern und sortieren können, ist aber nicht Teil
dieses Pakets.

## Ausdrücklich freigegebene Änderungen

Nur diese, keine weiteren.

- **Neue Testdatei** `tests/test_campaigns.py` — springt still ab, solange
  `engine/campaigns.py` fehlt.
- **Ergänzung in `OFFENE_FRAGEN.md`**: die 24-Stunden-Annahme aus
  Entscheidung 3, mit den gemessenen Werten.

Kein bestehender Test, kein bestehendes Fixture wird angefasst.

## Vertrag an die Umsetzung (AP-05k)

### Modul

1. **`engine/campaigns.py`**, rein wie jedes Engine-Modul (Regel 6): keine
   Datenbank, keine Uhrzeit, kein Zufall.
2. **`CampaignKandidat`** als `@dataclass(frozen=True)`:
   `typ: str` (`"ic"` oder `"financing"`), `kette_a: Chain`,
   `kette_b: Chain`. `kette_a` ist stets die **chronologisch früher
   eröffnete** der beiden Ketten (`eroeffnet_am`, bei Gleichstand der
   Naturschlüssel — siehe Punkt 5); bei „financing" ist das genau die
   Bestandskette mit dem Roll, das ergibt sich zwangsläufig aus der Regel.
3. **`campaign_kandidaten(chains: Iterable[Chain]) -> tuple[CampaignKandidat, ...]`**
   als einzige öffentliche Funktion.

### IC-Kandidat

4. Zwei Ketten sind ein IC-Kandidat, wenn **alle** zutreffen:
   - gleiches `underlying`,
   - `Chain.seite` beider ist gesetzt und **unterschiedlich** — eine
     `"Call"`, die andere `"Put"` (nicht `"n.a."`, nicht `None`),
   - die `expiry` des jeweils **letzten Glieds** (`glieder[-1].structure.expiry`)
     ist bei beiden gesetzt und **identisch**,
   - die Intervalle `[eroeffnet_am, beendet_am oder unbegrenzt)` beider
     Ketten überschneiden sich (Entscheidung 1).

### Financing-Kandidat

5. Eine Bestandskette A und eine neue Kette B sind ein Financing-Kandidat,
   wenn:
   - A mindestens ein Glied mit `verknuepfungstyp == "roll"` hat,
   - `Chain.seite` beider ist gesetzt und **unterschiedlich** (dieselbe
     Bedingung wie beim IC-Kandidaten — „Gegenseite"),
   - gleiches `underlying`,
   - B in `FINANCING_FENSTER` (Entscheidung 3, 24 Stunden) um den
     **frühesten** Rollzeitpunkt von A eröffnet wurde:
     `|B.eroeffnet_am − erster_roll_zeitpunkt(A)| <= FINANCING_FENSTER`.
     Der Rollzeitpunkt eines Glieds ist dessen `eroeffnet_am`
     (`structure.eroeffnet_am` des rollenden Glieds — der Moment, in dem
     die Fortsetzung entstand).
   - A und B sind nicht dieselbe Kette.

### Determinismus

6. **Naturschlüssel für Ketten, lokal im Modul** (Regel 6 verbietet den
   Import aus `journal.rebuild`, dasselbe Muster wie
   `journal/preise.py._schluessel`): `"k:" +` die sortierten
   `open_exec_id` der Legs des **ersten** Glieds, mit `|` verbunden.
7. **Sortierung des Ergebnisses:** aufsteigend nach `typ`
   (`"financing"` vor `"ic"`, alphabetisch), dann nach dem Naturschlüssel
   von `kette_a`, dann von `kette_b`. Das Ergebnis hängt nicht von der
   Reihenfolge der Eingabe ab.

## Abnahme

- `tests/test_campaigns.py` läuft vollständig grün, sobald
  `engine/campaigns.py` existiert.
- Alle übrigen Tests bleiben grün, `ruff check .` sauber.
- `git diff --stat` der Umsetzung zeigt ausschließlich `engine/campaigns.py`.

## Ausdrücklich nicht Teil dieses Pakets

Kein Klassifikationsdialog, keine Persistenz (`campaign_links`), keine
API, keine Oberfläche. Keine Unterscheidung, welche Seite die „geplante"
IC-Seite und welche die Gegenfinanzierung ist — das ist laut Plan eine
Absichtsfrage und bleibt beim Nutzer.
