"""Strategie-Scorecard (AP-06sc): je OA-Strategie, welche Positionen verdienen.

Grundlage sind die Positionen der Kontosicht (Ketten) mit ihrem Ergebnis netto
in EUR, wirtschaftlich gerechnet — dieselbe Zahl wie in Equity und
Positionsliste (``analytics.kennzahlen``). Seit AP-04z gehören Zuteilungen
und Covered Calls zur Position; ihr Ergebnis steht also bei der Strategie, die
sie verursacht hat.

Je Strategie (``None`` = ohne Strategie), nur geschlossene Positionen:
Anzahl, Gewinner, Verlierer, Trefferquote, Summe, Ø je Position, Ø Gewinn,
Ø Verlust, Profit-Faktor (Σ Gewinne ÷ |Σ Verluste|; ohne Verluste ``None``),
größter Gewinn und Verlust, maximaler Drawdown der aufsummierten Kurve in der
Reihenfolge der Schließung (Start 0), Zuteilungsquote und Ø Haltedauer in
Tagen. Offene Positionen zählen nur in ``offen``; ohne Wechselkurs nur in
``kurs_fehlt`` (nie still 0).

Rundung (benannt, Regel 5): Quoten und Profit-Faktor vier Stellen,
Haltedauer eine Stelle, beides HALF_UP. Beträge bleiben ungerundet.

Rein (Regel 6); ``strategie_bericht`` ist die lesende Hülle.
"""

import pathlib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from analytics.equity import equity_auswertung
from analytics.kennzahlen import kennzahlen_auswertung
from journal.db import create_db_engine
from journal.schema import (
    chain_links,
    chains,
    executions,
    instruments,
    legs,
    structures,
)

_NULL = Decimal(0)
_VIER = Decimal("0.0001")
_EINE = Decimal("0.1")


@dataclass(frozen=True)
class StrategieZeile:
    strategie: str | None
    anzahl: int
    offen: int
    gewinner: int
    verlierer: int
    kurs_fehlt: int
    trefferquote: Decimal | None
    summe_eur: Decimal
    durchschnitt_eur: Decimal | None
    durchschnitt_gewinn_eur: Decimal | None
    durchschnitt_verlust_eur: Decimal | None
    profit_faktor: Decimal | None
    groesster_gewinn_eur: Decimal | None
    groesster_verlust_eur: Decimal | None
    max_drawdown_eur: Decimal
    zuteilungsquote: Decimal | None
    haltedauer_tage: Decimal | None
    erste_schliessung: datetime | None
    letzte_schliessung: datetime | None


@dataclass(frozen=True)
class StrategieBericht:
    """Scorecard samt Überleitung zum realisierten Gesamtergebnis (Equity):
    realisiert_gesamt = Σ Strategien (geschlossene Positionen)
                        + ohne_position (lose Legs, AP-06i)
                        + abgrenzung (Rest: realisierte Teile offener
                          Positionen, z. B. Roll-Schritte, und — mit Zeitraum —
                          Positionen über die Zeitraumgrenze)."""

    zeilen: list[StrategieZeile]
    summe_strategien_eur: Decimal
    realisiert_gesamt_eur: Decimal
    ohne_position_eur: Decimal
    abgrenzung_eur: Decimal


def _quote(z: Decimal | int, n: Decimal | int) -> Decimal | None:
    if not n:
        return None
    return (Decimal(z) / Decimal(n)).quantize(_VIER, rounding=ROUND_HALF_UP)


def strategie_auswertung(positionen: list[dict]) -> list[StrategieZeile]:
    """``positionen``: ``chain_id``, ``strategie``, ``eroeffnet_am``,
    ``beendet_am`` (None = offen), ``netto_eur`` (None = kein Kurs oder offen),
    ``zuteilung`` (bool). Ergebnis nach Summe absteigend, bei Gleichstand nach
    Name."""
    je: dict[str | None, list[dict]] = {}
    for p in positionen:
        je.setdefault(p["strategie"], []).append(p)

    zeilen = []
    for strategie, liste in je.items():
        offen = sum(1 for p in liste if p["beendet_am"] is None)
        geschlossen = [p for p in liste if p["beendet_am"] is not None]
        kurs_fehlt = sum(1 for p in geschlossen if p["netto_eur"] is None)
        gezaehlt = sorted(
            (p for p in geschlossen if p["netto_eur"] is not None),
            key=lambda p: (p["beendet_am"], p["chain_id"]),
        )
        werte = [p["netto_eur"] for p in gezaehlt]
        gewinne = [w for w in werte if w > 0]
        verluste = [w for w in werte if w < 0]
        summe = sum(werte, _NULL)
        summe_verluste = sum(verluste, _NULL)

        kurve = hoch = _NULL
        drawdown = _NULL
        for w in werte:
            kurve += w
            hoch = max(hoch, kurve)
            drawdown = min(drawdown, kurve - hoch)

        tage = [
            Decimal((p["beendet_am"] - p["eroeffnet_am"]).total_seconds()) / Decimal(86400)
            for p in gezaehlt
        ]
        anzahl = len(werte)
        zeilen.append(
            StrategieZeile(
                strategie=strategie,
                anzahl=anzahl,
                offen=offen,
                gewinner=len(gewinne),
                verlierer=len(verluste),
                kurs_fehlt=kurs_fehlt,
                trefferquote=_quote(len(gewinne), anzahl),
                summe_eur=summe,
                durchschnitt_eur=summe / anzahl if anzahl else None,
                durchschnitt_gewinn_eur=sum(gewinne, _NULL) / len(gewinne) if gewinne else None,
                durchschnitt_verlust_eur=summe_verluste / len(verluste) if verluste else None,
                profit_faktor=_quote(sum(gewinne, _NULL), -summe_verluste)
                if verluste
                else None,
                groesster_gewinn_eur=max(werte) if werte else None,
                groesster_verlust_eur=min(werte) if werte else None,
                max_drawdown_eur=drawdown,
                zuteilungsquote=_quote(sum(1 for p in gezaehlt if p["zuteilung"]), anzahl),
                haltedauer_tage=(sum(tage, _NULL) / len(tage)).quantize(
                    _EINE, rounding=ROUND_HALF_UP
                )
                if tage
                else None,
                erste_schliessung=gezaehlt[0]["beendet_am"] if gezaehlt else None,
                letzte_schliessung=gezaehlt[-1]["beendet_am"] if gezaehlt else None,
            )
        )
    zeilen.sort(key=lambda z: (-z.summe_eur, z.strategie or ""))
    return zeilen


