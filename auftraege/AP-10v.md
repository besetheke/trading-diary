# AP-10v — Abnahmebasis: Steuerliche Auswertung (Töpfe, Jahresabgrenzung, CSV)

modell: stark
status: fertig
aendert: tests/test_steuer.py (neu), auftraege/AP-10k.md (neu), OFFENE_FRAGEN.md (OF-58, OF-59)
aendert_tests: ja
abhaengig_von: AP-04sw (legs trägt beide Sichten; rebuild liest Kapitalmaßnahmen)

## Ziel

Vorbereitungspaket für AP-10 im Stil von AP-13v: Die Abnahmebasis entsteht vor
der Umsetzung. Dieses Paket implementiert nichts (CLAUDE.md, Regel 1a). Es
liefert den verbindlichen Vertrag für `analytics/steuer.py` und
`journal/steuer.py` sowie die Abnahmetests `tests/test_steuer.py`, deren
erwartete Zahlen per Hand gerechnet und im Test begründet sind (Regel 8).
Rot bis AP-10k umsetzt — der Importfehler des fehlenden Moduls ist der
vereinbarte Startzustand, kein Defekt der Tests.

AP-10 ist im Plan hinter AP-06 einsortiert; das Paket wurde auf Entscheidung
des Nutzers vorgezogen. Das ist unbedenklich: Die Auswertung liest `legs`,
`executions`, `instruments` und `flex_cash_transactions` (AP-02 bis AP-04),
keine Kennzahlen aus AP-06.

## Datenlage (gemessen, nicht geraten)

- `legs` (schema.py): `brutto_pnl`, `kommission_gesamt`, `offen_ja_nein`,
  `basis_ungeklaert`, `sicht` ('konto'/'kette'), `close_exec_id` bei
  Schließung — die Kontosicht ist die Steuer-Sicht (Plan §5).
- `executions.buchungskurs` (ExactDecimal, nullable): Kurs der Buchung zu EUR
  an der Ausführung — die EUR-Sicht, die IB in seinen Reports ebenso bildet.
- `instruments.asset_class`: STK/OPT/FOP/FUT/CASH (Ausprägungen aus den
  Golden-Daten; kein erschöpfendes CHECK, deshalb behandelt Vertrag 4
  Unbekanntes als Fehler statt still).
- `flex_cash_transactions` (§6.1): Zinsen, Quellensteuer, Dividenden,
  Gebühren, Einzahlungen — Rohdaten mit `typ`, `betrag`, `waehrung`.
- Kapitalmaßnahmen (OF-23): Transfer auf neue conid; ein Split realisiert
  nichts und verschiebt nur die Basis (Menge UND Preis) — deshalb landet im
  Zuflussjahr nur die Verkaufs-Leg, nie der Stichtag selbst.

## Entscheidungen (durch den Auftraggeber, dieses Paket)

1. **Zufluss bei Schließung** (`handelszeit`-Jahr der schließenden
   Ausführung), für Verfall und Zuteilung/Ausübung genauso wie für Verkauf —
   §11-Ordnungsmäßigkeit: Die Zahlen müssen je Leg belegbar sein, nicht
   periodisiert glatt. Offene Legs haben keinen Zufluss.
2. **Naive Zeitstempel** wie gespeichert (Anschluss an OF-04): `.year` direkt,
   keine Umrechnung. OF-58 dokumentiert die Grenze.
3. **EUR-Ausweis über `buchungskurs` der Schließung** (IB-vergleichbare
   Sicht, OF-59): `netto_eur_ib = netto × buchungskurs`. Fehlt der Kurs,
   zählt die Leg trotzdem (Instrumentwährung), der Mangel wird gezählt und
   als Fehler benannt — kein stiller Kurs 1, auch nicht bei EUR-Instrumenten.
4. **`basis_ungeklaert` außerhalb der Summen**: realisiert, aber Herkunft der
   Basis ungeklärt — eigene Liste `ungeklaert`, kein Topf-Beitrag. Eine Zahl
   unbekannter Herkunft wird nicht in eine Summe gemischt, die jemand als
   Tatsache liest (Scheingewinn-Problem, schema.py zu `basis_ungeklaert`).
