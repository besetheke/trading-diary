# ruff: noqa: E501
"""Manuelle Strategiezuordnung an Ketten (AP-17g, Review M03).

Der Nutzer setzt einer Kette (auch diskretionären Positionen ohne OA-Trade) eine Strategie, mit Begründung. Die Zuordnung hängt am
**Naturschlüssel** der Kette und überlebt damit jeden Rebuild; sie wird nach dem OA-Abgleich angewandt und lässt ``oa_erkennung`` leer
(die Prüfregel erlaubt dort nur auto/heuristik); die Herkunft „manuell“ führt diese Tabelle und zeigt die API (Regel 7). Widerspricht OA, bleibt die manuelle Zuordnung und der Widerspruch wird gezählt und in
der Datenqualität-Liste gezeigt. Rücknahme löscht nichts, sie stellt den Stand vor der Zuordnung wieder her (Regel 4).
"""
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from journal.schema import chain_links, chains, strategie_zuordnungen, structures


def _setzen(verbindung: Connection, chain_id: int, strategie: str | None, erkennung: str | None) -> None:
    verbindung.execute(update(chains).where(chains.c.chain_id == chain_id).values(oa_strategie=strategie, oa_erkennung=erkennung))
    struktur_ids = select(chain_links.c.structure_id).where(chain_links.c.chain_id == chain_id)
    verbindung.execute(update(structures).where(structures.c.structure_id.in_(struktur_ids))
                       .values(oa_strategie=strategie, oa_erkennung=erkennung))


def anwenden(verbindung: Connection, ketten_id_konto: dict[str, int], ketten_id_kette: dict[str, int]) -> tuple[int, int, int]:
    """Nach dem OA-Abgleich: aktive Zuordnungen auf die Ketten beider Sichten legen.

    Rückgabe ``(angewandt, widerspruch, verwaist)`` für die Kontosicht: angewandt = Zuordnungen mit Kette; widerspruch = OA hatte eine
    andere Strategie gesetzt; verwaist = Naturschlüssel ohne Kette (die Zeile bleibt unverändert stehen, nichts geht verloren)."""
    angewandt = widerspruch = verwaist = 0
    for z in verbindung.execute(select(strategie_zuordnungen).where(strategie_zuordnungen.c.zurueckgenommen_am.is_(None))).mappings():
        nk, strategie = z["natur_schluessel"], z["strategie"]
        konflikt = None
        if nk in ketten_id_konto:
            vorher = verbindung.execute(select(chains.c.oa_strategie).where(chains.c.chain_id == ketten_id_konto[nk])).scalar()
            if vorher is not None and vorher != strategie:
                konflikt = vorher
                widerspruch += 1
            angewandt += 1
            _setzen(verbindung, ketten_id_konto[nk], strategie, None)
        else:
            verwaist += 1
        if nk in ketten_id_kette:
            _setzen(verbindung, ketten_id_kette[nk], strategie, None)
        if konflikt != z["konflikt_oa"] and nk in ketten_id_konto:
            verbindung.execute(update(strategie_zuordnungen).where(strategie_zuordnungen.c.natur_schluessel == nk).values(konflikt_oa=konflikt))
    return angewandt, widerspruch, verwaist


