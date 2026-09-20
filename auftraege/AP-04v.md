---
titel: Abnahmebasis fuer die AP-04-Persistenz (rebuild, Overrides)
modell: stark
status: offen
abhaengig_von: AP-04
aendert_tests: ja
---

# AP-04v · Abnahmebasis für die Persistenz

Vorbereitungspaket nach Plan §11.2, Schritt 1: Das starke Modell schreibt
Tests, Fixtures und Migration, das günstige implementiert dagegen.
**Dieses Paket implementiert die Persistenz nicht.** Die Umsetzung ist
danach AP-04p (günstiges Modell).

## Ausgangslage

`engine/matching.py`, `engine/structures.py` und `engine/chains.py` sind
fertig, rein (Regel 6) und gegen die Golden-Historie geprüft — aber sie
rechnen ausschließlich im Speicher. **Nichts davon steht in der
Datenbank.** Das Schema aus AP-01 hält alle Tabellen bereit (`legs`,
`structures`, `chains`, `chain_links`, `chain_overrides`,
`assignment_links`); es fehlen die Schreibschicht, das Kommando
`journal rebuild` und die Anwendung der Overrides.

Warum das ans günstige Modell geht: Die fachlichen Urteile sind gefallen
und stehen im Plan. Was bleibt, ist Abbildung auf ein festes Schema gegen
harte Tests — kein Ermessen. Und es fasst `fixtures/golden/` nicht an; alle
Fixtures dieses Pakets sind frei erfunden.

## Die zwei Entscheidungen, die nicht beim Umsetzer liegen

Sie stehen hier, weil sie sonst geraten würden.

**1. Der Rebuild ersetzt nicht durch Neuanlage, sondern gleicht ab.**
`chain_overrides` verweist per Fremdschlüssel auf `chains.chain_id` und
`structures.structure_id`. Würde ein Rebuild diese Tabellen leeren und neu
füllen, bekämen dieselben Sachverhalte neue Nummern — und jeder manuelle
Override zeigte danach auf etwas anderes oder ins Leere. Die Abnahme „Ein
Override überlebt ein vollständiges `rebuild`" (Plan §6, AP-04) wäre nicht
erfüllbar.

Deshalb tragen `structures` und `chains` einen **Naturschlüssel**, der sich
aus dem Inhalt ergibt und über Läufe hinweg gleich bleibt. Der Rebuild
gleicht über ihn ab: Bekanntes behält seine Nummer, Neues bekommt eine,
Verschwundenes wird entfernt. `legs` braucht das nicht — auf `leg_id`
verweist nichts.

**2. Ohne FX wird kein Euro-Betrag geschrieben.** `chains.netto_pnl_eur`
und `structures.netto_pnl_eur` bleiben leer. Die Umrechnung nach P4 ist
AP-06; hier einen Kurs zu unterstellen hieße raten (Regel 10). Die
Beträge in Instrumentenwährung werden vollständig geschrieben.

## Ausdrücklich freigegebene Änderungen an Tests, Fixtures und Schema

Nur diese, keine weiteren.

- **Eine neue Migration** (Regel 3, bestehende bleiben unangetastet):
  - `legs.structure_id` — Integer, nullable, FK auf `structures`, Index.
    Nullable, weil nicht jede Leg in einer Struktur landet (P7-Vorfilter,
    `nicht_strukturiert`).
  - `structures.natur_schluessel` — Text, NOT NULL, UNIQUE.
  - `chains.natur_schluessel` — Text, NOT NULL, UNIQUE.
  - Entsprechende Ergänzung in `journal/schema.py`.
- **Eine neue Testdatei** `tests/test_rebuild.py`, die still abspringt,
  solange `journal/rebuild.py` fehlt (`pytest.importorskip`, wie
  `tests/test_matching.py`).
- **Ein neues Fixture-Modul** `tests/fixtures_rebuild.py` — frei erfundene
  Ausführungen als Python-Literale, kein XML, kein Golden.

**Nicht freigegeben:** alles unter `tests/` und `fixtures/` außerhalb
dieser beiden neuen Dateien. Kein bestehender Test wird angefasst.

## Vertrag an die Umsetzung (AP-04p)

### Modul und Einstiegspunkt

1. **`journal/rebuild.py`** mit
   `rebuild(db_pfad, *, busy_timeout_ms=...) -> RebuildErgebnis`.
   **Nicht unter `engine/`** — das Modul liest und schreibt eine Datenbank
   und wäre dort ein Verstoß gegen Regel 6.
2. `RebuildErgebnis` ist ein `@dataclass(frozen=True)` mit den Zählwerten:
   `legs`, `structures`, `chains`, `chain_links`, `nicht_strukturiert`,
   `overrides_angewandt`, `overrides_verwaist`.
3. **`journal rebuild`** als Unterbefehl in `journal/cli.py`, mit `--db`
   wie `journal import`. Gibt die Zählwerte aus und liefert Rückgabewert 1,
   wenn `overrides_verwaist > 0`.

### Ablauf

