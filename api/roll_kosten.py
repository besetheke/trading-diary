# ruff: noqa: E501
"""Roll-Kosten und Kommissionsattribution für die Oberfläche (AP-17g, Review M01).

Reiner Weiterreicher der vorhandenen Rechenkerne ``analytics.kommission`` und ``analytics.degradation`` — keine zweite
Rechnung. Beträge als Dezimal-Zeichenketten in EUR (wirtschaftlich, wie die Kerne). Die Roll-Degradation kennt nur die
Kettensicht; in der Kontosicht bleibt sie leer.
"""
import pathlib
from decimal import Decimal

from analytics.degradation import degradations_bericht
from analytics.kommission import kommissions_bericht


def _t(wert: Decimal | None) -> str | None:
    return None if wert is None else str(wert)


def _ketten_infos(db_pfad, sicht: str, summen) -> dict:
    """Je Kette der Auswertung: Basiswert, Strategie, Zeiten, Rolls und die Beträge (Brutto, Kommission, Netto in EUR),
    damit jede Summe bis zur Position nachprüfbar ist. Schlüssel ist die chain_id als Text."""
    from sqlalchemy import select

    from journal.db import create_db_engine
    from journal.schema import chains

    ids = [s[0] for s in summen]
    if not ids:
        return {}
    betraege = {s[0]: (s[1], s[2]) for s in summen}
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        zeilen = v.execute(
            select(chains.c.chain_id, chains.c.underlying, chains.c.asset_class, chains.c.oa_strategie,
                   chains.c.eroeffnet_am, chains.c.beendet_am, chains.c.anzahl_rolls)
            .where(chains.c.chain_id.in_(ids), chains.c.sicht == sicht)
        ).mappings().all()
    aus = {}
    for z in zeilen:
        brutto, komm = betraege[z["chain_id"]]
        aus[str(z["chain_id"])] = {
            "basiswert": z["underlying"], "anlageklasse": z["asset_class"], "strategie": z["oa_strategie"],
            "eroeffnet_am": str(z["eroeffnet_am"]), "beendet_am": None if z["beendet_am"] is None else str(z["beendet_am"]),
            "rolls": z["anzahl_rolls"], "brutto_eur": _t(brutto), "kommission_eur": _t(komm),
            "netto_eur": None if brutto is None else _t(brutto + komm),
        }
    return aus


def roll_kosten_aufbauen(db_pfad: str | pathlib.Path, sicht: str = "kette", nur_qualitaetsstufe_a: bool = False) -> dict:
    kommission = kommissions_bericht(db_pfad, sicht=sicht, nur_qualitaetsstufe_a=nur_qualitaetsstufe_a)
    antwort: dict = {
        "sicht": sicht,
        "anzahl_ketten_gesamt": kommission.anzahl_ketten_gesamt,
        "kommission": [
            {
                "dimension": g.dimension, "schluessel": g.schluessel, "anzahl_ketten": g.anzahl_ketten,
                "anzahl_ketten_abgeschlossen": g.anzahl_ketten_abgeschlossen,
                "anzahl_ketten_kurs_fehlt": g.anzahl_ketten_kurs_fehlt,
                "brutto_eur": _t(g.brutto_eur), "kommission_eur": _t(g.kommission_eur),
                "netto_eur": _t(g.netto_eur), "kommissionsanteil": _t(g.kommissionsanteil),
                "ketten_ids": list(g.ketten_ids), "ketten_ids_kurs_fehlt": list(g.ketten_ids_kurs_fehlt),
            }
            for g in kommission.gruppen
        ],
        "degradation": None,
        "degradation_abdeckung": [],
        "ketten": _ketten_infos(db_pfad, sicht, kommission.ketten_summen),
    }
    if sicht == "kette":
        d = degradations_bericht(db_pfad, nur_qualitaetsstufe_a=nur_qualitaetsstufe_a)
        antwort["degradation"] = [
            {
                "modus": g.modus, "roll_gruppe": g.roll_gruppe, "anzahl_ketten": g.anzahl_ketten,
                "summe_netto_eur": _t(g.summe_netto_eur), "durchschnitt_netto_eur": _t(g.durchschnitt_netto_eur),
                "trefferquote": _t(g.trefferquote), "anzahl_ketten_kurs_fehlt": g.anzahl_ketten_kurs_fehlt,
                "ketten_ids": list(g.ketten_ids), "ketten_ids_kurs_fehlt": list(g.ketten_ids_kurs_fehlt),
            }
            for g in d.gruppen
        ]
        antwort["degradation_abdeckung"] = [
            {
                "modus": a.modus, "ketten_abgeschlossen": a.ketten_abgeschlossen, "ketten_ausgewertet": a.ketten_ausgewertet,
                "abdeckung_ketten": _t(a.abdeckung_ketten), "rollverknuepfungen": a.rollverknuepfungen,
                "offene_kandidaten": a.offene_kandidaten, "abdeckung_rollverknuepfungen": _t(a.abdeckung_rollverknuepfungen),
            }
            for a in d.abdeckung
        ]
    return antwort
