# ruff: noqa: E501
"""Wege der manuellen Strategiezuordnung (AP-17g, M03); die Logik steht in ``journal.strategie_zuordnung``."""
from fastapi import HTTPException
from pydantic import BaseModel

from journal import strategie_zuordnung as zuordnung_modul


class StrategieEingabe(BaseModel):
    """Manuelle Strategiezuordnung an einer Kette."""

    strategie: str
    begruendung: str | None = None


def registriere(applikation, engine) -> None:
    @applikation.get("/strategie-zuordnung/{chain_id}")
    def strategie_zuordnung_lesen(chain_id: int) -> dict:
        """Strategie der Kette, ihre Herkunft (OA oder manuell) und eine eventuelle manuelle Zuordnung (M03)."""
        with engine.connect() as verbindung:
            try:
                return zuordnung_modul.lesen(verbindung, chain_id)
            except LookupError as fehler:
                raise HTTPException(status_code=404, detail=str(fehler)) from fehler

    @applikation.put("/journal/strategie-zuordnung/{chain_id}")
    def strategie_zuordnung_setzen(chain_id: int, eingabe: StrategieEingabe) -> dict:
        """Setzt die Strategie dauerhaft (überlebt Import und Rebuild), mit Begründung; wirkt sofort in allen Filtern."""
        with engine.begin() as verbindung:
            try:
                return zuordnung_modul.zuordnen(verbindung, chain_id, eingabe.strategie, eingabe.begruendung)
            except LookupError as fehler:
                raise HTTPException(status_code=404, detail=str(fehler)) from fehler
            except ValueError as fehler:
                raise HTTPException(status_code=422, detail=str(fehler)) from fehler

    @applikation.post("/journal/strategie-zuordnung/{chain_id}/zuruecknehmen")
    def strategie_zuordnung_zuruecknehmen(chain_id: int) -> dict:
        """Nimmt die manuelle Zuordnung zurück (der Stand davor kehrt wieder; die Zeile bleibt, Regel 4)."""
        with engine.begin() as verbindung:
            try:
                return zuordnung_modul.zuruecknehmen(verbindung, chain_id)
            except LookupError as fehler:
                raise HTTPException(status_code=404, detail=str(fehler)) from fehler
