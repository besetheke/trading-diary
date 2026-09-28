---
titel: Campaign-Kandidaten (engine/campaigns.py)
modell: guenstig
status: fertig
abhaengig_von: AP-05v
---

# AP-05k · Campaign-Kandidaten

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-05v). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag 1–7 in `auftraege/AP-05v.md`. Lies ihn
vollständig, samt dem Abschnitt „Die drei Entscheidungen, die nicht beim
Umsetzer liegen".

## Worum es geht

Zwei Kandidatenregeln aus dem Plan (§6, AP-05) als reine Funktion über
bereits gebildete Ketten: **IC-Kandidat** (zwei Ketten, die zusammen einen
Iron Condor ergeben könnten) und **Financing-Kandidat** (eine neue Kette
als mögliche Gegenfinanzierung eines Rolls). Beides sind **Vorschläge** —
nichts wird entschieden, nichts gespeichert, nichts klassifiziert. Das
kommt in einem späteren Paket.

## Zu bauen

Ein einziges neues Modul: `engine/campaigns.py`, mit
`CampaignKandidat` und `campaign_kandidaten()` nach Vertrag 1–7.

## Wo du abschreiben sollst statt neu zu erfinden

- **Baumuster für eine Kandidatenfunktion**: `engine/chains.py`,
  `rollkandidaten()` und `Rollkandidat` — dieselbe Bauart (reine Funktion,
  gibt ein sortiertes Tupel von Kandidaten zurück, kein Seiteneffekt).
- **Naturschlüssel einer Kette ohne Datenbankzugriff**: das Muster in
  `journal/preise.py`, Funktion `_schluessel()` — dort für Strukturen,
  hier für Ketten über deren erstes Glied (Vertrag 6).
- **`Chain`-Felder**: `engine/chains.py`, Dataclass `Chain` — `seite`,
  `underlying`, `eroeffnet_am`, `beendet_am`, `glieder`.

## Die zwei Stellen, an denen erfahrungsgemäß geraten wird

1. **Überlappung, nicht „beide gerade offen"** (Entscheidung 1). Eine
   offene Kette hat `beendet_am = None` — das heißt „bis auf Weiteres",
   nicht „kein Ende". Beim Intervallvergleich zählt das als unbegrenzt in
   die Zukunft, nicht als Sonderfall, der übersprungen wird.
2. **Der Rollzeitpunkt ist die Eröffnung des rollenden Glieds**, nicht die
   Schließung des vorigen. `glied.structure.eroeffnet_am` des ersten
   Glieds mit `verknuepfungstyp == "roll"` in der Kette.

## Grenzen

- Kein Eingriff in `engine/chains.py`, `engine/structures.py` oder
  `engine/matching.py`.
- Keine Persistenz, keine Migration, keine API, keine Oberfläche.
- Keine Entscheidung, welche Seite „die IC-Seite" und welche „die
  Gegenfinanzierung" ist — laut Plan eine Absichtsfrage, bleibt offen.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_campaigns.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `engine/campaigns.py`.