def zuordnen(verbindung: Connection, chain_id: int, strategie: str, begruendung: str | None, jetzt: datetime | None = None) -> dict:
    """Setzt die Strategie für die Kette (Kontosicht-ID) dauerhaft und wirkt sofort in beiden Sichten."""
    strategie = (strategie or "").strip()
    if not strategie:
        raise ValueError("Strategie ohne Inhalt")
    zeile = verbindung.execute(select(chains.c.natur_schluessel, chains.c.oa_strategie, chains.c.oa_erkennung)
                               .where(chains.c.chain_id == chain_id)).mappings().first()
    if zeile is None:
        raise LookupError(f"Kette {chain_id} nicht gefunden")
    nk, jetzt = zeile["natur_schluessel"], jetzt or datetime.now()
    alt = verbindung.execute(select(strategie_zuordnungen).where(strategie_zuordnungen.c.natur_schluessel == nk)).mappings().first()
    aktiv = alt is not None and alt["zurueckgenommen_am"] is None
    # Der Stand vor der ersten manuellen Zuordnung wird gemerkt (nicht der manuelle Wert selbst)
    vorher = alt["oa_vorher"] if aktiv else zeile["oa_strategie"]
    erkennung_vorher = alt["oa_erkennung_vorher"] if aktiv else zeile["oa_erkennung"]
    konflikt = alt["konflikt_oa"] if aktiv else (zeile["oa_strategie"] if zeile["oa_strategie"] not in (None, strategie) else None)
    werte = {"strategie": strategie, "begruendung": (begruendung or "").strip() or None, "zurueckgenommen_am": None,
             "geaendert_am": jetzt, "oa_vorher": vorher, "oa_erkennung_vorher": erkennung_vorher, "konflikt_oa": konflikt}
    if alt is None:
        verbindung.execute(strategie_zuordnungen.insert().values(natur_schluessel=nk, erstellt_am=jetzt, **werte))
    else:
        verbindung.execute(update(strategie_zuordnungen).where(strategie_zuordnungen.c.natur_schluessel == nk).values(**werte))
    for ketten_id in verbindung.execute(select(chains.c.chain_id).where(chains.c.natur_schluessel == nk)).scalars().all():
        _setzen(verbindung, ketten_id, strategie, None)
    return lesen(verbindung, chain_id)


def zuruecknehmen(verbindung: Connection, chain_id: int, jetzt: datetime | None = None) -> dict:
    """Nimmt die manuelle Zuordnung zurück: der Stand vor der Zuordnung kehrt zurück, die Zeile bleibt (mit Zeitpunkt der Rücknahme)."""
    zeile = verbindung.execute(select(chains.c.natur_schluessel).where(chains.c.chain_id == chain_id)).mappings().first()
    if zeile is None:
        raise LookupError(f"Kette {chain_id} nicht gefunden")
    nk = zeile["natur_schluessel"]
    z = verbindung.execute(select(strategie_zuordnungen).where(strategie_zuordnungen.c.natur_schluessel == nk,
                                                               strategie_zuordnungen.c.zurueckgenommen_am.is_(None))).mappings().first()
    if z is None:
        raise LookupError("keine aktive manuelle Zuordnung")
    verbindung.execute(update(strategie_zuordnungen).where(strategie_zuordnungen.c.natur_schluessel == nk)
                       .values(zurueckgenommen_am=jetzt or datetime.now(), konflikt_oa=None))
    for ketten_id in verbindung.execute(select(chains.c.chain_id).where(chains.c.natur_schluessel == nk)).scalars().all():
        _setzen(verbindung, ketten_id, z["oa_vorher"], z["oa_erkennung_vorher"])
    return lesen(verbindung, chain_id)


def lesen(verbindung: Connection, chain_id: int) -> dict:
    k = verbindung.execute(select(chains.c.natur_schluessel, chains.c.oa_strategie, chains.c.oa_erkennung)
                           .where(chains.c.chain_id == chain_id)).mappings().first()
    if k is None:
        raise LookupError(f"Kette {chain_id} nicht gefunden")
    z = verbindung.execute(select(strategie_zuordnungen).where(strategie_zuordnungen.c.natur_schluessel == k["natur_schluessel"])).mappings().first()
    aktiv = z is not None and z["zurueckgenommen_am"] is None
    return {
        "chain_id": chain_id, "strategie": k["oa_strategie"], "herkunft": "manuell" if aktiv else k["oa_erkennung"],
        "manuell": None if not aktiv else {"strategie": z["strategie"], "begruendung": z["begruendung"], "erstellt_am": str(z["erstellt_am"]),
                                           "geaendert_am": None if z["geaendert_am"] is None else str(z["geaendert_am"]),
                                           "oa_widerspricht": z["konflikt_oa"], "stand_vorher": z["oa_vorher"]},
        "zurueckgenommen_am": None if z is None or z["zurueckgenommen_am"] is None else str(z["zurueckgenommen_am"]),
    }
