# Checkliste: Schritt auf das Echtgeld-Konto (Entscheidungshilfe, keine Freigabe)

Stand 22.10.2026. Der Roller handelt bisher nur Paper (Port 7497, Konto DU…). Dieser Schritt ist eine Entscheidung des Nutzers.
In der Station zeigt die Karte „Echtgeld-Reife“ (Seite Roller) die gemessenen Kriterien; die Schwellen sind Annahmen (OF-104).

## Voraussetzung: Marktdaten
Paper-Fills sind simuliert und sagen über Fill-Qualität wenig. Ohne Live-Marktdaten (Datenquelle „live“) lässt sich der
Preisteil (Startpreis, Nachziehen, Grenzen) nicht beurteilen.

## A. Gemessen (Karte „Echtgeld-Reife“)
- Datenquelle live, durchgehend seit mindestens 5 Tagen
- mindestens 10 vollständige Rolls ohne Auffälligkeit
- mindestens 30 geschlossene Ketten
- keine angehaltene Kette, keine Meldung „Bestand ohne Kette“

## B. Manuell abhaken
- Dienstneustart mitten in einer laufenden Order: kein Waisen-Bestand, keine doppelte Order
- Not-Aus wirkt auch während eines Tagesprogramms
- Ursache der nicht füllenden 0DTE-Call-Spreads verstanden (IB-Kombi-Quote im Verlauf) oder bewusst ausgeschlossen
- Restore-Probe aus der Sicherung (M08)
- Live-Modus mit harten Grenzen gebaut (siehe C)
- Fill-Qualität gegen den Mittelkurs über mehrere Wochen mit Live-Daten beurteilt

## C. Im Code zu bauen, bevor Live möglich ist (heute verweigert der Roller Live)
- Ausdrücklicher Live-Modus, nie als Vorgabe; Kontonummer-Prüfung
- 1 Kontrakt, feste Liste erlaubter Strategien, Tageslimit für Kredit und Verlust
- Automatik zunächst aus: Rolls und Early Exits nur per Freigabe
- Meldungen bei jeder Order an nbillinger@gmx.de

## Stufen
1. Paper mit Live-Daten, Kriterien A und B erfüllen (2–3 Wochen).
2. Echtgeld, eine Strategie, 1 Kontrakt, Automatik aus (etwa 4 Wochen).
3. Weitere Strategien oder Automatik nur nach sauberer Stufe 2.
