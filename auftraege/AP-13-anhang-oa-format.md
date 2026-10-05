---
titel: Formatspezifikation OptionApp-Trade-Export
modell: -
status: referenz
---

# Anhang · Format des OptionApp-Trade-Exports

Grundlage für die synthetischen Fixtures in AP-13. Abgeleitet aus zwei echten
Exporten mit zusammen 244 Trades und 856 Legs. Dieses Dokument enthält **keine
Kontodaten**, nur Struktur, Wertebereiche und Grammatik.

## Datei

- **XLSX**, nicht CSV. Ein Arbeitsblatt, benannt `Trades`. Bereich `A1:K<n>`.
- Eine Kopfzeile, keine Fußzeile, keine Leerspalte.
- Elf Spalten in fester Reihenfolge.

## Zahlenformate — innerhalb derselben Datei uneinheitlich

Das ist die wichtigste Falle:

| Spalte | Speicherung | Beispielform |
|---|---|---|
| `Open`, `Close` | Gleitkommazahl | `11.49` — Punkt als Dezimaltrennzeichen |
| `Stops` | Text | `-` oder `0` oder `-14.4` — Punkt |
| `Profit` | Text | `-1.234,56 $` — **Komma** als Dezimaltrennzeichen, Punkt als Tausendertrennzeichen, angehängtes Währungszeichen |

Ein Parser, der eine einheitliche Konvention unterstellt, scheitert. `Profit` muss
eigens behandelt werden: Währungszeichen abtrennen, Tausenderpunkte entfernen,
Komma zu Punkt.

## Spalten in Reihenfolge

| # | Spalte | Typ | Format / Wertebereich | leer möglich |
|---|---|---|---|---|
| 0 | Entry Time | Text | `JJJJ/MM/TT hh:mm:ss` | nein |
| 1 | Strategy | Text | Strategiekennung, z. B. `QQQ: DC14/28` | nein |
| 2 | Name | Text | freier Text plus `[<Nummer>]` am Ende | nein |
| 3 | Strikes | Text | Leg-Grammatik, siehe unten | nein |
| 4 | Quantity | Text | `n/m`, beobachtet `1/1`, `2/2`, `3/3` | nein |
| 5 | Open | Zahl | Dezimalpunkt | siehe unten |
| 6 | Close | Zahl | Dezimalpunkt | siehe unten |
| 7 | Stops | Text | `-` wenn keiner, sonst Zahl mit Dezimalpunkt, auch `0` oder negativ | nein |
| 8 | Profit | Text | `-1.234,56 $` | nein |
| 9 | Close Time | Text | `JJJJ/MM/TT hh:mm:ss` | siehe unten |
| 10 | Status | Aufzählung | siehe unten | nein |

## Leg-Grammatik der Spalte `Strikes`

Legs getrennt durch Leerzeichen-Schrägstrich-Leerzeichen (` / `). Je Leg:

```
[-]<Menge>x<C|P><Strike> (<JJMMTT>)
```

Beispiel: `-1xC751 (260831) / 1xP717 (260918)`

- Führendes Minus bedeutet Short, kein Vorzeichen bedeutet Long.
- `C` Call, `P` Put.
- Verfall als sechsstelliges `JJMMTT`, in Klammern, mit einem Leerzeichen davor.
- **Über 856 Legs kein einziger Ausreißer.** Der Parser darf die Grammatik streng
  prüfen und bei Abweichung abbrechen, statt zu raten.
- Beobachtet wurden nur ganzzahlige Strikes. Der Parser sollte dennoch einen
  optionalen Dezimalteil zulassen, weil Strike-Konventionen halbe Punkte kennen.
