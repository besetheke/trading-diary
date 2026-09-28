---
titel: Abnahmebasis für den OA-Abgleich (Verknüpfung und Ergebnisvergleich)
modell: stark
status: fertig
abhaengig_von: AP-04
aendert_tests: ja
---

# AP-13v · Abnahmebasis für den OA-Abgleich

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-13k (günstiges Modell).

Fachliche Grundlage: Plan §6, AP-13, zweiter Teil („Verknüpfung und
Ergebnisabgleich... bleiben beim starken Modell"), sowie §6.1, Abschnitt
„Verknüpfung OA-Export ↔ Flex-Ketten". Der Parser-Teil (AP-13p/pk/pl/pm,
AP-13q/r) ist fertig und bleibt unverändert — dieses Paket baut nur den
zweiten, bisher nicht begonnenen Teil.

Siehe `OFFENE_FRAGEN.md`, **OF-53**: der Fingerabdruck verzichtet bewusst
auf die Entry Time (unvergleichbare Zeitzone, bereits in
`auftraege/AP-13-anhang-oa-format.md` Punkt 4 festgehalten) und vergleicht
nur die Leg-Spezifikation.

## Worum es geht

Eine reine Funktion, die importierte OA-Trades (`optionapp_trades`/
`optionapp_legs`, roh vorhanden) gegen bereits gebildete Ketten
(`engine.chains.bilde_chains()`) verknüpft:

