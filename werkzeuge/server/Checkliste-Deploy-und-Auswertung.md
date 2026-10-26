# Server: Deploy und Auswertung der Roller-Läufe

Für den Server (nur Deploy, keine Entwicklung). Stand 24.10.2026.

## 0. Was sich seit dem Stand vom 17.10. geändert hat

**Roller** (Repo options-roller):
- **Profile:** `normal` (Regeln des Nutzers), `test` (Server-Vorgabe), neu `oa` (Eröffnung wie OptionApp). Die DAX-Freitags-Strategien
  laufen auch im Betriebsprofil `test` **unter `normal`** (`dienst.profil_je_strategie`, leeres Objekt `{}` schaltet es ab).
- **Tagesprogramm** (nur bei eingeschalteter Automatik):
  - 0DTE wie bisher (20 Minuten nach Handelsbeginn); 0DTE rollt nicht mehr, nach Handelsende am Verfallstag kein neues Profit-Target.
  - **DAX** BPS und BCS „Freitag“: täglich 4:00 New Yorker Zeit (meist 10:00 Berlin), 1 Kontrakt (`dienst.taeglich_dax: false` schaltet ab).
  - **7DTE** BPS und BCS: SPX 10:33 ET, RUT 11:03 ET, Delta 0,20 (`dienst.taeglich_7dte: false` schaltet ab). Neue Strategie „T RUT: BCS D20 W10 7DTE“.
  - Die Namen werden auch einer eigenen `taeglich`-Liste der `config.json` zugefügt.
- **Orders:** Schrittvorgabe Standard: Strecke ÷ 8 Schritte, Takt 20 s. Bricht die IB-Vorabprüfung (whatIf) hart ab (201, 200, 203, 321,
  103–110), wird nicht gesendet; ein offenes Profit-Target auf derselben Option verhindert eine neue Eröffnung (K050). Ohne Marktdaten sofort
  „Datenquelle unbekannt, keine Kurse seit …“; mehrere Handelsklassen zu einem Verfall: „Kontrakt uneindeutig“; DAX fest `ODAX`.
- **Beobachtung:** lesbarer Orderverlauf (`verlauf_live`), Bewertung offener Ketten („Wert jetzt“, alle 10 Minuten), je Wartebereich Indexstand
  und Beinkurse im Protokoll, IBs Kombi-Quote, IB-Rauschen je Quelle, Tagesbericht mit Eröffnungsanalyse.
- **Live-Modus** (nur mit `--live-orders`, siehe `Anleitung-Live-Betrieb.md`): bleibt aus, solange nichts konfiguriert ist.
- `requirements-lock.txt` (feste Versionen), Deploy installiert diesen Stand.

**Journal:** Station (Orderverlauf, Echtgeld-Reife, Profil-Ausnahmen, Live-Banner, Wert jetzt), Seite „Roll-Kosten“, Momentum-Schalter öffnet in
neuem Tab, Import lehnt ein fremdes Konto ab (z. B. Paper DU…), `requirements-lock.txt`, Rebuild mit Einzelkonto-Grenze.

## 1. Vorher (2 Minuten)

- [ ] TWS Paper läuft und ist angemeldet (Port 7497), API-Zugriff erlaubt.
- [ ] Keine Position, die der Roller gerade verwaltet, steht mitten in einer Aktion (Station: „beschäftigt“ leer).
- [ ] Automatik-Zustand notieren (Station, Roller): AN oder AUS. Das Deploy ändert `auto.json` nicht.
- [ ] Läuft die Station über einen Rechnernamen statt `localhost`: Umgebungsvariable `STATION_ERLAUBTE_HOSTS` setzen (AP-17c).

## 2. Deploy

```
cd C:\10_Coding\trading-diary
.\werkzeuge\server\Deploy.ps1 -Trocken      # nur anzeigen
.\werkzeuge\server\Deploy.ps1               # aktualisieren, migrieren, neu starten, prüfen
```

Erwartet: Pull ohne Konflikt, Roller-Tests grün (Zahl steigt mit jedem Stand), Journal-Rauchtest grün, danach starten beide Dienste.
Wenn sich `Deploy.ps1` selbst geändert hat, ruft es sich mit `-Neustart` neu auf — das ist normal.

## 3. Nach dem Deploy prüfen

