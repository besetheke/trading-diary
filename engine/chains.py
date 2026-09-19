"""Structures → Chains: Zuteilungsübergang, Rolls, Kettenidentität (AP-04,
Teil 2 — „Positionen → Ketten").

Baut auf ``engine.structures.bilde_structures()`` auf. Reines Modul wie
``engine.matching``/``engine.structures`` — keine DB, kein `journal rebuild`,
kein Override-Mechanismus; das bleibt Sache der Persistenzschicht.

Erkennungsreihenfolge, Fortsetzung (§6, AP-04):

- **2a, Zuteilung.** Schließt eine Structure per Zuteilung
  (``schluss_ereignistyp == 'assignment'``), und liefert ein zeitgleich per
  Zuteilung eröffnetes Aktienbein auf demselben Underlying (aus
  ``nicht_strukturiert``, s. Teil 1), setzt sich die Kette in dieser
  Aktienposition fort — als eigene, synthetisch gebildete Structure
  (Methode ``zuteilung``), bis diese ihrerseits schließt.
- **3, Futures.** Schließt eine Future-Structure und eröffnet eine andere
  Future-Structure auf demselben Underlying innerhalb desselben
  Zeitfensters wie Schritt 2 (§6 nennt für Futures-Rolls kein eigenes
  Fenster; ``ZEITFENSTER`` aus ``engine.structures`` wird wiederverwendet —
  **dokumentierte Annahme, siehe OFFENE_FRAGEN.md OF-35**), ist das ein
  ``contract_roll``.
- **4, Aktien.** Keine automatische Kettenbildung: Tranchen bleiben
  eigenständige Structures/Ketten. Die einzige Ausnahme ist die Fortsetzung
  aus Schritt 2a — eine per Zuteilung entstandene Position wird dort
  ausdrücklich an die vorangehende Kette angehängt, nicht als neue,
  unabhängige Aktienkette gezählt.

**Kettenidentität bei OptionApp-Positionen.** Trägt eine Structure eine
OA-Referenz, bilden alle Structures mit **demselben** ``oa_trade`` (über
verschiedene ``oa_order``-Werte hinweg) eine Kette — das ist die
gemessene Roll-Semantik aus §6.1 („OA-Trades mit mehr als einer Expiry:
27"). Ohne OA-Referenz und ohne Futures-Roll bildet jede Structure ihre
eigene, ungerollte Kette.

**Offene Annahme (Regel 10, OF-35):** Für Optionspositionen **ohne**
OA-Referenz nennt der Plan keine Roll-Erkennung analog zu Futures — nur
Schritt 3 spricht ausdrücklich von Futures. Angenommen: Options-Rolls ohne
OA-Referenz werden **nicht** automatisch verkettet; jede so gebildete
Structure ist ihre eigene, ungerollte Kette. Das ist an den Golden-Daten
nur indirekt over den Vergleich mit der Referenzzahl (134 Ketten, 66 BCS,
68 BPS) prüfbar, nicht direkt belegt.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace

from engine.structures import (
    ZEITFENSTER,
    LegSchluessel,
    NichtStrukturiert,
    Structure,
    StrukturErgebnis,
    schliessung_bestimmen,
)

# Endzustand-Vokabular exakt wie journal.schema.chains (§5).
ENDZUSTAND_JE_EREIGNIS = {
    "assignment": "Assigned",
    "exercise": "Assigned",
    "expiry": "Verfall",
    "trade": "Geschlossen",
}

# ---------------------------------------------------------------------------
# Ergebnis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainGlied:
    """Eine Structure innerhalb einer Kette, mit ihrer Rolle."""

    structure: Structure
    sequenz: int
    verknuepfungstyp: str  # open / roll (close/adjust: s. Modul-Docstring, noch nicht vergeben)
    erkennung: str  # auto / heuristik / manuell (CLAUDE.md Regel 7)


@dataclass(frozen=True)
class Chain:
    glieder: tuple[ChainGlied, ...]
    underlying: str
    asset_class: str
    seite: str | None  # Call / Put / n.a.
    eroeffnet_am: datetime
    beendet_am: datetime | None
    anzahl_rolls: int
    endzustand: str | None  # Verfall / Geschlossen / Assigned / Offen


@dataclass(frozen=True)
class KettenErgebnis:
    chains: tuple[Chain, ...]


# ---------------------------------------------------------------------------
# Zuteilungsübergang (Schritt 2a)
# ---------------------------------------------------------------------------


def _zuteilungs_structure(
    ns: NichtStrukturiert,
    leg: Mapping,
    executions: Mapping[str, Mapping],
    instrument: Mapping,
) -> Structure:
    """Bildet eine synthetische Ein-Bein-Structure für ein per Zuteilung
    eröffnetes Aktienbein — dieselbe Schluss-Logik wie ``bilde_structures()``,
    aber ohne an der regulären Erkennungsreihenfolge teilzunehmen (das Bein
    ist nach P7 dort ausdrücklich ausgeschlossen)."""
    oeffnung = executions[leg["open_exec_id"]]

    status, geschlossen_am, schluss_ereignistyp, brutto_pnl = schliessung_bestimmen(
        [SimpleNamespace(leg=leg)], executions
    )
    return Structure(
        leg_schluessel=(ns.leg_schluessel,),
        asset_class=instrument.get("asset_class"),
        typ="Stock" if instrument.get("asset_class") == "STK" else "Custom",
        underlying=instrument.get("underlying") or instrument.get("symbol"),
        expiry=instrument.get("expiry"),
        short_strike=None,
        long_strike=None,
        breite=None,
        menge=leg["menge"],
        eroeffnet_am=oeffnung["handelszeit"],
        dte_bei_eroeffnung=None,
        methode="zuteilung",
        erkennung="auto",
        status=status,
        geschlossen_am=geschlossen_am,
        schluss_ereignistyp=schluss_ereignistyp,
        brutto_pnl=brutto_pnl,
        kommission_gesamt=leg["kommission_gesamt"],
        rechte=frozenset(),
        oa_trade=None,
    )


def _zuteilungs_fortsetzungen(
    struktur_ergebnis: StrukturErgebnis,
    legs_je_schluessel: Mapping[LegSchluessel, Mapping],
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
) -> dict[int, Structure]:
    """Liefert je Index einer zuteilungsschließenden Structure in
    ``struktur_ergebnis.structures`` die Fortsetzungs-Structure, falls eine
    per Zuteilung eröffnete Aktienzeile zum selben Zeitpunkt und Underlying
    unter ``nicht_strukturiert`` gefunden wird."""
    zuteilungs_kandidaten: list[tuple[NichtStrukturiert, Mapping, Mapping]] = []
    for ns in struktur_ergebnis.nicht_strukturiert:
        if "assignment" not in ns.grund:
            continue
        leg = legs_je_schluessel.get(ns.leg_schluessel)
        if leg is None:
            continue
        oeffnung = executions.get(leg["open_exec_id"])
        if oeffnung is None or oeffnung["ereignistyp"] != "assignment":
            continue
        instrument = instruments.get(leg["conid"])
        if instrument is None:
            continue
        zuteilungs_kandidaten.append((ns, leg, instrument))

    fortsetzung_je_index: dict[int, Structure] = {}
    verbraucht: set[LegSchluessel] = set()
    for index, structure in enumerate(struktur_ergebnis.structures):
        if structure.schluss_ereignistyp != "assignment":
            continue
        for ns, leg, instrument in zuteilungs_kandidaten:
            if ns.leg_schluessel in verbraucht:
                continue
            oeffnung = executions[leg["open_exec_id"]]
            passendes_underlying = (
                instrument.get("underlying") or instrument.get("symbol")
            ) == structure.underlying
            if passendes_underlying and oeffnung["handelszeit"] == structure.geschlossen_am:
                fortsetzung_je_index[index] = _zuteilungs_structure(
                    ns, leg, executions, instrument
                )
                verbraucht.add(ns.leg_schluessel)
                break
    return fortsetzung_je_index


# ---------------------------------------------------------------------------
# Futures-Rolls (Schritt 3)
# ---------------------------------------------------------------------------


def _futures_rolls_verketten(structures: list[Structure]) -> dict[int, int]:
    """Liefert je Index einer schließenden Future-Structure den Index der
    Structure, die den Roll fortsetzt (nächste Future-Eröffnung desselben
    Underlyings innerhalb von ``ZEITFENSTER`` nach der Schließung)."""
    je_underlying: dict[str, list[int]] = {}
    for index, s in enumerate(structures):
        if s.typ == "Future":
            je_underlying.setdefault(s.underlying, []).append(index)

    fortsetzung_je_index: dict[int, int] = {}
    for indizes in je_underlying.values():
        indizes.sort(key=lambda i: structures[i].eroeffnet_am)
        verbraucht: set[int] = set()
        for i in indizes:
            s = structures[i]
            if s.status != "geschlossen" or s.geschlossen_am is None:
                continue
            beste = None
            for j in indizes:
                if j == i or j in verbraucht:
                    continue
                kandidat = structures[j]
                delta = kandidat.eroeffnet_am - s.geschlossen_am
                if delta.total_seconds() < 0 or delta > ZEITFENSTER:
                    continue
                if beste is None or kandidat.eroeffnet_am < structures[beste].eroeffnet_am:
                    beste = j
            if beste is not None:
                fortsetzung_je_index[i] = beste
                verbraucht.add(beste)
    return fortsetzung_je_index


# ---------------------------------------------------------------------------
# Kettenbildung
# ---------------------------------------------------------------------------


def bilde_chains(
    struktur_ergebnis: StrukturErgebnis,
    legs: Iterable[Mapping],
    executions: Iterable[Mapping],
    instruments: Mapping[int, Mapping],
) -> KettenErgebnis:
    """Verkettet Structures zu Chains (§6, AP-04, Schritte 2a–4)."""
    executions_je_id = {satz["exec_id"]: satz for satz in executions}
    legs_je_schluessel = {
        LegSchluessel(leg["open_exec_id"], leg.get("close_exec_id")): leg for leg in legs
    }

    structures = list(struktur_ergebnis.structures)
    zuteilungs_fortsetzung = _zuteilungs_fortsetzungen(
        struktur_ergebnis, legs_je_schluessel, executions_je_id, instruments
    )
    futures_fortsetzung = _futures_rolls_verketten(structures)

    # Kettenidentität: OA-Trade gruppiert über oa_order-Grenzen hinweg;
    # sonst ist jede Structure zunächst ihre eigene Kette, es sei denn, sie
    # wird unten als Fortsetzung an eine vorhergehende angehängt.
    ketten_sequenzen: dict[str, list[int]] = {}
    eigene_kette: list[int] = []
    for index, s in enumerate(structures):
        if s.oa_trade:
            ketten_sequenzen.setdefault(f"oa:{s.oa_trade}", []).append(index)
        else:
            eigene_kette.append(index)

    sequenzen: list[list[int]] = list(ketten_sequenzen.values())
    for index in eigene_kette:
        sequenzen.append([index])

    # Futures-Rolls verschmelzen zwei (bislang eigenständige) Sequenzen.
    index_zu_sequenz = {i: seq_id for seq_id, seq in enumerate(sequenzen) for i in seq}
    for von_index, nach_index in futures_fortsetzung.items():
        von_seq = index_zu_sequenz[von_index]
        nach_seq = index_zu_sequenz[nach_index]
        if von_seq == nach_seq:
            continue
        sequenzen[von_seq].extend(sequenzen[nach_seq])
        for i in sequenzen[nach_seq]:
            index_zu_sequenz[i] = von_seq
        sequenzen[nach_seq] = []

    chains: list[Chain] = []
    for sequenz_indizes in sequenzen:
        if not sequenz_indizes:
            continue
        sequenz_indizes = sorted(
            set(sequenz_indizes), key=lambda i: structures[i].eroeffnet_am
        )
        glied_structures = [structures[i] for i in sequenz_indizes]

        # Zuteilungsübergang: hängt die synthetische Fortsetzung an, sofern
        # eine gefunden wurde — auch mitten in einer OA-Kette möglich.
        anhang: list[Structure] = []
        for i in sequenz_indizes:
            if i in zuteilungs_fortsetzung:
                anhang.append(zuteilungs_fortsetzung[i])
        alle_structures = glied_structures + anhang

        glieder = tuple(
            ChainGlied(
                structure=s,
                sequenz=pos + 1,
                verknuepfungstyp="open" if pos == 0 else "roll",
                erkennung="auto",
            )
            for pos, s in enumerate(alle_structures)
        )

        letzte_structure = alle_structures[-1]
        eroeffnet_am = min(s.eroeffnet_am for s in alle_structures)
        vollstaendig_geschlossen = all(s.status == "geschlossen" for s in alle_structures)
        beendet_am = letzte_structure.geschlossen_am if vollstaendig_geschlossen else None
        endzustand = (
            ENDZUSTAND_JE_EREIGNIS.get(letzte_structure.schluss_ereignistyp, "Geschlossen")
            if vollstaendig_geschlossen
            else "Offen"
        )
        anzahl_rolls = len(alle_structures) - 1

        asset_classes = {s.asset_class for s in alle_structures}
        asset_class = alle_structures[0].asset_class if len(asset_classes) > 1 else next(
            iter(asset_classes)
        )
        seite = _seite_bestimmen(alle_structures)
        underlying = alle_structures[0].underlying

        chains.append(
            Chain(
                glieder=glieder,
                underlying=underlying,
                asset_class=asset_class,
                seite=seite,
                eroeffnet_am=eroeffnet_am,
                beendet_am=beendet_am,
                anzahl_rolls=anzahl_rolls,
                endzustand=endzustand,
            )
        )

    chains.sort(key=lambda c: (c.eroeffnet_am, c.underlying))
    return KettenErgebnis(chains=tuple(chains))


def _seite_bestimmen(structures: list[Structure]) -> str | None:
    rechte: set[str] = set()
    for s in structures:
        rechte |= s.rechte
    if rechte == {"C"}:
        return "Call"
    if rechte == {"P"}:
        return "Put"
    if rechte:
        return "n.a."
    return None
