"""Abgleich OA ↔ IB (AP-13ab): stimmt das Ergebnis, das OptionApp je Trade
ausweist, mit dem überein, was IB tatsächlich gebucht hat?

IB-Ergebnis eines OA-Trades: Σ (brutto + Kommission) aller Legs, deren
eröffnende Ausführung die OA-Nummer trägt (Orderreferenz), plus die Legs der
daraus zugeteilten Aktien (``assignment_links``, AP-04z) — die Zuteilung gehört
zum Trade. Verglichen wird in der Währung des Trades mit OAs Gewinn in
Originalwährung.

Einordnung je Trade (erste zutreffende): ``offen`` (ein Leg offen oder OA
RUNNING), ``fehlt`` (keine Ausführung bei IB), ``waehrung`` (OA-Währung ≠
IB-Währung — OA hat umgerechnet, kein Vergleich), ``gleich`` (|Δ| ≤ 0,05),
``verrechnet`` (der Trade teilt Kontrakte mit anderen OA-Trades, IB hat sie im
Konto gegeneinander geschlossen — die Gruppe stimmt, |Δ| ≤ 0,05 je Trade),
``zuteilung`` (Aktie aus Zuteilung im Ergebnis), ``schaetzung`` (OA-Status
„estimated"), ``gering`` (|Δ| ≤ 1,00, meist OAs geschätzte Kommission),
``sonst``. Alle außer ``offen``/``fehlt``/``waehrung`` gehen in die Summen ein;
„abweichend" sind ``zuteilung``/``schaetzung``/``sonst``.

Rein (Regel 6); ``oa_vergleich_bericht`` ist die lesende Hülle.
"""

import json
import pathlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from journal.db import create_db_engine
from journal.schema import assignment_links, executions, legs, optionapp_trades

_NULL = Decimal(0)
TOLERANZ = Decimal("0.05")
GERING = Decimal("1.00")
VERGLEICHBAR = ("gleich", "verrechnet", "gering", "zuteilung", "schaetzung", "sonst")
ABWEICHEND = ("zuteilung", "schaetzung", "sonst")


@dataclass(frozen=True)
class TradeVergleich:
    oa_trade: str
    strategie: str | None
    status: str
    schluss_zeit: datetime | None
    waehrung: str
    oa_profit: Decimal
    ib_netto: Decimal | None
    differenz: Decimal | None
    grund: str


@dataclass(frozen=True)
class StrategieVergleich:
    strategie: str | None
    waehrung: str
    anzahl: int
    gleich: int
    verrechnet: int
    gering: int
    abweichend: int
    offen: int
    fehlt: int
    waehrung_unklar: int
    summe_oa: Decimal
    summe_ib: Decimal
    differenz: Decimal


@dataclass(frozen=True)
class OaVergleich:
    trades: list[TradeVergleich]
    strategien: list[StrategieVergleich]


def oa_vergleich(
    oa_trades: list[dict],
    leg_zeilen: list[dict],
    exec_je_id: dict[str, dict],
    zuteilungs_paare: list[tuple[str, str]],
) -> OaVergleich:
    """``oa_trades``: oa_trade, strategie, status, profit, waehrung,
    schluss_zeit. ``exec_je_id``: exec_id → oa_trade, waehrung."""
    legs_je_trade: dict[str, list[dict]] = {}
    legs_je_oeffnung: dict[str, list[dict]] = {}
    for leg in leg_zeilen:
        legs_je_oeffnung.setdefault(leg["open_exec_id"], []).append(leg)
        nr = exec_je_id.get(leg["open_exec_id"], {}).get("oa_trade")
        if nr:
            legs_je_trade.setdefault(nr, []).append(leg)
    aktie_je_option: dict[str, list[str]] = {}
    for option_exec, aktie_exec in zuteilungs_paare:
        aktie_je_option.setdefault(option_exec, []).append(aktie_exec)

    trades: list[TradeVergleich] = []
    for t in oa_trades:
        eigene = legs_je_trade.get(t["oa_trade"], [])
        aktien = [
            leg
            for eigen in eigene
            for aktie_exec in aktie_je_option.get(eigen["close_exec_id"] or "", [])
            for leg in legs_je_oeffnung.get(aktie_exec, [])
        ]
        alle = eigene + aktien
        ib_waehrung = (
            exec_je_id.get(eigene[0]["open_exec_id"], {}).get("waehrung") if eigene else None
        )
        ib_netto = differenz = None
        if t["status"] == "RUNNING" or any(leg["close_exec_id"] is None for leg in alle):
            grund = "offen"
        elif not eigene:
            grund = "fehlt"
        elif ib_waehrung != t["waehrung"]:
            grund = "waehrung"
        else:
            ib_netto = sum(
                (leg["brutto_pnl"] + (leg["kommission_gesamt"] or _NULL) for leg in alle), _NULL
            )
            differenz = ib_netto - t["profit"]
            if abs(differenz) <= TOLERANZ:
                grund = "gleich"
            elif aktien:
                grund = "zuteilung"
            elif "estimated" in t["status"]:
                grund = "schaetzung"
            else:
                grund = "sonst"
        trades.append(TradeVergleich(
            oa_trade=t["oa_trade"], strategie=t["strategie"], status=t["status"],
            # Währung des Trades: die der IB-Buchung, sonst die von OA.
            schluss_zeit=t["schluss_zeit"], waehrung=ib_waehrung or t["waehrung"],
            oa_profit=t["profit"],
            ib_netto=ib_netto, differenz=differenz, grund=grund,
        ))

    trades = _verrechnung(trades, leg_zeilen, exec_je_id)

    je: dict[tuple[str | None, str], list[TradeVergleich]] = {}
    for tv in trades:
        je.setdefault((tv.strategie, tv.waehrung), []).append(tv)
    strategien = []
    for (strategie, waehrung), liste in je.items():
        vergleichbar = [tv for tv in liste if tv.grund in VERGLEICHBAR]
        summe_oa = sum((tv.oa_profit for tv in vergleichbar), _NULL)
        summe_ib = sum((tv.ib_netto for tv in vergleichbar), _NULL)
        strategien.append(StrategieVergleich(
            strategie=strategie, waehrung=waehrung, anzahl=len(liste),
            gleich=sum(1 for tv in liste if tv.grund == "gleich"),
            verrechnet=sum(1 for tv in liste if tv.grund == "verrechnet"),
            gering=sum(1 for tv in liste if tv.grund == "gering"),
            abweichend=sum(1 for tv in liste if tv.grund in ABWEICHEND),
            offen=sum(1 for tv in liste if tv.grund == "offen"),
            fehlt=sum(1 for tv in liste if tv.grund == "fehlt"),
            waehrung_unklar=sum(1 for tv in liste if tv.grund == "waehrung"),
            summe_oa=summe_oa, summe_ib=summe_ib, differenz=summe_ib - summe_oa,
        ))
    strategien.sort(key=lambda s: (-abs(s.differenz), s.strategie or "", s.waehrung))
    return OaVergleich(trades=trades, strategien=strategien)


