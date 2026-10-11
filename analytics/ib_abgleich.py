"""Abgleich des realisierten Ergebnisses: Journal gegen IB (AP-08u2).

Zerlegt den Unterschied zwischen dem realisierten Ergebnis des Journals
(Equity, EUR) und IBs realisiertem Ergebnis (Σ ``fifoPnlRealized`` × Kurs je
Ausführung) in belegte Ursachen. Vergleichseinheit ist die **schließende
Ausführung**: das Journal liefert die Legs, die sie schließt, IB seinen Wert für
genau diese Zeile.

Identitäten (exakt, keine Schätzung):

- Je schließender Ausführung ``E`` mit IB-Kurs ``k(E)``:
  ``J_EUR(E) − IB(E)·k(E) = [J_EUR(E) − J_nat(E)·k(E)] + [J_nat(E) − IB(E)]·k(E)``
  — der erste Teil ist die **Währungsmethode** (Journal: jede Seite zum Kurs
  ihres Tages; IB: Ergebnis in Positionswährung zum Kurs der Schließung), der
  zweite die **Methode der Einstände** (IB bucht eine zugeteilte oder ausgeübte
  Option mit 0 und verschiebt die Prämie in den Einstand der Aktie).
- Der Methodenteil ist im Wesentlichen die Prämie, die noch im Einstand
  **gehaltener** Positionen steckt: Journal-Einstand der offenen Legs minus
  IBs ``costBasisMoney``, zum Kurs der Eröffnung (``praemien_im_einstand``).
- Die Equity zählt ein Leg erst, wenn seine Struktur geschlossen ist; IB zählt
  je Ausführung. Geschlossene Legs in offenen Strukturen sind der
  **Zeitpunkt**-Teil.
- ``nicht_zugeordnet`` ist, was danach übrig bleibt — es wird ausgewiesen,
  nicht verteilt.

Rein (``ib_abgleich``) und Hülle (``ib_abgleich_bericht``) wie die übrigen
Analytikmodule; alle Beträge ``Decimal``.
"""

import json
import pathlib
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select

from analytics.kennzahlen import _wirtschaftlich, bewerte_barausgleich
from journal.db import create_db_engine
from journal.schema import (
    executions,
    flex_ib_realized,
    flex_open_positions,
    instruments,
    legs,
    structures,
)

_NULL = Decimal("0")
_TOLERANZ = Decimal("0.02")  # „gleich" je Zeile in Positionswährung (Rundung)


@dataclass(frozen=True)
class IbAbgleich:
    journal_legs_eur: Decimal            # Σ geschlossene Legs (Kontosicht), EUR
    ib_realisiert_eur: Decimal           # Σ IB fifoPnlRealized × Kurs
    waehrungsmethode: Decimal
    methode_einstand: Decimal            # [J_nat − IB]·k über alle Zeilen
    praemien_im_einstand: Decimal        # gehaltene Positionen, Kurs der Eröffnung
    praemien_im_einstand_heute: Decimal  # dieselben, zum Kurs des Bestands
    zeitpunkt_offene_strukturen: Decimal
    anzahl_legs_offene_strukturen: int
    zeilen_gleich: int
    zeilen_abweichend: int


def _d(wert) -> Decimal | None:
    if wert is None:
        return None
    return wert if isinstance(wert, Decimal) else Decimal(str(wert))


