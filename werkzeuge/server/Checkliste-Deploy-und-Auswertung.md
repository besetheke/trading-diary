# Server: Deploy und Auswertung der Roller-Läufe

Für den Server (nur Deploy, keine Entwicklung). Stand 17.10.2026: Roller `cc55049` (IB-Preisschutz, Kostenbremse,
gruppiertes Fehlerprotokoll, Auswertungsskript), Journal mit Kettenliste, Titel-Dividenden, Steuer-Seite und
Momentum-Schalter.

## 1. Vorher (2 Minuten)

- [ ] TWS Paper läuft und ist angemeldet (Port 7497), API-Zugriff erlaubt.
- [ ] Keine Position, die der Roller gerade verwaltet, steht mitten in einer Aktion (Station: „beschäftigt“ leer).
- [ ] Automatik-Zustand notieren (Station, Roller): AN oder AUS. Das Deploy ändert `auto.json` nicht.

## 2. Deploy

```
cd C:\10_Coding\trading-diary
.\werkzeuge\server\Deploy.ps1 -Trocken      # nur anzeigen
.\werkzeuge\server\Deploy.ps1               # aktualisieren, migrieren, neu starten, prüfen
```

Erwartet: Pull ohne Konflikt, Roller-Tests grün (362), Journal-Rauchtest grün, danach starten beide Dienste.
Wenn sich `Deploy.ps1` selbst geändert hat, ruft es sich mit `-Neustart` neu auf — das ist normal.

## 3. Nach dem Deploy prüfen

- [ ] Station → Roller: Verbindung grün, Profil (normal/test) wie vorher, Automatik wie notiert.
- [ ] Journal öffnet, Seite „Steuer“ lädt (sie braucht die Flex-Daten des Servers; leere Tabellen sind kein Fehler).
- [ ] `python -m roller.pruefung` meldet keine Fehler (macht das Deploy schon, bei Zweifel von Hand).
- [ ] Mail: Testmail aus der Station oder `python -m roller.mailtest` kommt bei nbillinger@gmx.de an.

## 4. Nach einem Handelstag auswerten

```
cd C:\10_Coding\options-roller
.venv\Scripts\python.exe -m roller.auswertung --tage 1
```

Für mehrere Tage `--tage 5`. Die Ausgabe zeigt je Art (Eröffnung, Roll, Schließen) und je Strategie:

| Spalte | Bedeutung | Worauf achten |
|---|---|---|
| Läufe / gefüllt / Quote | Orders, davon gefüllt | Quote sehr niedrig → Startanteil oder Grenze zu eng |
| Dauer (Median) | Sekunden bis zum Fill | wächst sie stark, zieht der Roller zu langsam nach |
| Weg (Ø, max) | Anteil der Strecke Startpreis → Grenze, bei dem gefüllt wurde (0 = zum Startpreis, 1 = an der Grenze) | Ø nahe 1: der Start (Anteil 0,25) ist zu optimistisch; Ø nahe 0: man könnte höher starten |
| 202 / 2161 | IB-Preisschutz / Deckel | viele 202: Startpreis zu aggressiv für verzögerte Quoten; 2161: IB deckelt still |
| Storno@G | an der Grenze storniert | zeigt, dass die Grenze greift |
| PreSub | am Ende `PreSubmitted` | SPX-0DTE-Rätsel: unten steht dann `whyHeld` |

Darunter: Kostenbremse (Zahl der Fälle mit Zahlen), gruppierte IB-Meldungen, Datenquellenwechsel
(live/verzögert), Automatik-Pausen und die nicht gefüllten Läufe mit Status, Start, Grenze und IB-Codes.

## 5. Was an den Server-Betreuer zurückgemeldet werden soll

1. Die komplette Ausgabe von `python -m roller.auswertung --tage 1` (enthält keine Kontodaten außer Kettennummern).
2. Bei `PreSubmitted`: die Zeilen „whyHeld“ und ob die TWS dort eine Meldung zeigt (Screenshot ohne Konto).
3. Bei Kostenbremse: ob die gemeldeten Zahlen zum Eindruck passen (zu früh oder zu spät gebremst).
4. Auffälligkeiten der Station (z. B. Verbindungsabbrüche mit Uhrzeit).

Die Annahmen, die mit diesen Zahlen geprüft werden, stehen in `OFFENE_FRAGEN.md` (OF-90): Startanteil 0,25,
Kostenbremse 40 % (normal) und 60 % (test), gruppierte Fehlercodes.
