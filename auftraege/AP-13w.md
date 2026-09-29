---
titel: Abnahmebasis für die Persistenz des OA-Abgleichs
modell: stark
status: fertig
abhaengig_von: AP-13k
aendert_tests: ja
---

# AP-13w · Abnahmebasis für die Persistenz des OA-Abgleichs

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-13wk (günstiges Modell).

Fachliche Grundlage: Plan §6, AP-13 — „`Strategy` und `Status` ergänzen
Kette und Strukturen." `engine.oa_abgleich.oa_abgleich()` (AP-13k, fertig)
liefert das Ergebnis bereits berechnet; dieses Paket schreibt es in die
Datenbank.

## Bereits erledigt (Teil dieses Pakets, nicht der Umsetzung)

- **Migration** `migrations/versions/a3e8f1c9d426_ap13w_oa_strategie_status.py`:
  drei Spalten je auf `structures` und `chains` — `oa_strategie` (Text),
  `oa_status` (Text), `oa_erkennung` (Text, Check `IN ('auto', 'heuristik')`),
  alle entleerbar.
- `journal/schema.py`: beide Tabellendefinitionen entsprechend erweitert.

Führe `alembic upgrade head` in einer Testumgebung aus, um das zu
verifizieren — nicht neu schreiben.

## Worum es geht

Ein neues Modul `journal/oa_persistenz.py` liest die importierten
OA-Trades (`optionapp_trades`/`optionapp_legs`), ruft
`engine.oa_abgleich.oa_abgleich()` mit den bereits im Speicher gebildeten
Ketten auf und schreibt `oa_strategie`/`oa_status`/`oa_erkennung` auf die
betroffene Kette **und** jede ihrer Strukturen (derselbe Wert — OA kennt
keine feinere Ebene als den Trade). Wiring in `journal/rebuild.py`.

## Zu bauen

### `journal/oa_persistenz.py`

```python
def oa_werte_schreiben(
    verbindung: Connection,
    kette_je_schluessel: dict[str, Kette],
    struktur_je_schluessel: dict[str, Struktur],
    struktur_id_je_schluessel: dict[str, int],
    ketten_id_je_schluessel: dict[str, int],
    exec_je_id: Mapping[str, Mapping],
    instrument_je_conid: Mapping[int, Mapping],
) -> tuple[int, int]:  # (Anzahl zugeordnet, Anzahl Fehler)
```

Ablauf:

1. `optionapp_trades` und `optionapp_legs` lesen, zu
   `engine.oa_abgleich.OATradeEintrag`/`OALegSignatur` zusammensetzen
   (Spalten sind bereits die passenden Typen — direkte Übernahme, kein
   Mapping nötig).
2. `oa_abgleich(oa_trades, list(kette_je_schluessel.values()), exec_je_id,
   instrument_je_conid)` aufrufen.
3. Für jede `OAZuordnung`: die Chain-Instanz `z.chain` ist **dasselbe
   Objekt**, das in `kette_je_schluessel` steht (keine Kopie) — ihren
   Naturschlüssel über eine Umkehrabbildung nach Python-Objektidentität
   finden (`{id(v): k for k, v in kette_je_schluessel.items()}`), **nicht**
   `journal.rebuild._kette_schluessel()` importieren (Zirkelimport:
   `rebuild.py` importiert dieses Modul). Dieselbe Technik für
   `struktur_je_schluessel` → `z.chain.glieder[*].structure`.
4. `UPDATE` auf `chains`/`structures` mit den drei Feldern für jede
   Zuordnung. Nicht zugeordnete oder fehlerhafte OA-Trades schreiben
   nichts.
5. Rückgabe: `(len(ergebnis.zuordnungen), len(ergebnis.fehler))`.

### `journal/rebuild.py`

- `_struktur_zeile()` und `_kette_zeile()`: die drei neuen Felder mit
  `None` in den zurückgegebenen Dict aufnehmen (Baseline bei **jedem**
  Schreiben — siehe „Die Stelle, an der erfahrungsgemäß geraten wird").
- Nach dem Schreiben von `chain_links`, vor oder nach
  `_assignment_links_neu_schreiben()`: `oa_werte_schreiben()` aufrufen,
  mit `kette_je_schluessel`, `struktur_je_schluessel`,
  `struktur_id_je_schluessel`, `ketten_id_je_schluessel`,
  `bestand.exec_je_id`, `bestand.instrument_je_conid` (alle bereits lokale
  Variablen an dieser Stelle in `_rebuild_laufen()`).
- `RebuildErgebnis` um zwei Zählfelder erweitern (wie `kandidaten_offen`,
  nicht persistiert, jeden Lauf neu berechnet): `oa_zugeordnet: int = 0`,
  `oa_fehler: int = 0`.
- `journal/cli.py`, `rebuild`-Zweig: die Summenzeile um beide Zahlen
  ergänzen, nach demselben Muster wie `kandidaten_offen`. Kein neuer
  Exit-Code — anders als verwaiste Overrides ist ein OA-Fehler kein
  Datenintegritätsbruch, nur eine sichtbare Information (Plan: „nie
  stillschweigend verworfen" heißt sichtbar, nicht abbruchpflichtig).

## Die Stelle, an der erfahrungsgemäß geraten wird

**Baseline vor Zuordnung, bei jedem Lauf.** `_struktur_zeile()`/
`_kette_zeile()` setzen die drei Felder immer zuerst auf `None`, bevor
`oa_werte_schreiben()` danach gezielt überschreibt. Ohne diese Baseline
bliebe eine Zuordnung nach einem Rebuild bestehen, bei dem der OA-Trade
gar nicht mehr importiert ist (Export gelöscht, Klammernummer geändert)
— eine veraltete Tatsache, die niemand mehr korrigiert hat (`tests/
test_rebuild_oa.py::test_zweiter_lauf_entfernt_eine_veraltete_zuordnung`
prüft genau das).

## Grenzen

- Kein Eingriff in `engine/oa_abgleich.py`, `engine/chains.py`,
  `engine/structures.py`.
- Keine Interpretation von `oa_status`/`oa_strategie` — reines
  Durchreichen, wie in `engine.oa_abgleich` bereits festgelegt.
- Keine API-, keine Oberflächenänderung — nur Persistenz. Die Anzeige ist
  ein eigenes, noch nicht geschriebenes Paket.
- Keine Fehlerliste in der Datenbank — nur die Zählwerte in
  `RebuildErgebnis`/CLI-Ausgabe. Eine strukturierte Fehlerliste (welcher
  OA-Trade, welcher Grund) wäre Sache eines künftigen
  Abgleichswerkzeugs, nicht dieses Pakets.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_rebuild_oa.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt `journal/oa_persistenz.py` (neu),
  `journal/rebuild.py`, `journal/cli.py`.
