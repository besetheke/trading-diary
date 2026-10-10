"""Kosten & Erträge (AP-06f): Kommissionen, Gebühren, Zinsen, Dividenden,
Quellensteuer, Barausgleich, Ein-/Auszahlungen — je Kategorie und je Monat,
in EUR, wahlweise für einen Zeitraum.

Vertrag ist ``auftraege/AP-06f.md``; die Abnahmetests in
``tests/test_cashflows.py`` sind unveränderlich. Alle Beträge ``Decimal``
(Regel 5).

Quellen und EUR-Rechnung — keine zweite, abweichende Rechnung:

- **Kommissionen** aus ``executions``: ``kommission × buchungskurs`` derselben
  Ausführung, wie Tranche I (``_wirtschaftlich``) die Kommission bewertet.
  Gezählt wird jede Ausführung mit Kommission ≠ 0; fehlt der Kurs, zählt sie
  nur als ``anzahl_kurs_fehlt`` (kein Ersatzkurs, Tranche I E4).
- **Barausgleich** aus ``executions``: Zuteilung/Ausübung eines
  Barausgleich-Instruments, bewertet über ``bewerte_barausgleich`` (AP-06x)
  — ``Seitenvorzeichen × schlusskurs × |menge| × multiplikator ×
  buchungskurs``.
- **Cash-Buchungen** aus ``flex_cash_transactions``: ``betrag × kurs``; den
  Kurs (``fxRateToBase``) reicht die Hülle aus dem Rohsatz herein.
  Unbekannte Buchungstypen landen in ``sonstige`` — nie still verworfen.

Kommissionen und Barausgleich stecken bereits im realisierten Ergebnis
(Tranche I); ``im_ergebnis_enthalten`` markiert das, damit sie niemand ein
zweites Mal addiert (Kapitalentwicklung, AP-06g).

Zeitraum: nach dem Datum der Buchung bzw. der Ausführung, beide Enden
einschließlich (wie AP-08f2).
"""

import json
import pathlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from analytics.kennzahlen import bewerte_barausgleich
from journal.db import create_db_engine
from journal.schema import executions, flex_cash_transactions, instruments

KATEGORIEN = (
    "kommissionen",
    "kommissionsanpassungen",
    "gebuehren",
    "zinsen_erhalten",
    "zinsen_gezahlt",
    "dividenden",
    "quellensteuer",
    "barausgleich",
    "sonstige",
    "ein_auszahlungen",
)

IM_ERGEBNIS_ENTHALTEN = frozenset({"kommissionen", "barausgleich"})

# IB-Flex-Typen der Cash-Buchungen (§6.1) → Kategorie. Alles andere: sonstige.
TYP_KATEGORIE = {
    "Dividends": "dividenden",
    "Payment In Lieu Of Dividends": "dividenden",
    "Withholding Tax": "quellensteuer",
    "Broker Interest Received": "zinsen_erhalten",
    "Broker Interest Paid": "zinsen_gezahlt",
    "Other Fees": "gebuehren",
    "Commission Adjustments": "kommissionsanpassungen",
    "Deposits/Withdrawals": "ein_auszahlungen",
}

_VORZEICHEN = {"SELL": 1, "BUY": -1}
_NULL = Decimal("0")


@dataclass(frozen=True)
class CashflowKategorie:
    kategorie: str
    anzahl: int                    # Buchungen mit Kurs, genau die in der Summe
    summe_eur: Decimal
    anzahl_kurs_fehlt: int
    im_ergebnis_enthalten: bool


@dataclass(frozen=True)
class CashflowMonat:
    monat: str                     # 'JJJJ-MM'
    kategorie: str
    anzahl: int
    summe_eur: Decimal
    anzahl_kurs_fehlt: int


@dataclass(frozen=True)
class CashflowErgebnis:
    kategorien: tuple[CashflowKategorie, ...]   # alle, in der Reihenfolge KATEGORIEN
    monate: tuple[CashflowMonat, ...]           # nur Monat/Kategorie mit Buchung


