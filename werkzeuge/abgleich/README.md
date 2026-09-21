# Abgleich gegen die Golden-Daten

Diese Skripte sind der Nachweis für die Abnahme von AP-03 (Plan §6, zwei
Hälften: Bestandsabgleich und Geldtest). Sie liegen im Repo, damit sich jede
Prüfung nach einer Nachbesserung unverändert wiederholen lässt — eine
Neufassung aus dem Gedächtnis kann sich unbemerkt unterscheiden.

**Regeln (CLAUDE.md, Regel 2):**

- Die Skripte lesen `fixtures/golden/`, schreiben nichts und legen keine
  Datenbank an; alles läuft im Speicher.
- Ausgegeben werden ausschließlich Zählwerte, Aufzählungswerte, relative
  Größenordnungen und Pseudonyme — keine Beträge, Titel, `conid`s oder
  Kontonummern. Das gilt auch für Fehlermeldungen.
- Nur Pakete des starken Modells führen sie aus.

**Provisorisch:** Solange der Import das echte Flex-Format nicht liest
(OF-19 bis OF-22), passen die Skripte ihn nur im eigenen Prozess an. Diese
Anpassungen sind Befund, nicht Lösung, und entfallen nach der Nachbesserung von
AP-02.

| Skript | Prüft |
|---|---|
| `golden_barausgleich.py` | Geldtest je schließender Ausführung und je Basiswert, mit und ohne Barausgleich (OF-24, OF-25) |
| `golden_lieferart.py` | Ob `settlementPolicyMethod` barausgeglichene von physischen Zuteilungen trennt (OF-25) |
| `golden_bestandsabgleich_of23.py` | Bestandsabgleich mit dem echten `ingest.flex`-Parser und der echten `engine.matching.bilde_legs()`; `kapitalmassnahmen` wird für den Lauf aus `CorporateAction`-Rohzeilen nach `actionID` abgeleitet (OF-23, OF-27) |
| `golden_geldtest_fifopnl.py` | Genauigkeitsprüfung: Geldtest je schließender Ausführung gegen IBs `fifoPnlRealized` (roh, nicht periodenaggregiert — vermeidet die Überlappung der Exporte); Re-Lauf der OF-24-Messung mit dem echten, jetzt korrigierten Matching |
| `golden_geldtest_restdifferenz_je_instrument.py` | Erzeugt `auftraege/AP-03-restdifferenz-je-instrument.csv` — die für AP-04 bezifferte Prämien-Restdifferenz je Instrument (Pseudonym), nicht nur aggregiert |
| `golden_geldtest_vollstaendigkeit.py` | Vollständigkeitsprüfung: importierte Ausführungen (IBs `fifoPnlRealized`) gegen IBs `FIFOPerformanceSummaryInBase` je verfügbarem, modellfreiem Fenster und Anlageklasse — deckt fehlende Round Trips auf, die die Genauigkeitsprüfung nicht sehen kann |
| `pseudonym.py` | Gemeinsamer Baustein: stabiler, gesalzener Hash je `conid` für Ausgaben, die Instrumente einzeln referenzieren müssen (Regel 2); Salz liegt bei `fixtures/golden/`, außerhalb des Repositorys |
| `golden_ketten_invarianten.py` | AP-04: prüft `engine.chains.bilde_chains()` gegen die gesamte Golden-Historie auf vier Invarianten (keine Structure in zwei Ketten, nur das letzte Kettenglied darf offen sein, jede Rollverknüpfung bleibt auf demselben Underlying, Ketten- und Struktur-Ergebnissumme stimmen überein) — die zweite der drei AP-04-Abnahmeprüfungen |
| `golden_oa_abgleich.py` | AP-04: vergleicht das erste Kettenglied je `oa_trade` gegen die Leg-Zusammensetzung eines echten OptionApp-Exports (`Trades_JJJJ-MM_OA.xlsx`) — die erste der drei AP-04-Abnahmeprüfungen; weist Abweichungen durch kontoweite Verrechnung eigens aus (OF-36) |
| `golden_ketten_stichprobe.py` | AP-04: erzeugt die Prüfdatei `fixtures/golden/Stichprobe_Ketten[_vN].xlsx` für die dritte Abnahmeprüfung — gerollte DAX/ESTX50-Ketten (Heuristik, Belegt) und eine nach Grund geschichtete Gegenprobe nicht verketteter Paare, mit Eröffnungs- und Schlusspreis je Glied. **Einzige Ausnahme vom Schreibverbot:** schreibt genau diese Datei, nur nach `fixtures/golden/`. Überschreibt nie: ein zweiter Lauf legt `_v2` an und übernimmt die Urteile der jüngsten Fassung |

**Fehlermeldungen:** Parserfehler nennen Tradenummer und Zellwert. Jedes
Skript, das echte Exporte parst, fängt sie ab und gibt nur das betroffene
Feld aus (Zwischenfall OF-40).

Aufruf aus dem Projektverzeichnis:
`.venv\Scripts\python.exe werkzeuge\abgleich\<skript>.py`
