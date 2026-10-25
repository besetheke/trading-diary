# ruff: noqa: E501
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
    zuordnen_eins_zu_eins,
)
from ingest.optionomega import legs_lesen
from journal.db import create_db_engine
from journal.schema import (
    executions,
    instruments,
    legs,
    oo_trades,
    oo_zuordnung,
    optionapp_trades,
)

# AP-12c: Schwellen der Ursachenbestimmung — Annahmen (OF-84), hier an einer
# Stelle änderbar.
TOLERANZ_JE_KONTRAKT = Decimal("10")          # USD: darunter „in Toleranz"
EINSTIEG_MINUTEN = 3                          # darüber: „Einstiegszeit"
AUSSTIEG_MINUTEN = 5                          # darüber: „Exit-Logik"
# Backtest-Schlussgründe, die einen Verfall bedeuten (alles andere ist ein
# vorzeitiger Ausstieg des Backtests).
OO_VERFALL = ("Expired", "Would've Exercised")

CENT = Decimal("0.01")
ANTEIL = Decimal("0.0001")
EROEFFNUNG_FENSTER = timedelta(minutes=2)


@dataclass(frozen=True)
class OoZeile:
    eroeffnung: Eroeffnung
    kontrakte: int
    pl: Decimal
    offen: bool
    geschlossen: datetime | None = None
    grund: str = ""


@dataclass(frozen=True)
class LiveZeile:
    eroeffnung: Eroeffnung
    kontrakte: int
    profit: Decimal | None  # USD; None = offen oder andere Währung
    offen: bool
    # AP-12c: Ausstieg laut IB — Zeit der letzten schließenden Ausführung und ob
    # er ein Verfall war; None, solange keine schließende Ausführung bekannt ist.
    ende: datetime | None = None
    ausgelaufen: bool | None = None


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


@dataclass
class UrsachenSumme:
    anzahl: int = 0
    summe: Decimal = Decimal("0")


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
    ursache: str | None = None
    zeitversatz_min: int | None = None
    kontrakt_effekt: Decimal | None = None
    # AP-17g (M07): ``ursache`` ist die ERSTE erkannte Abweichung in fester Reihenfolge, keine kausale Zerlegung.
    # ``abweichungen`` nennt ALLE beobachteten Unterschiede des Paars (kontrakte, einstiegszeit, strikeauswahl, exit_art,
    # exit_zeit); ``rest_unerklaert`` heißt: keine Abweichung gefunden, der Betrag bleibt ungeklärt (Slippage ist nur eine
    # Vermutung). Ausstiegsart je Seite getrennt; der Partner stammt aus der Zeitfenster-Paarung.
    abweichungen: tuple = ()
    rest_unerklaert: bool = False
    ausstieg_backtest: str | None = None
    ausstieg_live: str | None = None
    partner_herkunft: str | None = None


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
    # AP-12c: jedes Paar mit genau einer Ursache; Summe über die Ursachen =
    # differenz. Der Kontrakteffekt (Dollar insgesamt) steht daneben.
    ursachen: dict[str, UrsachenSumme] = field(default_factory=dict)
    kontrakt_effekt: Decimal = Decimal("0")
    # M07: Paare mit mindestens zwei beobachteten Abweichungen (die „erste“ Ursache erklärt dann nicht alles)
    mehrfach_abweichend: int = 0
    details: list[VergleichDetail] = field(default_factory=list)


@dataclass(frozen=True)
class BacktestBericht:
    zuordnungen: list[ZuordnungZeile]
    vergleich: list[VergleichZeile]
    ohne_zuordnung: list[tuple[str, int]]


def _je_kontrakt(betrag: Decimal, kontrakte: int) -> Decimal:
    return (betrag / kontrakte).quantize(CENT, ROUND_HALF_UP)


def _strikes(legs) -> list[tuple]:
    return sorted((leg.right, leg.seite, leg.strike) for leg in legs)