4. Lesen: `executions`, `instruments`, `corporate_actions`. Die
   Kapitalmaßnahmen werden aus den `corporate_actions`-Rohzeilen nach
   `actionID` abgeleitet — **wie in
   `werkzeuge/abgleich/golden_bestandsabgleich_of23.py`**, Funktion
   `kapitalmassnahmen_ableiten()`. Sieh dort nach, statt es neu zu
   erfinden.
5. Rechnen: `bilde_legs()` → `bilde_structures()` → `bilde_chains()`.
   **Die Engine wird nicht geändert.** Fällt dabei etwas auf, ist das ein
   Eintrag in `OFFENE_FRAGEN.md` und ein Abbruch, keine Korrektur.
6. Schreiben in der Reihenfolge `structures` → `legs` → `chains` →
   `chain_links`, danach Overrides anwenden.

### Naturschlüssel

7. **Struktur:** die `open_exec_id` ihrer Legs, aufsteigend sortiert, mit
   `|` verbunden. Beispiel: `"E1|E2"`. Er ist stabil, weil `exec_id` die
   IB-`tradeID` ist und sich nicht ändert.
8. **Kette:** der Naturschlüssel ihrer **ersten** (eröffnenden) Struktur,
   mit vorangestelltem `k:`. Rolls hängen hinten an; der Kettenanfang
   bleibt derselbe.
9. **Abgleich statt Neuanlage:** Ein bekannter Naturschlüssel behält seine
   `structure_id` bzw. `chain_id`, seine Felder werden aktualisiert. Ein
   unbekannter wird angelegt. Ein Schlüssel, der nicht mehr vorkommt, wird
   gelöscht — **außer** `chain_overrides` verweist auf ihn (siehe 16).

### Felder

10. **`structures`:** `asset_class`, `typ`, `underlying`, `expiry`,
    `short_strike`, `long_strike`, `breite`, `menge`, `eroeffnet_am`,
    `geschlossen_am`, `dte_bei_eroeffnung`, `status`, `brutto_pnl`
    übernehmen die gleichnamigen Felder der `Structure`.
    `kommission` kommt aus `kommission_gesamt`.
    `strategy_id` bleibt leer (AP-05).
10a. **`netto_pnl` = `brutto_pnl` + `kommission`** — **addiert, nicht
    subtrahiert.** Kommissionen stehen mit dem Vorzeichen da, das IB
    liefert: negativ, wenn sie Geld kosten. Gemessen über die
    Golden-Historie: 23.971 Ausführungen mit negativer, 8.164 ohne und
    **340 mit positiver** Kommission — Gutschriften, die es wirklich gibt.
    Wer subtrahiert, dreht bei allen das Vorzeichen; wer `abs()` nimmt,
    macht aus den 340 Gutschriften Kosten. Bei leerem `brutto_pnl` bleibt
    `netto_pnl` leer.
11. **`structures.waehrung`** steht nicht an der `Structure` und wird aus
    den `executions` ihrer Legs gelesen. **Tragen sie verschiedene
    Währungen, ist das ein Abbruch mit Nennung des Naturschlüssels** — kein
    Vorrang, keine Wahl der häufigsten.
12. **`structures.erkennung`** hat ein eigenes Vokabular
    (`order_id`/`heuristik`/`manuell`, CHECK aus AP-01) und wird aus
    `Structure.methode` abgeleitet:
    `oa` → `order_id`, `exec_batch` → `order_id`, `zeitfenster` →
    `heuristik`. Das ist genau die Unterscheidung, die der Plan verlangt:
    über Order-ID oder über Heuristik gebildet. Das Feld
    `Structure.erkennung` der Dataclass ist **nicht** die Quelle dieser
    Spalte.
13. **`chains`:** `underlying`, `asset_class`, `seite`, `eroeffnet_am`,
    `beendet_am`, `anzahl_rolls`, `endzustand` aus der `Chain`.
    `netto_pnl_eur` bleibt leer (siehe Entscheidung 2).
14. **`chain_links`:** `sequenz`, `verknuepfungstyp` und `erkennung`
    kommen unverändert aus `ChainGlied`. `erkennung` unterscheidet bereits
    zwischen `auto` (über die Order-Nummer belegt) und `heuristik` (aus
    zeitlicher Nähe geschlossen) — **nicht überschreiben, nicht
    vereinheitlichen.**
15. **`legs`:** aus `MatchingErgebnis.legs`; `structure_id` zeigt auf die
    Struktur, in der die Leg gelandet ist, sonst leer. Vollständiger
    Austausch, kein Naturschlüssel nötig.

### Overrides

16. **`chain_overrides` wird niemals geschrieben oder gelöscht** — es ist
    Benutzerdatum (Regel 4). Der Rebuild liest es und wendet es an.
