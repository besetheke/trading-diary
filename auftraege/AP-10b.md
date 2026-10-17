---
titel: Steuer nach Zufluss je Zahlungsstrom — Vorbereitung (Regeln, Tests, Fixtures)
modell: stark
status: fertig
abhaengig_von: AP-10, AP-10v, AP-16
aendert_tests: ja
---

# AP-10b · Steuer nach Zufluss — Abnahmebasis

**Vorbereitungspaket** nach CLAUDE.md 1a: legt die Abnahmebasis von AP-10c an und **implementiert nichts**.
Ausgangspunkt: Arbeitsstand des Steuerberaters (OF-92) und das Review des Kollegen zum Plan `a193f1d` (OF-93,
sieben Änderungen, hier eingearbeitet). **Arbeitsstand, nicht gesichert:** Jede Regel ist vor Abnahme von AP-10c vom
Steuerberater zu bestätigen. Die Tests halten die Regeln fest, sie beweisen nicht ihre Richtigkeit. Keine
Steuerberatung; Verlustverrechnung, Anlage KAP und SO füllt der Berater aus.

## Ändernde Tests (namentlich, CLAUDE.md 1a)

Dieses Paket legt neue Tests an. Zwei **bestehende, außerhalb eines Pakets entstandene** Tests prüfen die alte
Methode oder den alten Antwortaufbau und werden hier **ersetzt**; die Prüflogik bleibt (es ändert sich, *was*
erwartet wird):

- `tests/test_api_steuer.py::test_steuer_auswertung_leer` — erwartet die alte Antwortstruktur
  (`{"jahre": [], "toepfe": [], "fehler": []}`); künftig mit Metadaten (Methode, Kursquelle, Datumsregeln,
  Formularjahr, Status). Geprüft wird weiter: leere Datenbank → leere, wohlgeformte Antwort.
- `tests/test_steuer_jahre.py` (beide Alt-Tests `test_toepfe_aller_waehrungen_…`, `test_praemie_der_lieferungen_…`,
  `test_ertraege_je_jahr_…`) — bestätigen die Jahresübersicht der alten Schließungsjahr-Methode; sie werden durch
  Tests der neuen Jahresübersicht ersetzt.

**Unberührt bleiben** `tests/test_steuer.py`, `tests/test_cashflows.py` und alle AP-10-Fixtures (Altverfahren).

## Regeln, die die Tests festhalten

R1 **Stillhalterprämie** (verkauft eröffnetes Bein): Zufluss im Jahr, in dem die Prämie tatsächlich zufließt
   (§ 11, § 20 Abs. 1 Nr. 11 EStG) — **auch wenn die Position noch offen ist**. Kein Überspringen offener Beine
   (das tut AP-10, Vertrag 2).
R2 **Glattstellung** (Rückkauf): negative Einnahme im Jahr der Zahlung.
R3 **Barausgleich** (Indexoptionen): gezahlter Betrag = Termingeschäftsverlust im Jahr der Zahlung.
R4 **Verfall:** beim Stillhalter geschieht nichts weiter; bei gekaufter Option ist der wertlose Verfall ein
   Termingeschäftsverlust in Höhe der gezahlten Prämie (BMF, Rn. 27/32 — zu bestätigen).
R5 **Spreads je Bein, gekaufte Optionen nach Ausgang:** das verkaufte Bein wie R1/R2. Das gekaufte Bein:
   - *Glattstellung oder Verfall* → Termingeschäft (Gewinn/Verlust).
   - *Ausübung mit Lieferung, Long Call* → die Optionskosten gehören zu den **Anschaffungskosten des Basiswerts**.
   - *Ausübung mit Lieferung, Long Put* → die Optionskosten gehen in das **Veräußerungsergebnis des Basiswerts**
     (BMF, Rn. 22/29 — zu bestätigen).
   „Prämie bleibt separat“ gilt für die **Stillhalterprämie**, nicht für jede Option.
