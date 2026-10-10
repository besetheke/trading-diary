---
titel: Equity-Kurve und Drawdown (AP-06, Tranche IV)
modell: stark
status: fertig
abhaengig_von: AP-06v
aendert_tests: ja
---

# AP-06e · Equity-Kurve und Drawdown (AP-06, Tranche IV)

Vorbereitungspaket und Umsetzung in einem (beide Rollen vom starken Modell
übernommen — kein Übergabepunkt an ein günstiges Modell für dieses Paket).
Neue Testdateien `tests/test_equity.py` (6 Tests, reine Funktion) und
`tests/test_api_equity.py` (3 Tests, API), keine bestehende Erwartung
geändert.

Plan AP-06: „Equity-Kurve und Drawdown · Aufschlüsselung nach Index, Seite,
DTE-Band, Breite" — dieses Paket liefert den ersten Teil (Equity-Kurve,
Drawdown, Monatsübersicht); die Aufschlüsselung nach DTE-Band/Breite ist
**nicht** Teil dieses Pakets (separat zu beauftragen).

## Entscheidungen (E1–E7)

- **E1 Sicht.** Nur die Kontosicht — Geld ist Kontosicht-Sache (Plan §5,
  „diese Sicht ist für Geld maßgeblich"). Anders als die Roll-Degradation
  (AP-06d, E1), die bewusst nur die Kettensicht zulässt. `sicht != 'konto'`
  → `ValueError`.
- **E2 Tagesgruppierung.** Eine geschlossene Struktur zählt an ihrem
  `geschlossen_am`-Datum (nur das Datum). Mehrere Strukturen am selben Tag
  summieren sich. Tage ohne abgeschlossene Struktur erzeugen keine Zeile
  (wie die Kalenderübersicht, AP-07t); die kumulierte Summe läuft trotzdem
  lückenlos weiter.
- **E3 Kursmangel.** Zählt als eigener Tag/Monat, wenn er der einzige
  Beitrag ist, mit `netto_eur=0` und `anzahl_..._kurs_fehlt > 0` — kein
  stilles Verschwinden. Offene Strukturen tragen nirgends bei.
- **E4 Drawdown.** Je Tag `kumuliert − laufendes_hoch` (laufendes Hoch über
  alle bisherigen `kumuliert`-Werte, inklusive des Tages selbst), immer
  ≤ 0. Der maximale Drawdown ist das Minimum dieser Reihe; ohne Tage 0 und
  `None` als Datum.
- **E5 Monatsübersicht.** Je Kalendermonat (`JJJJ-MM`): Anzahl, Summe,
  Durchschnitt (zwei Stellen HALF_UP), Trefferquote (vier Stellen, wie
  Tranche I E5).
- **E6 Stufenfilter** `--nur-stufe-a`: wie Tranche I/III, entfernt Strukturen
  ganz, auch aus der Tagesreihe.
- **E7 Ausgabe.** `journal kennzahlen DATEI --equity DATEI2`, unabhängig von
  `--sicht` (Equity liest immer Kontosicht selbst). Eine CSV, Semikolon,
  UTF-8 mit BOM, Zeilenende `\n`: Kopf, je Tag eine `tag`-Zeile, je Monat
  eine `monat`-Zeile.

## Schnittstellen (verbindlich)

- `analytics/equity.py`: `equity_auswertung(ketten_zeilen, struktur_zeilen,
  glieder_zeilen, leg_zeilen, ausfuehrungs_zeilen, instrumenten_zeilen, *,
  sicht="konto", nur_qualitaetsstufe_a=False)` (rein), `equity_bericht(db_pfad,
  *, nur_qualitaetsstufe_a=False)` (liest, schreibt nichts), `als_csv(ergebnis)`,
  Datenklassen `EquityTag`, `EquityMonat`, `EquityErgebnis`.
- `api/app.py`: `GET /equity` — immer aktiv, rein lesend, reicht
  `equity_bericht` durch (erster echter Kennzahlen-Endpunkt der Lese-API,
  Plan AP-07 „Rest").

## Abnahme

`tests/test_equity.py` und `tests/test_api_equity.py` grün (Handrechnung im
Moduldocstring bzw. Testdocstring), Gesamtsuite grün, `ruff check .` sauber.
Ohne Modul rot (`ModuleNotFoundError`), ohne Route 404.
