---
titel: Roll-Kosten in der Oberfläche und festgeschriebene Abhängigkeiten (M01, M08)
modell: stark
status: teilweise   # M03, M04, M06 offen
abhaengig_von: AP-17
aendert_tests: nein
---

# AP-17g · Teil 1 des Ausbaus aus dem Review

## M08 Abhängigkeiten festschreiben

`requirements-lock.txt` (Journal und Roller, `pip freeze` vom 18.10.2026, ohne `ibapi`, das aus `C:\TWS` kommt).
`setup.cmd` und `Deploy.ps1` installieren zuerst den festen Stand; fehlt die Datei, gilt wie bisher die offene Mindestversion.
Test: `tests/test_abhaengigkeiten_fest.py` (exakte Versionen, deckt `pyproject.toml` ab, Skripte nutzen die Datei).

## M01 Roll-Kosten und Kommission

`GET /roll-kosten-auswertung?sicht=kette|konto&nur_a=…` (`api/roll_kosten.py`) reicht `analytics.kommission` und
`analytics.degradation` unverändert weiter (EUR, Dezimal-Texte). Seite `/roll-kosten` („Roll-Kosten“ im Journal-Menü):
Ergebnis nach 0/1/2/3+ Rolls (Anzahl, Summe, Ø netto, Trefferquote, Ketten ohne Kurs, beide Modi `belegt` und
`belegt_bestaetigt`), Abdeckung samt offenen Rollkandidaten, Kommission nach Roll-Anzahl, Strategie, Basiswert, Anlageklasse;
beide Sichten ausdrücklich benannt. Test: `tests/test_api_roll_kosten.py`.

## M01 Drilldown (24.10.2026, erledigt)

Jede Zeile der Seite „Roll-Kosten“ (Ergebnis nach Rolls, Kommission nach Gruppe) klappt auf die gezählten Ketten auf: Link zur Position,
Basiswert, Strategie, Zeitraum, Rolls, Brutto, Kommission und Netto in EUR; Ketten ohne Kurs sind markiert. Die Rechenkerne geben dafür
`ketten_ids` je Gruppe und `ketten_summen` zurück (neue Felder mit Vorgabe, bestehende Tests unverändert). Test: `tests/test_api_roll_kosten.py`
(IDs stimmen mit Anzahlen überein, Beträge der Ketten ergeben die Gruppensumme).

## M05 Journal-Suche, Tag-Filter, Anhänge (25.10.2026, erledigt)

`GET /journal-suche` (Notiztexte und Tag-Namen, Filter „alle/irgendeines dieser Tags“, Bereichsart, nur mit Anhang; ohne Filter die zentrale
Liste aller markierten oder kommentierten Situationen) mit Position als Trefferkontext; Seite „Suche“ im Menü. Anhänge: `POST
/journal/{typ}/{id}/anhaenge` (Dateiinhalt als Körper, nur aus der Station), `GET /journal/{typ}/{id}/anhaenge`, `GET /anhang/{id}`;
png, jpeg, gif, webp, pdf, txt, höchstens 5 MB und 20 je Bereich, Ablage in `anhaenge/` neben der Datenbank (Name bereinigt, kein
Ausbrechen über `..`), `nosniff`. **Kein Löschen** von Anhängen (CLAUDE.md Regel 4). Tests: `tests/test_journal_suche.py` (7), darunter die
Abfrage „alle schlecht getimten Rolls mit Screenshot“ und Erreichbarkeit nach dem Rebuild.

## M07 Live-/Backtest-Abweichungen als Indizien (25.10.2026, erledigt bis auf Korrektur des Partners)

Je Paar bleibt `ursache` die **erste erkannte** Abweichung in fester Reihenfolge (bestehende Summen und Tests unverändert), daneben stehen jetzt
`abweichungen` (alle beobachteten Unterschiede: Kontraktzahl, Einstiegszeit, Strikes, Art und Zeitpunkt des Ausstiegs), `rest_unerklaert`
(keine Abweichung gefunden: Slippage ist nur eine Vermutung), die Ausstiegsart je Seite (Verfall, vorzeitig bzw. Rückkauf) und `partner_herkunft`
(„zeitfenster“); je Strategiepaar `mehrfach_abweichend`. Die Oberfläche beschriftet „erste erkannte Abweichung (kein Nachweis der Ursache)“, zeigt
„beobachtet außerdem“ und „ungeklärter Rest“. Tests: `tests/test_backtest_indizien.py` (6). **Offen:** den abgeleiteten Partner in der Oberfläche
korrigieren (eigene Zuordnungstabelle), und die Auswertung der tatsächlichen Fillpreise je Order (nur Ausstiegsart und -zeit sind getrennt).

