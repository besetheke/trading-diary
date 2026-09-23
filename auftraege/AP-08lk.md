---
titel: Anzeigefehler der Detailansicht - Naturschluessel und Nachkommastellen
modell: guenstig
status: offen
abhaengig_von: AP-08l
---

# AP-08lk · Zwei Anzeigefehler

Korrekturpaket. Beide Punkte stammen aus dem Augenschein des Nutzers am
22.09.2026 — dem Teil der Abnahme, den kein Test leisten konnte.
**Tests und Fixtures sind tabu.**

## 1 · Der Naturschlüssel sprengt das Raster (muss)

In der Detailansicht läuft der Wert der Zeile `Struktur` aus seiner Spalte
und schiebt sich über die Beschriftung der nächsten (`Basiswert` erscheint
als „…wert"). Der Schlüssel besteht aus zwei zehnstelligen IB-Nummern,
verbunden mit `|` — bei mehrbeinigen Strukturen entsprechend mehr. Das
Raster der Definitionsliste rechnet nicht damit.

**Anforderung:** Der Wert bleibt vollständig zugänglich, verdeckt aber
nichts. Wie — gekürzt mit Auslassung und vollem Wert im `title`, Umbruch,
eigene Zeile über die volle Breite, Schriftart mit fester Laufweite — ist
deine Entscheidung. Zwei Dinge sind Vorgabe:

- **Nichts überlappt**, auch nicht bei einer Struktur mit vier Legs, also
  bei einem Schlüssel aus vier Nummern.
- **Der vollständige Schlüssel bleibt erreichbar**, zum Kopieren. Er ist
  der Schlüssel, über den die Durchsicht der Rollkandidaten zurückliest
  (`journal kandidaten-einlesen`) — ein gekürzter Wert ohne Zugriff auf das
  Ganze wäre unbrauchbar.

Sieh dir bei der Gelegenheit die übrigen Definitionslisten beider Ansichten
auf denselben Fehler an; lange Werte gibt es auch bei `Basiswert` und
`Endzustand` nicht, aber die Spaltenbreiten sind dieselbe Bauart.

## 2 · Fünf Nachkommastellen in der Positionsliste (freigegeben)

> **Freigegeben durch den Nutzer am 22.09.2026** („kürzen ja"). Punkt 2 ist
> damit Teil des Auftrags.

Die Spalte `Ergebnis netto` zeigt Werte wie `-149.52224`. Das ist **kein
Fehler**: Die Kommissionen von IB tragen mehr als zwei Nachkommastellen
(OF-18), und die Oberfläche reicht die Zeichenkette unverändert durch, wie
Vertrag 8 es verlangt. In einer Liste ist es trotzdem Lärm.

In der **Positionsliste** auf zwei Nachkommastellen
anzeigen, den vollständigen Wert im `title` der Zelle. In der
**Detailansicht** bleibt der volle Wert stehen — dort ist die Genauigkeit
der Zweck.

**Die Grenze bleibt Vertrag 8:** Gekürzt wird eine **Zeichenkette**, nicht
gerechnet. Kein `parseFloat`, kein `Number()`, kein `toFixed` — alles drei
schickt den Betrag durch eine Gleitkommazahl und hebt genau den Schutz auf,
den API und Oberfläche über die ganze Kette aufbauen. Zulässig ist
ausschließlich Zeichenarbeit am Text: Stelle des Punkts suchen, hinten
abschneiden, kaufmännisch runden **von Hand** oder gar nicht runden, sondern
nur abschneiden — und wenn abgeschnitten wird, muss der Titel den vollen
Wert zeigen.

Wenn dir das zu fein erscheint: Das ist es auch. Deshalb steht der Punkt
unter Freigabe und nicht im Pflichtteil.

## Abnahme

- Gesamte Testsuite grün, `ruff check .` sauber.
- `npm run build` läuft durch.
- **Du siehst dir beide Ansichten selbst an** und berichtest, was du
  gesehen hast — insbesondere eine Struktur mit vier Legs, falls du eine
  findest (Filter `Basiswert` auf einen Index, dann eine Kette mit
  mehrbeiniger Struktur öffnen).
- `git diff --stat` zeigt ausschließlich `ui/`.