def _ursache(o: OoZeile, x: LiveZeile, bt: Decimal, lv: Decimal) -> tuple[str, int]:
    """Genau eine Ursache je Paar, in fester Prüfreihenfolge (AP-12c):
    Kontraktzahl, Toleranz, Einstiegszeit, Strikeauswahl, Exit-Logik, Slippage.
    Dazu der Zeitversatz des Einstiegs in Minuten (Bot − Backtest)."""
    versatz = round((x.eroeffnung.zeit - o.eroeffnung.zeit).total_seconds() / 60)
    if o.kontrakte != x.kontrakte:
        return "kontrakte", versatz
    if abs(lv - bt) <= TOLERANZ_JE_KONTRAKT:
        return "toleranz", versatz
    if abs(versatz) > EINSTIEG_MINUTEN:
        return "einstiegszeit", versatz
    if _strikes(o.eroeffnung.legs) != _strikes(x.eroeffnung.legs):
        return "strikeauswahl", versatz
    if x.ausgelaufen is not None and o.geschlossen is not None:
        oo_verfall = o.grund in OO_VERFALL
        if oo_verfall != x.ausgelaufen:
            return "exit", versatz
        if not oo_verfall and x.ende is not None and abs(
                (x.ende - o.geschlossen).total_seconds()) > AUSSTIEG_MINUTEN * 60:
            return "exit", versatz
    return "slippage", versatz


def _abweichungen(o: OoZeile, x: LiveZeile) -> tuple[str, ...]:
    """Alle beobachteten Unterschiede eines Paars (AP-17g, M07), unabhängig von der Höhe des Betrags und der Reihenfolge der
    ersten Ursache: Kontraktzahl, Einstiegszeit, Strikes, Art und Zeit des Ausstiegs."""
    aus = []
    versatz = round((x.eroeffnung.zeit - o.eroeffnung.zeit).total_seconds() / 60)
    if o.kontrakte != x.kontrakte:
        aus.append("kontrakte")
    if abs(versatz) > EINSTIEG_MINUTEN:
        aus.append("einstiegszeit")
    if _strikes(o.eroeffnung.legs) != _strikes(x.eroeffnung.legs):
        aus.append("strikeauswahl")
    if x.ausgelaufen is not None and o.geschlossen is not None:
        oo_verfall = o.grund in OO_VERFALL
        if oo_verfall != x.ausgelaufen:
            aus.append("exit_art")
        elif not oo_verfall and x.ende is not None and abs((x.ende - o.geschlossen).total_seconds()) > AUSSTIEG_MINUTEN * 60:
            aus.append("exit_zeit")
    return tuple(aus)


def _ausstieg_backtest(o: OoZeile) -> str | None:
    if o.geschlossen is None:
        return None
    return "verfall" if o.grund in OO_VERFALL else "vorzeitig"


def _ausstieg_live(x: LiveZeile) -> str | None:
    if x.ausgelaufen is None:
        return None
    return "verfall" if x.ausgelaufen else "rueckkauf"


def _lokale_paare(oo_s: str, oa_s: str, oo: list[OoZeile], live: list[LiveZeile]
                  ) -> dict[str, str]:
    """Paarung eines Backtests mit EINEM Bot (AP-12b): Trades eines anderen
    Bots nehmen ihm keinen Partner weg — derselbe Backtest kann gegen
    mehrere Bots laufen (SPY: IF7 und XSP: IF7)."""
    return zuordnen_eins_zu_eins(
        [z.eroeffnung for z in oo if z.eroeffnung.strategie == oo_s],
        [z.eroeffnung for z in live if z.eroeffnung.strategie == oa_s],
    )


