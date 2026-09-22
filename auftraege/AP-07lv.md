---
titel: Abnahmebasis fuer die Lese-API (AP-07l)
modell: stark
status: fertig
abhaengig_von: AP-04p
aendert_tests: ja
---

# AP-07lv · Abnahmebasis für die Lese-API

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-07l (günstiges Modell).

Fachliche Grundlage: Plan §6, AP-07 in der zweigeteilten Fassung — die
Lese-API wird vor AP-06 gezogen, weil Ketten, Strukturen und Legs seit
AP-04p in der Datenbank stehen und keine Kennzahl brauchen, um sichtbar zu
sein (Textvorschlag in
`auftraege/AP-07-vorschlag-zwei-sichten-und-vorziehen.md`).

## Die vier Entscheidungen, die nicht beim Umsetzer liegen

**1. Geld geht als Zeichenkette über die Leitung.** JSON kennt nur
Gleitkommazahlen. Ein `Decimal`, das als Zahl serialisiert wird, ist genau
der stille Genauigkeitsverlust, den Regel 5 verbietet — und er fiele erst
auf, wenn eine Summe um Cents danebenliegt. Alle Geldfelder sind deshalb
Zeichenketten in Dezimalschreibweise (`"92.00"`), niemals Zahlen.

**2. Jede Geldangabe nennt Währung und Sicht.** Die Währung, weil es keine
Umrechnung gibt, solange AP-06 fehlt; die Sicht, weil es seit OF-36 zwei
gibt. Die Lese-API liefert ausschließlich die **Kontosicht** (`"konto"`) —
die Kettensicht ist noch nicht gebaut. Ohne dieses Feld stünden später
Zahlen zweier Sichten nebeneinander, ohne dass man ihnen ansieht, welche
welche ist.

**3. Keine währungsübergreifende Summe.** Enthält eine Kette Strukturen in
verschiedenen Währungen, bleibt ihre Ergebnissumme **leer** — mit der Liste
der vorkommenden Währungen daneben. Eine Zahl, die USD und EUR addiert,
wäre falsch, und eine, die stillschweigend eine Währung bevorzugt, wäre
schlimmer.

**4. Nichts wird gerechnet, außer einer Summe mit Namen.** Die API reicht
durch, was in der Datenbank steht. Die einzige Ausnahme ist
`struktur_summe_netto` je Kette — die Summe der `netto_pnl` ihrer
Strukturen. Sie ist keine Kennzahl (die kommen in AP-06), sondern genau die
Größe, die Invariante 4 der AP-04-Abnahme ohnehin prüft.

## Ausdrücklich freigegebene Änderungen

Nur diese, keine weiteren.

- **Neue Testdatei** `tests/test_api_lesen.py` — springt still ab, solange
  `api/app.py` fehlt.
- **Neue Abhängigkeiten** in `pyproject.toml`: `fastapi` (Laufzeit) und
  `httpx` (Entwicklung — der Testclient von Starlette braucht ihn).
- Kein bestehender Test, kein bestehendes Fixture wird angefasst.

## Vertrag an die Umsetzung (AP-07l)

### Anwendung

1. **`api/app.py`** mit `erzeuge_app(db_pfad) -> FastAPI` und einem
   Modulobjekt `app`, das den Pfad aus `--db`-Logik wie die CLI bezieht
   (Umgebungsvariable `JOURNAL_DB`, sonst `journal.db`, OF-06).
2. **Ausschließlich lesend.** Im OpenAPI-Schema kommt keine andere Methode
   als `get` vor. Die Anwendung schreibt nie, auch keinen `rebuild`.
3. Datenbankzugriff über `create_db_engine()` aus `journal/db.py` (Regel 9
   — die Pragmas setzt die Factory, nicht dieses Modul).

### Endpunkte

4. **`GET /ketten`** — Liste. Antwort:
   `{"gesamt": <int>, "treffer": [<Kette>, ...]}`. `gesamt` ist die Anzahl
   **vor** Begrenzung, damit eine Oberfläche blättern kann.
   Abfrageparameter, alle entleerbar:
   `basiswert`, `anlageklasse`, `seite`, `endzustand`,
   `min_rolls` / `max_rolls` (ganzzahlig, ≥ 0),
   `eroeffnet_ab` / `eroeffnet_bis` (Datum),
   `limit` (Vorgabe 50, Höchstwert 500), `offset` (Vorgabe 0).
   Sortierung: `eroeffnet_am` **absteigend**, bei Gleichstand nach
   `chain_id` — das Neueste zuerst, und deterministisch.
