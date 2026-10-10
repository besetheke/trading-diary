---
titel: Filter an /ketten und GET /auswertung (Verlauf und Ergebnis der gefilterten Ketten)
modell: guenstig
status: fertig
abhaengig_von: AP-06e, AP-06i, AP-08f2
aendert_tests: nein
---

# AP-07f · Positionsfilter im Backend

Teil des Facelifts (`auftraege/AP-08f.md`, Zeile AP-07f). Der Nutzer will die
Positionen nach Zeit (Eröffnung/Schließung), Währung, Strategie und mehr
filtern und für den **gefilterten Rest** Verlauf und Ergebnis sehen. Die
Abnahmebasis hat das starke Modell gelegt (eigener Commit):
`tests/test_api_filter.py` (24 Fälle) und `tests/test_api_filter_lose_legs.py`
(Regel für lose Legs unter Filtern), **unveränderlich**, derzeit rot.
Erwartungswerte stehen im Kopf der Testdateien.

Reine Python-Arbeit in `api/app.py` und `analytics/equity.py`. Keine
Oberfläche (das ist AP-08g2b).

## 1. Gemeinsame Filterbedingungen für `/ketten`

Die Bedingungen aus `GET /ketten` wandern in eine Hilfsfunktion
(`_ketten_bedingungen(...)`, Liste von SQL-Bedingungen auf `chains`, immer mit
`chains.c.sicht == "konto"`), die `/ketten` und `/auswertung` gemeinsam
nutzen. **Bestehendes Verhalten bleibt stellenidentisch** (alle bisherigen
Tests laufen unverändert; `eroeffnet_ab`/`eroeffnet_bis` nicht anfassen).

Neue Parameter an `/ketten`:

| Parameter | Bedeutung |
|---|---|
| `geschlossen_ab`, `geschlossen_bis` | Ende der Kette (`beendet_am`), beide Enden **einschließlich** des Tages; offene Ketten (kein Ende) fallen heraus, sobald einer gesetzt ist |
| `waehrung` | Kette hat mindestens ein Glied (`chain_links` → `structures`) in dieser Währung |
| `strategie` | `chains.oa_strategie` ist gleich dem Wert |
| `von`, `bis` | **Z3** (AP-08f): aktiv im Zeitraum = eröffnet bis `bis` (Tag einschließlich) **und** (offen **oder** beendet ab `von`, Tag einschließlich) |

- „Tag einschließlich" für Datumsparameter gegen `DateTime`-Spalten:
  `>= Mitternacht(ab)` und `< Mitternacht(bis + 1 Tag)`. Die bestehende
  Spalten-/Typbehandlung (SQLAlchemy `DateTime`) beibehalten.
- Ungültig → **422** (wie `/equity`): `geschlossen_ab > geschlossen_bis`,
  `von > bis`, kein gültiges Datum.
- `gesamt` zählt weiter vor der Begrenzung.

## 2. `GET /auswertung`

Parameter: alle Kettenfilter von `/ketten` **außer** Sortierung und Blättern
(`basiswert`, `anlageklasse`, `seite`, `endzustand`, `min_rolls`, `max_rolls`,
`eroeffnet_ab`, `eroeffnet_bis`, `geschlossen_ab`, `geschlossen_bis`,
`waehrung`, `strategie`) sowie `von`, `bis`.

**Achtung, `von`/`bis` bedeuten hier etwas anderes als bei `/ketten`:** Bei
`/auswertung` gilt **Z2/Z4** wie bei `GET /equity` — gezählt wird am
Schließungstag der Struktur, die Kurve beginnt im Zeitraum bei 0. Die
Z3-Bedingung (aktiv im Zeitraum) wird bei `/auswertung` **nicht** auf die
Ketten angewendet; `von`/`bis` gehen nur an die Equity.

Ablauf:

1. Ketten-IDs = `chain_id` aller Ketten, die die Kettenfilter erfüllen
   (ohne `von`/`bis`).
2. Ist **mindestens ein Kettenfilter** gesetzt, zählen nur Strukturen der
   gefundenen Ketten (`ketten_ids`); sonst alles.
3. **Lose Legs (AP-06i) unter Filtern — Regel des Nutzers:** Ein Filter, den
   ein loses Leg kennt, gilt auch für das lose Leg; ein Filter, den es nicht
   kennt, schließt es aus. Ohne Filter zählt es mit.

   | Filter | loses Leg |
   |---|---|
   | `basiswert` | `instruments.underlying` des Legs (sonst `symbol`) |
   | `anlageklasse` | `instruments.asset_class` |
   | `waehrung` | `executions.waehrung` der **schließenden** Ausführung |
   | `geschlossen_ab`, `geschlossen_bis` | Tag der schließenden Ausführung (`handelszeit`), beide Enden einschließlich |
   | `eroeffnet_ab`, `eroeffnet_bis` | Eröffnung des Legs (`handelszeit` der eröffnenden Ausführung), gleiche Vergleichslogik wie bei den Ketten |
   | `strategie`, `seite`, `endzustand`, `min_rolls`, `max_rolls` | **schließen es aus** (kennt es nicht) |