def _vergleich(oo_s: str, oa_s: str, oo: list[OoZeile], live: list[LiveZeile],
               paare: dict[str, str], gepaart: set[str]) -> VergleichZeile:
    """``paare``: die Paarung dieses Backtests mit diesem Bot; ``gepaart``:
    alle Live-Trades dieses Bots, die irgendein zugeordneter Backtest erklärt."""
    eigene_oo = [z for z in oo if z.eroeffnung.strategie == oo_s]
    eigene_live = [z for z in live if z.eroeffnung.strategie == oa_s]
    live_je = {z.eroeffnung.schluessel: z for z in live}
    zeile = VergleichZeile(oo_s, oa_s)
    live_tage = [z.eroeffnung.zeit.date() for z in eigene_live]
    oo_tage = [z.eroeffnung.zeit.date() for z in eigene_oo]
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
            ursache, versatz = _ursache(o, partner, bt, lv)
            effekt = (partner.kontrakte - o.kontrakte) * lv if ursache == "kontrakte" else None
            u = zeile.ursachen.setdefault(ursache, UrsachenSumme())
            u.anzahl += 1
            u.summe += lv - bt
            if effekt is not None:
                zeile.kontrakt_effekt += effekt
            abweichungen = _abweichungen(o, partner)
            if len(abweichungen) >= 2:
                zeile.mehrfach_abweichend += 1
            zeile.details.append(VergleichDetail(
                "paar", e.zeit, partner.eroeffnung.zeit, partner.eroeffnung.schluessel,
                o.kontrakte, partner.kontrakte, bt, lv, lv - bt, ursache, versatz, effekt,
                abweichungen=abweichungen, rest_unerklaert=(ursache == "slippage" and not abweichungen),
                ausstieg_backtest=_ausstieg_backtest(o), ausstieg_live=_ausstieg_live(partner),
                partner_herkunft="zeitfenster"))
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
    oo_je_id = {z.eroeffnung.schluessel: z.eroeffnung for z in oo}
    lokal_alle: dict[tuple[str, str], dict[str, str]] = {}
    for k in set(vorschlag) | set(entscheidungen):
        lokal_alle[k] = _lokale_paare(k[0], k[1], oo, live)
    for k in sorted(set(vorschlag) | set(entscheidungen),
                    key=lambda k: (k[0], -len(lokal_alle[k]), k[1])):
        # Treffer: Paarung dieses Backtests mit genau diesem Bot (AP-12b) —
        # dieselbe Zahl wie im Vergleich. Der Anteil bleibt der an allen
        # Treffern des Vorschlags (nächster Bot gewinnt).
        eigene_tage = [oo_je_id[s].zeit.date() for s in lokal_alle[k]]
        n = len(eigene_tage)
        anteil = ((Decimal(n) / je_oo[k[0]]).quantize(ANTEIL, ROUND_HALF_UP)
                  if je_oo[k[0]] else Decimal("0"))
        zuordnungen.append(ZuordnungZeile(
            k[0], k[1], "manuell" if k in entscheidungen else "heuristik",
            entscheidungen.get(k, "vorschlag"), n, anteil, anteil >= EINDEUTIG_AB,
            anzahl[k[0]], min(eigene_tage) if n else None,
            max(eigene_tage) if n else None))

    aktiv = [z for z in zuordnungen if z.status != "abgelehnt"]
    lokal = {(z.oo_strategie, z.oa_strategie):
             _lokale_paare(z.oo_strategie, z.oa_strategie, oo, live) for z in aktiv}
    erklaert: dict[str, set[str]] = defaultdict(set)
    for (_, oa_s), p in lokal.items():
        erklaert[oa_s] |= set(p.values())
    vergleich = [
        _vergleich(z.oo_strategie, z.oa_strategie, oo, live,
                   lokal[(z.oo_strategie, z.oa_strategie)], erklaert[z.oa_strategie])
        for z in sorted(aktiv, key=lambda z: (z.oo_strategie, z.oa_strategie))
    ]
    mit = {z.oo_strategie for z in aktiv}
    ohne = [(s, anzahl[s]) for s in sorted(anzahl) if s not in mit]
    return BacktestBericht(zuordnungen, vergleich, ohne)


CSV_KOPF = (
    "backtest;bot;art;eroeffnung_backtest;eroeffnung_bot;oa_trade;versatz_min;"
    "kontrakte_backtest;kontrakte_bot;pl_backtest;pl_bot;differenz;ursache;kontrakt_effekt"
)


def als_csv(bericht: BacktestBericht) -> str:
    """Alle Paare und Einzelfälle der nicht abgelehnten Zuordnungen als CSV
    (Semikolon, Beträge je Kontrakt in USD mit zwei Nachkommastellen, leer =
    kein Wert) — für den Monatsvergleich in Excel."""
    def geld(w: Decimal | None) -> str:
        return "" if w is None else f"{w:.2f}"

    def zeit(z: datetime | None) -> str:
        return "" if z is None else z.strftime("%Y-%m-%d %H:%M:%S")

    def zahl(n) -> str:
        return "" if n is None else str(n)

    zeilen = [CSV_KOPF]
    for v in bericht.vergleich:
        for d in v.details:
            zeilen.append(";".join([
                v.oo_strategie, v.oa_strategie, d.art, zeit(d.zeit_backtest), zeit(d.zeit_live),
                d.oa_trade or "", zahl(d.zeitversatz_min), zahl(d.kontrakte_backtest),
                zahl(d.kontrakte_live), geld(d.pl_backtest), geld(d.pl_live),
                geld(d.differenz), d.ursache or "", geld(d.kontrakt_effekt),
            ]))
    return "\n".join(zeilen)


