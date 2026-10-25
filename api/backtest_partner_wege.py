# ruff: noqa: E501
"""Wege der Partnerkorrektur für Backtest-Trades (AP-17g, M07); die Logik steht in ``journal.backtest_partner``."""
from fastapi import HTTPException
from pydantic import BaseModel

from journal import backtest_partner as modul


class PartnerEingabe(BaseModel):
    oo_trade: int
    oa_strategie: str
    oa_trade: str | None = None  # leer = ausdrücklich kein Partner
    begruendung: str | None = None


class PartnerRuecknahme(BaseModel):
    oo_trade: int


def registriere(applikation, engine) -> None:
    @applikation.get("/backtests/partner-kandidaten")
    def partner_kandidaten(oo_trade: int, oa_strategie: str) -> list[dict]:
        """Live-Trades der OA-Strategie in der Nähe des Backtest-Trades, nächste zuerst."""
        with engine.connect() as verbindung:
            try:
                return modul.kandidaten(verbindung, oo_trade, oa_strategie)
            except LookupError as fehler:
                raise HTTPException(status_code=404, detail=str(fehler)) from fehler

    @applikation.post("/journal/backtests/partner")
    def partner_setzen(eingabe: PartnerEingabe) -> dict:
        """Korrigiert den Live-Partner (oder legt ausdrücklich keinen fest); wirkt sofort in der Auswertung."""
        with engine.begin() as verbindung:
            try:
                return modul.setzen(verbindung, eingabe.oo_trade, eingabe.oa_strategie, eingabe.oa_trade, eingabe.begruendung)
            except LookupError as fehler:
                raise HTTPException(status_code=404, detail=str(fehler)) from fehler
            except ValueError as fehler:
                raise HTTPException(status_code=409, detail=str(fehler)) from fehler

    @applikation.post("/journal/backtests/partner/zuruecknehmen")
    def partner_zuruecknehmen(eingabe: PartnerRuecknahme) -> dict:
        """Nimmt die Korrektur zurück; die Zeile bleibt (Regel 4), es gilt wieder die Zeitfenster-Paarung."""
        with engine.begin() as verbindung:
            try:
                return modul.zuruecknehmen(verbindung, eingabe.oo_trade)
            except LookupError as fehler:
                raise HTTPException(status_code=404, detail=str(fehler)) from fehler