def ib_abgleich(
    leg_zeilen: list[dict],
    offene_strukturen: set[int],
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    ib_zeilen: dict[str, tuple[Decimal, Decimal | None]],
    bestand_zeilen: list[dict],
) -> IbAbgleich:
    """Rein. ``leg_zeilen``: Legs der Kontosicht (``structure_id``, ``conid``,
    ``open_exec_id``, ``close_exec_id``, ``menge``, ``brutto_pnl``,
    ``kommission_gesamt``, ``open_faktor``, ``close_faktor``).
    ``ib_zeilen``: exec_id → (fifoPnlRealized, Kurs). ``bestand_zeilen``: Bestand
    laut IB je conid (``conid``, ``kosten``: costBasisMoney, ``kurs``)."""
    ausfuehrungs_zeilen = bewerte_barausgleich(ausfuehrungs_zeilen, instrumenten_zeilen)
    exec_je_id = {a["exec_id"]: a for a in ausfuehrungs_zeilen}
    mult_je_conid = {i["conid"]: _d(i["multiplikator"]) for i in instrumenten_zeilen}

    j_eur: dict[str, Decimal] = defaultdict(lambda: _NULL)
    j_nat: dict[str, Decimal] = defaultdict(lambda: _NULL)
    zeitpunkt = _NULL
    anzahl_zeitpunkt = 0
    offen_je_conid: dict[int, list[dict]] = defaultdict(list)
    for leg in leg_zeilen:
        if leg["close_exec_id"] is None:
            offen_je_conid[leg["conid"]].append(leg)
            continue
        wert = _wirtschaftlich([leg], exec_je_id, mult_je_conid) or _NULL
        j_eur[leg["close_exec_id"]] += wert
        j_nat[leg["close_exec_id"]] += (_d(leg["brutto_pnl"]) or _NULL) + (
            _d(leg["kommission_gesamt"]) or _NULL
        )
        if leg["structure_id"] is not None and leg["structure_id"] in offene_strukturen:
            zeitpunkt += wert
            anzahl_zeitpunkt += 1

    zeilen = set(j_eur) | {e for e, (p, _) in ib_zeilen.items() if p != 0}
    waehrung = methode = _NULL
    gleich = abweichend = 0
    for exec_id in zeilen:
        ib_wert, ib_kurs = ib_zeilen.get(exec_id, (_NULL, None))
        a = exec_je_id.get(exec_id)
        kurs = ib_kurs if ib_kurs is not None else (
            a["buchungskurs"] if a is not None and a["buchungskurs"] is not None else Decimal(1)
        )
        waehrung += j_eur[exec_id] - j_nat[exec_id] * kurs
        methode += (j_nat[exec_id] - ib_wert) * kurs
        if abs(j_nat[exec_id] - ib_wert) <= _TOLERANZ:
            gleich += 1
        else:
            abweichend += 1

    praemien_hist = praemien_heute = _NULL
    for b in bestand_zeilen:
        offene = offen_je_conid.get(b["conid"], [])
        if not offene:
            continue
        mult = mult_je_conid.get(b["conid"], Decimal(1))
        einstand = gewicht = mengen = _NULL
        for leg in offene:
            a = exec_je_id[leg["open_exec_id"]]
            faktor = _d(leg.get("open_faktor")) or Decimal(1)
            menge = abs(_d(leg["menge"]))
            vorzeichen = 1 if a["side"] == "BUY" else -1
            einstand += vorzeichen * (a["preis"] / faktor) * menge * mult - (
                _d(leg["kommission_gesamt"]) or _NULL
            )
            gewicht += menge * (a["buchungskurs"] or Decimal(1))
            mengen += menge
        differenz = einstand - _d(b["kosten"])
        praemien_hist += differenz * (gewicht / mengen)
        praemien_heute += differenz * _d(b["kurs"])

    ib_summe = sum((p * (k if k is not None else Decimal(1)) for p, k in ib_zeilen.values()), _NULL)
    return IbAbgleich(
        journal_legs_eur=sum(j_eur.values(), _NULL),
        ib_realisiert_eur=ib_summe,
        waehrungsmethode=waehrung,
        methode_einstand=methode,
        praemien_im_einstand=praemien_hist,
        praemien_im_einstand_heute=praemien_heute,
        zeitpunkt_offene_strukturen=zeitpunkt,
        anzahl_legs_offene_strukturen=anzahl_zeitpunkt,
        zeilen_gleich=gleich,
        zeilen_abweichend=abweichend,
    )


def ib_abgleich_bericht(db_pfad: str | pathlib.Path) -> IbAbgleich:
    """Liest die Kontosicht, IBs Werte und den jüngsten Bestand; nur lesend."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        leg_zeilen = [dict(z) for z in v.execute(
            select(legs.c.structure_id, legs.c.conid, legs.c.open_exec_id, legs.c.close_exec_id,
                   legs.c.menge, legs.c.brutto_pnl, legs.c.kommission_gesamt,
                   legs.c.open_faktor, legs.c.close_faktor).where(legs.c.sicht == "konto")
        ).mappings()]
        offene = {z for (z,) in v.execute(
            select(structures.c.structure_id).where(
                structures.c.sicht == "konto", structures.c.geschlossen_am.is_(None))
        )}
        ausfuehrungen = [dict(z) for z in v.execute(
            select(executions.c.exec_id, executions.c.conid, executions.c.side, executions.c.menge,
                   executions.c.preis, executions.c.kommission, executions.c.buchungskurs,
                   executions.c.ereignistyp, executions.c.schlusskurs)
        ).mappings()]
        instrumente = [dict(z) for z in v.execute(
            select(instruments.c.conid, instruments.c.multiplikator, instruments.c.abwicklungsart)
        ).mappings()]
        ib = {z["exec_id"]: (z["fifo_pnl_realized"], z["fx_rate_to_base"]) for z in v.execute(
            select(flex_ib_realized.c.exec_id, flex_ib_realized.c.fifo_pnl_realized,
                   flex_ib_realized.c.fx_rate_to_base)
        ).mappings()}
        stichtag = v.execute(select(func.max(flex_open_positions.c.stichtag))).scalar()
        bestand = []
        if stichtag is not None:
            for z in v.execute(select(flex_open_positions.c.conid, flex_open_positions.c.roh_json)
                               .where(flex_open_positions.c.stichtag == stichtag)).mappings():
                roh = json.loads(z["roh_json"])
                if roh.get("levelOfDetail") not in (None, "SUMMARY"):
                    continue
                if roh.get("costBasisMoney") in (None, "") or roh.get("fxRateToBase") in (None, ""):
                    continue
                bestand.append(dict(conid=z["conid"], kosten=Decimal(roh["costBasisMoney"]),
                                    kurs=Decimal(roh["fxRateToBase"])))
    return ib_abgleich(leg_zeilen, offene, ausfuehrungen, instrumente, ib, bestand)
