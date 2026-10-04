---
titel: Kommissionsattribution (analytics/kommission.py, CLI --kommission)
modell: guenstig
status: fertig
abhaengig_von: AP-06w
---

# AP-06wk · Kommissionsattribution

Umsetzungspaket nach Plan §11.2, Schritt 2, gegen die Abnahmebasis AP-06w
(Vertrag und `tests/test_kommissions_attribution.py`, E1–E7 freigegeben).
**Tests und Fixtures sind tabu.** Maßgeblich ist `auftraege/AP-06w.md`.

Dokumentation nachträglich (04.10.2026): Das günstige Modell hat direkt
gegen AP-06w umgesetzt, bevor dieses Auftragsdokument existierte; der Inhalt
folgt dem Vertrag 1:1.

## Gebaut

- `analytics/kommission.py`: reine Funktion `kommissions_attribution(...)`
  (Signatur wie `kennzahlen_auswertung`), `als_csv`, DB-Hülle
  `kommissions_bericht(db_pfad, sicht, nur_qualitaetsstufe_a)`.
- `journal/cli.py`: `journal kennzahlen ... --kommission <datei>`.

## Meldung der Umsetzung (Regel 1)

Der letzte CLI-Test war mit der Fixture nie erfüllbar. Das günstige Modell hat
ihn **nicht** geändert, sondern gemeldet; Korrektur durch das starke Modell in
`auftraege/AP-06wvk.md`.

## Anmerkung für später (kein Mangel)

`_eur_teile`, `_beteiligt` und `_qualitaetsstufe` wiederholen die Rechnung aus
`analytics/kennzahlen.py` (Regel 3 von Tranche I), statt sie zu importieren.
Beide Stellen sind heute durch Handwerte gegeneinander abgesichert; ein
späteres Refactoring zu einer gemeinsamen Funktion verhindert, dass die zwei
Kopien auseinanderlaufen (genau der Fehlertyp aus AP-06vk).

## Abnahme

- `tests/test_kommissions_attribution.py` 11/11 grün, Gesamtsuite grün,
  `ruff check .` sauber.
- `git diff --stat`: `analytics/kommission.py` (neu), `journal/cli.py`.
