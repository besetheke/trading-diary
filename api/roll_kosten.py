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
            }
            for g in kommission.gruppen
        ],
        "degradation": None,
        "degradation_abdeckung": [],
    }
    if sicht == "kette":
        d = degradations_bericht(db_pfad, nur_qualitaetsstufe_a=nur_qualitaetsstufe_a)
        antwort["degradation"] = [
            {
                "modus": g.modus, "roll_gruppe": g.roll_gruppe, "anzahl_ketten": g.anzahl_ketten,
                "summe_netto_eur": _t(g.summe_netto_eur), "durchschnitt_netto_eur": _t(g.durchschnitt_netto_eur),
                "trefferquote": _t(g.trefferquote), "anzahl_ketten_kurs_fehlt": g.anzahl_ketten_kurs_fehlt,
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
