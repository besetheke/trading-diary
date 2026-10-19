# ruff: noqa: E501
"""DAX Synthetic für die Oberfläche: reicht ``analytics.dax_synthetic`` als Dezimal-Texte weiter."""
import pathlib
from datetime import datetime

from analytics.dax_synthetic import SCHUTZ_PUT_MIN_DTE, SHORT_CALL_MAX_DTE, dax_synthetic_bericht


def _t(w) -> str | None:
    return None if w is None else str(w)


def dax_synthetic_aufbauen(db_pfad: str | pathlib.Path) -> dict:
    erg = dax_synthetic_bericht(db_pfad, datetime.now())
    return {
        "erkennung": "heuristik",
        "regeln": {"schutz_put_min_dte": SCHUTZ_PUT_MIN_DTE, "short_call_max_dte": SHORT_CALL_MAX_DTE},
        "aktiv_von": _t(erg.aktiv_von), "aktiv_bis": _t(erg.aktiv_bis), "sonstige": erg.sonstige,
        "bausteine": [{"art": b.art, "anzahl": b.anzahl, "offen": b.offen, "kontrakte": _t(b.kontrakte), "brutto": _t(b.brutto),
                       "kommission": _t(b.kommission), "netto": _t(b.netto)} for b in erg.bausteine],
        "trades": [{"leg_id": x["leg_id"], "baustein": x["baustein"], "eroeffnet": _t(x["eroeffnet"]),
                    "beendet": _t(x["beendet"]), "art": x["asset_class"], "recht": x["right"], "strike": _t(x["strike"]),
                    "verfall": _t(x["expiry"]), "menge": _t(x.get("menge")), "brutto": _t(x["brutto"]),
                    "kommission": _t(x["kommission"]),
                    "netto": None if x["brutto"] is None else _t(x["brutto"] + (x["kommission"] or 0))}
                   for x in erg.trades],
        "einheiten": [{"put_leg_id": e.put_leg_id, "strike": _t(e.strike), "verfall": str(e.verfall),
                       "eroeffnet": _t(e.eroeffnet), "beendet": _t(e.beendet),
                       "ergebnis": {k: _t(w) for k, w in e.ergebnis.items()}} for e in erg.einheiten],
    }
