---
titel: "Analytik I: EUR-Fundament und Kennzahlen je Ebene (Abnahmebasis)"
paket: AP-06v
modell: stark
status: fertig
abhaengig_von: AP-04, AP-04s
naechstes: AP-06k
---

# AP-06v · Analytik I — Abnahmebasis

Verbindlicher Vertrag für die erste Tranche von AP-06, geschrieben nach §11.2
des Plans (starkes Modell schreibt Abnahmebasis und Tests, bevor gebaut wird).
Maßgeblich ist §6 AP-06 im Plan zusammen mit §5 („Zwei Sichten",
„Währungsumrechnung") und den Prinzipien P2, P3, P4, P6.

## Tranchierung von AP-06

AP-06 im Plan ist zu groß für ein Paket. Es wird geschnitten — jede Tranche
mit eigener Abnahmebasis, Umsetzungspaket und eigener Freigabe:

- **I (dieses Paket) — Fundament:** EUR-Umrechnung nach P4 mit beiden Sichten
  und Währungseffekt, Netto-P&L und Trefferquote auf Struktur- und
  Kette-Ebene, Qualitätsstufen-Filter, `fx_rates`-Befüllung, Materialisieren
  der EUR-Kettenwerte in `metrics_by_chain`, CLI `journal kennzahlen`.
- **II — Kommissionsattribution** (Kernfrage 2): absolut und in Prozent des
  Bruttoergebnisses, aufgeschlüsselt nach Index, Anlageklasse, Strategie,
  Roll-Anzahl.
- **III — Roll-Degradation** (Kernfrage 1): Ergebnis nach 0/1/2/3+ Rolls auf
  belegten Ketten mit ausgewiesener Abdeckung. Die Variante „belegte plus
  bestätigte Kandidaten" wirkt erst mit der Entscheidung zu OF-54.
- **IV — Equity-Kurve und Drawdown** inklusive Form der Cache-Tabellen
  (löst OF-01; `metrics_daily`).
- **V — Campaign-Ebene** (Gegenfinanzierungswirkung, `metrics_by_campaign`):
  wartet auf den AP-05-Rest und damit auf eine Nutzerentscheidung.

AP-07-Rest (Kennzahl-Endpunkte, Dashboard) baut auf I–IV auf; die hier
entstehenden Datenklassen sind dafür die Vorlage.

## Startzustand (vereinbart)

`tests/test_kennzahlen.py` existiert und ist rot — allein wegen
`ModuleNotFoundError: No module named 'analytics.kennzahlen'`. Die übrige
Suite bleibt grün. Das ist der vereinbarte Startzustand, kein Defekt.

## Datenlage (gemessen, nicht geraten)

- `chains.netto_pnl_eur` ist nach jedem `rebuild` leer (in
  `tests/test_rebuild.py` verankert); der Spaltenkommentar in
  `journal/schema.py` sagt: Umrechnung geschieht in der Analyseschicht, das
  Ergebnis wird hier gespeichert. Niemand schreibt die Spalte heute.
- `executions.buchungskurs` (`fxRateToBase`) ist je Ausführung verfügbar und
  nullable (§5: „Kursquelle ist durchgehend fxRateToBase an der jeweiligen
  Ausführung; eine externe Kursquelle wird nicht benötigt"; EUR trägt 1).
- `fx_rates` existiert mit (datum, waehrung, kurs_eur, quelle) und ist leer.
- `metrics_daily` und `metrics_by_campaign` sind Stellvertreter mit nur
  einer id-Spalte (OF-01, Tranche IV/V). `metrics_by_chain` ebenso — es wird
  hier erstmals geformt (E2: `chain_id`, `netto_eur_wirtschaftlich`,
  `netto_eur_ib`), per Migration.
- `analytics/` enthält nur `__init__.py`.
- Ketten, Strukturen, Legs und Kettenglieder existieren je Sicht (`konto`,
  `kette`); Struktur-Geldbeträge sind abgenommen und handgerechnet
  dokumentiert (`tests/test_rebuild.py`, `tests/fixtures_rebuild.py`).

## Entscheidungen (vom Nutzer zu prüfen)

**E1 — Auswertungssicht ist die Kettensicht** (freigegeben mit
dokumentierter Einschränkung). §5: die Kettensicht
„beantwortet ‚wie schneidet diese Strategie ab' und trägt die
Roll-Degradation". Tranche I wertet deshalb `sicht = 'kette'` aus; der
Bericht-Parameter `--sicht konto` existiert (die Zeilen werden ja für beide
Sichten geliefert), aber die strategischen Fragen laufen über die Kettensicht.
Kontosicht-Geld bleibt AP-10 und dem Abgleich vorbehalten. Jede Zeile trägt
ihre Sicht; eine Mischung gibt es nicht.

Zwei dokumentierte Grenzen der Kettensicht (Freigabe E1):

- `chain_overrides` wirken nur in der Kontosicht (AP-04sw) — bestätigte
  Rolls existieren in der Kettensicht nicht. Die Abnahme von AP-06 verlangt
  die Degradationsvariante „belegte plus bestätigte Ketten“ (Plan §6); sie
  braucht vorher das Nachziehpaket „Overrides auch in der Kettensicht
  anwenden“ (OF-61, zu entscheiden vor Tranche III) und geht mit E1 nicht
  still verloren.
- Umgeleitete Beine ohne freien Schließer bleiben offene Ketten
  (AP-04s-Grenze): sie erscheinen als offene Zeilen und zählen nicht in
  Quoten oder Summen. Die verlangte Abdeckungs-Angabe gehört zur
  Degradation (Tranche III), nicht zu diesem Paket.

**E2 — Wirtschaftliche Sicht maßgeblich; Speicherort ist
`metrics_by_chain`, nicht `chains.netto_pnl_eur`.** §5 nennt
zwei EUR-Sichten; maßgeblich für die Strategiefrage ist die wirtschaftliche
(jeder Zahlungsstrom mit dem Kurs seiner eigenen Ausführung), denn nur sie
beantwortet, „ob eine Strategie Geld verdient hat oder nur der Dollar". Die
IB-vergleichbare Sicht ist Vergleichsgröße für den Währungseffekt.
Speicherort ist die Cache-Tabelle `metrics_by_chain` (Materialisierung,
verwerfbar): `_kette_zeile()` im Rebuild setzt `netto_pnl_eur` bei jedem
Lauf auf `None` zurück — ein Wert der Analyseschicht in `chains` hinge an
der Reihenfolge Rebuild vor Analytik, eine stille Abhängigkeit (Freigabe
E2). `chains.netto_pnl_eur` bleibt deshalb dauerhaft leer: Plan §5 führt
die Spalte, die Verankerung „leer nach rebuild“ in `tests/test_rebuild.py`
bleibt gültig, nur der Spaltenkommentar in `journal/schema.py` wird
korrigiert. Weil es zwei EUR-Sichten gibt, tragen die Cache-Spalten den
Sichtnamen: `netto_eur_wirtschaftlich`, `netto_eur_ib` (der
Währungseffekt ist die Differenz und wird nicht gespeichert). Beide Sichten
werden mit derselben Methode gefüllt, durch die Analyseschicht
(`journal kennzahlen`), nie durch `rebuild`.

**E3 — fx_rates wird Materialisierung, nicht Rechenquelle der Tranche.**
Die Kennzahlen rechnen mit dem buchungskurs der jeweiligen Ausführung (§5
wörtlich). `fx_rates` wird zusätzlich je (datum, waehrung) gefüllt — Kurs der
letzten Ausführung des Tages, gekennzeichnet `quelle =
'abgeleitet_letzte_ausfuehrung'` (abgeleitet, nicht mit einer echten
Kursquelle verwechselbar; Freigabe E3) — als Inspektionsquelle und
als Basis der Tagesaggregation in Tranche IV. Diese Trennung vermeidet, dass ein
Tagesmittelkurs still in die Handelsergebnisse eingerechnet wird. Die
Tageskurs-Regel selbst ist eine Annahme (OF-60).

**E4 — Fehlender Kurs ist Mangel, nie Kurs 1.** Wie OF-59 für AP-10: Eine
Kette mit mindestens einer Ausführung ohne buchungskurs bekommt keine
EUR-Zahlen, zählt `eur_kurs_fehlt` und erscheint in der Fehlerliste. Kein
stiller Ersatzkurs. Die Trefferquote bleibt davon unberührt, denn ihr
Vorzeichen steht in Instrumentenwährung fest.

**E5 — Trefferquote zählt Abgeschlossenes.** Nenner sind Ketten mit
`beendet_am` und vorhandenem netto (offene Ketten und Strukturen zählen
nicht), Zähler die mit netto > 0. Netto genau 0,00 zählt in den Nenner und
nicht in den Zähler — kein Treffer (im Test belegt, damit es niemand beim
Bauen nebenbei entscheidet; Freigabe E5). Quoten als Decimal, gerundet auf
vier Stellen, HALF_UP.

**E6 — Qualitätsstufe ist das Minimum über die beteiligten Ausführungen.**
Eine Kette ist so gut wie ihre schlechteste Ausführung (P6). Das Minimum
bildet der Code über eine explizite Rangfolge (A→0, B→1, C→2), nicht über
den Stringvergleich — A < B < C ist heute zufällig auch alphabetisch, und
eine dazukommende Stufe bräche sonst still (Freigabe E6). Eine unbekannte
Stufe — an der Datenbank verhindert sie das CHECK — wirft in der reinen
Funktion einen Fehler. Der Filter
`--nur-stufe-a` entfernt solche Zeilen aus allen Summen und Quoten; die
Zeilen verschwinden nicht still aus dem Bericht, sondern ganz (sie sind
unbewertet gewollt weggefiltert — im Gegensatz zu Kursmängeln, die als
Fehlerliste bleiben).

## Der Vertrag

Alles liegt in `analytics/kennzahlen.py` (rein, P2 — keine Uhr, kein
Netzwerk, kein Zufall; gleiche Eingabe → bitgleiche Ausgabe) und einer
I/O-Hülle `kennzahlen_bericht` an gleicher Stelle. Alle Geldbeträge sind
`Decimal`.

### Datenklassen

```python
@dataclass(frozen=True)
class KennzahlKette:
    chain_id: int
    sicht: str                      # 'kette' oder 'konto' — immer gefüllt
    underlying: str
    asset_class: str
    anzahl_rolls: int
    abgeschlossen: bool             # beendet_am ist nicht leer
    waehrung: str                   # der Strukturen der Kette
    netto: Decimal | None           # Instrumentenwährung, Summe der Strukturen
    netto_eur_wirtschaftlich: Decimal | None
    netto_eur_ib: Decimal | None
    waehrungseffekt_eur: Decimal | None   # wirtschaftlich − IB
    eur_kurs_fehlt: int             # Ausführungen der Kette ohne buchungskurs
    qualitaetsstufe: str            # schlechteste beteiligte Ausführung

@dataclass(frozen=True)
class KennzahlStruktur:
    structure_id: int
    chain_id: int
    sicht: str
    typ: str
    waehrung: str
    brutto: Decimal | None
    kommission: Decimal | None
    netto: Decimal | None
    netto_eur_wirtschaftlich: Decimal | None

@dataclass(frozen=True)
class KennzahlFehler:
    schluessel: str                 # Ketten-Id als Text
    grund: str                      # 'buchungskurs_fehlt' | 'waehrung_gemischt'

@dataclass(frozen=True)
class KennzahlErgebnis:
    sicht: str
    ketten: tuple[KennzahlKette, ...]
    strukturen: tuple[KennzahlStruktur, ...]
    fehler: tuple[KennzahlFehler, ...]
    summe_netto_eur: Decimal | None     # wirtschaftlich, ohne mangelbehaftete
    trefferquote_kette: Decimal | None  # 4 Stellen, HALF_UP
    trefferquote_struktur: Decimal | None
    anzahl_ketten_abgeschlossen: int
    anzahl_strukturen_abgeschlossen: int
```

### Signaturen

```python
def kennzahlen_auswertung(
    ketten_zeilen: list[dict],          # chains (alle Sichten)
    struktur_zeilen: list[dict],        # structures (alle Sichten)
    glieder_zeilen: list[dict],         # chain_links
    leg_zeilen: list[dict],             # legs
    ausfuehrungs_zeilen: list[dict],    # executions
    instrumenten_zeilen: list[dict],    # instruments
    *,
    sicht: str = "kette",
    nur_qualitaetsstufe_a: bool = False,
) -> KennzahlErgebnis: ...

def fx_tageskurse(ausfuehrungs_zeilen: list[dict]) -> list[dict]: ...

def als_csv(ergebnis: KennzahlErgebnis) -> str: ...

def kennzahlen_bericht(
    db_pfad: str | Path,
    *,
    sicht: str = "kette",
    nur_qualitaetsstufe_a: bool = False,
) -> KennzahlErgebnis: ...
```

`kennzahlen_auswertung` und `fx_tageskurse` sind rein; `kennzahlen_bericht`
liest die Tabellen (gefiltert auf die angegebene Sicht), ruft die reine
Funktion und schreibt `fx_rates` sowie `metrics_by_chain` vollständig neu
(Regel 11; `metrics_by_chain` für **beide** Sichten, `chains.netto_pnl_eur`
bleibt leer) — Schreibzugriffe nur hier, nie in der reinen Funktion.

### Regeln

1. **Sicht ist Bestandteil jeder Zeile** und Parameter der Auswertung.
   Eingangszeilen der falschen Sicht werden nicht gelesen. Ketten- und
   Strukturzeilen im Ergebnis tragen die angeforderte Sicht.
2. **Ketten-netto (Instrumentenwährung)** ist die Summe der `netto_pnl` der
   zugehörigen Strukturen (Zuordnung über `chain_links`). Ist eine Struktur
   offen oder ohne netto, ist das Ketten-netto `None` — keine Teilsumme.
3. **Wirtschaftliche EUR-Sicht** (maßgeblich): je beteiligter Ausführung der
   Zahlungsstrom `preis × menge × multiplikator` mit Vorzeichen der Seite
   (SELL +, BUY −), multipliziert mit dem `buchungskurs` **derselben**
   Ausführung; Kommissionen je Ausführung mit deren Kurs. EUR-Ausführungen
   haben den Faktor 1 und brauchen keinen `fx_rates`-Eintrag. Die
   Zahlungsströme ergeben sich aus den Legs der Sicht (open/close_exec_id,
   menge) und dem Instrument (multiplikator).
4. **IB-vergleichbare EUR-Sicht** (nur Vergleichsgröße): netto der Zeile in
   Instrumentenwährung × buchungskurs der **zeitlich letzten schließenden
   Ausführung** der Zeile (Kette: über alle close_exec_id ihrer Legs;
   Struktur: über die ihrer Legs). Gleichstand der handelszeit: größte
   exec_id. (Die exakte Lot-Zuordnung von IB lebt in AP-10; hier dient die
   Größe nur dem Währungseffekt.)
5. **Währungseffekt = wirtschaftlich − IB-vergleichbar**, je Zeile. Beide
   `None`, sobald ein Kurs fehlt.
6. **Fehlender buchungskurs** (E4): `netto_eur_*` und `waehrungseffekt_eur`
   der Zeile sind `None`, `eur_kurs_fehlt` zählt die betroffenen
   Ausführungen, die Kette steht mit Grund `buchungskurs_fehlt` in der
   Fehlerliste und bleibt aus `summe_netto_eur` heraus. Trefferquote und
   Qualitätsstufe bleiben.
7. **Offene Ketten** (`beendet_am` leer): netto `None`, nicht in Quoten und
   Summen, keine Fehlerzeile. Offene Strukturen analog.
8. **Trefferquote** (E5): Zähler netto > 0, Nenner netto vorhanden und
   abgeschlossen; netto genau 0 zählt in den Nenner und nicht in den Zähler.
   `Decimal`-Division, gerundet auf 4 Stellen, HALF_UP.
   Nenner 0 → Quote `None`.
9. **Qualitätsstufe je Zeile** (E6) ist das Minimum über die Ausführungen
   aller Legs der Zeile, gebildet über eine explizite Rangfolge im Code
   (A→0, B→1, C→2; unbekannte Stufe → Fehler) statt über den
   Stringvergleich.
   `nur_qualitaetsstufe_a=True` entfernt jede Zeile mit Minimum ≠ A aus dem
   gesamten Ergebnis (Ketten, Strukturen, Summen, Quoten, Anzahlen).
10. **`waehrung_gemischt`**: Strukturen einer Kette mit unterschiedlichen
    Währungen (nach heutigem Datenmodell nicht erreichbar) ergeben statt
    einer Zahl diese Fehlerzeile — defensiv, kein Raten.

11. **Materialisierung**: `metrics_by_chain` (E2) wird vollständig neu
    geschrieben (verwerfbar): je Kette **beider** Sichten eine Zeile mit
    `netto_eur_wirtschaftlich` und `netto_eur_ib`; offen oder
    kursmangelbehaftet → beide `NULL`. `chains.netto_pnl_eur` bleibt leer.
    `fx_rates` wird vollständig neu geschrieben (verwerfbar): je
    (datum, waehrung ≠ EUR) der buchungskurs der letzten Ausführung des
    Tages (max handelszeit, Gleichstand größte exec_id),
    `quelle = 'abgeleitet_letzte_ausfuehrung'`, sortiert nach (datum,
    waehrung).
12. **Sortierung**: Ketten nach chain_id, Strukturzeilen nach
    (chain_id, structure_id), Fehler nach (schluessel, grund).
13. **CSV** (`als_csv`): Semikolon-getrennt, 22 Spalten, Kopf exakt:

    ```
    abschnitt;sicht;chain_id;underlying;asset_class;status;anzahl_rolls;waehrung;netto;netto_eur_wirtschaftlich;netto_eur_ib;waehrungseffekt_eur;eur_kurs_fehlt;qualitaetsstufe;structure_id;typ;brutto;kommission;schluessel;grund;trefferquote_kette;trefferquote_struktur
    ```

    - `kette`-Zeile: Spalten 1–14 gefüllt (status: `offen`/`abgeschlossen`),
      15–22 leer.
    - `struktur`-Zeile: 1–3, 8–10 und 15–18 gefüllt, Rest leer.
    - `fehler`-Zeile: 1–2, 19–20 gefüllt.
    - `summe`-Zeile (eine, zuletzt): 1–2, Spalte 10 = `summe_netto_eur`,
      13 = Anzahl mangelbehafteter Ketten, 21–22 = Trefferquoten.
    - Beträge mit zwei Nachkommastellen, Quoten mit vier.

    Der CLI-Subcommand `journal kennzahlen <datei>` schreibt dieses CSV als
    UTF-8 mit BOM (wie AP-10) und nimmt `--db`, `--sicht {kette,konto}`,
    `--nur-stufe-a`. Exit-Code 0 im Erfolg.

## Grenzen

- Keine Kommissionsaufschlüsselung, keine Degradation, keine Equity-Kurve,
  kein Cache (Tranchen II–IV); keine Campaign-Ebene (Tranche V, AP-05-Rest).
- Keine neuen API-Endpunkte (AP-07-Rest) und keine UI (AP-08-Rest).
- Keine Zeitzonen-Logik: handelszeit ist naiv, wie gespeichert (OF-04).
- `metrics_daily` und `metrics_by_campaign` bleiben Stellvertreter (OF-01
  offen bis Tranche IV/V); `metrics_by_chain` wird hier minimal geformt (E2).
- Keine Overrides in der Kettensicht (AP-04sw-Grenze): Die
  Degradationsvariante „belegte plus bestätigte“ (Tranche III) wartet auf
  das Nachziehpaket aus OF-61; umgeleitete Beine ohne freien Schließer
  bleiben offene Ketten (AP-04s) und zählen nicht in Quoten — die
  Abdeckungs-Angabe gehört zu Tranche III.

## Abnahmekriterien

1. `tests/test_kennzahlen.py` ist unveränderlich und wird grün — jeder
   Erwartungswert ist im Test von Hand gerechnet und begründet (Regel 8).
2. Die übrige Suite bleibt grün; `ruff check .` bleibt sauber.
3. `journal kennzahlen <datei> --db <db>` schreibt das CSV mit BOM; Kopf
   exakt wie Regel 13.
4. Nach dem Bericht enthält `metrics_by_chain` je Sicht genau eine Zeile je
   Kette mit `netto_eur_wirtschaftlich` und `netto_eur_ib` (`NULL` nur nach
   Regel 11: offen oder Kursmangel); `chains.netto_pnl_eur` bleibt auch nach
   dem Bericht leer; `fx_rates` enthält genau die Tageskurse nach Regel 11 —
   alles gegen den synthetischen Bestand geprüft, nicht gegen echte Daten.
