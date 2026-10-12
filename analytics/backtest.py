"""Live gegen Backtest (AP-12a): Zuordnung OO-Strategie → OA-Strategie und
Vergleich der Ergebnisse je Kontrakt.

- **Zuordnungen**: errechnete Vorschläge (``engine.oo_zuordnung``,
  ``erkennung = heuristik``) und die Entscheidungen des Nutzers aus
  ``oo_zuordnung`` (``manuell``: ``bestaetigt`` / ``abgelehnt``).
- **Vergleich** je nicht abgelehnter Zuordnung, in USD **je Kontrakt**
  (Kontrakte = ggT der Leg-Mengen, auf beiden Seiten gleich gerechnet; je
  Kontrakt auf Cent, HALF_UP — benannte Rundung, Regel 5):
  ``paar`` — OO-Trade mit Live-Partner dieser OA-Strategie, beide geschlossen;
  ``nur_backtest`` — geschlossener OO-Trade ohne jeden Live-Partner an einem
  Tag, an dem der Bot lief (erster bis letzter Live-Trade der OA-Strategie);
  ``nur_live`` — geschlossener Live-Trade der OA-Strategie ohne jeden
  OO-Partner an einem Tag im Zeitraum des Backtests (ein Trade, den eine
  andere OO-Variante erklärt, fehlt dem Backtest nicht);
  ``offen`` — OO ``Backtest Completed`` oder Live-Partner noch offen.
- Live-Ergebnis ist der OA-Gewinn (USD) — nicht das IB-Ergebnis, das durch
  Konto-FIFO zwischen Bots wandert (AP-13ab). Live-Trades mit OA-Gewinn in
  anderer Währung bleiben außen vor.

``backtest_auswertung`` ist rein; ``backtest_bericht`` die lesende Hülle.
"""

import pathlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from analytics.oa_vergleich import _oa_waehrung_und_profit
from engine.oo_zuordnung import (
    EINDEUTIG_AB,
    Eroeffnung,
    Leg,
    kontrakte,
    paaren,
    vorschlaege,
)
from ingest.optionomega import legs_lesen
from journal.db import create_db_engine
from journal.schema import executions, instruments, oo_trades, oo_zuordnung, optionapp_trades

CENT = Decimal("0.01")
ANTEIL = Decimal("0.0001")
EROEFFNUNG_FENSTER = timedelta(minutes=2)


@dataclass(frozen=True)
class OoZeile:
    eroeffnung: Eroeffnung
    kontrakte: int
    pl: Decimal
    offen: bool


@dataclass(frozen=True)
class LiveZeile:
    eroeffnung: Eroeffnung
    kontrakte: int
    profit: Decimal | None  # USD; None = offen oder andere Währung
    offen: bool


@dataclass(frozen=True)
class ZuordnungZeile:
    oo_strategie: str
    oa_strategie: str
    erkennung: str
    status: str
    treffer: int
    anteil: Decimal
    eindeutig: bool
    oo_anzahl: int
    erster: date | None
    letzter: date | None


@dataclass(frozen=True)
class VergleichDetail:
    art: str
    zeit_backtest: datetime | None
    zeit_live: datetime | None
    oa_trade: str | None
    kontrakte_backtest: int | None
    kontrakte_live: int | None
    pl_backtest: Decimal | None
    pl_live: Decimal | None
    differenz: Decimal | None


@dataclass
class VergleichZeile:
    oo_strategie: str
    oa_strategie: str
    paare: int = 0
    summe_backtest: Decimal = Decimal("0")
    summe_live: Decimal = Decimal("0")
    differenz: Decimal = Decimal("0")
    nur_backtest: int = 0
    summe_nur_backtest: Decimal = Decimal("0")
    nur_live: int = 0
    summe_nur_live: Decimal = Decimal("0")
    offen: int = 0
    details: list[VergleichDetail] = field(default_factory=list)