def cashflow_auswertung(
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    cash_zeilen: list[dict],
    *,
    von: date | None = None,
    bis: date | None = None,
) -> CashflowErgebnis:
    """Rein (P2). ``cash_zeilen`` tragen ``datum``, ``typ``, ``betrag``,
    ``waehrung`` und ``kurs`` (fxRateToBase, ``None`` wenn unbekannt)."""
    if von is not None and bis is not None and von > bis:
        raise ValueError(f"Zeitraum ungültig: von {von} liegt nach bis {bis}")

    def im_zeitraum(tag: date) -> bool:
        return (von is None or tag >= von) and (bis is None or tag <= bis)

    # (kategorie, monat) -> [anzahl, summe, kurs_fehlt]
    posten: dict[tuple[str, str], list] = {}

    def buche(kategorie: str, zeitpunkt, betrag_eur: Decimal | None) -> None:
        tag = zeitpunkt.date() if hasattr(zeitpunkt, "date") else zeitpunkt
        if not im_zeitraum(tag):
            return
        eintrag = posten.setdefault((kategorie, f"{tag.year:04d}-{tag.month:02d}"), [0, _NULL, 0])
        if betrag_eur is None:
            eintrag[2] += 1
        else:
            eintrag[0] += 1
            eintrag[1] += betrag_eur

    for a in ausfuehrungs_zeilen:
        kommission = a.get("kommission")
        if kommission is not None and kommission != _NULL:
            kurs = a.get("buchungskurs")
            buche("kommissionen", a["handelszeit"], None if kurs is None else kommission * kurs)

    mult_je_conid = {z["conid"]: z["multiplikator"] for z in instrumenten_zeilen}
    bewertet = bewerte_barausgleich(ausfuehrungs_zeilen, instrumenten_zeilen)
    for original, a in zip(ausfuehrungs_zeilen, bewertet, strict=True):
        if a is original:
            continue  # nicht ersetzt: kein Barausgleich-Ereignis
        kurs = a.get("buchungskurs")
        betrag = (
            None
            if kurs is None
            else _VORZEICHEN[a["side"]] * a["preis"] * abs(a["menge"])
            * mult_je_conid[a["conid"]] * kurs
        )
        buche("barausgleich", a["handelszeit"], betrag)

    for c in cash_zeilen:
        kategorie = TYP_KATEGORIE.get(c["typ"], "sonstige")
        kurs = c.get("kurs")
        buche(kategorie, c["datum"], None if kurs is None else c["betrag"] * kurs)

    kategorien = []
    for kategorie in KATEGORIEN:
        eintraege = [w for (k, _), w in posten.items() if k == kategorie]
        kategorien.append(
            CashflowKategorie(
                kategorie=kategorie,
                anzahl=sum(w[0] for w in eintraege),
                summe_eur=sum((w[1] for w in eintraege), _NULL),
                anzahl_kurs_fehlt=sum(w[2] for w in eintraege),
                im_ergebnis_enthalten=kategorie in IM_ERGEBNIS_ENTHALTEN,
            )
        )
    monate = [
        CashflowMonat(monat=monat, kategorie=kategorie, anzahl=w[0], summe_eur=w[1],
                      anzahl_kurs_fehlt=w[2])
        for (kategorie, monat), w in sorted(
            posten.items(), key=lambda p: (p[0][1], KATEGORIEN.index(p[0][0]))
        )
    ]
    return CashflowErgebnis(kategorien=tuple(kategorien), monate=tuple(monate))


def _kurs_aus_rohsatz(roh_json: str) -> Decimal | None:
    """``fxRateToBase`` des Flex-Rohsatzes als Decimal — Zahlen nie über
    float (Regel 5); fehlt oder leer: ``None``."""
    roh = json.loads(roh_json, parse_float=Decimal, parse_int=Decimal)
    wert = roh.get("fxRateToBase")
    if wert in (None, ""):
        return None
    return Decimal(str(wert))


def cashflow_bericht(
    db_pfad: str | pathlib.Path,
    *,
    von: date | None = None,
    bis: date | None = None,
) -> CashflowErgebnis:
    """Liest Ausführungen, Instrumente und Cash-Buchungen (P3). Schreibt nichts."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        ausfuehrungs_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    executions.c.exec_id,
                    executions.c.conid,
                    executions.c.side,
                    executions.c.menge,
                    executions.c.preis,
                    executions.c.kommission,
                    executions.c.buchungskurs,
                    executions.c.handelszeit,
                    executions.c.ereignistyp,
                    executions.c.schlusskurs,
                )
            ).mappings()
        ]
        instrumenten_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    instruments.c.conid,
                    instruments.c.multiplikator,
                    instruments.c.abwicklungsart,
                )
            ).mappings()
        ]
        cash_zeilen = [
            dict(
                datum=z["datum"],
                typ=z["typ"],
                betrag=z["betrag"],
                waehrung=z["waehrung"],
                kurs=_kurs_aus_rohsatz(z["roh_json"]),
            )
            for z in verbindung.execute(
                select(
                    flex_cash_transactions.c.datum,
                    flex_cash_transactions.c.typ,
                    flex_cash_transactions.c.betrag,
                    flex_cash_transactions.c.waehrung,
                    flex_cash_transactions.c.roh_json,
                )
            ).mappings()
        ]
    return cashflow_auswertung(
        ausfuehrungs_zeilen, instrumenten_zeilen, cash_zeilen, von=von, bis=bis
    )