- **Produktcode (Gesamtexport 2026, AP-13pn, OF-66).** DAX-Trades der OptionApp
  tragen vor dem Recht einen Eurex-Produktcode: `-1xODAP P23000 (260918)`. Er
  besteht aus drei bis sechs Großbuchstaben, gefolgt von einem Leerzeichen, und
  ist je Leg optional. Er lockert nur diese Stelle der Grammatik; Richtung,
  Menge, Recht, Strike und Verfall bleiben maßgeblich, der Code geht nicht in die
  Leg-Identität ein (der Rohwert `roh` behält ihn). Kleinbuchstaben oder ein
  ungültiges Recht bleiben ein Defekt der Quelle.
- Legs je Trade: beobachtet 2 (47 Fälle), 3 (26) und 4 (171). **Drei Legs sind ein
  regulärer Fall**, keine Anomalie — eine Typisierung, die nur Zwei-Leg-Verticals
  kennt, ist falsch.

## Schlüssel in der Spalte `Name`

Am Zeilenende steht die OptionApp-Trade-Nummer in eckigen Klammern. Davor steht
frei editierbarer Text, der vom Nutzer gepflegt wird und beliebige Zeichen
enthalten kann, einschließlich Umlauten und Klammern in Wörtern.

- In beiden Exporten in allen 244 Zeilen vorhanden und durchgehend eindeutig.
- Diese Nummer entspricht `Trade` in der `orderReference` des Flex-Exports
  (gemessen: 66 von 66 Treffern im Überschneidungszeitraum, §6.1 des Plans).
- **Nur die letzte Klammergruppe der Zeile auswerten**, da der freie Text selbst
  Klammern enthalten kann.
- Fehlt die Klammernummer, bricht der Import mit Nennung der Zeile ab. Ein Trade
  ohne Schlüssel lässt sich nicht verknüpfen und darf nicht stillschweigend
  durchlaufen.

## Spalte `Status`

Beobachtete Werte: `EXPIRED`, `CLOSED`, `PARTIALLY STOPPED`,
`EXPIRED (estimated)`, `STOPPED`, `UNMANAGED`.

Das ist der Endzustand der Kette, den die Rohdaten sonst nicht hergeben —
insbesondere `PARTIALLY STOPPED` wäre aus Brokerdaten kaum erkennbar. Unbekannte
Werte werden roh gespeichert und in `OFFENE_FRAGEN.md` gemeldet, nicht auf einen
bekannten Wert abgebildet.

## Weitere Eigenheiten

1. **`Quantity` ist ein Verhältnis `n/m`.** In den Referenzexporten sind beide
   Zahlen stets gleich. Der Parser darf das nicht voraussetzen; beide Werte
   getrennt speichern.
2. **`Stops` trägt `-` für „kein Stop".** Das ist kein fehlender Wert, sondern
   eine Aussage. `0` kommt ebenfalls vor und bedeutet etwas anderes als `-`.
3. **`Close` und `Close Time` sind in den Referenzexporten immer gefüllt**, weil
   beide nur abgeschlossene Trades enthalten. Enthält ein Export offene Trades,
   müssen beide Spalten leer sein dürfen. Die Fixtures sollen diesen Fall
   abdecken, auch wenn er bisher nicht beobachtet wurde.
4. **Zeitstempel nicht zum Abgleich verwenden.** Das Format ist ein drittes neben
   TDP und Flex, und die Zeitzone ist ungeprüft. Die Verknüpfung stiftet
   ausschließlich die Klammernummer.
5. **Abdeckung:** der Export enthält nur von OptionApp gesteuerte Strategien.
   DAX, ESTX50, Futures und diskretionäre Einzelwerte kommen darin nicht vor.
   Rund 61 % der Ausführungen im Flex-Bestand tragen keine OA-Referenz.

## Abgrenzung dieses Pakets

Der Parser liest die Datei, prüft die Grammatik und legt die Trades mit ihren
Legs ab. **Die Verknüpfung mit den Ketten und der Ergebnisabgleich gehören nicht
dazu** — sie brauchen AP-04 und bleiben beim starken Modell.
