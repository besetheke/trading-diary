---
titel: Roller R3 abschließen und Umzug auf den Server vorbereiten
modell: stark
status: offen
abhaengig_von: AP-14e
aendert_tests: nein
---

# AP-14f · Roller R3 abschließen, Server vorbereiten

Stand 13.10.2026. Der Roller (`options-roller`) eröffnet Strategien und rollt Ketten am
Paper-Konto nach der Rollregel des Nutzers; die Station zeigt die Ketten und gibt Rolls
und Eröffnungen per Klick frei (AP-14e). Dieses Paket schließt R3 ab und bereitet den
Betrieb auf dem Server vor.

**Plan:** `plan/` ist für Umsetzungspakete schreibgeschützt. Der Abschnitt unten
„Vorschlag für `plan/zielbild-station.md`“ ist zur Übernahme durch den Nutzer bestimmt.

## Bereits umgesetzt (options-roller, Commits bis `fd28ded`)

- Rollregel je Strategie (`roller/strategie.py`), Ketten mit `orderRef R3|Kette|Strategie`.
- Wächter im Dienst (`--paper-orders --mails`): Signal, Vorschlag, Alarm, Mails.
- Wiederanlauf-Abgleich offener Orders, Handelszeiten aus IB (liquidHours), Early Exit.
- Alle Orders über clientId 3 (IB storniert nur Orders derselben clientId).

## Abnahme (vor dem Umzug)

1. Ein echter Roll mit Signal, per Klick in der Station freigegeben, gefüllt; neues
   Profit-Target gesetzt; Mail.
2. DAX in der Eurex-Zeit: Eröffnung und Roll (Wochenoption `ODAP`, Tick, Multiplikator 5).
3. Abschluss einer Kette: Profit-Target gefüllt oder Verfall oder Early Exit — Kette
   „geschlossen“, Mail. Testketten K002–K004 verfallen am 20.10.2026.
4. Wiederanlauf im Ernstfall: Dienst während eines Rolls beenden, Neustart; liegengebliebene
   Order storniert, Profit-Target wiederhergestellt, Meldung.
5. Deployment — vorbereitet 13.10.2026: `Schnellstart` startet den Roller mit,
   `config.json` Abschnitt `dienst` je Rechner, `roller.pruefung`, `werkzeuge\server\Deploy.ps1`;
   der Umzug selbst ist AP-15.

## Danach

- Was-wäre-wenn-Prüfung (`whatIf`, Margin) vor jeder Order.
- AP-11: das Journal ordnet Roller-Ketten über `orderReference` zu.
- R4 Schattenmodus (Live-Konto lesend; eher auf dem Server).
- Roll-Statistik je Strategie; Wiedereinstieg (zurückgestellt).

## Offene Annahmen

Siehe `OFFENE_FRAGEN.md`, OF-85.

---

## Vorschlag für `plan/zielbild-station.md`

**Tabelle „Systeme“, Zeile Options Roller:** `R3 auf Paper (13.10.2026)` · `Seite „Roller“:
Status, Ketten, Eröffnen, Roll-Freigabe`.

**IB-Client-IDs, Ergänzung:** Alle Orders des Rollers laufen über clientId 3 — IB lässt eine
Order nur von der clientId stornieren, die sie aufgegeben hat.

**Rechner, Ergänzung „Marktdaten“ (Befund 13.10.2026):** Läuft die Live-TWS derselben
Anmeldung auf einem anderen Rechner, bekommt die Paper-TWS keine Daten (`10197`,
historisch `162 … different IP address`). Mit geteilten Abos liefert die Paper-TWS
Live-Daten, die Live-TWS dann nicht. Ohne Teilen und nach Neustart: verzögerte Daten.
Die Paper-Simulation füllt Kombis meist erst nahe am natürlichen Preis.

**Roller, neuer Abschnitt „Rollregel (Nutzer, 13.10.2026)“** — je Strategie konfigurierbar:

- Signal: |Delta| des Short über der Schwelle seiner Restlaufzeit — ≤ 7 DTE 0,38 ·
  ≤ 14 DTE 0,42 · ≤ 21 DTE 0,46 · ≤ 28 DTE 0,50; darüber abwarten.
- Ziel +1 Woche; +2 Wochen nur als letzte Option. Breite und Kontraktzahl bleiben.
- Put-Spread horizontal mit Kredit, sonst diagonal nach unten, kostenneutral.
  Call-Spread immer diagonal nach oben, kostenneutral.
- Nach dem Roll: neues Short-Delta mindestens 0,05 unter der Schwelle der neuen Laufzeit.
- Kostenneutral: Mittelkurs, Nachziehen höchstens bis 0,10 Debit (RUT 0,05, DAX 1,0).
- Gap (|Delta| ≥ Schwelle + 0,10 oder Short im Geld): Debit bis 50 % des Erstkredits.
- Kein zulässiger Roll: nur alarmieren.
- Profit-Target: Restwert (SPX 0,50, DAX 2 Pkt), höchstens Nettokredit der Kette minus
  ein Tick — die Kette soll positiv schließen.
- Early Exit aktiv: am Verfallstag in den letzten 30 min, wenn |Delta| ≥ 0,15 und kein Roll
  fällig ist (Roll-Regel 0,38 hat Vorrang); Vorschlag mit Freigabe.
- Handelszeit laut IB (Feiertage, Halbtage), 15 min Abstand zu Beginn und Ende.
- Keine Obergrenze für die Zahl der Rolls; kumulierter Roll-Debit höchstens 100 % des
  Erstkredits, danach Alarm (OF-85, entschieden 13.10.2026).
- Wiedereinstieg zurückgestellt. Mails an die eingetragenen Empfänger.

**Roller, Stufe:** „R3 Vorschlag + Freigabe per Klick (Paper-Konto) — läuft“; Order-Sperre
seit R3 nur für die Dauer einer Bestellung gesetzt und nur gegen Paper (Port 7497, Konto `DU…`).

## Automatik (R5 auf Paper) — 14.10.2026

Nutzerwunsch: im Paper-Konto direkt automatisieren, um besser zu testen. Umgesetzt im Roller
(`StrategieWaechter`, Standard **aus**, Schalter in der Station, „Not-Aus“ wirkt sofort):
zulässige Rolls und Early Exits führt der Roller selbst aus. Leitplanken: nur Paper (Port 7497,
Konto `DU…`), nur Handelszeit laut IB, nur Vorschläge innerhalb der Regeln, höchstens 10 Aktionen
am Tag über alle Ketten (`auto_max_pro_tag`), nach einem nicht gefüllten Versuch keine weitere
Automatik für diese Kette am selben Tag, angehaltene Ketten nie, optional nur mit Live-Daten
(`auto_nur_live`), jede Aktion als Mail. Eröffnungen bleiben Handarbeit (Wiedereinstieg
zurückgestellt). Zustand in `%LOCALAPPDATA%\OptionsRoller\auto.json` (überlebt Neustarts).
Für das Live-Konto ist die Automatik gesperrt — dafür braucht es R4 (Schattenmodus) und ein eigenes Paket.