R6 **Zuteilung/Lieferung (Stillhalter):** Aktie zum Strike; Stillhalterprämie separat (R1). **Erwerbskosten erhöhen die
   Anschaffungskosten, Veräußerungskosten mindern den Erlös** — „Strike plus Transaktionskosten“ gilt nicht pauschal.
   IB-Berichtswerte dienen nur dem Abgleich.
R7 **Datum und Kurs je Vorgang (konsistent):** Jeder Zahlungsstrom trägt `steuerdatum`, `fx_datum`, `waehrungspaar`,
   `kursquelle` und `pruefstatus`. Eine zentrale **Regeltabelle je Vorgangsart** (Prämie, Glattstellung, Barausgleich,
   Wertpapierkauf, Wertpapierverkauf, Dividende, Zins) legt fest, welches Datumsfeld (`tradeDate`, `dateTime`,
   `settleDateTarget`, Cash-`settleDate`) Steuerdatum und welches FX-Datum ist. Ein **globaler Schalter
   `handel`/`settle` genügt nicht**: Steuerdatum und Kursdatum dürfen nicht versehentlich verschiedene Tage
   verbinden. Vorgabe bis zur Klärung: je Vorgangsart ein Eintrag mit Status „ungeprüft“; die Auswertung zählt,
   wie viele Buchungen bei Wechsel der Regel in ein anderes Jahr fielen (Betroffenheit). **Kursbeschaffung
   austauschbar** (Schnittstelle `Kursquelle`; IB-Kurs je Ausführung ist die erste Implementierung, EZB eine
   mögliche zweite) — IB oder EZB blockiert die Entwicklung nicht; **vor fachlicher Freigabe** ist zu belegen, dass
   der Kurs zum maßgeblichen Datum und zur richtigen Zielwährung gehört. Der Kurs der Schließung auf das Netto
   (AP-10 bisher) ist ungeeignet.
R8 **Verlusttöpfe:** Aktienverluste nur mit Aktienveräußerungsgewinnen. Übrige Verluste innerhalb der Kapitaleinkünfte
   mit positiven Kapitalerträgen ohne die frühere 20.000-€-Beschränkung. Keine Verrechnung mit anderen Einkunftsarten.
   Das Paket **verrechnet nicht**; es weist **Gewinne und Verluste getrennt** aus (nicht nur den Saldo) je Topf.
   Ungeklärte SYEP- und Fremdwährungsvorgänge sind **nicht verbindlich SO-Einkünfte**, sondern „Einordnung offen
   (SO-Kandidat)“. Verlustvorträge aus Bescheiden sind **Eingabe** (leer, wenn unbekannt), nie Ergebnis.
R9 **Zinsen und Kosten:** Habenzinsen brutto; Sollzinsen und Marktdatengebühren als „nicht abziehbar“ (zu bestätigen);
   Kommissionen je Geschäft nach R5/R6 (Erwerbs- oder Veräußerungskosten).
R10 **Quellensteuer:** Je **konkreter Bruttozahlung** (Zuordnung Steuerbuchung ↔ Dividende) die vorläufige Obergrenze
    `min(einbehalten, DBA-Satz × Brutto)`; Satz je Land aus **einer Tabelle** (`issuerCountryCode`), USA 15 %, Land
    ohne Eintrag → nicht berechnet. **Drei getrennte Zustände:** *vorläufig anrechenbar*, *möglicherweise
    erstattungsfähig* (Überhang), *ungeklärt* (keine Zuordnung, Ersatzzahlung, Land ohne Satz). Die deutsche
    Anrechnungsbegrenzung ist nicht geprüft; die Zahl ist eine **vorläufige Obergrenze**, nicht die endgültig
    anrechenbare Steuer (§ 32d Abs. 5 EStG). Ersatzzahlungen: nicht automatisch in KAP 41. Irische Zinsquellensteuer:
    nicht anrechenbar.
