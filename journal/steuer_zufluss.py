# ruff: noqa: E501
"""Steuer nach Zufluss aus der Datenbank (AP-10c): liest die Kontosicht und übergibt an die reine Rechnung.

Nur lesend. Gelesen werden Legs der Kontosicht, Ausführungen (mit Handels- und Abrechnungsdatum und der
IB-Unterkategorie aus dem Rohsatz), Instrumente und die Cash-Buchungen. Die Kontosicht ist die Steuer-Sicht
(Plan §5); Zeilen der Kettensicht werden nicht gelesen.
"""

import json
import pathlib
from datetime import date

from sqlalchemy import select

from analytics.steuer_konfig import STANDARD_KONFIG, Konfig
from analytics.steuer_zufluss import Anfangsbestand, SteuerZuflussErgebnis, steuer_zufluss
from journal.db import create_db_engine
from journal.schema import executions, flex_cash_transactions, instruments, legs


def _flex_datum(wert) -> date | None:
    """``20260918`` oder ``2026-09-18`` (auch mit angehängter Uhrzeit) als Datum; sonst ``None``."""
    if not wert:
        return None
    text = str(wert).split(";")[0].strip()
    try:
        if len(text) == 8 and text.isdigit():
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def steuer_zufluss_bericht(
    db_pfad: str | pathlib.Path,
    *,
    konfig: Konfig = STANDARD_KONFIG,
    anfangsbestaende: list[Anfangsbestand] | tuple = (),
) -> SteuerZuflussErgebnis:
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        leg_zeilen = [
            dict(z)
            for z in v.execute(
                select(
                    legs.c.leg_id, legs.c.conid, legs.c.open_exec_id, legs.c.close_exec_id, legs.c.menge,
                    legs.c.open_faktor, legs.c.close_faktor, legs.c.offen_ja_nein, legs.c.basis_ungeklaert,
                ).where(legs.c.sicht == "konto")
            ).mappings()
        ]
        ausfuehrungen = []
        for z in v.execute(
            select(
                executions.c.exec_id, executions.c.conid, executions.c.side, executions.c.menge,
                executions.c.preis, executions.c.waehrung, executions.c.kommission,
                executions.c.kommission_waehrung, executions.c.buchungskurs, executions.c.handelszeit,
                executions.c.ereignistyp, executions.c.schlusskurs, executions.c.roh_json,
            )
        ).mappings():
            roh = json.loads(z["roh_json"])
            e = {k: z[k] for k in z if k != "roh_json"}
            e["trade_date"] = _flex_datum(roh.get("tradeDate"))
            e["settle_date"] = _flex_datum(roh.get("settleDateTarget"))
            e["unterkategorie"] = roh.get("subCategory")
            ausfuehrungen.append(e)
        instrument_zeilen = [
            dict(z)
            for z in v.execute(
                select(
                    instruments.c.conid, instruments.c.asset_class, instruments.c.multiplikator,
                    instruments.c.abwicklungsart, instruments.c.symbol, instruments.c.underlying,
                    instruments.c.waehrung, instruments.c.right,
                )
            ).mappings()
        ]
        cash = []
        for z in v.execute(
            select(
                flex_cash_transactions.c.datum, flex_cash_transactions.c.typ, flex_cash_transactions.c.betrag,
                flex_cash_transactions.c.waehrung, flex_cash_transactions.c.beschreibung,
                flex_cash_transactions.c.roh_json,
            )
        ).mappings():
            roh = json.loads(z["roh_json"], parse_float=str)
            kurs = roh.get("fxRateToBase")
            from decimal import Decimal

            cash.append(
                {
                    "datum": z["datum"], "typ": z["typ"], "betrag": z["betrag"], "waehrung": z["waehrung"],
                    "beschreibung": z["beschreibung"], "symbol": roh.get("symbol") or None,
                    "kurs": Decimal(str(kurs)) if kurs not in (None, "") else None,
                    "settle_date": _flex_datum(roh.get("settleDate")),
                    "land": roh.get("issuerCountryCode") or None,
                }
            )
    return steuer_zufluss(
        leg_zeilen, ausfuehrungen, instrument_zeilen, cash, konfig=konfig, anfangsbestaende=anfangsbestaende
    )
