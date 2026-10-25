# ruff: noqa: E501
"""Wege zum Entscheiden von Kampagnen-Kandidaten (AP-17g, M02); die Logik steht in ``journal.kampagnen_entscheidung``."""
from fastapi import HTTPException
from pydantic import BaseModel

from journal import kampagnen_entscheidung as modul


class KandidatEntscheidung(BaseModel):
    schluessel_a: str
    schluessel_b: str
    typ: str  # ic | financing
    urteil: str  # ja | nein
    typ_a: str | None = None
    typ_b: str | None = None
    bemerkung: str | None = None
    ueberschreiben: bool = False


def registriere(applikation, engine) -> None:
    @applikation.get("/kampagnen-kandidaten")
    def kampagnen_kandidaten() -> dict:
        """Offene Kandidaten gruppiert nach Kette A, dazu die verworfenen Paare (zum ausdrücklichen Umentscheiden)."""
        return {**modul.kandidaten(engine), "verworfen": modul.verworfene(engine)}

    @applikation.post("/journal/kampagnen-kandidaten/entscheiden")
    def kampagnen_kandidat_entscheiden(eingabe: KandidatEntscheidung) -> dict:
        """Bestätigt oder verwirft ein Kandidatenpaar; Widerspruch → 409, nichts wird geschrieben."""
        try:
            return modul.entscheiden(
                engine, schluessel_a=eingabe.schluessel_a, schluessel_b=eingabe.schluessel_b, typ=eingabe.typ, urteil=eingabe.urteil,
                typ_a=eingabe.typ_a, typ_b=eingabe.typ_b, bemerkung=eingabe.bemerkung, ueberschreiben=eingabe.ueberschreiben,
            )
        except ValueError as fehler:
            raise HTTPException(status_code=409, detail=str(fehler)) from fehler