R11 **Ersatzzahlungen und SYEP:** getrennt ausgewiesen — *Dividendenersatz* und *laufende Vergütung* nicht zusammen;
    die IB-Bezeichnung „Interest“ entscheidet nicht. Die Freigrenze 256 € (§ 22 Nr. 3 EStG) wird nur als
    **Information** auf die Summe gezeigt: „Einordnung offen; Freigrenze nicht abschließend geprüft“ — kein
    „steuerfrei“. Die Ursache je Buchung ist mit den Daten nicht bestimmbar → „ungeklärt“.
R12 **KAP-Zeilen:** eine Tabelle `Posten → Zeile` **je Formularjahr**, nicht in der Logik. 2025 gemäß Antwort (19, 20,
    22, 23, 41); **2026 „ungeprüft“**. Die Ausgabe führt Formularjahr und Status.
R13 **Instrumentklassifikation (neu):** Der Code ordnet bisher jedes `STK` dem Aktien-Topf zu; IB nutzt `STK` auch für
    ETFs, ETPs und ETNs (Investmentsteuerrecht, Teilfreistellung, KAP-INV). Gehaltene oder gelieferte
    **ETF/ETN/ETP-Anteile** werden erkannt und als „**ungeklärt (InvStG)**“ ausgesondert, solange ihre Behandlung
    fehlt; eine **Option auf einen ETF** ist davon zu unterscheiden. Quelle: `subCategory` im Flex-Rohsatz der
    Ausführung (im Echtbestand 9 ETF-Symbole, 73 Ausführungen: EWZ, IWM, QQQ, SMH, SPY, TLT, UNG, WCBR, XLU). Gelesen
    wird zur Berichtszeit aus `executions.roh_json`; **keine Schemaänderung** in diesem Paket (CLAUDE.md Regel 3).
R14 **Fehlerisolierung und Genauigkeit der Ströme:** Jeder Zahlungsstrom steht für sich. Ein fehlender Kurs einer
    Schließung darf eine bekannte Eröffnungsprämie nicht verschwinden lassen (die vorhandene Zerlegung `leg_seiten`
    liefert bei fehlendem Kurs `None` für die ganze Leg-Liste und ist **nicht** die Grundlage). **Jede
    Eröffnungsprämie und jede Kommission wird genau einmal erfasst** (Invariante, siehe Tests 12–14).
R15 **Fehlende Daten und offene Regeln getrennt:** zwei Listen in jeder Ausgabe — `datenluecken` (Kurs fehlt,
    Ausführung fehlt, Land ohne Satz …) und `regeln_offen` (ETF, Ersatzzahlung, SYEP, USD-Konto, Datumsregel …).
R16 **Schnittstelle für Anfangsbestände:** Eingabestruktur `Anfangsbestand` (Instrument, Menge, Anschaffungskosten,
    Anschaffungsdatum, Währung); leer = Warnung „Jahresergebnis unvollständig“. Reale Werte kommen später (AP-10d);
    Verlustvorträge sind getrennt und blockieren die Ereignisrechnung nicht.

## Testdaten

Neue, frei erfundene Testwelt mit von Hand gerechneten Werten (CLAUDE.md Regel 8): `tests/test_steuer_zufluss.py`,
`tests/fixtures/steuer_zufluss/`. Pflichtfälle, je mit Handrechnung im Kopf der Datei:

1. Short Put eröffnet 29.12.2025, zurückgekauft 05.01.2026: Prämie 2025, Rückkauf 2026 (negativ).
2. Wie 1 mit zwei Datumsregeln: Einordnung unterscheidet sich; Betroffenheit = 1; Steuerdatum und FX-Datum gehören
   zum selben Vorgang (Test schlägt fehl, wenn sie verschiedene Tage verbinden, ohne ausgewiesen zu sein).
