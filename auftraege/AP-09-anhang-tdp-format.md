---
titel: Formatspezifikation Trading-Diary-Pro-Export
modell: -
status: referenz
---

# Anhang · Format des Trading-Diary-Pro-Exports

> **Stand 15.09.2026:** Ob AP-09 überhaupt gebraucht wird, ist offen — die
> Reichweitenprüfung in OF-30 zeigt, dass Flex die gesamte Kontohistorie ab
> 04/2022 abdeckt. Dieser Anhang bleibt als Formatreferenz gültig; die
> Entscheidungen zu fehlender `Contract Id`, fehlender Abwicklungsart,
> Kontozuordnung und Dublettenprüfung stehen in OF-30.

Grundlage für die synthetischen Fixtures in AP-09. Alle Angaben sind aus zwei
echten Exporten abgeleitet; dieses Dokument enthält **keine Kontodaten**, nur
Struktur, Wertebereiche und Formatmuster.

## Datei

- CSV, Komma als Feldtrenner, Zeilenende CRLF, UTF-8 **ohne** BOM.
- Dezimaltrennzeichen ist das **Komma**, Tausendertrennzeichen der Punkt.
  Zahlenfelder sind daher zwingend zu quoten.
- Eine Kopfzeile, keine Fußzeile.
- **Es gibt eine überzählige, namenlose Spalte am Zeilenende** (durchgehend leer).
  Der Parser muss sie tolerieren und verwerfen.

## Zwei Exportvarianten

| Variante | Spalten | enthält `Transaction ID` |
|---|---|---|
| Standard | 24 plus Leerspalte | nein |
| Vollständig (ausgeblendete Spalten eingeblendet) | 27 plus Leerspalte | ja |

**Für AP-09 ist ausschließlich die vollständige Variante brauchbar.** Nur sie
trägt `Transaction ID`, und das ist der Join-Schlüssel zum Flex-Bestand
(entspricht dort `tradeID`, §6.1 des Plans). Ein Standard-Export lässt sich nicht
dublettenfrei mit den Flex-Daten zusammenführen.

Die drei zusätzlichen Spalten sind `Transaction ID`, `ID`, `Transfer`.

## Spalten in Reihenfolge

| # | Spalte | Typ | Format / Wertebereich | leer möglich |
|---|---|---|---|---|
| 0 | Ticker | Text | Kontraktkürzel, z. B. `C ODAX 20260911 26250 W` | nein |
| 1 | Description | Text | Klartext, z. B. `DAX 11SEP26 26250 C` | nein |
| 2 | Date | Zeitstempel | `TT.MM.JJJJ hh:mm:ss` | nein |
| 3 | Buy/Sell | Aufzählung | `Buy`, `Sell` | nein |
| 4 | Shares | Dezimal | 7 Nachkommastellen, z. B. `10,0000000` | nein |
| 5 | Price | Dezimal | bis 7 Nachkommastellen | nein |
| 6 | Price In Base | Dezimal | bis 18 Nachkommastellen | nein |
| 7 | Commission | Dezimal | negativ, bis 7 Nachkommastellen | nein |
| 8 | Commission In Base | Dezimal | negativ, bis 16 Nachkommastellen | nein |
| 9 | Currency | Aufzählung | `EUR`, `USD` | nein |
| 10 | Conversion Rate | Dezimal | 9 Nachkommastellen | nein |
| 11 | Amount | Dezimal | bis 25 Stellen gesamt | nein |
| 12 | Amount In Base | Dezimal | bis 30 Stellen gesamt | nein |
| 13 | Tags | Text | im Referenzexport durchgehend leer | ja |
| 14 | Asset Category | Aufzählung | `Option`, `Stock`; erwartbar auch `Future` | nein |
| 15 | Multiplier | Dezimal | `1,0000000`, `5,0000000`, `10,0000000`, `100,0000000` | nein |
| 16 | Underlying Symbol | Text | Basiswertkürzel | nein |
| 17 | Expiration Date | Zeitstempel | `TT.MM.JJJJ hh:mm:ss` | ja, bei Aktien |
| 18 | Options Type | Aufzählung | `Call`, `Put` | ja, bei Aktien |
| 19 | Strike | Dezimal | bis 5 Nachkommastellen; bei Aktien `0,00000`, nicht leer | nein |
| 20 | Notes | Aufzählung | `A`, `Ep`, `Ex` (Ereignisse), `P` (Teilausführung, **kein** Ereignis); weitere Codes möglich | ja |
| 21 | Exchange | Text | Börsenkürzel, `--` bei Ereigniszeilen — **das** ist das Erkennungsmerkmal | ja |
| 22 | Account | Text | einstellige Kontokennung, kein Kontonummernwert | nein |
| 23 | Contract Id | Ganzzahl | 9-stellig, entspricht der IB-conid | ja, bei Zuteilungsbuchungen |
| 24 | Transaction ID | Ganzzahl | 10-stellig, **Join-Schlüssel**, eindeutig je Zeile | nein |
| 25 | ID | Ganzzahl | TDP-intern, fortlaufend nach Importreihenfolge | nein |
| 26 | Transfer | Aufzählung | `True`, `False`; im Referenzexport nur `False` | nein |
| 27 | *(ohne Namen)* | — | durchgehend leer | immer |

## Für die Fixtures wichtige Eigenheiten

1. **`Contract Id` und `Expiration Date` fehlen bei Zuteilungsbuchungen.** Im
   Referenzexport betrifft das genau die Aktienzeilen, die aus einer Zuteilung
   entstehen. Mindestens ein solcher Fall gehört in die Fixtures.
2. **Ereigniszeilen erkennt man an `Exchange == '--'`, nicht an `Notes`**
   (gemessen 15.09.2026, Korrektur der ersten Fassung dieses Anhangs): `P` trägt
   echte Börsen (CBOE, CBOE2, SAPPHIRE) und ist eine Teilausführung, also ein
   Handel — wie OF-20 schon für Flex festgestellt hat. Nur `Ep`, `Ex` und `A`
   tragen durchgehend `--`. Damit müssen unbekannte Zusatzcodes (`IA`, `FP`, `L`)
   gar nicht bekannt sein, um Ereignisse von Handel zu trennen.
3. **`Contract Id` ist die Instrumentenkennung, nicht der Trade.** Derselbe Wert
   erscheint mehrfach, wenn dasselbe Instrument geöffnet und geschlossen wird.
4. **`Transaction ID` ist je Zeile eindeutig.** Sie gruppiert nichts: die Legs
   einer Combo-Order tragen verschiedene Werte.
5. **`ID` ist wertlos für die Fachlogik.** Sie spiegelt nur die Importreihenfolge
   in TDP und darf nicht als Schlüssel dienen.
6. Nachkommastellen unterscheiden sich stark je Spalte. Die Fixtures sollen diese
   Bandbreite abbilden, damit der Parser nicht auf einer festen Stellenzahl
   aufsetzt.

## Nicht verwenden

Eine Datei `My_Portfolio_*.xls` ist **kein** TDP-Transaktionsexport, sondern eine
als Excel gespeicherte HTML-Tabelle mit Bestandsdaten. Sie trägt weder
`Transaction ID` noch die Spaltenstruktur oben und ist für AP-09 unbrauchbar.