4. `analytics/equity.py`: `equity_auswertung` und `equity_bericht` bekommen
   zwei neue Schlüsselwortparameter mit Standardwerten, die das bisherige
   Verhalten unverändert lassen:
   - `ketten_ids: frozenset[int] | None = None` — gesetzt: nur Strukturen,
     die über `glieder_zeilen` (`chain_links`) zu einer dieser Ketten
     gehören.
   - `lose_legs: LoseLegFilter | None | Literal[False] = None` —
     `None`: alle losen Legs (bisher); `False`: keine; sonst ein kleiner
     `@dataclass(frozen=True) LoseLegFilter` mit `basiswert`, `anlageklasse`,
     `waehrung`, `geschlossen_ab`, `geschlossen_bis`, `eroeffnet_ab`,
     `eroeffnet_bis` (je `None` = nicht filtern). (Namen und Form dürfen
     abweichen, solange die Tests grün sind; die Entscheidung gehört in den
     Modulkopf.)
   - `equity_bericht` liest dafür zusätzlich `instruments.underlying`,
     `instruments.asset_class` und `instruments.symbol`.
   - Die Filter für lose Legs werden **in der Python-Auswertung** angewendet
     (rein, keine SQL-Zeichenketten aus Eingaben).

Antwort (`AuswertungAntwort`):

```json
{
  "tage": [...], "monate": [...],
  "max_drawdown_eur": "…", "max_drawdown_datum": "…",
  "ergebnis": {
    "anzahl_ketten": 4,
    "anzahl_strukturen": 3,
    "summe_netto_eur": "94.00",
    "anzahl_kurs_fehlt": 0,
    "lose_legs_eingeschlossen": true
  }
}
```

- `tage`, `monate`, `max_drawdown_*` wie `GET /equity` — **dieselben
  Antwortmodelle wiederverwenden**, die Umwandlung aus dem Ergebnis in eine
  Hilfsfunktion ziehen, die `/equity` und `/auswertung` beide nutzen (kein
  kopierter Block).
- `anzahl_ketten`: Zahl der Ketten, die die Kettenfilter erfüllen
  (unabhängig von `von`/`bis`; offene Ketten zählen mit).
- `anzahl_strukturen`: Summe `tage[].anzahl_strukturen`.
- `summe_netto_eur`: Summe `tage[].netto_eur`, **als `Decimal` gerechnet**,
  Startwert `Decimal("0.00")`, Ausgabe über `_als_text`. Keine Rundung.
- `anzahl_kurs_fehlt`: Summe aus `anzahl_strukturen_kurs_fehlt` und
  `anzahl_lose_legs_kurs_fehlt` über alle Tage.
- `lose_legs_eingeschlossen`: `true`, wenn **kein Filter gesetzt ist, der
  lose Legs ausschließt** (`strategie`, `seite`, `endzustand`, `min_rolls`,
  `max_rolls`); sonst `false`. Es sagt, ob lose Legs mitgerechnet *werden
  dürfen*, nicht, ob eines vorkam.
- Route immer aktiv (nicht hinter `mit_journal`), **vor** der Rückfall-Route
  eintragen, nur lesend (`engine.connect()`), wie `/equity`.

## Ausdrücklich nicht Teil dieses Pakets

- Oberfläche, Vite-Proxy (`/auswertung` kommt mit AP-08g2b), `api.ts`.
- Eine Liste der wählbaren Werte (Basiswerte, Strategien, Währungen) für
  Auswahlfelder — eigenes kleines Paket, wenn die Oberfläche es braucht.
- Änderungen an `engine/`, `journal/`, Migrationen, `tests/`, `fixtures/`.
- Trefferquote/Durchschnitt im `ergebnis` (stehen je Monat in `monate`).

## Abnahme

`tests/test_api_filter.py` und `tests/test_api_filter_lose_legs.py` komplett grün, Gesamtsuite grün
(`.venv\Scripts\python.exe -m pytest -q` im Vordergrund, Ergebnis direkt
lesen, Timeout 10 Minuten), `ruff check .` sauber, `git diff --stat` nur
`api/app.py`, `analytics/equity.py` und dieses Auftragsdokument (Status auf
`fertig`). Vor Beginn und vor dem Commit `git pull --ff-only`.
