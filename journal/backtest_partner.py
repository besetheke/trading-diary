# ruff: noqa: E501
"""Partner eines Backtest-Trades korrigieren (AP-17g, Review M07).

Die Zeitfenster-Paarung (``engine.oo_zuordnung``) ist ein Vorschlag (Regel 7). Der Nutzer kann den Live-Partner eines Option-Omega-Trades ersetzen
oder ausdrücklich „kein Partner“ festhalten; die Korrektur hängt am Naturschlüssel des Backtest-Trades, trägt ``erkennung = manuell`` und wirkt in
der Auswertung (``analytics.backtest``). Eine Rücknahme setzt ``zurueckgenommen_am`` (Regel 4); wer eine Korrektur ändert, überschreibt nur ihr
Ziel und ihre Begründung.
"""
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from analytics.backtest import _live_laden
from journal.schema import backtest_partner, oo_trades

SUCHFENSTER = timedelta(days=2)


def _oo_trade(v: Connection, oo_id: int):
    z = v.execute(select(oo_trades.c.id, oo_trades.c.strategie, oo_trades.c.eroeffnet, oo_trades.c.legs_roh).where(oo_trades.c.id == oo_id)).mappings().first()
    if z is None:
        raise LookupError(f"Backtest-Trade {oo_id} nicht gefunden")
    return z


def kandidaten(v: Connection, oo_id: int, oa_strategie: str) -> list[dict]:
    """Live-Trades der OA-Strategie, die höchstens zwei Tage vom Backtest-Trade entfernt eröffnet wurden, nächste zuerst."""
    oo = _oo_trade(v, oo_id)
    treffer = []
    for x in _live_laden(v):
        e = x.eroeffnung
        if e.strategie != oa_strategie or abs(e.zeit - oo["eroeffnet"]) > SUCHFENSTER:
            continue
        treffer.append({
            "oa_trade": e.schluessel, "zeit": str(e.zeit), "kontrakte": x.kontrakte, "offen": x.offen,
            "abstand_min": round((e.zeit - oo["eroeffnet"]).total_seconds() / 60),
        })
    return sorted(treffer, key=lambda t: abs(t["abstand_min"]))


def setzen(v: Connection, oo_id: int, oa_strategie: str, oa_trade: str | None, begruendung: str | None, jetzt: datetime | None = None) -> dict:
    """Setzt den Partner (``oa_trade``) oder ausdrücklich keinen (``None``). ``ValueError``, wenn der Live-Trade nicht zur OA-Strategie gehört."""
    oo = _oo_trade(v, oo_id)
    if oa_trade is not None and not any(x.eroeffnung.schluessel == oa_trade and x.eroeffnung.strategie == oa_strategie for x in _live_laden(v)):
        raise ValueError(f"Live-Trade {oa_trade!r} gehört nicht zur OA-Strategie {oa_strategie!r}")
    schluessel = (backtest_partner.c.oo_strategie == oo["strategie"], backtest_partner.c.oo_eroeffnet == oo["eroeffnet"], backtest_partner.c.oo_legs_roh == oo["legs_roh"])
    werte = {"oa_trade": oa_trade, "begruendung": (begruendung or "").strip() or None, "zurueckgenommen_am": None}
    if v.execute(select(backtest_partner.c.oa_trade).where(*schluessel)).first() is None:
        v.execute(backtest_partner.insert().values(oo_strategie=oo["strategie"], oo_eroeffnet=oo["eroeffnet"], oo_legs_roh=oo["legs_roh"],
                                                   erkennung="manuell", erstellt_am=jetzt or datetime.now(), **werte))
    else:
        v.execute(update(backtest_partner).where(*schluessel).values(**werte))
    return {"oo_trade": str(oo_id), "oa_trade": oa_trade, "erkennung": "manuell"}


def zuruecknehmen(v: Connection, oo_id: int, jetzt: datetime | None = None) -> dict:
    """Nimmt die Korrektur zurück (die Zeile bleibt); danach gilt wieder die Zeitfenster-Paarung."""
    oo = _oo_trade(v, oo_id)
    ergebnis = v.execute(update(backtest_partner).where(
        backtest_partner.c.oo_strategie == oo["strategie"], backtest_partner.c.oo_eroeffnet == oo["eroeffnet"],
        backtest_partner.c.oo_legs_roh == oo["legs_roh"], backtest_partner.c.zurueckgenommen_am.is_(None),
    ).values(zurueckgenommen_am=jetzt or datetime.now()))
    if ergebnis.rowcount == 0:
        raise LookupError("keine aktive Korrektur")
    return {"oo_trade": str(oo_id), "zurueckgenommen": True}