5. **`GET /ketten/{chain_id}`** — eine Kette samt `glieder`, nach `sequenz`
   aufsteigend. Unbekannt → **404**.
6. **`GET /strukturen/{structure_id}`** — eine Struktur samt `legs`.
   Unbekannt → **404**.
7. **`GET /strukturen/{structure_id}/ausfuehrungen`** — der Drilldown:
   alle Ausführungen, die die Legs dieser Struktur eröffnen oder schließen,
   nach `handelszeit` aufsteigend, je mit `rolle` (`"eroeffnung"` oder
   `"schliessung"`). Unbekannt → **404**.

### Felder

8. **Kette:** `chain_id`, `natur_schluessel`, `underlying`, `asset_class`,
   `seite`, `eroeffnet_am`, `beendet_am`, `anzahl_rolls`, `endzustand`,
   `anzahl_glieder`, `struktur_summe_netto`, `waehrung`, `waehrungen`,
   `sicht`.
   - `seite`: `Call`, `Put`, `n.a.` (Calls **und** Puts) — oder **leer**,
     wenn die Kette keine Optionen enthält, etwa eine Aktientranche.
     Übernimm den Wert aus `chains.seite`, statt ihn neu abzuleiten.
   - `struktur_summe_netto`: Zeichenkette, oder **leer**, wenn die Kette
     mehrere Währungen enthält oder eine Struktur kein Ergebnis trägt (noch
     offen).
   - `waehrung`: die eine Währung der Kette, sonst leer.
   - `waehrungen`: Liste aller vorkommenden, immer gefüllt.
   - `sicht`: immer `"konto"` (Entscheidung 2).
9. **Kettenglied:** `sequenz`, `verknuepfungstyp`, `erkennung` und die
   Struktur.
10. **Struktur:** `structure_id`, `natur_schluessel`, `asset_class`, `typ`,
    `underlying`, `expiry`, `short_strike`, `long_strike`, `breite`,
    `menge`, `eroeffnet_am`, `geschlossen_am`, `dte_bei_eroeffnung`,
    `status`, `erkennung`, `brutto_pnl`, `kommission`, `netto_pnl`,
    `waehrung`, `sicht`.
11. **Leg:** `leg_id`, `conid`, `open_exec_id`, `close_exec_id`, `menge`,
    `matching_methode`, `offen_ja_nein`, `basis_ungeklaert`, `brutto_pnl`,
    `kommission_gesamt`.
12. **Ausführung:** `exec_id`, `rolle`, `conid`, `symbol`, `side`, `menge`,
    `preis`, `waehrung`, `kommission`, `handelszeit`, `ereignistyp`,
    `exec_batch`, `oa_trade`.
13. **Geld ist immer Zeichenkette** (Entscheidung 1): `brutto_pnl`,
    `kommission`, `kommission_gesamt`, `netto_pnl`, `struktur_summe_netto`,
    `preis`. Mengen und Strikes ebenso — auch sie sind `Decimal` in der
    Datenbank. Leere Werte bleiben leer, sie werden nie zu `"0"`.
14. **Zeitstempel** als ISO-8601 ohne Zeitzone, wie gespeichert (OF-04 —
    die Quelle liefert sie naiv, und wir erfinden keine Zone).

### Verhalten

15. **Leere Datenbank** liefert `{"gesamt": 0, "treffer": []}`, keinen
    Fehler.
16. **Ungültige Abfrageparameter** (negatives `limit`, `min_rolls` als
    Text) → **422**, die Vorgabe von FastAPI; nicht selbst abfangen.
17. **`limit` über dem Höchstwert** → 422, nicht stillschweigend gekappt.

## Abnahme

- `tests/test_api_lesen.py` — 19 Tests — läuft vollständig grün.
- Alle übrigen Tests bleiben grün; `ruff check .` sauber.
- `git diff --stat` der Umsetzung zeigt ausschließlich `api/`,
  `pyproject.toml` und `OFFENE_FRAGEN.md`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Kennzahlen (AP-06), keine Schreibendpunkte, keine Rollkandidaten
(nicht gespeichert, Neuberechnung dauert Minuten — Plan §6, Block B,
Regel 2), keine Kettensicht (OF-36), keine Oberfläche (AP-08l), keine
Authentifizierung (das Journal läuft lokal, §4).
