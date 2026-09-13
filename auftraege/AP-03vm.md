---
titel: Kapitalmaßnahmen als Transfer statt Faktor (OF-23)
modell: stark
status: fertig
abhaengig_von: AP-03vb
aendert_tests: ja
---

# AP-03vm · Kapitalmaßnahmen als Transfer

Korrekturpaket nach CLAUDE.md, Regel 1a. Die ursprüngliche Vertrag-Regel 6
(„Faktor auf derselben `conid`") ist fachlich falsch — IB bucht jede
gemessene Kapitalmaßnahme als Abgang auf der alten und Zugang auf einer
**neuen** `conid` (OF-23, 10 von 10 gemessenen Maßnahmen). Dieses Paket
korrigiert die betroffene Abnahmebasis und ergänzt sie um zwei bisher nicht
abgedeckte Fälle. **Implementiert wird nichts** — die Nachbesserung von
`engine/matching.py` macht danach AP-03.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **`fixtures/synthetisch/aktiensplit.json`** neu gefasst: die Kapitalmaßnahme
  überträgt auf eine neue `conid` (500003 → 500030), statt auf derselben zu
  bleiben; die zweite Ausführung liegt schon auf der neuen `conid`, wie im
  echten Export. Die Stichtagsgrenze bleibt als eigene Maßnahme (500009 →
  500032) erhalten. **Die Zahlenwerte sind identisch mit der Vorfassung** —
  nur die `conid`, auf der sie erscheinen, ändert sich für den
  transferierten Fall.
- **`tests/test_matching.py`**, die fünf Tests im Block „Aktiensplit vor dem
  Matching": Erwartungen auf `conid` 500030 statt 500003 umgestellt (Assert
  auf `leg.conid`, `legs_von(..., conid=500030)`); `test_split_wirkt_nicht_
  auf_ausfuehrungen_ab_dem_stichtag` prüft zusätzlich `legs_von(...,
  conid=500032) == []`. Die geprüften Zahlenwerte selbst bleiben
  unverändert.
- **`DEZIMALFELDER`** in `tests/test_matching.py` um `alte_menge`,
  `neue_menge`, `kosten_neu` ergänzt (sonst bleiben es Zeichenketten statt
  `Decimal`, Regel 5).
- **Zwei neue Fixtures**: `kapitalmassnahme_optionsanpassung.json`
  (Mengenverhältnis 5:4, nicht der glatte 2:1-Fall — deckt die gemessene
  Abweichung bei Optionsanpassungen FS/FI ab) und
  `kapitalmassnahme_reiner_zugang.json` (zwei Fälle: mit und ohne IBs
  Kostenangabe).
- **Vier neue Tests** am Ende von `tests/test_matching.py`:
  `test_optionsanpassung_uebertraegt_menge_nach_verhaeltnis_der_massnahme`,
  `test_optionsanpassung_glattes_verhaeltnis_waere_das_falsche_ergebnis`,
  `test_reiner_zugang_mit_kostenangabe_eroeffnet_zu_deren_stueckpreis`,
  `test_reiner_zugang_ohne_kostenangabe_ist_basis_ungeklaert`.

Bestehende Tests außerhalb der genannten Stellen bleiben unverändert.

## Vertrag (zur Übernahme in AP-03.md)

**Eingabe `kapitalmassnahmen`.** Jeder Eintrag trägt `aktion_id` (gruppiert
Abgang und Zugang derselben Maßnahme, IBs `actionID`), `konto`, `typ`
(Rohwert der Quelle), `stichtag`, `alter_conid` (`None` bei reinem Zugang),
`alte_menge` (`None` bei reinem Zugang), `neuer_conid`, `neue_menge`,
`kosten_neu` (optional, nur bei reinem Zugang relevant).

**Transfer** (`alter_conid` gesetzt): Faktor = `neue_menge / alte_menge`.
Jede Ausführung auf `alter_conid` **vor** dem Stichtag wechselt auf
`neuer_conid`: Menge × Faktor, Preis ÷ Faktor — Anschaffungskosten je Lot
bleiben dadurch unverändert. Eine Ausführung am Stichtag selbst oder danach
gilt bereits zu neuen Konditionen und bleibt unverschoben. Der Faktor ergibt
sich aus der Maßnahme, nicht aus einer angenommenen Standardrelation (2:1
o. Ä.).

**Reiner Zugang** (`alter_conid` ist `None`): Die Engine eröffnet ein
synthetisches Lot auf `neuer_conid` zum Zeitpunkt des Stichtags, Menge
`neue_menge`, Kommission 0. Liegt `kosten_neu`, ist der Stückpreis
`kosten_neu / neue_menge`; sonst ist der Preis 0 und das daraus entstehende
`Leg` trägt `basis_ungeklaert = True` — keine stille Nullbasis (führt bei
AP-10 sonst zu einem vollen Scheingewinn beim späteren Verkauf).

**Rückgabe.** `Leg` erhält das Feld `basis_ungeklaert: bool`, Standard
`False`. Entspricht `legs.basis_ungeklaert` (Migration `d7c4b6a1f9e3`).

**Ausdrücklich nicht Teil dieses Vertrags:** Wie „die Kette den Übergang
überlebt" (OF-23, Punkt 1) und die Kennzeichnung `instruments.angepasst`
(Punkt 2) dargestellt werden, ist Sache der Struktur-/Kettenerkennung
(AP-04) beziehungsweise der noch zu bauenden Ableitung von
`flex_corporate_actions` nach `corporate_actions` — beide liegen außerhalb
der reinen Matching-Funktion `bilde_legs`.

## Abnahme

- Die zehn betroffenen Tests (fünf umgestellte, vier neue, plus die
  ohnehin generische `test_jedes_leg_traegt_eine_positive_menge`, die
  `aktiensplit` mitprüft) schlagen gegen den jetzigen `engine/matching.py`
  fehl — Nachweis der Lücke.
- Alle übrigen Tests bleiben grün.
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_matching.py`, `fixtures/synthetisch/aktiensplit.json`, den
  zwei neuen Fixtures, sowie `journal/schema.py` und der neuen Migration
  `d7c4b6a1f9e3` (Regel 3: `corporate_actions` als Transfer,
  `instruments.angepasst`, `legs.basis_ungeklaert` — ohne diese Spalten ist
  der Vertrag nicht testbar). Kein `engine/`.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung im Matching. Keine Ableitung von `corporate_actions` aus
`flex_corporate_actions` (eigenes, späteres Paket). Keine Änderung an
`ingest/` oder `journal/` außerhalb der bereits migrierten Spalten.
