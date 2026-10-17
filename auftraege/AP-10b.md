---
titel: Steuer nach Zufluss je Zahlungsstrom — Vorbereitung (Regeln, Tests, Fixtures)
modell: stark
status: offen
abhaengig_von: AP-10, AP-10v, AP-16
aendert_tests: ja
---

# AP-10b · Steuer nach Zufluss — Abnahmebasis

**Vorbereitungspaket** nach CLAUDE.md 1a: legt die Abnahmebasis von AP-10c an und **implementiert nichts**. Es
legt ausschließlich **neue** Testdateien und Fixtures an; bestehende (`tests/test_steuer.py`, AP-10-Fixtures)
bleiben unberührt. Ausgangspunkt ist der Arbeitsstand des Steuerberaters (Antwort 17.10.2026 samt Anmerkungen des
Kollegen, OF-92). Er ist **Arbeitsstand, nicht gesichert**: Jede Regel unten ist vor Abnahme von AP-10c vom
Steuerberater zu bestätigen; die Tests halten sie fest, sie beweisen nicht ihre Richtigkeit.

Das Paket ist **keine Steuerberatung**: Es bereitet Zahlen auf; Verlustverrechnung, Anlage KAP und SO füllt der
Berater aus.

## Regeln, die die Tests festhalten

R1 **Stillhalterprämie** (verkauft eröffnetes Bein): Zufluss im Jahr, in dem die Prämie tatsächlich zufließt
   (§ 11, § 20 Abs. 1 Nr. 11 EStG). Das maßgebliche **Datumsfeld** ist eine Entscheidung (OF-92, Punkt 4); bis zur
   Klärung gilt eine einzige konfigurierbare Stelle `ZUFLUSS_DATUM` (``settle`` = `settleDateTarget`, ``handel`` =
   `tradeDate`), Vorgabe ``settle``. Die Auswertung nennt je Jahr, **wie viele Buchungen** bei Wechsel des Feldes
   in ein anderes Jahr fielen (Betroffenheit).
R2 **Glattstellung** (Rückkauf): negative Einnahme im Jahr der Zahlung (selbes Datumsfeld wie R1).
R3 **Barausgleich** (Indexoptionen): gezahlter Betrag = Termingeschäftsverlust, im Jahr der Zahlung.
R4 **Verfall:** *beim Stillhalter* geschieht nichts weiter (Prämie ist schon zugeflossen); *bei gekaufter Option*
   ist der wertlose Verfall ein Termingeschäftsverlust in Höhe der gezahlten Prämie (BMF, Rn. 27/32 — zu
   bestätigen).
R5 **Spreads je Bein:** das verkaufte Bein wie R1/R2, das gekaufte als Termingeschäft (Gewinn/Verlust bei
   Schließung, Verfall oder Ausübung). Nie das Netto des Spreads.
R6 **Zuteilung/Lieferung:** Aktie zum Strike, **zuzüglich zugehöriger Transaktionskosten**; die Stillhalterprämie
   bleibt separat (R1). IB-Berichtswerte („Stocks/Options realized“) dienen nur dem Abgleich.
R7 **Währung:** Anschaffungskosten und Erlöse getrennt zum steuerlich maßgeblichen Kurs: bei Wertpapier-An-/Verkauf
   der Geschäftsabschluss (Kurs der Ausführung, `fxRateToBase` der Ausführung), bei Prämie/Glattstellung Zufluss
   bzw. Zahlung. **Kursquelle und verwendete Datumsfelder werden in jeder Ausgabe benannt.** Der Kurs der
   Schließung auf das Netto ist ungeeignet (AP-10 bisher). IB-Kurs oder EZB-Referenzkurs ist offen (OF-92, Punkt 3).
R8 **Verlusttöpfe:** Aktienverluste nur mit Aktienveräußerungsgewinnen. Übrige Verluste innerhalb der Kapitaleinkünfte
   mit positiven Kapitalerträgen ohne die frühere 20.000-€-Beschränkung. **Keine** Verrechnung mit anderen
   Einkunftsarten; **SO-Einkünfte** (Ersatzzahlungen, laufende SYEP-Vergütung, private Fremdwährungsgeschäfte)
   stehen außerhalb. Das Paket **verrechnet nicht**; es weist die Töpfe getrennt aus. Verlustvorträge aus Bescheiden
   sind **Eingabe** (leer, wenn unbekannt), nie Ergebnis einer Rechnung.
R9 **Zinsen und Kosten:** Habenzinsen brutto; Sollzinsen und Marktdatengebühren als „nicht abziehbar“ ausgewiesen
   (zu bestätigen); Kommissionen je Geschäft (Teil der Transaktionskosten).
