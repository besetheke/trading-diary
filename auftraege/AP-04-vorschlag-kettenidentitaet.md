---
titel: Textvorschlag Plan §6 - Zeitfenster-Rolls werden Kandidaten
modell: stark
status: vorschlag
abhaengig_von: AP-04
---

# Vorschlag: Kettenidentität ohne heuristische Tatsachen

**Kein Arbeitspaket.** Fertiger Ersatztext für `plan/trading-journal-projektplan.md`,
§6, Abschnitt AP-04. `plan/` ist für Modelle gesperrt (die fachliche Wahrheit
gehört dem Nutzer), deshalb liegt der Text hier zum Übernehmen. **Sobald er im
Plan steht, kann diese Datei gelöscht werden.**

Grundlage: OF-41, zwei Durchsichten der Stichprobe durch den Nutzer
(21.09.2026), und dessen Entscheidung, dem Ansatz zu folgen.

---

## 1 · Ersetzt Block B, Regel 2

> 2. **Roll in zwei Orders:** Schließung und Eröffnung innerhalb von 3 Minuten,
>    gleicher Basiswert, gleiche Seite, vergleichbare Menge. Die Expiry
>    unterscheidet sich hier zwangsläufig.

**Neu:**

> 2. **Roll in zwei Orders — Kandidat, keine Kette.** Schließung und Eröffnung auf
>    demselben Basiswert und derselben Seite in zeitlicher Nähe, mit zwangsläufig
>    anderer Expiry, ergeben einen **Rollkandidaten**. Er wird vorgeschlagen und
>    wird erst durch Bestätigung zur Verknüpfung — wie bei den Futures (3).
>
>    *Begründung, gemessen (OF-41).* In der durchgesehenen Stichprobe waren von 25
>    über das Zeitfenster gebildeten Ketten **zehn falsch** und drei unklar,
>    während von acht über die Order-Nummer belegten Ketten **keine einzige**
>    falsch war. Das Zeitfenster verwechselt den Wiedereinstieg nach einem Profit
>    Target mit einem Roll — im Brokerbeleg sieht beides gleich aus — und
>    übersieht zugleich Rolls jenseits der drei Minuten. Eine Verknüpfung, die
>    etwa so oft falsch wie richtig ist, darf nicht als Tatsache in die
>    Roll-Degradation eingehen: Sie verfälscht genau die Kennzahl, für die sie
>    gedacht war.
>
>    *Menge ordnet, sie entscheidet nicht.* Ein Roll ist keine
>    Eins-zu-eins-Nachfolge. Positionen werden geteilt, zusammengelegt, erweitert
>    und teilweise gerollt; eine Bedingung, die vergleichbare Menge verlangt,
>    schließt deshalb echte Rolls aus. Zeitlicher Abstand, Mengenverhältnis und
>    ein Preisverlauf, der zum Fortführen passt, **sortieren die Kandidatenliste**
>    — sie entscheiden nicht über die Aufnahme.
>
>    *Bestätigung braucht kein neues Schema.* Ein bestätigter Kandidat ist eine
>    Zeile in `chain_overrides` (`erkennung = 'manuell'`). Kandidaten selbst
>    werden nicht gespeichert, sondern bei jedem `rebuild` neu vorgeschlagen;
>    bestätigte überleben ihn (P6).

## 2 · Ergänzt Block B am Ende

> 5. **Was eine Kette behauptet.** Eine Kette entsteht nur aus Belegen: gemeinsame
>    Order-Nummer (1), OptionApp-Referenz (0a) oder Zuteilung (2a). Alles andere
>    ist Vorschlag, bis der Nutzer es bestätigt (Regel 7). Der Broker zeichnet
>    Ausführungen auf, keine Absichten — was er nicht belegt, behauptet das
>    Journal nicht.

## 3 · Ersetzt die dritte Abnahmeprüfung

> *Stichprobe, Nicht-OA-Teil.* Für DAX und ESTX50 existiert keine externe
> Referenz. Eine Stichprobe gerollter Ketten wird einmal manuell durchgesehen,
> bestätigt und als Fixture eingefroren. […]

