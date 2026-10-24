# Anleitung: Roller im Live-Betrieb (Echtgeld)

Stand 24.10.2026. **Entscheidungshilfe, keine Freigabe**: den Schritt auf Echtgeld entscheidet der Nutzer. Voraussetzungen und Abnahmen stehen in
`Checkliste-Echtgeld.md`. Der Roller handelt ohne diese Anleitung weiter nur gegen Paper (Port 7497, Konto `DU…`).

## Was der Live-Modus ist

Ein eigener, ausdrücklicher Start (`--live-orders` bzw. `Start-Dienst-Live.ps1`). Er startet nur, wenn **alles** in der Konfiguration steht
(`roller/live.py`):

| Sicherung | Bedeutung |
|---|---|
| Freigabetext | `live.freigabe` = genau `ECHTGELD-FREIGEBEN` |
| Konto | `live.konto` = Echtgeld-Kontonummer (`U…`, nicht `DU…`); alle verbundenen Konten müssen `U…` sein und dieses Konto enthalten |
| Port | IB-Port 7496 (Live-TWS) |
| Profil | `dienst.profil` = `normal` oder `oa`, nie `test` |
| Datenordner | eigener Ordner `OptionsRollerLive` (setzt das Start-Skript über `ROLLER_DATEN_NAME`): Paper- und Live-Ketten mischen sich nie |
| Strategien | `live.strategien` nennt die erlaubten Strategien; leer = nichts erlaubt |
| Grenzen | `max_kontrakte` (1), `max_offene_ketten`, `max_eroeffnungen_pro_tag`, `max_tagesverlust` je Währung (Netto der heute geschlossenen Ketten), `max_margin_aenderung` je Eröffnung laut IB-Vorabprüfung (fehlt die Antwort, wird nicht eröffnet) |
| Automatik, Tagesprogramm | gesperrt, bis `automatik_erlaubt` bzw. `tagesprogramm_erlaubt` auf `true` stehen |

In der Station zeigt ein Banner „ECHTGELD-MODUS“ Konto, erlaubte Strategien, Grenzen und den heutigen Verlust.

## Konfiguration (Vorlage `config.beispiel.json`, Abschnitt `live`)

```json
"dienst": { "ib_port": 7496, "profil": "normal", "live_orders": false, ... },
"live": {
  "freigabe": "ECHTGELD-FREIGEBEN",
  "konto": "U1234567",
  "strategien": ["DAX: BPS D10 W300 Freitag", "DAX: BCS D10 W300 Freitag"],
  "max_kontrakte": 1, "max_offene_ketten": 4, "max_eroeffnungen_pro_tag": 2,
  "max_tagesverlust": {"EUR": 300}, "max_margin_aenderung": 5000,
  "automatik_erlaubt": false, "tagesprogramm_erlaubt": false
}
```

Die Zahlen sind Vorgaben, **die Werte legt der Nutzer fest** (OF-106). `live_orders` bleibt in der Datei `false`; gestartet wird bewusst über das Skript.

## Inbetriebnahme (Reihenfolge)

1. Paper-Dienst beenden (`Beenden-Dienst.ps1`): auf demselben Statusport darf nur ein Dienst laufen.
2. Live-TWS starten und anmelden (Port 7496, API aktiviert).
3. `config.json` prüfen: `python -m roller.pruefung` meldet „Live-Modus: alle Sicherungen gesetzt“ oder nennt die fehlende Sicherung.
4. `.\Start-Dienst-Live.ps1` und „ECHTGELD“ eintippen. Dienstlog: `%LOCALAPPDATA%\OptionsRollerLive\logs`. Verweigert der Dienst den Start,
   steht der Grund in `dienst-<Datum>-fehler.log` (z. B. „Live-Freigabe fehlt“).
5. Station: Banner prüfen, Konto stimmt, Automatik **gesperrt**.
6. Erste Eröffnung von Hand per Klick: 1 Kontrakt. Verlauf in der Station beobachten (Start-Limit, Wartebereiche, Fill), Mail prüfen.

## Täglicher Betrieb und Not-Aus

- Rolls und Early Exits führt der Nutzer per Freigabe aus; die Kostenbremse meldet „Weiterrollen oder Schließen?“, die Entscheidung liegt beim Nutzer.
- **Not-Aus:** Station → „Automatik aus“ (wirkt auch während eines Tagesprogramms); bei Störung `Beenden-Dienst.ps1`. Profit-Targets (GTC) bleiben
  bei IB bestehen.
- Das Journal bekommt die Ausführungen über den normalen Flex-Import desselben Kontos (`U…`); Roller-Orders tragen die `orderRef` `R3|…`.
  Das Paper-Konto darf nie in diese Datenbank (der Import lehnt es ab).

## Rückweg zu Paper

`Beenden-Dienst.ps1`, Live-TWS schließen, Paper-TWS starten, `Start-Dienst.ps1` (ohne `ROLLER_DATEN_NAME`, damit der Paper-Datenordner gilt).

## Nicht Teil dieser Anleitung

Steuerliche Behandlung der Live-Trades (Steuer-Seite ist ein Arbeitsstand), Mehrkonto im Journal, IBC.