R10 **Quellensteuer:** Auf **echte Dividenden** Anrechnung nach der Obergrenze des Quellenstaats; für USA 15 % der
   Bruttodividende. Satz je Land steht in **einer Tabelle** (`issuerCountryCode`); ein Land ohne Eintrag wird **nicht
   berechnet** und als „zu prüfen“ gemeldet. Anrechenbar = min(einbehalten, Satz × Brutto); der Rest „nicht
   anrechenbar“. **Ersatzzahlungen:** ihre Quellensteuer wird nicht automatisch in die anrechenbare Summe (KAP 41)
   übernommen, sondern gesondert als „zu prüfen“ ausgewiesen. Irische Zinsquellensteuer: nicht anrechenbar.
R11 **Ersatzzahlungen und SYEP** (SO nach § 22 Nr. 3, vorbehaltlich Bestätigung): getrennt ausgewiesen —
    *Dividendenersatz* und *laufende Vergütung* nicht zusammen, die IB-Bezeichnung „Interest“ entscheidet nicht.
    Die Freigrenze 256 € gilt für die **Summe** aller § 22-Nr.-3-Leistungen nach zugehörigen Kosten (steuerfrei sind
    **weniger als 256 €**), nicht je Zahlung. Die **Ursache** je Buchung ist mit den vorhandenen Daten nicht
    bestimmbar; sie steht als „ungeklärt“ in der Ausgabe (kein Raten).
R12 **KAP-Zeilen:** eine Tabelle `Posten → Zeile` **je Formularjahr**, nicht in der Logik. 2025 gemäß Antwort
    (19, 20, 22, 23, 41); **2026 ist als „ungeprüft“ gekennzeichnet**, bis der amtliche Vordruck vorliegt. Die
    Ausgabe führt das Formularjahr und diesen Status.

## Testdaten

Neue, frei erfundene Testwelt mit von Hand gerechneten Werten (CLAUDE.md Regel 8), `tests/test_steuer_zufluss.py`
und `tests/fixtures/steuer_zufluss/`. Pflichtfälle, je mit Handrechnung im Kopf der Datei:

1. Short Put eröffnet 29.12.2025, zurückgekauft 05.01.2026: Prämie 2025, Rückkauf 2026 (negativ).
2. Wie 1, aber Datumsfeld `handel`: Einordnung bei `settle` und `handel` unterscheidet sich; Betroffenheit = 1.
3. Credit-Spread: verkauftes und gekauftes Bein getrennt; Verfall beider (kurzes Bein ohne Wirkung, langes als Verlust).
4. Short Put zugeteilt: Aktie zum Strike plus Kommission; Prämie bleibt in R1, nicht in den Anschaffungskosten.
5. Barausgleich SPX: Zahlung = Termingeschäftsverlust im Zahlungsjahr.
6. Währung: Prämie am Tag A (Kurs a), Rückkauf am Tag B (Kurs b) — Ergebnis ≠ Netto × Kurs b; Quelle im Ausgabekopf.
7. Verlusttöpfe: Aktien −1.000, Termingeschäfte +500, Dividende +50: Aktienverlust wird nicht verrechnet, Rest ausgewiesen.
8. Quellensteuer: Dividende 100 USD, einbehalten 16,67 → anrechenbar 15,00, nicht anrechenbar 1,67; unbekanntes Land → „zu prüfen“.
9. Ersatzzahlung 22 USD mit Quellensteuer 3,30: nicht in KAP 41, getrennt als SO-Kandidat; Summe < 256 € → steuerfrei ausgewiesen.
10. Zeilentabelle: 2025 → Zeilen laut Antwort; 2026 → Status „ungeprüft“.
11. Lieferungs-Bein ohne Buchungskurs → Fehlerliste, kein stiller Kurs 1.

**Golden-Daten:** Ein Abgleichsskript `werkzeuge/abgleich/steuer_zufluss.py` (Regel 2: nur Zählwerte und Summen je
Jahr, nur starkes Modell) vergleicht die neue Methode mit der alten (Schließungsjahr) und mit IBs Berichtswerten
und gibt je Jahr die Abweichung aus. Es ist Nachweis der Abnahme und schreibt nichts.

## Ausdrücklich nicht Teil dieses Pakets

- Implementierung (AP-10c), Anfangsbestände, Ersatzzahlungs-Ursachen und USD-Kontoeffekte (AP-10d).
- Änderung von `analytics/steuer.py`, `tests/test_steuer.py` oder AP-10-Fixtures.
- Verlustverrechnung, Anlage-KAP-Ausfüllhilfe, Steuerberatung.
- Änderung des Projektplans §AP-10: **Vorschlag** an den Nutzer, nicht eigenmächtig (siehe AP-10c, Abschnitt Plan).
