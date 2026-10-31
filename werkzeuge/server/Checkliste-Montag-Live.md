# Checkliste: Live-Start DAX am Montag, 02.11.2026 (AP-21)

Alles, was ohne dich möglich ist, steht im Deploy. Offen bleiben nur Schritte, die ausdrücklich du ausführst: Kontonummer,
Freigabe und die Bestätigung „ECHTGELD“.

## 1. Deploy (Server, PowerShell)

```
cd C:\10_Coding\trading-diary
.\werkzeuge\server\Deploy.ps1
```

Der Deploy startet jetzt auch den **lesenden Live-Dienst** (Port 8601) und setzt `ROLLER_LIVE_STATUS_PORT=8601` für das Journal.
Am Ende prüft er die Live-Konfiguration (`python -m roller.live_einrichten --pruefen`) und meldet, was noch fehlt. Lief vorher
der Live-Dienst **mit Orders**, startet der Deploy ihn bewusst nicht neu (Eingabe „ECHTGELD“ nötig); eine Warnung sagt es.

## 2. Einmalig: Live einrichten (du)

```
cd C:\10_Coding\options-roller
.\Live-Einrichten.ps1
```

Fragt nach der Live-Kontonummer (`U…`) und dem Freigabetext (`ECHTGELD-FREIGEBEN`, genau so tippen). Schreibt den Abschnitt `live`
mit den Werten aus `config.beispiel.json` (Strategien DAX BPS D12 W250 14DTE 2 Kontrakte und BCS D12 W200 14DTE 1 Kontrakt,
max. 2 offene Ketten, kein Tagesverlust-Limit, Rolls nur per Freigabe) in `config.json`; Sicherung `config.vor-live-<Zeit>.json`.
Die Kontonummer erscheint nie in einer Ausgabe.

## 3. Live-Dienst starten (du, Fenster)

1. Live-TWS (Port 7496, eigener IB-Benutzer, API aktiv) angemeldet.
2. `.\Start-Dienst-Live.ps1`. Das Skript prüft **zuerst** Konfiguration und TWS-Port; fehlt etwas, bleibt der Lesedienst unangetastet.
   Dann „ECHTGELD“ eintippen. Das Skript ersetzt den Lesedienst (Port 8601) durch den Dienst mit Orders.
3. Station → Roller → Live: Karte „Strategien (LIVE-Konto)“ mit Konto, Strategien, Grenzen, Profil `normal`; „Neu prüfen“ ohne
   Fehler; **Automatik AN** (sonst keine Eröffnung um 15:45).
4. Im Block „Roller-Automatik“ stehen die geplanten Termine „Mo 02.11. 15:45“ für beide Strategien.

## 4. Montag 15:45 Berlin

- Die Automatik eröffnet BPS (2 Kontrakte) und BCS (1 Kontrakt). **Verfall:** Liegt kein Verfall auf Montag + 14 Tage, nimmt der
  Roller den nächstliegenden (bei DAX voraussichtlich Freitag 13.11., 11 DTE) — vorher entscheiden, ob das so gewollt ist.
- TWS daneben beobachten; Profit-Targets (GTC) müssen als Orders bei IB stehen. Rolls und Schließen nur per Klick mit Bestätigung.
- **Not-Aus:** Live-Karte „Not-Aus: Automatik aus“ oder `.\Beenden-Dienst.ps1 -Port 8601` (offene Orders bleiben bei IB).

## 5. Danach

Review der Rollstrategie am Freitag, 13.11.2026 (AP-20). Push aufs Handy (AP-18) ist noch nicht gebaut: Roll-Vorschläge kommen
bis dahin per Mail.