@dataclass(frozen=True)
class BacktestBericht:
    zuordnungen: list[ZuordnungZeile]
    vergleich: list[VergleichZeile]
    ohne_zuordnung: list[tuple[str, int]]


def _je_kontrakt(betrag: Decimal, kontrakte: int) -> Decimal:
    return (betrag / kontrakte).quantize(CENT, ROUND_HALF_UP)


def _vergleich(oo_s: str, oa_s: str, oo: list[OoZeile], live: list[LiveZeile],
               paare: dict[str, str]) -> VergleichZeile:
    eigene_oo = [z for z in oo if z.eroeffnung.strategie == oo_s]
    eigene_live = [z for z in live if z.eroeffnung.strategie == oa_s]
    live_je = {z.eroeffnung.schluessel: z for z in live}
    zeile = VergleichZeile(oo_s, oa_s)
    live_tage = [z.eroeffnung.zeit.date() for z in eigene_live]
    oo_tage = [z.eroeffnung.zeit.date() for z in eigene_oo]
    gepaart = set(paare.values())
    for o in eigene_oo:
        e = o.eroeffnung
        partner = live_je.get(paare.get(e.schluessel, ""))
        if o.offen or (partner is not None and partner.eroeffnung.strategie == oa_s
                       and partner.profit is None):
            zeile.offen += 1
            zeile.details.append(VergleichDetail(
                "offen", e.zeit, partner.eroeffnung.zeit if partner else None,
                partner.eroeffnung.schluessel if partner else None, o.kontrakte,
                partner.kontrakte if partner else None, None, None, None))
            continue
        bt = _je_kontrakt(o.pl, o.kontrakte)
        if partner is not None and partner.eroeffnung.strategie == oa_s:
            lv = _je_kontrakt(partner.profit, partner.kontrakte)
            zeile.paare += 1
            zeile.summe_backtest += bt
            zeile.summe_live += lv
            zeile.details.append(VergleichDetail(
                "paar", e.zeit, partner.eroeffnung.zeit, partner.eroeffnung.schluessel,
                o.kontrakte, partner.kontrakte, bt, lv, lv - bt))
        elif partner is None and live_tage and min(live_tage) <= e.zeit.date() <= max(live_tage):
            zeile.nur_backtest += 1
            zeile.summe_nur_backtest += bt
            zeile.details.append(VergleichDetail(
                "nur_backtest", e.zeit, None, None, o.kontrakte, None, bt, None, None))
    for x in eigene_live:
        e = x.eroeffnung
        if (e.schluessel in gepaart or x.profit is None or not oo_tage
                or not min(oo_tage) <= e.zeit.date() <= max(oo_tage)):
            continue
        lv = _je_kontrakt(x.profit, x.kontrakte)
        zeile.nur_live += 1
        zeile.summe_nur_live += lv
        zeile.details.append(VergleichDetail(
            "nur_live", None, e.zeit, e.schluessel, None, x.kontrakte, None, lv, None))
    zeile.differenz = zeile.summe_live - zeile.summe_backtest
    zeile.details.sort(key=lambda d: (d.zeit_backtest or d.zeit_live, d.art))
    return zeile


