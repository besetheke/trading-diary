---
titel: Zuteilungen und Wheels gehören zur Kette der Option
modell: stark
status: fertig
abhaengig_von: AP-04, AP-04pk, AP-13r3
aendert_tests: nein
---

# AP-04z · Position = ganzer Trade (OF-81)

Entscheidung des Nutzers (11.10.2026) zu OF-81: (1) Die Position endet erst mit
dem Verkauf der zugeteilten Aktien — ja. (2) Teilverkäufe werden nach dem Lot
der Zuteilung zugerechnet — ja. (3) Wheels (Put → Aktie → Call) sind eine
Position — ja.

## Vertrag (engine/chains.py, Docstring „2a′")

1. Der Zuteilungsübergang hängt am **Leg**: Schließt irgendein Options-Leg per
   Zuteilung oder Ausübung, setzt sich die Kette in der gelieferten Aktie fort,
   auch wenn die übrige Struktur anders schließt (Fall 5213).
2. Alle Legs der gelieferten Aktie gehören zur Kette, je Leg eine Struktur;
   Lots anderer Herkunft bleiben, wo sie sind (FIFO aus dem Matching).
   Naturschlüssel bei mehreren Legs derselben Lieferung: `<Eröffnung>><Schluss>`
   bzw. `>offen` (`Structure.schluessel_zusatz`); sonst unverändert.
3. Zuordnung Aktie ↔ Option über Zeitpunkt und Basiswert, bei mehreren
   Kandidaten Preis = Strike.
4. Wheel: Ketten aus reinen Short Calls auf denselben Basiswert, deren erste
   Struktur eröffnet wird, während zugeteilte Aktien gehalten werden, werden
   angehängt (Erkennung `heuristik`, Regel 7), solange Kontrakte ×
   Multiplikator die gehaltenen, noch nicht gedeckten Stücke nicht übersteigen.
5. Verknüpfungstypen `zuteilung` (auto) und `covered_call` (heuristik); beide
   zählen nicht als Roll. Migration `b2d6f8a4c1e7` erweitert die Prüfregel.
   Overrides erhalten diese Typen beim Neuordnen.
6. Die Kette endet mit der spätesten Schließung (auch nach Overrides).
7. `assignment_links` kommt aus `KettenErgebnis.zuteilungs_paare`; manuelle
   Paare bleiben.

Tests: `tests/test_chains_zuteilung.py` (10), `tests/test_rebuild_zuteilung.py`
(2). Bestehende Tests unverändert grün.

## Wirkung auf den echten Bestand (11.10.2026, Backup
`C:\Trading\backup\journal-vor-ap04z-20261011.db`)

- Ketten 7.467 → 6.557; 494 Zuteilungs-, 910 Covered-Call-Glieder (903 davon
  ohne eigene OA-Strategie, also manuell verkaufte Calls auf gehaltene Aktien).
- Lose Aktien-Legs aus Zuteilung 180 → 21; die 21 haben keine Options-
  Ausführung zur selben Zeit (u. a. MPT 2022/23 — Optionsseite fehlt in den
  Daten) und bleiben lose (weiter im Ergebnis über AP-06i).
- Realisiert (Equity) 88.384,62 → 88.384,66 € — die 4 Cent stammen aus der
  Rundung loser Legs auf Cent (AP-06i), die jetzt ungerundet in Strukturen
  stehen. Keine weitere Verschiebung.
- Trade 5213 (SPY 30DTE Strangle): Kette mit Put/Call, zugeteilter Aktie und
  sieben Covered Calls samt Rolls: −56,47 USD statt +12.406,46 USD.
