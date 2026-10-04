"""Steuerbericht aus der Datenbank (AP-10k, Vertrag 13).

Liest selbst — legs der Kontosicht, executions, instruments und
flex_cash_transactions — und übergibt an die reine Auswertung. Die
Kontosicht ist die Steuer-Sicht (Plan §5); Zeilen der Kettensicht werden
gar nicht erst gelesen, deshalb kann keine Vermischung entstehen.
"""

import pathlib

from sqlalchemy import select

from analytics.steuer import SteuerErgebnis, steuer_auswertung
from journal.db import create_db_engine
from journal.schema import executions, flex_cash_transactions, instruments, legs


def steuer_bericht(db_pfad: str | pathlib.Path) -> SteuerErgebnis:
    """Liest die Kontosicht der Datenbank und wertet sie steuerlich aus.

    Die Cash-Transaktionen werden komplett übergeben — auch Einzahlungen,
    bewusst ohne Typ-Semantik; das Filtern gehört dem Leser (Vertrag 13).
    """
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        leg_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    legs.c.leg_id,
                    legs.c.sicht,
                    legs.c.conid,
                    legs.c.close_exec_id,
                    legs.c.offen_ja_nein,
                    legs.c.basis_ungeklaert,
                    legs.c.menge,
                    legs.c.brutto_pnl,
                    legs.c.kommission_gesamt,
                ).where(legs.c.sicht == "konto")
            ).mappings()
        ]
        exec_je_id = {
            z["exec_id"]: dict(z)
            for z in verbindung.execute(
                select(
                    executions.c.exec_id,
                    executions.c.handelszeit,
                    executions.c.buchungskurs,
                )
            ).mappings()
        }
        instrument_je_conid = {
            z["conid"]: dict(z)
            for z in verbindung.execute(
                select(
                    instruments.c.conid,
                    instruments.c.asset_class,
                    instruments.c.symbol,
                    instruments.c.waehrung,
                )
            ).mappings()
        }
        cash_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    flex_cash_transactions.c.datum,
                    flex_cash_transactions.c.typ,
                    flex_cash_transactions.c.betrag,
                    flex_cash_transactions.c.waehrung,
                )
            ).mappings()
        ]
    return steuer_auswertung(
        leg_zeilen,
        exec_je_id,
        instrument_je_conid,
        cash_transaktionen=cash_zeilen,
    )
