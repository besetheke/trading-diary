# ruff: noqa: E501
"""Wirtschaftliche Beiträge einer Kampagne (AP-17g, Review M02).

Je Kette der Kampagne: geschlossen = Ergebnis (Brutto, Kommission, Netto in EUR); offen = nur Cash-Flow bisher, ausdrücklich
**kein Ergebnis**. Kampagnenergebnis = Summe der Netto-Beiträge der geschlossenen Ketten — genau die angezeigten Einzelbeiträge.
Regel für teilweise offene Kampagnen: das Ergebnis ist das bisher realisierte der geschlossenen Ketten und trägt den Status
``teilweise_offen``; der Cash-Flow der offenen Ketten steht getrennt daneben und wird nie dazugezählt. Fehlt bei einer
geschlossenen Kette der Kurs, bleibt das Ergebnis leer (Status ``kurs_fehlt``) statt still unvollständig zu summieren.
Reiner Weiterreicher von ``analytics.kommission``; Geld als Dezimal-Zeichenketten.
"""
import pathlib
from decimal import Decimal

from analytics.kommission import kommissions_bericht


def _t(wert: Decimal | None) -> str | None:
    return None if wert is None else str(wert)


def beitraege(db_pfad: str | pathlib.Path, chain_ids: list[int]) -> dict:
    erg = kommissions_bericht(db_pfad, sicht="konto")
    zu = set(chain_ids)
    zeilen: dict[int, dict] = {}
    for chain_id, brutto, komm in erg.ketten_summen:
        if chain_id in zu:
            zeilen[chain_id] = {"stand": "geschlossen", "brutto_eur": _t(brutto), "kommission_eur": _t(komm),
                                "netto_eur": None if brutto is None else _t(brutto + komm)}
    for chain_id, brutto, komm in erg.offene_summen:
        if chain_id in zu:
            zeilen[chain_id] = {"stand": "offen", "brutto_eur": _t(brutto), "kommission_eur": _t(komm),
                                "netto_eur": None if brutto is None else _t(brutto + komm)}
    geschlossen = [z for z in zeilen.values() if z["stand"] == "geschlossen"]
    offen = [z for z in zeilen.values() if z["stand"] == "offen"]
    kurs_fehlt = any(z["netto_eur"] is None for z in geschlossen)
    ergebnis = None
    if geschlossen and not kurs_fehlt:
        ergebnis = sum((Decimal(z["netto_eur"]) for z in geschlossen), Decimal(0))
    if not geschlossen:
        status = "offen"
    elif kurs_fehlt:
        status = "kurs_fehlt"
    elif offen:
        status = "teilweise_offen"
    else:
        status = "abgeschlossen"
    cashflow = None
    if offen and all(z["netto_eur"] is not None for z in offen):
        cashflow = sum((Decimal(z["netto_eur"]) for z in offen), Decimal(0))
    return {
        "je_kette": {str(k): v for k, v in zeilen.items()},
        "ergebnis_eur": _t(ergebnis), "ergebnis_status": status,
        "offener_cashflow_eur": _t(cashflow), "anzahl_geschlossen": len(geschlossen), "anzahl_offen": len(offen),
    }