1. **Verknüpfung über die Klammernummer** (`oa_trade`, Primärschlüssel,
   §6.1 „Entschieden") — nicht neu zu diskutieren.
2. **Fingerabdruck-Absicherung** über die Leg-Spezifikation des ersten
   Kettenglieds (Right/Strike/Expiry/Richtung als Menge) — stimmt sie
   nicht überein, wird die Zuordnung **nicht verworfen**, sondern als
   `erkennung="heuristik"` statt `"auto"` markiert (Regel 7, kein
   stiller Fehlerfall gemäß §6.1).
3. **Fehlerliste** für OA-Trades ohne eindeutige Kette — nie
   stillschweigend verworfen (Abnahmekriterium des Plans).
4. **Ergebnisabgleich**: OA-`profit` gegen `chain.brutto_pnl`, nur wenn
   die Kette geschlossen ist.
5. **Abdeckung**: Anteil der OA-Trades mit genau einer gefundenen Kette
   (unabhängig vom Fingerabdruck-Status) — Grundlage für die 95 %-Abnahme.

`Strategy`/`Status`-Übernahme in die Persistenz (neue Spalten,
Migration) ist **nicht** Teil dieses Pakets — das baut AP-13k. Die
Felder werden hier nur unverändert durchgereicht, damit AP-13k sie
persistieren kann.

## Zu bauen

Ein einziges neues Modul: `engine/oa_abgleich.py`.

### Datentypen

```python
@dataclass(frozen=True)
class OALegSignatur:
    right: str          # 'C' / 'P'
    strike: Decimal
    expiry: date
    richtung: int        # +1 long, -1 short (wie optionapp_legs.richtung)

@dataclass(frozen=True)
class OATradeEintrag:
    oa_trade: str
    legs: tuple[OALegSignatur, ...]
    profit: Decimal
    strategie: str
    status: str

@dataclass(frozen=True)
class OAZuordnung:
    oa_trade: str
    chain: Chain              # engine.chains.Chain
    fingerabdruck_treffer: bool
    erkennung: str             # auto / heuristik (Regel 7)
    ergebnis_oa: Decimal
    ergebnis_eigen: Decimal | None   # chain.brutto_pnl, None wenn offen
    abweichung: Decimal | None       # ergebnis_oa - ergebnis_eigen
    strategie: str
    status: str

@dataclass(frozen=True)
class OAFehler:
    oa_trade: str
    grund: str   # 'keine_kette' / 'mehrdeutig'

@dataclass(frozen=True)
class OAAbgleichErgebnis:
    zuordnungen: tuple[OAZuordnung, ...]
    fehler: tuple[OAFehler, ...]
    abdeckung: Decimal   # Anzahl(zuordnungen) / Anzahl(oa_trades), ungerundet
```

### Funktion

```python
def oa_abgleich(
    oa_trades: Iterable[OATradeEintrag],
    chains: Iterable[Chain],
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
) -> OAAbgleichErgebnis
```

Reine Funktion (Regel 6): keine DB, keine `datetime.now()`, kein Zufall.
`zuordnungen` und `fehler` deterministisch sortiert nach `oa_trade`.

## Ablauf (verbindlich, kein Implementierungsdetail zur freien Wahl)

1. Für jede `Chain`: die `oa_trade`-Nummer ist die eines beliebigen
   Executions ihrer Legs — durch die Kettenbildung (AP-04k, „0a,
   OptionApp-Referenz") tragen alle Executions einer Chain dieselbe
   Nummer, sofern eine vorhanden ist. Chains ganz ohne `oa_trade`
   (DAX, ESTX50, Futures, diskretionäre Werte — §6.1) werden
   ausgelassen, sind kein Fehlerfall.
2. Baue `chain_je_oa_trade: dict[str, list[Chain]]`.
3. Für jeden `OATradeEintrag`: Nachschlag in `chain_je_oa_trade`.
   - Leer → `OAFehler(oa_trade, "keine_kette")`.
   - Mehr als ein Treffer → `OAFehler(oa_trade, "mehrdeutig")`.
   - Genau ein Treffer → `OAZuordnung` bilden.
4. Fingerabdruck: Leg-Signatur des **ersten** Kettenglieds (`chain.glieder[0].structure`)
   — aufgelöst über `structure.leg_schluessel` → `executions[open_exec_id]`
   → `instruments[conid]`, wie in `werkzeuge/abgleich/golden_oa_abgleich.py`,
   Funktion `_eigene_legs()` (dort abschreiben, nicht neu erfinden — das
   Modul dort bleibt aber unberührt, es liegt unter `werkzeuge/` und
   dieses Paket darf keine Abhängigkeit dorthin einführen; nur das Muster
   übernehmen). Vergleich als Menge von `(right, strike, expiry, richtung)`
   gegen die Menge der `OALegSignatur`en des Trades.
5. `ergebnis_eigen = chain.brutto_pnl` (kann `None` sein).
   `abweichung = ergebnis_oa - ergebnis_eigen`, nur wenn `ergebnis_eigen`
   gesetzt ist, sonst `None`.
6. `abdeckung = Decimal(len(zuordnungen)) / Decimal(len(oa_trades))`, ohne
   Rundung — die Darstellung (Prozent, Nachkommastellen) ist Sache des
   Aufrufers.

## Wo du abschreiben sollst statt neu zu erfinden

- **Baumuster einer reinen Kandidaten-/Abgleichsfunktion**:
  `engine/campaigns.py` — Dataclasses, sortierte, deterministische
  Rückgabe, kein Seiteneffekt.
- **Auflösung von Leg-Signaturen ohne DB-Zugriff** (nur mit vorgeladenen
  `executions`/`instruments`-Mappings): `werkzeuge/abgleich/
  golden_oa_abgleich.py`, Funktionen `_eigene_legs()` und
  `_referenz_legs()` — exakt das Muster, das hier gebraucht wird, nur als
  Produktionscode statt Diagnoseskript.
- **`Chain`/`ChainGlied`/`Structure`-Felder**: `engine/chains.py`,
  `engine/structures.py`.

## Grenzen

- Kein Eingriff in `engine/chains.py`, `engine/structures.py`,
  `engine/matching.py`, `engine/campaigns.py`.
- Kein Eingriff in `werkzeuge/abgleich/golden_oa_abgleich.py` — nur das
  Muster abschreiben, keine Abhängigkeit von `werkzeuge/` aus `engine/`.
- Keine Persistenz, keine Migration, keine API, keine Oberfläche — das
  ist AP-13k.
- Keine Interpretation von `status`/`strategie` (z. B. Mapping auf
  Endzustände) — reines Durchreichen.
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, nicht gegen
  `journal.db` arbeiten. Alle Tests laufen auf erfundenen Daten.

## Abnahme

- `tests/test_oa_abgleich.py` läuft vollständig grün, alle übrigen Tests
  bleiben es, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `engine/oa_abgleich.py`.