3. Credit-Spread: Beine getrennt; kurzes Bein verfällt ohne Wirkung, langes als Verlust.
4. Short Put zugeteilt: Aktie zum Strike, Erwerbskosten in den Anschaffungskosten; Prämie bleibt in R1.
5. **Long Call ausgeübt** (Lieferung): Optionskosten in den Anschaffungskosten des Basiswerts; **Long Put ausgeübt**:
   im Veräußerungsergebnis des Basiswerts.
6. Barausgleich SPX: Zahlung = Termingeschäftsverlust im Zahlungsjahr.
7. **Währung:** Kauf 100 USD zu Kurs 0,90 → 90 EUR Anschaffungskosten, Verkauf 100 USD zu Kurs 0,80 → 80 EUR Erlös:
   Ergebnis **−10 EUR**, nicht 0 (das alte Netto-zum-Schlusskurs-Verfahren ergibt 0).
8. Verlusttöpfe: Aktien −1.000, Termingeschäfte +500, Dividende +50: nichts verrechnet; Gewinne und Verluste
   getrennt ausgewiesen.
9. Quellensteuer: Dividende 100 USD, einbehalten 16,67 → vorläufig anrechenbar 15,00, möglicherweise erstattungsfähig
   1,67; Land ohne Satz → ungeklärt.
10. **Ersatzzahlung** 22 USD mit Quellensteuer 3,30: nicht in KAP 41; Ausweis „Einordnung offen; Freigrenze nicht
    abschließend geprüft“ — **kein** „steuerfrei“ (der frühere Test 9 entfällt).
11. KAP-Zeilen: 2025 gemäß Antwort; 2026 → „ungeprüft“.
12. **Offene Short-Position** zum Jahresende: Prämie im Zuflussjahr gezählt.
13. **Teilglattstellung, offene Restmenge, Roll** (Glattstellung plus Neueröffnung): Σ Eröffnungsprämien und Σ
    Kommissionen = Σ der Ausführungen, jede genau einmal.
14. **Fehlender Kurs** der Schließung 2026: die Eröffnungsprämie 2025 bleibt erhalten, der Rückkauf steht in
    `datenluecken`.
15. **ETF-Lieferung:** Aktie vs. ETF — der ETF-Anteil steht in `regeln_offen` (InvStG), nicht im Aktien-Topf; eine
    Option auf den ETF bleibt Termingeschäft.
16. **Cash-Buchung ohne Kurs** (Dividende): erscheint in `datenluecken`, nicht still in einer Summe.
17. **Anfangsbestand** leer → Warnung; mit Eingabe → Bestand fließt in die FIFO-Paarung ein.
18. Gewinne/Verluste getrennt je Topf; Ausgabe `methode` nennt Kursquelle, Datumsregeln, Formularjahr, Prüfstatus.

**Golden-Daten:** `werkzeuge/abgleich/steuer_zufluss.py` (Regel 2: nur Zählwerte und Summen je Jahr, nur starkes
Modell) vergleicht neue und alte Methode und IBs Berichtswerte und gibt je Jahr die Abweichung nach Ursache aus
(Zeitpunkt, Kurs, Töpfe, offene Beine, ETF).

## Altverfahren ausdrücklich kennzeichnen

`journal steuer` (CLI-Export von AP-10) wird auf die neue Methode umgestellt **oder** trägt in Kopfzeile und
Dateiname „ALTVERFAHREN — Schließungsjahr, nicht zur Übernahme in die Steuererklärung“. Die Seite „Steuer“ trägt
diesen Hinweis bereits für die bisherigen Zahlen.

## Ausdrücklich nicht Teil dieses Pakets

- Implementierung (AP-10c); reale Anfangsbestände, Ersatzzahlungs-Ursachen, USD-Kontoeffekte (AP-10d).
- Änderung von `analytics/steuer.py`, `tests/test_steuer.py`, `tests/test_cashflows.py` und AP-10-Fixtures.
- Verlustverrechnung, Anlage-KAP-Ausfüllhilfe, Steuerberatung.
- Änderung des Projektplans §AP-10 (Vorschlag an den Nutzer, siehe AP-10c).