5. **Zuteilung/Ausübung realisiert an der Options-Leg** (Entscheidung (b) der
   Plan-Vorabfragen): Die Option schließt am Zuteilungstag mit ihrem
   Ergebnis, die synthetische Aktien-Leg bleibt offen bis zum Verkauf. Der
   IB-paritätische Ausweis („geparkte Prämie") hängt an OF-24 und ist nicht
   Teil dieses Pakets.
6. **CASH ausgeschlossen**: Devisenkostenrechnung, kein Termingeschäft —
   Fehler `cash_ausgeschlossen`, nie ein Topf-Beitrag.

## Der Vertrag (verbindlich für AP-10k)

### analytics/steuer.py — Datenklassen

```python
TOPF_AKTIEN = "aktien"
TOPF_TERMIN = "termingeschaefte"

@dataclass(frozen=True)
class TopfZeile:
    jahr: int
    topf: str                    # TOPF_AKTIEN oder TOPF_TERMIN
    waehrung: str                # Instrumentwährung der Legs
    brutto: Decimal
    kommission: Decimal          # negativ, wie gespeichert
    netto: Decimal               # brutto + kommission
    netto_eur_ib: Decimal        # Summe über Legs mit Buchungskurs
    eur_kurs_fehlt: int          # Legs ohne Buchungskurs in diesem Topf
    anzahl_legs: int
    basis_ungeklaert: int        # immer 0 — ungeklärte Legs stehen separat

@dataclass(frozen=True)
class SteuerLegZeile:            # Drilldown: jede bewertete Leg einzeln
    leg_id: int | None
    close_exec_id: str
    conid: int
    symbol: str
    handelszeit: datetime        # naive Schließungszeit
    jahr: int
    topf: str
    waehrung: str
    menge: Decimal
    brutto: Decimal
    kommission: Decimal
    netto: Decimal
    buchungskurs: Decimal | None
    netto_eur_ib: Decimal | None # None, wenn buchungskurs fehlt
    basis_ungeklaert: bool

@dataclass(frozen=True)
class ErtragsZeile:              # E8/Kapitalerträge, außerhalb der Töpfe
    jahr: int
    typ: str                     # Quellwert aus flex_cash_transactions.typ
    waehrung: str
    betrag: Decimal              # vorzeichentreu wie Quelle

@dataclass(frozen=True)
class SteuerFehler:
    schluessel: str              # close_exec_id der betroffenen Leg
    grund: str                   # siehe Regeln

@dataclass(frozen=True)
class SteuerErgebnis:
    toepfe: tuple[TopfZeile, ...]
    details: tuple[SteuerLegZeile, ...]
    ungeklaert: tuple[SteuerLegZeile, ...]
    ertraege: tuple[ErtragsZeile, ...]
    fehler: tuple[SteuerFehler, ...]
```


### analytics/steuer.py — Funktionen

```python
def steuer_auswertung(legs, exec_je_id, instrument_je_conid,
                      cash_transaktionen=()) -> SteuerErgebnis
def als_csv(ergebnis, jahr=None) -> str
```

`legs`: Iterierbares von Abbildungen mit den legs-Spalten (leg_id, sicht,
conid, close_exec_id, offen_ja_nein, basis_ungeklaert, menge, brutto_pnl,
kommission_gesamt). `exec_je_id`: exec_id → Abbildung mit handelszeit und
buchungskurs. `instrument_je_conid`: conid → Abbildung mit asset_class,
symbol, waehrung. `cash_transaktionen`: Abbildungen mit datum, typ, betrag,
waehrung (wie flex_cash_transactions; `steuer_bericht` übergibt alle Zeilen,
auch Einzahlungen — bewusst ohne Typ-Semantik, das Filtern gehört dem Leser).

### Regeln 1–11

1. Nur Kontosicht. Eine Leg mit `sicht != 'konto'` wird zurückgewiesen:
   Fehler `sicht_vermischung`, kein Beitrag zu irgendeiner Summe (Plan §5 —
   keine Abfrage liefert Zeilen beider Sichten; die Steuer wertet konto).
2. Offene Legs (`offen_ja_nein` oder `close_exec_id is None`): kein Zufluss,
   kein Fehler, keine Zeile.
3. Zuflussjahr = Jahr der `handelszeit` der schließenden Ausführung, naiv wie
   gespeichert (OF-04/OF-58). Fehlt die Schließung in `exec_je_id`:
   Fehler `schliessung_fehlt`.
4. Topf über `instrument_je_conid[conid]["asset_class"]`: STK → aktien;
   OPT/FOP/FUT → termingeschaefte; CASH → Fehler `cash_ausgeschlossen`;
   conid fehlt → `instrument_fehlt`; jeder andere Wert →
   `asset_class_unbekannt`. Nie still: unbekannt ist ein Fehler, kein Topf.
5. Beträge: brutto = brutto_pnl, kommission = kommission_gesamt (None gilt
   als 0 — bei Ereignis-Schließungen normal), netto = brutto + kommission.
   brutto_pnl None an einer geschlossenen Leg: Fehler `ergebnis_fehlt`,
   kein Topf-Beitrag.
6. EUR: netto_eur_ib = netto × buchungskurs der schließenden Ausführung.
   Fehlt der Kurs: Leg zählt vollständig in der Instrumentwährung,
   `eur_kurs_fehlt` steigt, Fehler `buchungskurs_fehlt`. Kein stiller
   Kurs 1 — auch EUR-Instrumente brauchen den Kurs in den Daten.
7. `basis_ungeklaert`: realisiert, aber Herkunft der Basis ungeklärt — kein
   Topf-Beitrag, eigene Zeile in `ungeklaert` (gleicher Typ wie details).
   Nichts Falsches wird summiert, nichts verschwiegen.
8. Drilldown: Summe der details je (jahr, topf, waehrung) gleich der
   TopfZeile — jede angezeigte Zahl bis zur Leg verfolgbar (§5).
9. Erträge: gruppiert (Jahr aus datum, typ, waehrung), Betrag
   vorzeichentreu summiert; nie in den Töpfen, nie in netto_eur_ib.
10. Sortierungen: toepfe (jahr, topf, waehrung); details und ungeklaert
    (handelszeit, close_exec_id); ertraege (jahr, typ, waehrung); fehler
    (schluessel, grund). Deterministisch, unveränderlich.
11. Reinheit (Regel 6): kein DB-Zugriff, keine Uhrzeit, kein Zufall.


### journal/steuer.py und CLI (Verträge 12/13)

```python
def steuer_bericht(db_pfad) -> SteuerErgebnis   # liest selbst, sicht='konto'
```

Liest legs der Kontosicht, executions, instruments, flex_cash_transactions
und ruft `steuer_auswertung`. CLI: `journal steuer <datei> [--jahr N]` mit
dem üblichen `--db`. `--jahr` filtert die Zeilen mit Jahresspalte; die
Fehlerliste bleibt — Datenqualität kennt kein Jahr. Die Datei schreibt die
CLI als UTF-8 mit BOM (Excel öffnet Umlaute ohne Nachfrage); Exit-Code 0 nur
mit geschriebenem Dateikörper.

### CSV-Format (Vertrag 12, in tests/test_steuer.py verankert)

Eine flache Tabelle, Semikolon-getrennt, Punkt als Dezimaltrenner,
Spaltenkopf deutsch, None als leeres Feld, Boolean als ja/nein, Zeilenende
`\n`, abschließender Umbruch. Spaltenreihenfolge: abschnitt, sicht, jahr,
topf, waehrung, brutto, kommission, netto, netto_eur_ib, eur_kurs_fehlt,
anzahl_legs, basis_ungeklaert, conid, symbol, close_exec_id, handelszeit,
menge, typ, betrag, schluessel, grund. Abschnitte in fester Reihenfolge:
topf, detail, ungeklaert, ertrag, fehler — jeweils in der Sortierung der
Ergebnistupel. handelszeit als ISO (`2024-08-30T15:00:00`). `sicht` trägt in
topf/detail/ungeklaert den Wert `konto` — jede Zahl nennt ihre Sicht (§5);
in ertrag/fehler bleibt das Feld leer.

## Grenzen

- Vorbereitung für den Steuerberater / die Anlage KAP, keine Steuerberatung;
  insbesondere bildet dieses Paket keine Verlustverrechnung, keinen
  Verlustvortrag und keine rechtlichen Töpfe (§20 Abs. 6 EStG) ab — es
  liefert die Zahlen je Topf und Jahr.
- Stillhalterprämien (§11/Einkünfte aus gewerblichen Grundstücks­handel
  bzw. §22 Nr. 3 EStG-Fragestellung) werden nicht gesondert ausgewiesen; die
  Behandlung ist mit dem Steuerberater offen (OF-24). Die Zahlen sind
  vollständig aus den Legs ablesbar.
- Zuteilung/Ausübung: Entscheidung (b) — die Options-Leg realisiert am
  Zuteilungstag, die synthetische Aktien-Leg bleibt offen. Der
  IB-paritätische Ausweis wartet auf die geparkte Prämie aus OF-24.
- Zeitstempel naiv (OF-58); eine spätere UTC-Migration ändert nur Daten,
  nicht diesen Vertrag.
- Einzahlungen/Auszahlungen erscheinen als Ertragszeilen mit ihrem
  Quell-Typen — bewusst ohne Semantik; die Bewertung gehört dem Leser.

## Abnahme

Maschinell nach AP-10k: `pytest` vollständig grün einschließlich
`tests/test_steuer.py`; `ruff check .` sauber; `git diff --stat` zeigt nur
`analytics/steuer.py`, `journal/steuer.py`, `journal/cli.py`.

Für dieses Paket selbst: Die Suite ohne `tests/test_steuer.py` bleibt grün;
die neue Datei ist ausschließlich wegen der fehlenden Module rot
(Importfehler), `ruff check .` sauber.

Manuell: Der Auftraggeber prüft die Entscheidungen 1–6 gegen die offenen
Fragen (OF-24, OF-57, OF-58, OF-59) und gibt die Abnahmebasis frei. Erst
danach startet AP-10k.