17. Eine Zeile `(chain_id, structure_id)` bedeutet: Diese Struktur gehört
    in diese Kette, was die Automatik auch gefunden hat. Anwendung: Die
    Struktur wird aus ihrer automatischen Kette gelöst und mit
    `erkennung = 'manuell'` an die genannte gehängt. Danach werden die
    Glieder der betroffenen Ketten nach `eroeffnet_am` neu durchnummeriert;
    Glied 1 trägt `verknuepfungstyp = 'open'`, alle weiteren `'roll'`.
18. Die Kennzahlen der betroffenen Ketten werden nachgezogen, nach genau
    denselben Regeln wie in `bilde_chains()`: `eroeffnet_am` ist das
    kleinste der Glieder, `anzahl_rolls` ist ihre Anzahl minus eins,
    `beendet_am` und `endzustand` nur gesetzt, wenn **alle** Glieder
    geschlossen sind — `endzustand` über
    `engine.chains.ENDZUSTAND_JE_EREIGNIS` aus dem letzten Glied,
    importiert, nicht nachgebaut.
19. Eine Kette, die durch einen Override **leer** würde, wird gelöscht.
20. **Verweist ein Override auf eine Kette oder Struktur, die es nicht
    mehr gibt**, wird die Zeile nicht gelöscht und nicht stillschweigend
    übergangen: Sie zählt in `overrides_verwaist` und wird benannt
    ausgegeben. Die betroffene Kette bzw. Struktur bleibt stehen (Regel 4).
21. **Nennt `chain_overrides` dieselbe Struktur in zwei Ketten**, ist das
    ein Abbruch mit Nennung beider Ketten. Keine Reihenfolgeregel, keine
    stille Entscheidung.
22. **`assignment_links`:** Zeilen mit `erkennung IN ('auto','heuristik')`
    werden neu geschrieben, Zeilen mit `erkennung = 'manuell'` bleiben
    unangetastet.

### Verhalten

23. **Idempotenz.** Zweimal `rebuild` hintereinander ergibt denselben
    Inhalt **und dieselben Nummern**. Das ist der Kern von Entscheidung 1
    und wird geprüft.
24. **Kurze Transaktionen, im Konfliktfall abbrechen statt blockieren**
    (Regel 9). `journal/db.py` setzt `busy_timeout` und die Pragmas bereits
    — benutze `create_db_engine()`, setze nichts selbst.
25. **Regel 4.** Ein Rebuild fasst nur `legs`, `structures`, `chains`,
    `chain_links` und die nicht-manuellen `assignment_links` an. Alles
    andere — `executions`, `instruments`, `corporate_actions`,
    `import_runs`, `chain_overrides`, `campaigns`, `campaign_links`,
    `campaign_overrides`, `journal_entries`, `tags`, `entity_tags`,
    `attachments`, `roller_link`, `strategies` — bleibt unberührt. Dass
    eine Tabelle leer ist, ist keine Erlaubnis, sie zu beschreiben.
26. **Regel 5.** Alle Geldbeträge als `Decimal` über `ExactDecimal`.
    Niemals `float`, keine Rundung.

## Abnahme

`tests/test_rebuild.py` prüft:

- **Grundlauf:** Aus einer Handvoll Ausführungen entstehen die erwarteten
  Zeilen in `legs`, `structures`, `chains`, `chain_links`; die Zählwerte im
  `RebuildErgebnis` stimmen mit dem Tabelleninhalt überein.
- **Idempotenz:** Zweimal `rebuild` — Inhalt und `structure_id`/`chain_id`
  sind identisch.
- **Zuwachs:** Ein Rebuild nach zusätzlich importierten Ausführungen lässt
  die Nummern der unveränderten Strukturen unangetastet.
- **Override überlebt:** Ein Override wird gesetzt, `rebuild` läuft, die
  Struktur hängt danach an der genannten Kette mit
  `chain_links.erkennung = 'manuell'`, und `chain_overrides` ist
  unverändert.
- **Verwaister Override** wird gezählt und benannt, nicht gelöscht.
- **Doppelter Override** bricht ab.
- **Attribution:** Eine über `exec_batch` gebildete Struktur trägt
  `erkennung = 'order_id'`, eine über das Zeitfenster gebildete
  `heuristik`; ein Zeitfenster-Roll trägt in `chain_links`
  `erkennung = 'heuristik'`.
- **Währungskonflikt** in einer Struktur bricht ab.
- **Regel 4:** Zeilen in `journal_entries` und `chain_overrides` überstehen
  einen Rebuild unverändert.
- **`netto_pnl_eur`** bleibt leer.

Ferner:

- Alle bestehenden Tests bleiben grün.
- `ruff check .` ist sauber.
- `git diff --stat` des Umsetzungspakets zeigt Änderungen ausschließlich
  in `journal/rebuild.py` und `journal/cli.py`. Kein `tests/`, kein
  `fixtures/`, kein `engine/`, keine Migration.

## Ausdrücklich nicht Teil dieses Pakets

Keine Kennzahlen (AP-06), keine FX-Umrechnung (P4/AP-06), keine Campaigns
(AP-05), keine Kandidatenmarkierung für Futures-Rolls (braucht eine
Oberfläche zum Bestätigen), keine Strategiezuordnung, keine API.
