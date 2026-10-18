---
titel: Trading-Befehle nur aus der Station (R01, Korrekturpaket)
modell: stark
status: fertig
abhaengig_von: AP-17
aendert_tests: ja
---

# AP-17c · Schutz der Trading-Steuerung (Review R01)

**Befund (18.10.2026, geprüft):** `POST /journal/roller-befehl/{name}` und `POST /journal/momentum/{aktion}` hatten keine Prüfung
der Herkunft. Der Server bindet an `127.0.0.1`, das schützt aber nicht vor einer Webseite im Browser desselben Rechners
(einfaches Formular-POST, DNS-Rebinding). Mildernd: Der Roller handelt nur am Paper-Konto, in der Handelszeit und innerhalb seiner
Leitplanken — der Fehler hätte also Automatik an/aus, Eröffnungen und Freigaben am Paper-Konto ausgelöst, nicht Live-Orders.

## Regel (vor jeder Handlung, 403 bei Verstoß)

1. **Host** muss `localhost`, `127.0.0.1` oder `::1` sein (zusätzliche Namen nur über die Umgebungsvariable
   `STATION_ERLAUBTE_HOSTS`, kommagetrennt — z. B. wenn die Station über einen Servernamen aufgerufen wird).
2. **Header `X-Trading-Station: 1`**: Ein fremder Aufrufer darf ihn ohne Vorabfrage nicht senden (die API hat kein CORS); die
   Oberfläche setzt ihn bei allen Schreibaufrufen.
3. **Origin**, falls vorhanden, muss zum Host passen; **Sec-Fetch-Site**, falls vorhanden, `same-origin` oder `none`
   (`same-site`, etwa eine andere Seite auf localhost mit anderem Port, wird abgelehnt).

Gilt für Roller-Befehle und Momentum Start/Stopp (`api/app.py`, `pruefe_station_aufruf`).

## Ändernde Tests (namentlich, CLAUDE.md 1a)

Die bestehenden Tests rufen die Route wie ein ungeschützter Client auf. Geändert wird nur der **Aufruf** (lokale Adresse und Header
der Station), nicht das, was geprüft wird:

- `tests/test_api_roller_befehl.py`: Hilfsfunktion `_klient` (Basisadresse `http://localhost`, Header der Station).
- `tests/test_api_roller_befehl_aufnehmen.py`: beide Tests (gleiche Anpassung des Clients).

Neu: `tests/test_api_trading_schutz.py` (der Angriff des Reviews, fremde Herkunft mit Header, fehlender Header, DNS-Rebinding,
Sec-Fetch-Site, legitimer Aufruf, zusätzlicher Host, Momentum).

## Hinweis für den Server

Wird die Station am Server über einen anderen Namen als `localhost`/`127.0.0.1` aufgerufen, vor dem Neustart des Journal-Dienstes
`STATION_ERLAUBTE_HOSTS` setzen (z. B. in `Start-Dienst`/Umgebung), sonst antwortet die Station auf Befehle mit 403.
