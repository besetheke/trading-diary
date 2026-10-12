# Zielbild · Trading Station (Stand 12.10.2026)

Entscheidung des Nutzers: **ein Werkzeug statt vieler** — zumindest die Oberfläche
ist eine; dahinter dürfen verschiedene Systeme laufen.

## Form: Föderation

- **Oberfläche:** die Web-Oberfläche des Journals ist die Station (Bereiche
  Journal · Abgleich & Tests · Roller · Momentum Lab · Breakout · System).
- **Dienste:** jedes System bleibt ein eigener Prozess mit eigener Datenbank und
  eigenen Tests und liefert eine kleine lokale Schnittstelle (Status, Daten,
  Befehle). Fällt ein Dienst aus, zeigt die Station ihn rot; die anderen laufen weiter.
- **Gemeinsam:** Startskript, Seite „System“, Konfiguration für IB-Zugang und
  Client-IDs, Backup; später eine gemeinsame Bibliothek (Symbole, Instrumente).
- **Nicht verschmolzen:** das Absetzen von Orders bleibt ein eigener, kleiner,
  getesteter Prozess (Roller).

IB-Client-IDs: OptionApp 1 · Downloader 2 · Roller 3 · Journal 4 (Basiswertkurse,
geplant) · 9 für Lesetests.

## Rechner

Entwicklung und Paper-Tests auf **NOX** (`C:\10_Coding`). Betrieb später auf dem
**Server**; dort wird nicht entwickelt — Stand kommt per Git und Deploy-Skript.

## Systeme

| System | Stand | Einbindung |
|---|---|---|
| Trading Journal | produktiv | ist die Station |
| Options Roller | R1 erledigt (12.10.2026) | Seite „Roller“, ab R2 mit Status |
| Momentum Lab | eigene Streamlit-Oberfläche, Port 8501 | eingebettet (Seite „Momentum Lab“) |
| Breakout Research | wird nach `C:\10_Coding` kopiert | Platzhalter, danach eingebettet bzw. API |

## Roller: Weg zum automatischen Rollen

R1 Inbetriebnahme → R2 im Cockpit sichtbar → R3 Vorschlag + Freigabe per Klick
(Paper-Konto) → R4 Schattenmodus → R5 Automatik mit Leitplanken: Freischaltung je
Strategie, höchstens N Kontrakte, nur Limit-Orders, maximale Zahl der Rolls und
maximaler kumulierter Roll-Verlust je Kette (Lehre DAX: BPS noExit, Kette 3840),
Tageslimits, Not-Aus, Protokoll und Mail je Aktion, kein Doppel-Abschicken.
Order-Sperre seit R1: nur mit `ROLLER_ORDERS_FREIGEGEBEN=ja`.