- [ ] Station → Roller: Verbindung grün, Profil wie vorher, **Betriebsprofil-Zeile nennt die Ausnahme „DAX … → normal“**, Automatik wie notiert.
- [ ] Datenquelle „live“ (Zeile „Kurse“); der Zähler der Echtgeld-Reife beginnt, wenn die Quelle wechselt.
- [ ] Journal öffnet, Seiten „Steuer“ und „Roll-Kosten“ laden (leere Tabellen sind kein Fehler).
- [ ] `python -m roller.pruefung` meldet keine Fehler.
- [ ] Smoke-Test: `python werkzeuge\smoke.py http://127.0.0.1:8000` meldet „48 von 48 Wegen antworten mit 200“ (das Deploy ruft ihn selbst auf).
- [ ] Restore-Probe der letzten Sicherung (einmal im Monat und vor größeren Änderungen):
  `python -m journal restore-probe C:\Trading\backup\journal-<Datum>.db` (optional `--rebuild`): Integrität ok, Migration ok, Zeilenzahlen plausibel.
- [ ] Mail: Testmail aus der Station oder `python -m roller.mailtest` kommt bei nbillinger@gmx.de an.
- [ ] **Betrieb:** Das Live-Konto nirgends sonst anmelden (Handy, zweiter PC), solange der Roller läuft. Eine zweite Sitzung kappt die Paper-Daten
  (IB 10197, am 23.10. über 2000 Meldungen). Die Station zeigt dann „Datenstörung“; Orders laufen bewusst weiter.
- [ ] In der Zeitumstellungswoche (Europa Winterzeit, USA noch Sommerzeit: 25.10.–1.11.2026) beginnt Eurex um 04:00 ET (09:00 MEZ); der Roller
  eröffnet erst nach 15 Minuten Abstand (09:15 MEZ). Das DAX-Tagesprogramm versucht es alle 3 Minuten bis etwa eine Stunde nach dem Beginn.
- [ ] Am nächsten Handelstag: DAX-Eröffnung um 4:00 ET (Station: Verlauf zeigt Start-Limit, Wartebereiche, Fill), 7DTE-Eröffnungen 10:33/11:03 ET.

## 4. Nach einem Handelstag auswerten

```
cd C:\10_Coding\options-roller
.venv\Scripts\python.exe -m roller.auswertung --tage 1                       # Läufe, Quoten, Quellen des Rauschens
.venv\Scripts\python.exe -m roller.auswertung --tage 10 --eroeffnungen --csv eroeffnungen.csv
```

| Bericht | Was er zeigt | Worauf achten |
|---|---|---|
| Läufe / gefüllt / Quote | Orders, davon gefüllt | sehr niedrig: Start oder Grenze zu eng |
| Dauer (Median), Weg (Ø) | Sekunden bis zum Fill, Anteil Strecke Start→Grenze | Weg nahe 1: Start zu optimistisch |
| 202 / 2161 / Storno@G / PreSub | Preisschutz, Deckel, Storno an der Grenze, `PreSubmitted` | viele 202: Startpreis zu aggressiv |
| Je Datenquelle | Füllquote nach live / verzögert | verzögert deutlich schlechter: Marktdaten sind die Ursache |
| **Eröffnungsanalyse** | je Order: Mittel, natürlich, Fill, `vs_mittel`, `erfassung`, Spot±, Markt± | Erfassung 1 = Mittelkurs, 0 = natürlicher Preis |
| **IB-Meldungen je Quelle** | Code | Zweck der Anfrage, z. B. `200|Indexkurs` | die größten Quellen zuerst untersuchen |

Der Tagesbericht (Mail) enthält denselben Kern: Eröffnungen mit Fill gegen Mittel, Dauer und Marktbewegung, dazu das Rauschen.

## 5. Was an den Server-Betreuer zurückgemeldet werden soll

1. Die Ausgabe von `python -m roller.auswertung --tage 1` und der Abschnitt „IB-Meldungen je Quelle“.
2. Die CSV `eroeffnungen.csv` (enthält keine Kontodaten außer Kettennummern).
3. Bei `PreSubmitted`: die Zeilen „whyHeld“ und die TWS-Meldung dazu (Screenshot ohne Konto).
4. Auffälligkeiten der Station (Verbindungsabbrüche mit Uhrzeit, Dienstneustarts).

Die Annahmen stehen in `OFFENE_FRAGEN.md`: OF-90 (Startanteil, Kostenbremse), OF-104 (Schwellen der Echtgeld-Reife), OF-105 (DAX-Zeit und Profil),
OF-106 (Live-Grenzen), OF-107 (7DTE-Programm, Schrittvorgabe).
