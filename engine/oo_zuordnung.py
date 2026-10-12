"""Zuordnung Option-Omega-Backtest → OA-Strategie (AP-12a), rein (Regel 6).

Die OO-Spalte ``Strategy`` und die OA-Strategie teilen keine Normalform. Sie
lassen sich aber über die Trades verbinden: Backtest und Bot öffnen am selben
Tag, zur selben Uhrzeit (beide US-Ostküstenzeit), dieselbe Struktur.

Ein OO-Trade passt zu einem Live-Trade, wenn
- der Tag gleich ist und die **Familie** des Basiswerts (SPX/XSP/SPY ·
  RUT/IWM · NDX/QQQ; sonst der Basiswert selbst),
- die **Signatur** gleich ist: die Legs nach (Call/Put, Strike, Verfall)
  sortiert, je Leg (Call/Put, Tage bis Verfall, Seite, Menge ÷ ggT aller
  Mengen) — Strikes selbst zählen nicht, nur ihre Reihenfolge,
- die **Spannweite** (größter − kleinster Strike ÷ mittlerer Strike, in
  Promille) höchstens um max(1, 30 % der OO-Spannweite) abweicht — trennt eine
  SPX-Vertikale mit 10 Punkten von einer mit 50, und SPY-Flügel von SPX-Flügeln,
- die Eröffnungen höchstens ``toleranz`` (20 Minuten) auseinanderliegen.

Unter mehreren Kandidaten gewinnt der zeitlich nächste. Die Schwellen sind
Annahmen aus dem Echtbestand (Auftrag AP-12a), keine Vorgaben des Plans.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import reduce
from math import gcd

TOLERANZ = timedelta(minutes=20)
SPANNWEITE_MIN = Decimal("1")
SPANNWEITE_ANTEIL = Decimal("0.3")
MIN_TREFFER = 2
MIN_ANTEIL = Decimal("0.5")
EINDEUTIG_AB = Decimal("0.8")

FAMILIE = {
    "SPX": "SPX", "SPXW": "SPX", "XSP": "SPX", "SPY": "SPX",
    "RUT": "RUT", "RUTW": "RUT", "IWM": "RUT",
    "NDX": "NDX", "NDXP": "NDX", "QQQ": "NDX",
}


@dataclass(frozen=True)
class Leg:
    menge: int
    seite: str  # "S" verkauft, "B" gekauft
    right: str  # "C" / "P"
    strike: Decimal
    expiry: date


@dataclass(frozen=True)
class Eroeffnung:
    """Ein OO-Trade (``schluessel`` = Zeilenkennung, ``strategie`` = OO-Text)
    oder ein Live-Trade (``schluessel`` = OA-Nummer, ``strategie`` =
    OA-Strategie)."""

    schluessel: str
    strategie: str
    zeit: datetime
    basiswert: str
    legs: tuple[Leg, ...]


@dataclass(frozen=True)
class Vorschlag:
    oo_strategie: str
    oa_strategie: str
    treffer: int
    anteil: Decimal
    eindeutig: bool
    erster: date
    letzter: date


def familie(basiswert: str) -> str:
    return FAMILIE.get(basiswert, basiswert)


def _zusammengefasst(legs) -> dict[tuple, int]:
    menge: dict[tuple, int] = defaultdict(int)
    for leg in legs:
        menge[(leg.right, leg.strike, leg.expiry, leg.seite)] += leg.menge
    return {k: m for k, m in menge.items() if m}


def kontrakte(legs) -> int:
    """ggT der (je Strike, Verfall und Seite zusammengefassten) Mengen."""
    mengen = list(_zusammengefasst(legs).values())
    return reduce(gcd, mengen) if mengen else 0


def signatur(legs, tag: date) -> tuple:
    z = _zusammengefasst(legs)
    if not z:
        return ()
    g = reduce(gcd, z.values())
    return tuple(
        (right, (expiry - tag).days, seite, m // g)
        for (right, _strike, expiry, seite), m in sorted(z.items())
    )


def spannweite(legs) -> Decimal:
    strikes = [leg.strike for leg in legs]
    mitte = sum(strikes) / len(strikes)
    return ((max(strikes) - min(strikes)) / mitte * 1000).quantize(
        Decimal("0.1"), ROUND_HALF_UP)


def _passt_breite(oo: Decimal, live: Decimal) -> bool:
    return abs(oo - live) <= max(SPANNWEITE_MIN, SPANNWEITE_ANTEIL * oo)


def paaren(
    oo: list[Eroeffnung], live: list[Eroeffnung], toleranz: timedelta = TOLERANZ
) -> dict[str, str]:
    """OO-Schlüssel → Schlüssel des zeitlich nächsten passenden Live-Trades."""
    index: dict[tuple, list[tuple[Eroeffnung, Decimal]]] = defaultdict(list)
    for x in live:
        if x.legs:
            index[(x.zeit.date(), familie(x.basiswert), signatur(x.legs, x.zeit.date()))].append(
                (x, spannweite(x.legs)))
    paare: dict[str, str] = {}
    for o in oo:
        if not o.legs:
            continue
        breite = spannweite(o.legs)
        tag = o.zeit.date()
        kandidaten = [
            x for x, b in index[(tag, familie(o.basiswert), signatur(o.legs, tag))]
            if abs(x.zeit - o.zeit) <= toleranz and _passt_breite(breite, b)
        ]
        if kandidaten:
            bester = min(kandidaten, key=lambda x: (abs(x.zeit - o.zeit), x.schluessel))
            paare[o.schluessel] = bester.schluessel
    return paare


PAARUNG_EINS_ZU_EINS = timedelta(minutes=90)


def _strike_abstand(a, b) -> Decimal:
    """Summe der Strike-Unterschiede, sortierte Strikes gegeneinander — nur ein
    Tiebreaker bei gleichem Zeitabstand."""
    sa = sorted(leg.strike for leg in a)
    sb = sorted(leg.strike for leg in b)
    if len(sa) != len(sb):
        return Decimal(0)
    return sum((abs(x - y) for x, y in zip(sa, sb, strict=True)), Decimal(0))


def zuordnen_eins_zu_eins(
    oo: list[Eroeffnung], live: list[Eroeffnung], toleranz: timedelta = PAARUNG_EINS_ZU_EINS
) -> dict[str, str]:
    """Paarung für den Vergleich eines BESTÄTIGTEN Paars Backtest ↔ Bot
    (AP-12c): derselbe Tag, dieselbe Familie, Signatur und Breite wie in
    ``paaren``, aber jeder Live-Trade nur einmal und mit großem Zeitfenster —
    sonst bliebe ein später einsteigender Bot ohne Partner und die Ursache
    „Einstiegszeit" wäre nie sichtbar. Der kleinste Zeitabstand gewinnt, dann
    der kleinste Strike-Abstand; Rest nach Schlüssel."""
    kandidaten = []
    for o in oo:
        if not o.legs:
            continue
        tag = o.zeit.date()
        sig = signatur(o.legs, tag)
        breite = spannweite(o.legs)
        for x in live:
            if not x.legs or x.zeit.date() != tag:
                continue
            if familie(x.basiswert) != familie(o.basiswert) or signatur(x.legs, tag) != sig:
                continue
            if abs(x.zeit - o.zeit) > toleranz or not _passt_breite(breite, spannweite(x.legs)):
                continue
            kandidaten.append((abs(x.zeit - o.zeit), _strike_abstand(o.legs, x.legs),
                               o.schluessel, x.schluessel))
    paare: dict[str, str] = {}
    belegt: set[str] = set()
    for _, _, o_id, x_id in sorted(kandidaten):
        if o_id not in paare and x_id not in belegt:
            paare[o_id] = x_id
            belegt.add(x_id)
    return paare


def vorschlaege(
    oo: list[Eroeffnung], live: list[Eroeffnung], paare: dict[str, str]
) -> list[Vorschlag]:
    """Je (OO-Strategie, OA-Strategie) Treffer und Anteil an allen Treffern der
    OO-Strategie; gezeigt ab ``MIN_TREFFER`` Treffern oder ``MIN_ANTEIL``."""
    live_je = {x.schluessel: x for x in live}
    treffer: Counter = Counter()
    tage: dict[tuple, list[date]] = defaultdict(list)
    for o in oo:
        if o.schluessel in paare:
            k = (o.strategie, live_je[paare[o.schluessel]].strategie)
            treffer[k] += 1
            tage[k].append(o.zeit.date())
    gesamt: Counter = Counter()
    for (s, _), n in treffer.items():
        gesamt[s] += n
    ergebnis = []
    for (s, oa), n in treffer.items():
        anteil = (Decimal(n) / gesamt[s]).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        if n >= MIN_TREFFER or anteil >= MIN_ANTEIL:
            ergebnis.append(Vorschlag(s, oa, n, anteil, anteil >= EINDEUTIG_AB,
                                      min(tage[(s, oa)]), max(tage[(s, oa)])))
    return sorted(ergebnis, key=lambda v: (v.oo_strategie, -v.treffer, v.oa_strategie))
