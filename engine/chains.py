"""Structures → Chains: Rolls, Zuteilungsübergang, Kettenidentität (AP-04,
Teil 2 — Block B, „Strukturen → Kette").

Baut auf ``engine.structures.bilde_structures()`` auf. Reines Modul wie
``engine.matching``/``engine.structures`` — keine DB, kein `journal rebuild`,
kein Override-Mechanismus; das bleibt Sache der Persistenzschicht.

Block B ist von Block A (Legs → Struktur, ``engine.structures``) bewusst
getrennt: „gleiche Expiry" gilt nur für die Strukturbildung dort — hier wäre
sie sinnwidrig, ein Roll wechselt gerade die Expiry (Plan, 19.09.2026, nach
Rückfrage präzisiert).

**0a, OptionApp-Referenz.** Structures mit derselben OA-Trade-Nummer (über
verschiedene ``oa_order``-Werte hinweg) bilden eine Kette — gemessen in §6.1
(„27 OA-Trades mit mehr als einer Expiry"). Keine Heuristik nötig.

**Klarstellung (Nutzer, 19.09.2026): OA rollt nicht selbst.** Jeder Roll
wird manuell über TWS ausgeführt, nie durch OA. Die ``oa_trade``-Nummer ist
die vom Nutzer in OA gepflegte Kettenreferenz — sie ordnet eine über TWS
gerollte Fortsetzung derselben Kampagne zu, ist aber selbst kein
Roll-Mechanismus. Folge für dieses Modul: Der eigentliche Rollvorgang muss
über Schritt 1/2 (``exec_batch``/Zeitfenster) erkennbar sein, genau wie bei
jeder anderen Structure auch — ``_rolls_verketten()`` läuft deshalb bewusst
über **alle** Structures, OA-referenzierte eingeschlossen, nicht nur über
die ohne ``oa_trade``. Eine TWS-gerollte Fortsetzung, die selbst keine
OA-Referenz trägt, wird so trotzdem an die OA-Kette angehängt, wenn
``exec_batch``/Zeitfenster passen.

**1, Roll in einer Order.** Schließt eine Combo-Ausführung — erkennbar am
gemeinsamen ``exec_batch`` — zugleich Legs einer Structure und eröffnet neue
auf demselben Basiswert, ist das ein Roll. Dieser Weg gilt für **alle**
Anlageklassen und ist bei Optionen ohne OA-Referenz der Regelfall, weil
Rolls üblicherweise als eine Order ausgeführt werden.

**2, Roll in zwei Orders.** Schließung und Eröffnung innerhalb von
``ZEITFENSTER`` (3 Minuten), gleicher Basiswert, gleiche Seite (Call/Put),
vergleichbare Menge — nur für Optionen (OPT/FOP); die Expiry unterscheidet
sich hier zwangsläufig und ist deshalb keine Bedingung. Nur Structures, die
nicht bereits über Schritt 1 verkettet wurden.

**2a, Zuteilung.** Schließt eine Structure per Zuteilung
(``schluss_ereignistyp == 'assignment'``), und liefert ein zeitgleich per
Zuteilung eröffnetes Aktienbein auf demselben Underlying (aus
``nicht_strukturiert``, s. Teil 1), setzt sich die Kette in dieser
Aktienposition fort — als eigene, synthetisch gebildete Structure (Methode
``zuteilung``), bis diese ihrerseits schließt.

**3, Futures — kein Zeitfenster.** Nur Schritt 1 (derselbe ``exec_batch``)
verkettet Futures automatisch. Eine Front-Monat-Schließung und eine
Back-Monat-Eröffnung am selben Handelstag **ohne** gemeinsamen ``exec_batch``
sind höchstens ein Kandidat für eine manuelle Bestätigung — dieses Modul
markiert solche Kandidaten nicht; das braucht den (noch nicht gebauten)
Override-Mechanismus der Persistenzschicht. Futures sind bei den bekannten
Konten ein seltener Fall; eine Heuristik dafür brächte mehr Risiko als
Nutzen (Nutzer, 19.09.2026).

**4, Aktien.** Keine automatische Kettenbildung: Tranchen bleiben
eigenständige Structures/Ketten. Die einzige Ausnahme ist die Fortsetzung
aus Schritt 2a.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace

from engine.structures import (
    ZEITFENSTER,
    LegSchluessel,
    NichtStrukturiert,
    Structure,
    StrukturErgebnis,
    mengen_vergleichbar,
    schliessung_bestimmen,
)

# Endzustand-Vokabular exakt wie journal.schema.chains (§5).
ENDZUSTAND_JE_EREIGNIS = {
    "assignment": "Assigned",
    "exercise": "Assigned",
    "expiry": "Verfall",
    "trade": "Geschlossen",
}

OPTIONS_ANLAGEKLASSEN = frozenset({"OPT", "FOP"})

# ---------------------------------------------------------------------------
# Ergebnis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainGlied:
    """Eine Structure innerhalb einer Kette, mit ihrer Rolle."""

    structure: Structure
    sequenz: int
    verknuepfungstyp: str  # open / roll (close/adjust: noch nicht vergeben)
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
    # Summe über alle Glieder — None, solange mindestens eines offen ist
    # (dieselbe Regel wie bei Structure: kein irreführendes Teilergebnis).
    brutto_pnl: Decimal | None
    kommission_gesamt: Decimal


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

    status, geschlossen_am, schluss_ereignistyp, brutto_pnl, schluss_exec_batch = (
        schliessung_bestimmen([SimpleNamespace(leg=leg)], executions)
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
        oeffnungs_exec_batch=None,
        schluss_exec_batch=schluss_exec_batch,
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
# Rolls: Schritt 1 (eine Order) und Schritt 2 (zwei Orders)
# ---------------------------------------------------------------------------


def _rolls_verketten(structures: list[Structure]) -> dict[int, int]:
    """Liefert je Index einer schließenden Structure den Index derjenigen,
    die den Roll fortsetzt — zuerst über Schritt 1 (gemeinsamer
    ``exec_batch``, alle Anlageklassen), dann über Schritt 2 (Zeitfenster,
    nur Optionen, für alles, was Schritt 1 nicht verkettet hat)."""
    fortsetzung: dict[int, int] = {}
    verbraucht: set[int] = set()

    # Schritt 1: dieselbe Combo-Ausführung schließt die eine, eröffnet die
    # andere Structure — erkennbar am gemeinsamen exec_batch.
    oeffnungsindizes_je_batch: dict[str, list[int]] = {}
    for index, s in enumerate(structures):
        if s.oeffnungs_exec_batch:
            oeffnungsindizes_je_batch.setdefault(s.oeffnungs_exec_batch, []).append(index)

    for index, s in enumerate(structures):
        if s.status != "geschlossen" or not s.schluss_exec_batch:
            continue
        for kandidat_index in oeffnungsindizes_je_batch.get(s.schluss_exec_batch, []):
            if kandidat_index == index or kandidat_index in verbraucht:
                continue
            fortsetzung[index] = kandidat_index
            verbraucht.add(kandidat_index)
            break

    # Schritt 2: kein gemeinsamer exec_batch — 3-Minuten-Fenster, gleicher
    # Basiswert, gleiche Seite, vergleichbare Menge. Nur Optionen; die
    # Expiry ist bewusst keine Bedingung (ein Roll wechselt sie gerade).
    je_underlying: dict[str, list[int]] = {}
    for index, s in enumerate(structures):
        if s.asset_class in OPTIONS_ANLAGEKLASSEN:
            je_underlying.setdefault(s.underlying, []).append(index)

    for indizes in je_underlying.values():
        indizes_sortiert = sorted(indizes, key=lambda i: structures[i].eroeffnet_am)
        for index in indizes_sortiert:
            if index in fortsetzung:
                continue
            s = structures[index]
            if s.status != "geschlossen" or s.geschlossen_am is None:
                continue
            beste = None
            for kandidat_index in indizes_sortiert:
                if kandidat_index == index or kandidat_index in verbraucht:
                    continue
                kandidat = structures[kandidat_index]
                delta = kandidat.eroeffnet_am - s.geschlossen_am
                if delta.total_seconds() < 0 or delta > ZEITFENSTER:
                    continue
                if kandidat.rechte != s.rechte:
                    continue
                if not mengen_vergleichbar(kandidat.menge, s.menge):
                    continue
                if beste is None or kandidat.eroeffnet_am < structures[beste].eroeffnet_am:
                    beste = kandidat_index
            if beste is not None:
                fortsetzung[index] = beste
                verbraucht.add(beste)
    return fortsetzung


# ---------------------------------------------------------------------------
# Kettenbildung
# ---------------------------------------------------------------------------


def bilde_chains(
    struktur_ergebnis: StrukturErgebnis,
    legs: Iterable[Mapping],
    executions: Iterable[Mapping],
    instruments: Mapping[int, Mapping],
) -> KettenErgebnis:
    """Verkettet Structures zu Chains (§6, AP-04, Block B)."""
    executions_je_id = {satz["exec_id"]: satz for satz in executions}
    legs_je_schluessel = {
        LegSchluessel(leg["open_exec_id"], leg.get("close_exec_id")): leg for leg in legs
    }

    structures = list(struktur_ergebnis.structures)
    zuteilungs_fortsetzung = _zuteilungs_fortsetzungen(
        struktur_ergebnis, legs_je_schluessel, executions_je_id, instruments
    )
    roll_fortsetzung = _rolls_verketten(structures)

    # Kettenidentität: OA-Trade gruppiert über oa_order-Grenzen hinweg;
    # sonst ist jede Structure zunächst ihre eigene Kette, es sei denn, sie
    # wird unten über einen Roll (Schritt 1/2) an eine vorhergehende
    # angehängt.
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

    # Rolls (Schritt 1/2) verschmelzen zwei (bislang eigenständige)
    # Sequenzen — auch dann, wenn eine Seite bereits Teil einer OA-Kette ist.
    index_zu_sequenz = {i: seq_id for seq_id, seq in enumerate(sequenzen) for i in seq}
    for von_index, nach_index in roll_fortsetzung.items():
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
        asset_class = (
            alle_structures[0].asset_class
            if len(asset_classes) > 1
            else next(iter(asset_classes))
        )
        seite = _seite_bestimmen(alle_structures)
        underlying = alle_structures[0].underlying
        kommission_gesamt = sum(
            (s.kommission_gesamt for s in alle_structures), Decimal(0)
        )
        brutto_pnl = (
            sum(
                (s.brutto_pnl for s in alle_structures if s.brutto_pnl is not None),
                Decimal(0),
            )
            if vollstaendig_geschlossen
            else None
        )

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
                brutto_pnl=brutto_pnl,
                kommission_gesamt=kommission_gesamt,
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
