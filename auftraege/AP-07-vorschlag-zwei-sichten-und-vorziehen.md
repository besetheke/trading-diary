---
titel: Textvorschlag Plan - zwei Sichten (OF-36) und Vorziehen der Lese-Oberflaeche
modell: stark
status: vorschlag
abhaengig_von: AP-04
---

# Vorschlag: Zwei Sichten, und die Oberfläche vorziehen

**Kein Arbeitspaket.** Fertiger Ersatztext für
`plan/trading-journal-projektplan.md`. `plan/` ist für Modelle gesperrt,
deshalb liegt er hier zum Übernehmen. **Sobald er im Plan steht, kann diese
Datei gelöscht werden.**

Grundlage: zwei Entscheidungen des Nutzers vom 22.09.2026 — OF-36 wird mit
**zwei Sichten** beantwortet, und die Lese-Oberfläche wird vor die Analytik
gezogen.

---

## 1 · Neuer Abschnitt in §5 (Datenmodell), vor den Tabellen

> ### Zwei Sichten auf dieselben Ausführungen
>
> Ein Ergebnis lässt sich auf zwei Arten zurechnen, und beide werden
> gebraucht:
>
> - **Kontosicht (netto).** FIFO je `conid` über das ganze Konto, genau wie
>   IB es rechnet. Halten zwei Vorgänge gegenläufige Positionen im selben
>   Kontrakt, verrechnen sie sich. **Diese Sicht ist für Geld maßgeblich**:
>   Sie trägt die Abnahme aus AP-03, und nur sie speist die steuerliche
>   Auswertung (AP-10).
> - **Kettensicht (brutto).** Zurechnung je Vorgang, wie die OptionsApp sie
>   führt: Ein Trade behält seine Beine, auch wenn ein anderer sie
>   kontoweit ausgeglichen hat. Sie beantwortet „wie schneidet diese
>   Strategie ab" und trägt die Roll-Degradation.
>
> **Warum beide.** Gemessen über die Historie betrifft der Unterschied 206
> Ausführungen in 184 Vorgängen, mit steigender Tendenz (OF-36). Die Summe
> über alles ist in beiden Sichten gleich; was sich verschiebt, ist die
> Zurechnung zwischen zwei Vorgängen. Für die Steuer wäre die Kettensicht
> falsch, für die Strategiefrage die Kontosicht unbrauchbar.
>
> **Getrennt gehalten, umschaltbar gezeigt.** Die beiden Sichten entstehen
> aus **zwei getrennten Zuordnungen** derselben Ausführungen, nicht aus zwei
> Darstellungen derselben Zahlen: Die Kettensicht verlangt eine eigene
> Zuordnung innerhalb des Vorgangs, sonst bliebe das ausgeglichene Bein
> verschwunden. Sie werden getrennt gespeichert und nie vermischt. Die
> Oberfläche zeigt eine davon und erlaubt das Umschalten; **jede Zahl trägt,
> aus welcher Sicht sie stammt.** Eine Summe über beide Sichten gibt es
> nicht.
>
> **Reihenfolge.** Die Kontosicht ist gebaut (AP-03, AP-04). Die Kettensicht
> ist ein eigenes Paket und wird vor AP-06 gebraucht, nicht vorher — bis
> dahin zeigt die Oberfläche die Kontosicht und sagt das auch.

## 2 · Ersetzt AP-07

> ### AP-07 · API
> **Ziel:** FastAPI-Schicht über Analytik und Benutzerdaten.

**Neu:**

> ### AP-07 · API
> **Ziel:** FastAPI-Schicht über die Daten des Journals.
>
> **Zweigeteilt (Nutzer, 22.09.2026).** Der Plan verkettete bisher
> AP-06 → AP-07 → AP-08, sodass die erste bedienbare Oberfläche hinter der
> vollständigen Analytik lag. Positionen, Strukturen und Ketten stehen aber
> seit AP-04 in der Datenbank und brauchen keine Kennzahl, um sichtbar zu
> sein. Deshalb:
>
> - **AP-07l · Lese-API (vorgezogen, vor AP-06).** Endpunkte über das, was
>   `journal rebuild` erzeugt: Ketten mit ihren Gliedern, Strukturen mit
>   Legs, Ausführungen im Drilldown, offene Rollkandidaten. Read-only.
> - **AP-07 · Rest (nach AP-06).** Kennzahlen-Endpunkte, Write-Endpunkte für
>   Journal, Tags, Overrides und Kampagnen-Klassifikation.
>
> **Ausgang:** OpenAPI-Schema, Contract-Tests dagegen.
> **Abnahme:** Kein Endpunkt liefert Zahlen, die nicht aus der Datenbank
> stammen — die Lese-API rechnet nichts aus, sie reicht durch. **Jede
> Geldangabe nennt ihre Währung und ihre Sicht** (§5, Zwei Sichten); es gibt
> keine währungsübergreifende Summe, solange die Umrechnung nach P4 fehlt
> (AP-06).

## 3 · Ergänzt AP-08

Nach dem Satz „**Ziel:** Bedienbares Frontend, im Betrieb statisch
ausgeliefert." einfügen:

> **Zweigeteilt, parallel zu AP-07.** **AP-08l · Positionsliste und
> Detailansicht** (vorgezogen, auf AP-07l): die Liste aller Ketten mit
> Filtern, die Detailansicht mit Roll-Zeitstrahl und Drilldown bis zur
> Ausführung, und die Durchsicht der Rollkandidaten — sie löst die
> Datei-Rundreise aus §6, Block B, Regel 2 ab. **AP-08 · Rest** (nach
> AP-06): Dashboard, Kampagnenansicht, Kalender, Journal-Editor.
>
> Die vorgezogene Fassung zeigt ausdrücklich **keine** Kennzahlen und keine
> währungsübergreifenden Summen; sie nennt die Sicht, aus der ihre Zahlen
> stammen.

## 4 · Ergänzt §11.1 (Zuordnung)

> | AP-07, AP-08, AP-10, AP-13 Parser | günstig | Fleißarbeit gegen feste Verträge |

**Ergänzen:**

> Das gilt auch für die vorgezogenen Teile AP-07l und AP-08l: feste
> Verträge, synthetische Fixtures, kein Zugriff auf `fixtures/golden/`.

---

## Was das für die Umsetzung bedeutet

1. **AP-07lv** (stark): Abnahmebasis der Lese-API — Endpunkte, Schemata,
   Contract-Tests, FastAPI als Abhängigkeit.
2. **AP-07l** (günstig): Umsetzung.
3. **AP-08lv / AP-08l**: dasselbe für die Oberfläche.
4. Die **Kettensicht** (OF-36) bleibt ein eigenes Paket vor AP-06. Bis
   dahin zeigt die Oberfläche die Kontosicht.

**Was bewusst liegen bleibt:** OF-42 (Schnitt mehrterminiger Strukturen aus
einer Order) — die 57 Fälle fallen in der Detailansicht auf, und dann ist
der Befund greifbarer als heute.