## M03 Manuelle Strategiezuordnung (25.10.2026, erledigt für Ketten)

Neue Tabelle `strategie_zuordnungen` (Migration `b3f1a8c2d6e9`), am **Naturschlüssel** der Kette: Strategie, Begründung, Zeitstempel, der Stand vor
der Zuordnung und ein eventueller OA-Widerspruch. Der Rebuild wendet aktive Zuordnungen nach dem OA-Abgleich in beiden Sichten an (Kette und
ihre Strukturen) und zählt angewandte, widersprechende und verwaiste (`RebuildErgebnis.strategie_*`). Wege: `GET /strategie-zuordnung/{id}`,
`PUT /journal/strategie-zuordnung/{id}`, `POST …/zuruecknehmen` (die Rücknahme löscht nichts, Regel 4); auf der Positionsseite der Block
„Strategie“. Die Datenqualität-Liste zeigt Widersprüche zu OA und verwaiste Zuordnungen. Die Herkunft „manuell“ steht in der Tabelle, weil die
Prüfregel für `oa_erkennung` an Ketten und Strukturen nur auto/heuristik erlaubt (kein Umbau der Tabellen). Tests: `tests/test_strategie_zuordnung.py` (6).
Nicht Teil: eigene Zuordnung auf Strukturebene, Rücknahme von Roll-Entscheidungen in der Oberfläche (die bestehende Rollkandidaten-Seite entscheidet).

## M06 Begriffe und Bewertungsstichtag (25.10.2026, erste Stufe erledigt)

Baustein `ErgebnisBegriffe` (Dashboard, Positionen, Titel, Strategien): einheitliche Definitionen von realisiert, teilrealisiert, unrealisiert und gesamt,
ausdrücklich benannter Bewertungsstichtag (Bestand des letzten Abrufs) und eine deutliche Warnung, wenn der gewählte Endtag davor liegt und
Unrealisiertes deshalb nicht verfügbar ist. Offen (zweite Stufe): historischer Depotzustand aus Ausführungen bis zum Stichtag plus passendem Snapshot;
Überleitbarkeit in Kampagnen. Test: `tests/test_ergebnisbegriffe.py`.

## M04 Datenqualität als Arbeitsliste (25.10.2026, erledigt)

Neue Tabelle `betriebslaeufe` (Migration `a1c4e7b9d2f5`): `journal abrufen`, `journal import` und `journal rebuild` protokollieren je Lauf Ergebnis
(ok/fehler/teilweise) und Meldung. `GET /datenqualitaet-liste` und die Seite „Datenqualität“ trennen **letzten erfolgreichen Abruf, Import und
Rebuild** und zeigen Fehlschläge/Teilerfolge; die Punkte (Betrieb, Legs ohne Struktur, Kapitalmaßnahmen ohne Kosten, fehlende Wechselkurse,
offene Rollkandidaten, Abgleichsreste) tragen Art, Schwere, Anzahl, Betrag, **Zeitraum**, betroffene Objekte und Lösungsweg. Die Startseite
zeigt bei Fehlern oder Warnungen einen Hinweis mit Link zur Arbeitsliste. Tests: `tests/test_datenqualitaet.py` (10). Ist die Tabelle noch nicht
migriert, meldet die Liste das ausdrücklich („alembic upgrade head“).

## M08 (25.10.2026, erledigt)

`python -m journal restore-probe <sicherung>` (Integrität, Migration, optional Rebuild in temporärer Kopie), `werkzeuge/smoke.py` (jede Seite
und jeder API-Weg antwortet; das Deploy ruft ihn auf), Vorabprüfung der Downloads vor dem Stoppen der Dienste in `Deploy.ps1`.

## Offen (ohne OF-102)

Browser-Smoke-Test und Restore-Probe (M08),
Vorabprüfung aller Downloads vor dem Stoppen der Dienste. M02–M07 folgen.