**Neu:**

> *Stichprobe, Nicht-OA-Teil.* Für DAX und ESTX50 existiert keine externe
> Referenz. Eine Stichprobe wird durchgesehen und als Fixture eingefroren.
> Maßstab ist getrennt nach Herkunft:
>
> - **Belegte Ketten müssen fehlerfrei sein.** Ein Fehler dort ist ein
>   Abnahmehindernis. (Gemessen 21.09.2026: 8 von 8 richtig.)
> - **Kandidaten werden nicht auf Trefferquote geprüft.** Sie behaupten nichts;
>   geprüft wird, dass sie vollständig angeboten werden — kein bestätigter Roll
>   der Stichprobe fehlt in der Kandidatenliste — und dass eine Bestätigung ein
>   vollständiges `rebuild` überlebt.
>
> Jede Kette trägt aus, woher ihre Verknüpfungen stammen. Jede Auswertung weist
> ihre **Abdeckung** aus: den Anteil belegter und bestätigter Verknüpfungen an
> den betrachteten Ketten.

## 4 · Ergänzt die Abnahme von AP-06

> Die Roll-Degradationsauswertung reproduziert die bekannte Aussage, dass Ketten
> ohne Roll am besten abschneiden.

**Ergänzen:**

> Sie läuft wahlweise nur auf belegten Ketten oder auf belegten plus bestätigten
> und nennt in beiden Fällen die Abdeckung. Unbestätigte Kandidaten gehen nie
> ein.

## 5 · Ergänzt AP-11

> **Ziel:** Der Roller schreibt beim Aufsetzen einer Position die Absicht mit
> (IC-Seite, Gegenfinanzierung, Neueröffnung) und füllt `roller_link`.

**Ergänzen:**

> Damit ist AP-11 die einzige Quelle echter Absicht. Rückwirkend lässt sie sich
> nicht rekonstruieren — der Nutzer selbst konnte gerollte von wiedereröffneten
> Positionen im Nachhinein nicht sicher unterscheiden (OF-41). Für alles, was vor
> AP-11 liegt, bleibt die Bestätigung von Hand der einzige Weg; für alles danach
> entfällt das Raten.

---

## Was das für die Umsetzung bedeutet

Noch nicht gebaut, in dieser Reihenfolge sinnvoll:

1. `engine/chains.py`: Schritt 2 erzeugt keine Verknüpfung mehr, sondern eine
   Kandidatenliste. `_rolls_verketten()` verkettet nur noch über `exec_batch`;
   die Mengenbedingung wandert aus der Auswahl in die Sortierung.
2. Kandidatenliste als Rückgabewert von `bilde_chains()` — rein berechnet, nicht
   persistiert, sortiert nach Abstand, Mengenverhältnis und Preisbild.
3. `journal rebuild` wendet `chain_overrides` wie bisher an; die Bestätigung
   selbst braucht eine Oberfläche (AP-08) oder vorläufig ein CLI-Kommando.
4. Auswertungen (AP-06) führen die Abdeckung mit.

**Erwartete Wirkung auf den Bestand, gemessen:** Bei DAX und ESTX50 hängen 41
von 168 gerollten Ketten an mindestens einem Zeitfenster-Glied. Diese zerfallen
zunächst in kürzere Ketten und warten auf Bestätigung; die belegten 127 bleiben
unverändert.

**Was bewusst offen bleibt:** Ein gelerntes Modell zur Sortierung der Kandidaten
(OF-41, „erwogen und verworfen") — erst sinnvoll, wenn genug bestätigte Fälle
vorliegen, und auch dann nur als Sortierhilfe, nie als Wahrheitsquelle.

**Was dieser Vorschlag nicht anfasst:** Block A (Legs → Struktur). Das
Zeitfenster bei der Strukturbildung führt zwei Beine *einer* Order zusammen und
ist etwas anderes als die Verkettung. Ein Hinweis aus der Stichprobe
(„Offensichtlicher Trade falsch gebaut") zielt dorthin und ist gesondert zu
prüfen.