def backtest_auswertung(oo: list[OoZeile], live: list[LiveZeile],
                        entscheidungen: dict[tuple[str, str], str]) -> BacktestBericht:
    oo_e = [z.eroeffnung for z in oo]
    live_e = [z.eroeffnung for z in live]
    paare = paaren(oo_e, live_e)
    vorschlag = {(v.oo_strategie, v.oa_strategie): v for v in vorschlaege(oo_e, live_e, paare)}

    live_strat = {e.schluessel: e.strategie for e in live_e}
    roh: Counter = Counter()
    je_oo: Counter = Counter()
    tage: dict[tuple, list[date]] = defaultdict(list)
    for e in oo_e:
        if e.schluessel in paare:
            k = (e.strategie, live_strat[paare[e.schluessel]])
            roh[k] += 1
            je_oo[e.strategie] += 1
            tage[k].append(e.zeit.date())

    anzahl = Counter(e.strategie for e in oo_e)
    zuordnungen = []
    for k in sorted(set(vorschlag) | set(entscheidungen),
                    key=lambda k: (k[0], -roh[k], k[1])):
        n = roh[k]
        anteil = ((Decimal(n) / je_oo[k[0]]).quantize(ANTEIL, ROUND_HALF_UP)
                  if je_oo[k[0]] else Decimal("0"))
        zuordnungen.append(ZuordnungZeile(
            k[0], k[1], "manuell" if k in entscheidungen else "heuristik",
            entscheidungen.get(k, "vorschlag"), n, anteil, anteil >= EINDEUTIG_AB,
            anzahl[k[0]], min(tage[k]) if n else None, max(tage[k]) if n else None))

    aktiv = [z for z in zuordnungen if z.status != "abgelehnt"]
    vergleich = [_vergleich(z.oo_strategie, z.oa_strategie, oo, live, paare)
                 for z in sorted(aktiv, key=lambda z: (z.oo_strategie, z.oa_strategie))]
    mit = {z.oo_strategie for z in aktiv}
    ohne = [(s, anzahl[s]) for s in sorted(anzahl) if s not in mit]
    return BacktestBericht(zuordnungen, vergleich, ohne)


def _live_laden(v) -> list[LiveZeile]:
    oa = {}
    for z in v.execute(select(optionapp_trades)).mappings():
        if z["status"] == "CANCELED":
            continue
        waehrung, profit = _oa_waehrung_und_profit(dict(z))
        offen = z["status"] == "RUNNING"
        oa[z["oa_trade"]] = (z["strategie"], None if offen or waehrung != "USD" else profit, offen)
    roh: dict[str, list] = defaultdict(list)
    for z in v.execute(
        select(executions.c.oa_trade, executions.c.handelszeit, executions.c.side,
               executions.c.menge, instruments.c.underlying, instruments.c.right,
               instruments.c.strike, instruments.c.expiry)
        .join(instruments, instruments.c.conid == executions.c.conid)
        .where(executions.c.oa_trade.is_not(None), executions.c.ereignistyp == "trade",
               instruments.c.asset_class.in_(("OPT", "FOP")))
        .order_by(executions.c.handelszeit)
    ).mappings():
        if z["oa_trade"] in oa:
            roh[z["oa_trade"]].append(z)
    ergebnis = []
    for nummer, zeilen in roh.items():
        beginn = zeilen[0]["handelszeit"]
        legs = tuple(
            Leg(int(abs(z["menge"])), "S" if z["side"] == "SELL" else "B", z["right"],
                Decimal(z["strike"]), z["expiry"])
            for z in zeilen if z["handelszeit"] - beginn <= EROEFFNUNG_FENSTER
        )
        strategie, profit, offen = oa[nummer]
        e = Eroeffnung(nummer, strategie, beginn, zeilen[0]["underlying"], legs)
        ergebnis.append(LiveZeile(e, kontrakte(legs), profit, offen))
    return ergebnis


def backtest_bericht(db_pfad: str | pathlib.Path) -> BacktestBericht:
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        oo = [
            OoZeile(Eroeffnung(str(z["id"]), z["strategie"], z["eroeffnet"], z["basiswert"],
                               tuple(legs_lesen(z["legs_roh"], z["eroeffnet"].date()))),
                    z["kontrakte"], z["pl"], z["offen"])
            for z in v.execute(select(oo_trades)).mappings()
        ]
        live = _live_laden(v)
        entscheidungen = {(z["oo_strategie"], z["oa_strategie"]): z["status"]
                          for z in v.execute(select(oo_zuordnung)).mappings()}
    return backtest_auswertung(oo, live, entscheidungen)
