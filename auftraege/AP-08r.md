---
titel: Rollkandidaten in der Oberfläche prüfen
modell: stark
status: fertig
abhaengig_von: AP-04d, AP-04dv, AP-04v
aendert_tests: nein
---

# AP-08r · Rolls prüfen

Anlass: OF-79, Befund 2 — 719 Rollkandidaten (Roll in getrennten Orders) sind
Vorschläge (Regel 7) und zählen nicht als Roll. Bisher ging ihre Durchsicht nur
über die XLSX-Rundreise (`journal kandidaten-ausschreiben`/`-einlesen`).

## Vertrag

1. `GET /rollkandidaten`: offene Kandidaten, gruppiert nach schließender
   Position — dieselben Gruppen, Ränge und Preise wie die Datei (AP-04d,
   `_gruppen_bilden`). Bereits entschiedene Paare fehlen. Geld als Text.
   Ohne vorherigen Rebuild 409 (AP-04dv, Vertrag 9).
2. `POST /journal/rollkandidaten/urteil` (schreibende Routen nur unter /journal, AP-07j) (nur mit Journal, wie die Notizen):
   `schluessel_kette`, `schluessel_struktur`, `urteil` (`bestaetigt` |
   `abgelehnt`), `notiz`. Dieselben Regeln wie beim Einlesen
   (`_urteile_schreiben`): unbekannter Schlüssel 404, ungültiges Urteil 422,
   Widerspruch zu einer gespeicherten Entscheidung oder eine Struktur in zwei
   Ketten 409 — nichts wird geschrieben. Kurze Transaktion (Regel 9).
3. Urteile stehen in `chain_overrides` und wirken beim nächsten Rebuild
   (nächtlicher Abruf oder `journal rebuild`).
4. Oberfläche `/rolls` („Rolls prüfen" in der Navigation): Gruppen mit alter
   Position und Kandidaten (Rang, Legs, Eröffnung, Abstand, Preis auf,
   Mengenverhältnis), je Kandidat „Roll" / „Kein Roll"; 25 Gruppen je Seite;
   ein entschiedener Kandidat verschwindet sofort.

Tests: `tests/test_api_rollkandidaten.py` (7), Szenarien aus
`tests/fixtures_durchsicht.py`.

Laufzeit (Echtdaten): `GET /rollkandidaten` ≈ 4 s (536 Gruppen, 719 Kandidaten).
