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
        "bausteine": [{"art": b.art, "anzahl": b.anzahl, "offen": b.offen, "brutto": _t(b.brutto),
                       "kommission": _t(b.kommission), "netto": _t(b.netto)} for b in erg.bausteine],
        "einheiten": [{"put_leg_id": e.put_leg_id, "strike": _t(e.strike), "verfall": str(e.verfall),
                       "eroeffnet": _t(e.eroeffnet), "beendet": _t(e.beendet),
                       "ergebnis": {k: _t(w) for k, w in e.ergebnis.items()}} for e in erg.einheiten],
    }