def _live_laden(v) -> list[LiveZeile]:
    oa = {}
    for z in v.execute(select(optionapp_trades)).mappings():
        if z["status"] == "CANCELED":
            continue
        waehrung, profit = _oa_waehrung_und_profit(dict(z))
        offen = z["status"] == "RUNNING"
        oa[z["oa_trade"]] = (z["strategie"], None if offen or waehrung != "USD" else profit, offen)
    # Eröffnungsfingerabdruck und Endereignisse kommen aus getrennten Datenmengen (AP-17f, R07):
    # eröffnet wird per Trade; geendet wird laut gematchter Leg (close_exec_id) oder laut Ereignis
    # mit derselben OA-Nummer (Verfall, Zuteilung, Ausübung tragen oft keine oder eine andere).
    alle = {}
    for z in v.execute(
        select(executions.c.exec_id, executions.c.oa_trade, executions.c.handelszeit,
               executions.c.side, executions.c.menge, instruments.c.underlying,
               instruments.c.right, instruments.c.strike, instruments.c.expiry,
               executions.c.ereignistyp)
        .join(instruments, instruments.c.conid == executions.c.conid)
        .where(instruments.c.asset_class.in_(("OPT", "FOP")))
    ).mappings():
        alle[z["exec_id"]] = z
    schluss_je_eroeffnung: dict[str, set] = defaultdict(set)
    gematcht = select(legs.c.open_exec_id, legs.c.close_exec_id).where(
        legs.c.close_exec_id.is_not(None), legs.c.sicht == "konto")
    for z in v.execute(gematcht).mappings():
        schluss_je_eroeffnung[z["open_exec_id"]].add(z["close_exec_id"])
    schluss_ids = {c for ids in schluss_je_eroeffnung.values() for c in ids}
    roh: dict[str, list] = defaultdict(list)
    for exec_id, z in sorted(alle.items(), key=lambda p: (p[1]["handelszeit"], p[0])):
        if (z["oa_trade"] in oa and z["ereignistyp"] == "trade" and exec_id not in schluss_ids):
            roh[z["oa_trade"]].append((exec_id, z))
    ergebnis = []
    for nummer, paare in roh.items():
        zeilen = [z for _, z in paare]
        beginn = zeilen[0]["handelszeit"]
        eroeffnend = [(i, z) for i, z in paare if z["handelszeit"] - beginn <= EROEFFNUNG_FENSTER]
        legs_ = tuple(
            Leg(int(abs(z["menge"])), "S" if z["side"] == "SELL" else "B", z["right"],
                Decimal(z["strike"]), z["expiry"])
            for _, z in eroeffnend
        )
        eigene = {i for i, _ in eroeffnend}
        schluss = {c for i in eigene for c in schluss_je_eroeffnung.get(i, ())}
        schliessend = [alle[c] for c in schluss if c in alle]
        schliessend += [z for i, z in alle.items()
                        if z["oa_trade"] == nummer and i not in eigene and i not in schluss
                        and i not in schluss_ids and z["handelszeit"] - beginn > EROEFFNUNG_FENSTER]
        strategie, profit, offen = oa[nummer]
        e = Eroeffnung(nummer, strategie, beginn, zeilen[0]["underlying"], legs_)
        ergebnis.append(LiveZeile(
            e, kontrakte(legs_), profit, offen,
            ende=max((z["handelszeit"] for z in schliessend), default=None),
            ausgelaufen=(all(z["ereignistyp"] != "trade" for z in schliessend)
                         if schliessend else None),
        ))
    return ergebnis


def backtest_bericht(
    db_pfad: str | pathlib.Path, *, von: date | None = None, bis: date | None = None
) -> BacktestBericht:
    """Lesende Hülle. ``von``/``bis`` begrenzen beide Seiten auf den Tag der
    Eröffnung — so lässt sich Monat für Monat vergleichen (AP-12c)."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        oo = [
            OoZeile(Eroeffnung(str(z["id"]), z["strategie"], z["eroeffnet"], z["basiswert"],
                               tuple(legs_lesen(z["legs_roh"], z["eroeffnet"].date()))),
                    z["kontrakte"], z["pl"], z["offen"], z["geschlossen"], z["grund"])
            for z in v.execute(select(oo_trades)).mappings()
        ]
        live = _live_laden(v)
        entscheidungen = {(z["oo_strategie"], z["oa_strategie"]): z["status"]
                          for z in v.execute(select(oo_zuordnung)).mappings()}
    def im_zeitraum(tag: date) -> bool:
        return (von is None or tag >= von) and (bis is None or tag <= bis)

    oo = [z for z in oo if im_zeitraum(z.eroeffnung.zeit.date())]
    live = [z for z in live if im_zeitraum(z.eroeffnung.zeit.date())]
    return backtest_auswertung(oo, live, entscheidungen)
