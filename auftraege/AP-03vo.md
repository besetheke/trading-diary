---
titel: Barausgleich/Lieferung-Prüfung auf Optionen beschränken (OF-28)
modell: stark
status: entwurf
abhaengig_von: AP-03vb
aendert_tests: ja
---

# AP-03vo · Barausgleich/Lieferung nur an der Option prüfen

Korrekturpaket nach CLAUDE.md, Regel 1a. Vertrag Regel 7 (AP-03vb, OF-25)
verlangt eine ``abwicklungsart`` an **jeder** Ausführung mit
``ereignistyp in (assignment, exercise)``. Der Re-Lauf gegen Golden-Daten
(OF-27) zeigte: Eine physische Zuteilung/Ausübung bucht IB als **zwei**
Ausführungszeilen mit demselben Ereigniscode — die schließende Optionszeile
und die eröffnende/schließende Aktienlieferung. Die Aktienzeile trägt nie
eine ``abwicklungsart`` (``settlementPolicyMethod`` ergibt nur für Optionen
einen Sinn; gemessen an allen 639 Lieferzeilen der Golden-Daten,
ausnahmslos). Die heutige Prüfung bricht deshalb bei **jedem** echten Konto
mit physischer Zuteilung/Ausübung ab — nicht nur bei einer Datenlücke,
sondern systematisch, per Konstruktion. Dieses Paket korrigiert die
betroffene Abnahmebasis. **Implementiert wird nichts** — die Nachbesserung
von ``engine/matching.py`` macht danach AP-03.

## Ausdrücklich freigegebene Änderungen an Tests und Fixtures

Nur diese, keine weiteren.

- **Eine neue Fixture**: ``barausgleich_lieferung_aktienleg.json`` — eine
  physische Zuteilung mit beiden Beinen: Optionszeile (conid 500040,
  ``abwicklungsart='lieferung'``) und Aktienlieferung (conid 500041, `STK`,
  ohne ``abwicklungsart``).
- **Zwei neue Tests** am Ende des Barausgleich-Blocks in
  ``tests/test_matching.py``:
  ``test_aktienlieferung_einer_zuteilung_braucht_keine_abwicklungsart``
  (die Aktienzeile bricht nicht ab und matcht zu ihrem eigenen Preis) und
  ``test_optionsbein_der_lieferung_bleibt_von_der_aktienzeile_unberuehrt``
  (Regressionsschutz: das Optionsbein verhält sich wie zuvor).
- **Modul-Docstring** um einen Nachtrag-Absatz ergänzt (gleiches Muster wie
  die vorherigen Nachträge).

Bestehende Tests außerhalb dieser Stellen bleiben unverändert — insbesondere
bleibt jeder bisherige Barausgleich-/Lieferung-Test an einer Option
unverändert in seiner Erwartung.

## Vertrag (Präzisierung von AP-03.md, Regel 7)

Die Barausgleich/Lieferung-Prüfung (``_abwicklung_pruefen``) gilt nur für
Ausführungen, deren Instrument eine Option ist (``asset_class`` `OPT` oder
`FOP`). Bei jeder anderen Anlageklasse — insbesondere der Aktienlieferung
einer Zuteilung/Ausübung — nimmt die Zeile zwar weiterhin am Matching teil
(``ereignistyp`` bleibt matchend, § MATCHENDE_EREIGNISTYPEN), aber ohne die
Abwicklungsart-Prüfung: sie matcht zu ihrem eigenen Ereigniszeilenpreis wie
eine gewöhnliche Ausführung. `FOP` ist eingeschlossen, obwohl in den
gemessenen Golden-Daten nicht belegt — es ist wie `OPT` ein Optionsinstrument
mit derselben ``settlementPolicyMethod``-Semantik, keine geratene Erweiterung
auf eine unbelegte Anlageklasse.

Am bisherigen Verhalten für Optionen selbst (Regel 7, AP-03vb) ändert sich
nichts.

## Abnahme

- Die beiden neuen Tests schlagen gegen den jetzigen `engine/matching.py`
  fehl (`ValueError`, Aktienzeile ohne `abwicklungsart`) — Nachweis der
  Lücke.
- Alle übrigen Tests in `tests/test_matching.py` bleiben grün (belegt: 76 →
  78 Tests, davon 76 unverändert grün, 2 neue rot).
- `git diff --stat` zeigt Änderungen ausschließlich in
  `tests/test_matching.py` und der neuen Fixture
  `fixtures/synthetisch/barausgleich_lieferung_aktienleg.json`. Kein
  `engine/`, kein Schema, keine Migration.

## Ausdrücklich nicht Teil dieses Pakets

Keine Umsetzung im Matching. Keine Aussage zum Geldtest oder zur
Kostenbasis der zugeteilten Aktien (die Prämie-in-Aktienbasis-Frage aus
OF-24 bleibt unberührt — diese Fixture verwendet bewusst einen einfachen
Kauf/Verkauf am Aktienbein, keine Prämienverrechnung).