def _verrechnung(
    trades: list[TradeVergleich], leg_zeilen: list[dict], exec_je_id: dict[str, dict]
) -> list[TradeVergleich]:
    """Gruppen verrechneter Trades (Leg eröffnet von Trade X, geschlossen von
    einer Ausführung des Trades Y) gemeinsam prüfen; danach ``gering``."""
    eltern: dict[str, str] = {}

    def wurzel(x: str) -> str:
        while eltern.get(x, x) != x:
            x = eltern[x]
        return x

    for leg in leg_zeilen:
        a = exec_je_id.get(leg["open_exec_id"], {}).get("oa_trade")
        b = exec_je_id.get(leg["close_exec_id"] or "", {}).get("oa_trade")
        if a and b and a != b:
            eltern[wurzel(a)] = wurzel(b)

    gruppen: dict[str, list[TradeVergleich]] = {}
    for tv in trades:
        gruppen.setdefault(wurzel(tv.oa_trade), []).append(tv)
    verrechnet: set[str] = set()
    for mitglieder in gruppen.values():
        if len(mitglieder) < 2 or any(m.differenz is None for m in mitglieder):
            continue
        if abs(sum((m.differenz for m in mitglieder), _NULL)) <= TOLERANZ * len(mitglieder):
            verrechnet.update(m.oa_trade for m in mitglieder if m.grund != "gleich")

    ergebnis = []
    for tv in trades:
        grund = tv.grund
        if tv.oa_trade in verrechnet:
            grund = "verrechnet"
        elif grund == "sonst" and abs(tv.differenz) <= GERING:
            grund = "gering"
        if grund != tv.grund:
            tv = TradeVergleich(**{**tv.__dict__, "grund": grund})
        ergebnis.append(tv)
    return ergebnis


def _oa_waehrung_und_profit(zeile: dict) -> tuple[str, Decimal]:
    """Gewinn in Originalwährung, wenn der Export ihn trägt (neue OA-Version,
    AP-13r3); sonst OAs USD-Wert („$")."""
    try:
        roh = json.loads(zeile["roh_json"])
    except ValueError:
        roh = None
    if isinstance(roh, dict) and "zeile" in roh and isinstance(roh["zeile"], dict):
        roh = roh["zeile"]
    orig = roh.get("Profit (orig.)") if isinstance(roh, dict) else None
    if isinstance(roh, dict) and roh.get("Currency") and orig not in (None, ""):
        return roh["Currency"], Decimal(roh["Profit (orig.)"])
    return ("USD" if zeile["profit_waehrung"] in ("$", None) else zeile["profit_waehrung"],
            zeile["profit"])


def oa_vergleich_bericht(
    db_pfad: str | pathlib.Path, *, von: date | None = None, bis: date | None = None
) -> OaVergleich:
    """Lesende Hülle (Kontosicht); ``von``/``bis`` am OA-Schlusstag, offene
    Trades zählen immer. CANCELED-Trades (nie eröffnet) bleiben außen vor."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        oa = []
        for z in v.execute(select(optionapp_trades)).mappings():
            if z["status"] == "CANCELED":
                continue
            ende = z["schluss_zeit"]
            if ende is not None and (
                (von is not None and ende.date() < von) or (bis is not None and ende.date() > bis)
            ):
                continue
            waehrung, profit = _oa_waehrung_und_profit(dict(z))
            oa.append(dict(oa_trade=z["oa_trade"], strategie=z["strategie"],
                           status=z["status"], profit=profit, waehrung=waehrung,
                           schluss_zeit=ende))
        exec_je_id = {
            z["exec_id"]: dict(oa_trade=z["oa_trade"], waehrung=z["waehrung"])
            for z in v.execute(select(executions.c.exec_id, executions.c.oa_trade,
                                      executions.c.waehrung)).mappings()
        }
        leg_zeilen = [dict(z) for z in v.execute(select(
            legs.c.open_exec_id, legs.c.close_exec_id, legs.c.brutto_pnl,
            legs.c.kommission_gesamt,
        ).where(legs.c.sicht == "konto")).mappings()]
        paare = [(a, b) for a, b in v.execute(select(
            assignment_links.c.option_exec_id, assignment_links.c.stock_exec_id))]
    return oa_vergleich(oa, leg_zeilen, exec_je_id, paare)
