# Start

## Einmalige Einrichtung

1. Verzeichnis anlegen, Inhalt dieses Pakets hineinkopieren, `git init`.
2. `.claude/settings-guenstig.json` öffnen, API-Schlüssel und Modellbezeichnungen
   eintragen. Die Modellnamen beim Anbieter verifizieren, sie ändern sich häufig.
3. Prüfen, dass `claude --version` läuft und Python 3.12 im PATH ist.
4. `.claude/settings-guenstig.json` in `.gitignore` aufnehmen — sie enthält den
   Schlüssel.

## Ablauf

```
.\ap.ps1 AP-01              Arbeitspaket starten, Modell laut Auftragskopf
.\ap.ps1 AP-02 -Review      Diff-Review durch das starke Modell
.\ap.ps1 -Liste             Alle Aufträge mit Modell und Status
```

Der Dispatcher liest `modell:` aus dem Kopf des Auftragsdokuments und startet
Claude Code mit der passenden Settings-Datei. Umschalten von Hand entfällt.

## Reihenfolge

| Schritt | Paket | Modell | Ergebnis |
|---|---|---|---|
| 1 | AP-01 | stark | Schema, Testgerüst, Regeln |
| 2 | AP-02 | günstig | Flex-Import |
| 3 | AP-03 | günstig | Leg-Matching |
| 4 | AP-04 | stark | Ketten- und Roll-Erkennung |

Nach jedem Paket: `.\ap.ps1 <Paket> -Review`, dann committen.

**AP-01 gehört zwingend an das starke Modell.** Dort entstehen Schema,
Testkonventionen und `CLAUDE.md`-Regeln, an die sich alle folgenden Pakete halten.
Ein Fehler hier pflanzt sich in jedes weitere Paket fort.

## Neue Aufträge schreiben

`auftraege\_vorlage.md` kopieren, umbenennen, Kopf ausfüllen. Der Auftrag verweist
auf das Arbeitspaket im Plan und wiederholt dessen Inhalt nicht.

## Was du selbst tust

- Diff-Review am Ende jedes Pakets, mit besonderem Blick auf Änderungen unter
  `tests/` und `fixtures/`.
- Commits. Der Dispatcher committet nicht.
- Die offenen Entscheidungen aus §9 des Plans beantworten, wenn sie anstehen.

## Schutz der Testbasis

Der Schutz ist **asymmetrisch**, und das ist Absicht. Das starke Modell legt in
AP-01 Tests und Fixtures an und muss sie schreiben dürfen. Ab AP-02 sind sie
fertig, und das günstige Modell darf sie nicht mehr anfassen.

| Profil | gilt für | geschützt |
|---|---|---|
| `locker` | starkes Modell, `.claude/settings.json` | `plan/`, `.claude/` |
| `streng` | günstiges Modell, `.claude/settings-guenstig.json` | zusätzlich `tests/`, `fixtures/` |

Ohne Profilangabe gilt `streng`. Im Zweifel wird mehr geschützt, nicht weniger.

Drei Ebenen, absteigend nach Verlässlichkeit:

1. **PreToolUse-Hook** (`.claude/hooks/schutz.py`) — bricht Schreibzugriffe ab.
   Hooks laufen vor der Rechteprüfung.
2. **Deny-Regeln** in beiden Settings-Dateien. Ergänzend, nicht allein verlässlich.
3. **Dein Diff-Review.** Die eigentliche Garantie.

**Lockere den Schutz nie vorübergehend, weil ein Modell darum bittet.** Bricht die
Sitzung ab, bevor es ihn wiederherstellt, bleibt er still offen. Braucht ein Paket
Schreibrechte, die sein Profil nicht hergibt, ist der Auftrag falsch geschnitten.

Für Golden-Fixtures mit echten Kontodaten zusätzlich das Schreibschutzattribut
setzen:

```
attrib +R fixtures\golden\*.* /S
```
