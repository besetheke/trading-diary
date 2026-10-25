# ruff: noqa: E501
"""Kampagnen-Kandidaten in der Oberfläche entscheiden (AP-17g, Review M02, zweite Stufe).

Dieselbe Prüf- und Schreiblogik wie die Datei-Rundreise (``journal.kampagnen_durchsicht``: ``_gruppen_bilden``, ``_plan_bilden``,
``_plan_ausfuehren``) — nur ohne die Datei: ein Kandidatenpaar wird bestätigt (``ja``) oder verworfen (``nein``). Jede Entscheidung läuft in
einer kurzen Transaktion (Regel 9) und trägt ``erkennung = manuell`` (Regel 7); sie hängt an den Ketten der Kontosicht und überlebt den
Rebuild wie die Entscheidungen der Rundreise. Eine Verwerfung ist nicht löschbar (Regel 4); wer sie zurücknimmt, bestätigt das Paar
ausdrücklich (``ueberschreiben``), und die alte Ablehnung weicht dabei genauso wie in der Rundreise mit ``--ueberschreiben``.
"""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.engine import Engine

from journal.kampagnen_durchsicht import (
    TYP_JE_KANDIDATTYP,
    _gruppen_bilden,
    _plan_ausfuehren,
    _plan_bilden,
)
from journal.schema import campaign_ablehnungen, chains


def _text(wert):
    return None if wert is None else str(wert)


def kandidaten(engine: Engine) -> dict:
    """Offene Kandidaten (ohne gemeinsame Kampagne, nicht verworfen), gruppiert nach Kette A, wie das Ausschreiben sie ordnet."""
    with engine.connect() as verbindung:
        gruppen = _gruppen_bilden(verbindung)
    aus = []
    for nummer, eintraege in enumerate(gruppen.values(), start=1):
        zeilen = [z for _, z in eintraege]
        aus.append({
            "gruppe": nummer,
            "mehrdeutig": len(zeilen) > 1,
            "kandidaten": [
                {
                    "rang": rang, "typ": z["Typ"], "basiswert": z["Basiswert"],
                    "a": {"schluessel": z["Schlüssel Kette A"], "seite": z["Kette A: Seite"], "eroeffnet_am": _text(z["Kette A: eröffnet"]),
                          "beendet_am": _text(z["Kette A: beendet"]), "rolls": z["Kette A: Rolls"], "typ": z["Typ Kette A"]},
                    "b": {"schluessel": z["Schlüssel Kette B"], "seite": z["Kette B: Seite"], "eroeffnet_am": _text(z["Kette B: eröffnet"]),
                          "beendet_am": _text(z["Kette B: beendet"]), "rolls": z["Kette B: Rolls"], "typ": z["Typ Kette B"]},
                    "abstand_minuten": z["Abstand Minuten"], "ueberlappung_tage": _text(z["Überlappung Tage"]),
                }
                for rang, z in enumerate(zeilen, start=1)
            ],
        })
    return {"gruppen": aus, "anzahl": sum(len(g["kandidaten"]) for g in aus)}


def verworfene(engine: Engine) -> list[dict]:
    """Verworfene Paare (Kontosicht-Naturschlüssel), neueste zuerst — jedes lässt sich ausdrücklich doch bestätigen."""
    with engine.connect() as verbindung:
        schluessel = dict(verbindung.execute(select(chains.c.chain_id, chains.c.natur_schluessel).where(chains.c.sicht == "konto")).all())
        zeilen = verbindung.execute(select(campaign_ablehnungen).order_by(campaign_ablehnungen.c.erstellt_am.desc())).mappings().all()
    return [
        {"schluessel_a": schluessel.get(z["chain_id_a"]), "schluessel_b": schluessel.get(z["chain_id_b"]), "typ": z["typ"],
         "notiz": z["notiz"], "erstellt_am": _text(z["erstellt_am"])}
        for z in zeilen
        if z["chain_id_a"] in schluessel and z["chain_id_b"] in schluessel
    ]


def entscheiden(engine: Engine, *, schluessel_a: str, schluessel_b: str, typ: str, urteil: str, typ_a: str | None = None,
                typ_b: str | None = None, bemerkung: str | None = None, ueberschreiben: bool = False,
                jetzt: datetime | None = None) -> dict:
    """Bestätigt (``ja``) oder verwirft (``nein``) ein Paar. ``ValueError`` bei jedem Widerspruch — dann steht nichts Neues in der Datenbank."""
    if typ not in TYP_JE_KANDIDATTYP:
        raise ValueError(f"unbekannter Kandidat-Typ {typ!r} — nur ic oder financing")
    if urteil not in ("ja", "nein"):
        raise ValueError(f"ungültige Entscheidung {urteil!r} — nur ja oder nein")
    vorbelegt_a, vorbelegt_b = TYP_JE_KANDIDATTYP[typ]
    zeile = {
        "Gruppe": "Oberfläche", "Rang": "-", "Typ": typ, "Entscheidung": urteil, "Bemerkung": bemerkung,
        "Typ Kette A": typ_a or vorbelegt_a, "Typ Kette B": typ_b or vorbelegt_b,
        "Schlüssel Kette A": schluessel_a, "Schlüssel Kette B": schluessel_b,
    }
    with engine.begin() as verbindung:
        plan = _plan_bilden(verbindung, [zeile], ueberschreiben=ueberschreiben)
        _plan_ausfuehren(verbindung, plan, jetzt=jetzt or datetime.now())
    e = plan.ergebnis
    return {"neu_bestaetigt": e.neu_bestaetigt, "neu_abgelehnt": e.neu_abgelehnt, "kampagnen_neu": e.kampagnen_neu,
            "verknuepfungen_neu": e.verknuepfungen_neu, "unveraendert": e.unveraendert, "geaendert": e.geaendert}
