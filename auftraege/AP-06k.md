---
titel: "Analytik I: EUR-Fundament und Kennzahlen je Ebene (Umsetzung)"
paket: AP-06k
modell: guenstig
status: fertig
abhaengig_von: "AP-06v, freigegeben"
naechstes: AP-06w
---

# AP-06k · Analytik I — Umsetzung

Vertrag ist `auftraege/AP-06v.md` (dort Datenklassen, Signaturen, Regeln 1–13,
CSV-Format). Die Abnahmetests in `tests/test_kennzahlen.py` sind
**unveränderlich** — jede Abweichung zwischen Implementierung und Test ist ein
Fehler der Implementierung, nicht der Tests.

## Zu bauen

1. **`analytics/kennzahlen.py`** — Datenklassen und Funktionen nach Vertrag:
   `kennzahlen_auswertung` (rein, P2), `fx_tageskurse` (rein), `als_csv`,
   `kennzahlen_bericht` (I/O-Hülle: liest chains/structures/chain_links/legs/
   executions/instruments, ruft die reine Funktion und schreibt `fx_rates`
   sowie `metrics_by_chain` vollständig neu — beide Sichten, Regel 11;
   `chains.netto_pnl_eur` bleibt leer).
   Das Paket `analytics/` existiert bereits (leeres `__init__.py`).
2. **CLI-Subcommand `journal kennzahlen <datei>`** in `journal/cli.py` nach
   dem Muster der bestehenden Subcommands: Optionen `--db`,
   `--sicht {kette,konto}` (Default `kette`), `--nur-stufe-a` (Flag).
   Ausgabe: CSV nach Vertrag Regel 13 als UTF-8 mit BOM. Exit-Code 0 im
   Erfolg.

Eine Migration (E2): `metrics_by_chain` bekommt seine Form — `chain_id`
(Fremdschlüssel auf `chains.chain_id`, eindeutig), `netto_eur_wirtschaftlich`
und `netto_eur_ib` (beide `ExactDecimal`, nullable; der Währungseffekt ist
die Differenz und wird nicht gespeichert). In `journal/schema.py` wird der
Stellvertreter ersetzt und der Kommentar an `chains.netto_pnl_eur`
korrigiert („bleibt dauerhaft leer; die EUR-Materialisierung liegt in
`metrics_by_chain`, AP-06 E2" — der heutige Kommentar sagt, das Ergebnis
werde dort gespeichert, und wäre falsch). `fx_rates` existiert schon;
`metrics_daily`/`metrics_by_campaign` bleiben Stellvertreter (OF-01,
Tranche IV/V).

## Reihenfolge

1. Migration und `journal/schema.py` (E2).
2. Modul ohne Schreibzugriffe grün gegen die reinen Tests.
3. `kennzahlen_bericht` inklusive Materialisierung; E2E-Tests grün.
4. CLI; CLI-Test grün.
5. `ruff check .` und Gesamtsuite grün.

## Wo du abschreiben sollst statt neu zu erfinden

- CSV mit BOM und CLI-Muster: `journal/cli.py` (bestehende Subcommands) und
  `tests/test_steuer.py` (dort CLI- und BOM-Prüfung, gleiches Muster).
- E2E-Befüllung (import_runs/instruments/executions direkt, dann
  `rebuild`): `tests/test_steuer.py` und `tests/fixtures_rebuild.py`.
- Decimal-Disziplin (kein float, keine stillen Rundungen): durchgängig
  `journal/schema.py` (ExactDecimal) und die bestehenden Tests.

## Grenzen

Keine Kommissionsaufschlüsselung, keine Degradation, keine Equity-Kurve,
keine Cache-Tabellen, keine Campaign-Ebene, keine API, keine UI (alles
spätere Tranchen beziehungsweise AP-07/AP-08-Rest). Keine Zeitzonenlogik —
handelszeit ist naiv, wie gespeichert.
