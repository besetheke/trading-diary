# Anleitung: Push-Meldungen aufs Handy mit ntfy

Gilt für AP-18, Stufe 1. Der Code dafür ist noch nicht gebaut (Paket zurückgestellt); diese Anleitung bereitet Handy und Server vor und
lässt sich schon jetzt von Hand prüfen. ntfy ist kostenlos und braucht kein Konto.

## 1. Thema wählen (das ist dein Passwort)

Bei ntfy.sh kann jeder, der den Themennamen kennt, mitlesen und senden. Wähle deshalb einen langen, zufälligen Namen, zum Beispiel
`roller-` plus 20 Zeichen aus Buchstaben und Ziffern (`roller-k7x2m9qa4tb8w3ndf5yc`). Nirgends veröffentlichen, nicht ins Repository.
Alternative ohne Mitleser-Risiko: einen eigenen ntfy-Server im Tailnet betreiben (später, falls gewünscht).

## 2. Handy

1. App „ntfy“ installieren (Android: Play Store oder F-Droid, iPhone: App Store).
2. In der App „+“ → Thema abonnieren → den gewählten Namen eintragen, Server `ntfy.sh` lassen.
3. Benachrichtigungen für die App erlauben. Auf Android zusätzlich: Akku-Optimierung für ntfy ausschalten, sonst kommen Meldungen verspätet.
   Auf dem iPhone sind Meldungen über den ntfy.sh-Server sofort, wenn die App Mitteilungen darf.
4. Für wichtige Meldungen in den Themen-Einstellungen die Priorität „hoch“ als „Nicht stören“-Ausnahme erlauben (Verlustgrenze, Not-Aus).

## 3. Von Hand testen (vom Server aus)

PowerShell auf dem Server:

```powershell
Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/DEIN-THEMA" -Body "Test vom Roller-Server" -Headers @{ Title = "Roller Test"; Priority = "default" }
```

Das Handy muss sofort klingeln. Kommt nichts an: Thema in App und Befehl vergleichen, Akku-Optimierung prüfen, Internetzugang des Servers prüfen
(Port 443 ausgehend genügt, keine Freigabe nach innen).

Dringende Meldung testen:

```powershell
Invoke-RestMethod -Method Post -Uri "https://ntfy.sh/DEIN-THEMA" -Body "Verlustgrenze erreicht" -Headers @{ Title = "Roller ALARM"; Priority = "urgent"; Tags = "warning" }
```

## 4. Was später in der Konfiguration steht

Im Abschnitt `push` der `config.json` des Rollers (nicht ins Repository, der Themenname ist das Geheimnis):

```json
"push": { "dienst": "ntfy", "server": "https://ntfy.sh", "thema": "DEIN-THEMA", "ereignisse": "alle" }
```

Wegen der Geheimhaltung wird das Thema wie das SMTP-Passwort aus dem Windows-Anmeldeinformationsspeicher gelesen, die Konfiguration
nennt dann nur den Schlüsselnamen. Gewollte Ereignisse (Entscheidung vom 25.10.2026): Fills (Eröffnung, Roll, Profit-Target), Roll-Vorschläge,
Roll nicht erfolgreich, Verlust- und Live-Grenze, keine Marktdaten, TWS oder Dienst getrennt, Not-Aus, Automatik-Pause, Order an der Grenze
storniert, Kostenbremse. Nie: das IB-Rauschen (10090, 200, 2188). Die Mail an nbillinger@gmx.de bleibt zusätzlich bestehen.

## 5. Tailscale

Tailscale ist auf Server und Handy vorhanden. Für die spätere lesende Mobilansicht (Stufe 2) wird der Rechnername im Tailnet gebraucht
(`tailscale status` auf dem Server zeigt ihn, Form `servername.tailnet-name.ts.net`). Die Station bleibt dabei nur im privaten Netz erreichbar,
nie öffentlich; Befehle gehen weiter nur aus der lokalen Station.