def strategie_bericht(
    db_pfad: str | pathlib.Path, *, von: date | None = None, bis: date | None = None
) -> StrategieBericht:
    """Lesende Hülle: Positionen der Kontosicht; ``von``/``bis`` begrenzen auf
    Positionen, die im Zeitraum geschlossen wurden (offene zählen, wenn sie
    vor ``bis`` eröffnet wurden). Schreibt nichts."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        ketten_zeilen = [dict(z) for z in v.execute(select(
            chains.c.chain_id, chains.c.underlying, chains.c.asset_class,
            chains.c.anzahl_rolls, chains.c.beendet_am, chains.c.eroeffnet_am,
            chains.c.oa_strategie,
        ).where(chains.c.sicht == "konto")).mappings()]
        struktur_zeilen = [dict(z) for z in v.execute(select(
            structures.c.structure_id, structures.c.typ, structures.c.waehrung,
            structures.c.brutto_pnl, structures.c.kommission, structures.c.netto_pnl,
            structures.c.geschlossen_am,
        ).where(structures.c.sicht == "konto")).mappings()]
        glieder_zeilen = [dict(z) for z in v.execute(select(
            chain_links.c.chain_id, chain_links.c.structure_id, chain_links.c.sequenz,
            chain_links.c.verknuepfungstyp, chain_links.c.erkennung,
        ).where(chain_links.c.sicht == "konto")).mappings()]
        leg_zeilen = [dict(z) for z in v.execute(select(
            legs.c.structure_id, legs.c.conid, legs.c.open_exec_id, legs.c.close_exec_id,
            legs.c.menge, legs.c.open_faktor, legs.c.close_faktor, legs.c.brutto_pnl,
            legs.c.kommission_gesamt,
        ).where(legs.c.sicht == "konto")).mappings()]
        ausfuehrungs_zeilen = [dict(z) for z in v.execute(select(
            executions.c.exec_id, executions.c.conid, executions.c.side, executions.c.menge,
            executions.c.preis, executions.c.waehrung, executions.c.kommission,
            executions.c.kommission_waehrung, executions.c.buchungskurs,
            executions.c.handelszeit, executions.c.qualitaetsstufe,
            executions.c.ereignistyp, executions.c.schlusskurs,
        )).mappings()]
        instrumenten_zeilen = [dict(z) for z in v.execute(select(
            instruments.c.conid, instruments.c.multiplikator, instruments.c.abwicklungsart,
            instruments.c.underlying, instruments.c.asset_class, instruments.c.symbol,
        )).mappings()]

    grundlage = kennzahlen_auswertung(
        ketten_zeilen, struktur_zeilen, glieder_zeilen, leg_zeilen,
        ausfuehrungs_zeilen, instrumenten_zeilen, sicht="konto",
    )
    netto_je_kette = {k.chain_id: k.netto_eur_wirtschaftlich for k in grundlage.ketten}
    mit_zuteilung = {
        g["chain_id"] for g in glieder_zeilen if g["verknuepfungstyp"] == "zuteilung"
    }
    positionen = []
    for k in ketten_zeilen:
        ende = k["beendet_am"]
        if ende is not None:
            if von is not None and ende.date() < von:
                continue
            if bis is not None and ende.date() > bis:
                continue
        elif bis is not None and k["eroeffnet_am"].date() > bis:
            continue
        positionen.append(dict(
            chain_id=k["chain_id"], strategie=k["oa_strategie"],
            eroeffnet_am=k["eroeffnet_am"], beendet_am=ende,
            netto_eur=netto_je_kette.get(k["chain_id"]) if ende is not None else None,
            zuteilung=k["chain_id"] in mit_zuteilung,
        ))
    zeilen = strategie_auswertung(positionen)
    equity = equity_auswertung(
        ketten_zeilen, struktur_zeilen, glieder_zeilen, leg_zeilen,
        ausfuehrungs_zeilen, instrumenten_zeilen, sicht="konto", von=von, bis=bis,
    )
    gesamt = sum((tag.netto_eur for tag in equity.tage), _NULL)
    ohne_position = sum((m.lose_legs_eur for m in equity.monate), _NULL)
    summe = sum((z.summe_eur for z in zeilen), _NULL)
    return StrategieBericht(
        zeilen=zeilen,
        summe_strategien_eur=summe,
        realisiert_gesamt_eur=gesamt,
        ohne_position_eur=ohne_position,
        abgrenzung_eur=gesamt - ohne_position - summe,
    )
