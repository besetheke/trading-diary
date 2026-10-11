---
titel: Depot — Bestand laut IB mit letztem Kurs und unrealisiertem Ergebnis
modell: stark
status: fertig
abhaengig_von: AP-02, AP-08h
aendert_tests: nein
---

# AP-08d · Depot

Wunsch des Nutzers (11.10.2026): „Den unrealisierten Gewinn/Verlust möchte ich
ebenfalls sehen können", „Wieso sehe ich nicht alle derzeitigen Aktien, die im
Portfolio sind?", „eine Spalte, wo offene Positionen mit dem letzten bekannten
Wert bepreist sind".

## Befund

Die Positionsliste zeigt **Ketten** von Geschäften (Kontosicht). Von IBs 10
Aktienwerten hängt nur einer an einer Aktien-Kette (Anlageklasse STK); die
übrigen neun stammen aus Zuteilungen und sitzen in Options-Ketten (Klasse OPT,
Endzustand „Offen") oder gehören zu keiner Kette. Der Filter „Aktie + Offen"
kann das Depot deshalb nicht zeigen — es braucht eine Ansicht nach Instrument
statt nach Kette.

## Umsetzung

- **`GET /depot`** (`api/app.py`): Bestand des jüngsten Stichtags aus
  `flex_open_positions` (Ebene SUMMARY). Je Position: Menge, Einstandskurs,
  letzter bekannter Kurs (`markPrice`), Marktwert (`positionValue`),
  unrealisiertes Ergebnis (`fifoPnlUnrealized`) — in Positionswährung und in
  EUR mit IBs `fxRateToBase` der Zeile; dazu Basiswert, Seite, Verfall, Strike
  aus den Instrumentdaten. Summen gesamt und je Klasse. Alles Werte der Quelle,
  nichts neu bewertet, Geld als Text, EUR als gerechnetes Produkt ohne Rundung.
  Abnahmebasis `tests/test_api_depot.py` (7 Tests, von Hand gerechnet).
- **Seite „Depot"** (`ui/src/Depot.tsx`, Adresse `/bestand`, da `/depot` der
  Endpunkt ist): Kopf (Stand, Marktwert, Unrealisiert, Anzahl), Summen je
  Klasse, Tabellen Aktien / Optionen / Übrige; der Basiswert verweist in die
  Positionsliste.
- **Dashboard:** im Abschnitt „Kontowert laut IB" die Kennzahl „Unrealisiert
  laut IB (Stand)" mit Verweis auf das Depot.

## Nachweis

Gesamtsuite grün, `ruff check .` sauber, Build ok. Echtbestand (Stichtag
2026-10-09, 138 Positionen): Marktwert **182.305,03 €**
(Aktien 255.548,73 €, Optionen −73.243,70 €) = IBs Kontowert-Anteil „Aktien +
Optionen" auf den Cent; unrealisiert **−46.361,74 €** (Aktien −45.125,92 €,
Optionen −1.235,82 €). Sichtprüfung mit ferngesteuertem Browser.

## Grenzen

- Der Kurs ist der **letzte bekannte** (Bericht des Stichtags), kein
  Echtzeitkurs. Die Datenbank hält nur einzelne Bestandsstichtage (11), daher
  gibt es das unrealisierte Ergebnis als Stand, nicht als Kurve über die Zeit.
- Unrealisiert ist **nicht** Teil der Equity (nur abgeschlossene Geschäfte).
