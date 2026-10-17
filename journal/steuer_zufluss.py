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


def fremdwaehrung_salden(db_pfad: str | pathlib.Path) -> list[dict]:
    """Jahres-Salden je Währung laut IB Cash Report (Perioden ab Jahresbeginn): ein negativer Endbestand heißt
    Sollsaldo (Margin-Kredit in dieser Währung), nicht Guthaben. Nur zur Anzeige — es wird nichts daraus gerechnet."""
    from journal.schema import flex_cash_report

    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        zeilen = v.execute(
            select(
                flex_cash_report.c.waehrung, flex_cash_report.c.von, flex_cash_report.c.bis,
                flex_cash_report.c.anfangsbestand, flex_cash_report.c.endbestand,
            )
            .where(flex_cash_report.c.ebene == "Currency")
            .order_by(flex_cash_report.c.waehrung, flex_cash_report.c.von)
        ).mappings().all()
    return [
        {"waehrung": z["waehrung"], "von": z["von"], "bis": z["bis"],
         "anfangsbestand": z["anfangsbestand"], "endbestand": z["endbestand"]}
        for z in zeilen
        if z["von"].month == 1 and z["von"].day <= 3  # volle Jahresperioden (Rolling-Fenster ausgeschlossen)
    ]


def listen_schreiben(ergebnis: SteuerZuflussErgebnis, ordner: pathlib.Path) -> dict[str, int]:
    """Schreibt die Einzelfall-Listen für den Steuerberater als CSV (UTF-8 mit BOM, Semikolon) in ``ordner``:
    Ersatzzahlungen, ETF-Beine, Optionskosten ohne Lieferung, Buchungen am Jahreswechsel,
    Quellensteuer zu prüfen. Sie enthalten Kontodaten — der Ordner gehört außerhalb des Repositorys."""
    from analytics.steuer_zufluss import _geld

    ordner.mkdir(parents=True, exist_ok=True)

    def regeldetails(art: str) -> list[dict]:
        return next((r.details for r in ergebnis.regeln_offen if r.art == art), [])

    def schreiben(name: str, kopf: list[str], zeilen: list[list[str]]) -> int:
        with open(ordner / name, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(";".join(kopf) + "\n")
            for z in zeilen:
                f.write(";".join(str(x).replace(";", ",").replace("\n", " ") for x in z) + "\n")
        return len(zeilen)

    anzahl = {}
    anzahl["ersatzzahlungen.csv"] = schreiben(
        "ersatzzahlungen.csv", ["jahr", "datum", "symbol", "betrag_eur", "waehrung", "beschreibung"],
        [[d["datum"][:4], d["datum"], d["symbol"], _geld(d["betrag_eur"]), d["waehrung"], d["beschreibung"]]
         for d in sorted(regeldetails("ersatzzahlung"), key=lambda d: d["datum"])],
    )
    anzahl["etf_beine.csv"] = schreiben(
        "etf_beine.csv", ["leg_id", "symbol", "eroeffnet", "geschlossen", "ergebnis_eur"],
        [[d["leg_id"], d["symbol"], d["eroeffnet"], d["geschlossen"], _geld(d["ergebnis_eur"])]
         for d in sorted(regeldetails("etf_investmentsteuer"), key=lambda d: d["geschlossen"])],
    )
    anzahl["optionskosten_ohne_lieferung.csv"] = schreiben(
        "optionskosten_ohne_lieferung.csv", ["symbol", "zeit", "kosten_eur"],
        [[d["symbol"], d["zeit"], _geld(d["kosten_eur"])] for d in sorted(regeldetails("optionskosten_ohne_lieferung"), key=lambda d: d["zeit"])],
    )
    anzahl["jahreswechsel.csv"] = schreiben(
        "jahreswechsel.csv", ["jahr", "jahr_bei_anderer_regel", "steuerdatum", "vorgang", "symbol", "betrag_eur", "exec_id"],
        [[s.jahr, s.jahr_alternativ, s.steuerdatum.isoformat(), s.vorgang, s.symbol, _geld(s.betrag_eur), s.exec_id or ""]
         for s in ergebnis.stroeme if s.jahr != s.jahr_alternativ],
    )
    anzahl["quellensteuer_zu_pruefen.csv"] = schreiben(
        "quellensteuer_zu_pruefen.csv", ["jahr", "steuerdatum", "zustand", "symbol", "betrag_eur"],
        [[s.jahr, s.steuerdatum.isoformat(), s.vorgang, s.symbol, _geld(s.betrag_eur)]
         for s in ergebnis.stroeme
         if s.vorgang in ("quellensteuer_erstattungsfaehig", "quellensteuer_ungeklaert", "quellensteuer_ersatzzahlung")],
    )
    return anzahl


def ib_daten_laden(db_pfad: str | pathlib.Path) -> tuple[list[dict], frozenset, frozenset]:
    """IBs Realized P/L je Ausführung (EUR), die Schließungen der Aktienbeine mit Lieferung und die offenen Legs."""
    from decimal import Decimal

    from analytics.steuer_zufluss import _LIEFERUNG_EREIGNISSE
    from journal.schema import flex_ib_realized

    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        klasse_je_conid = {z["conid"]: z["asset_class"] for z in v.execute(
            select(instruments.c.conid, instruments.c.asset_class)).mappings()}
        ib_zeilen = [
            {
                "exec_id": z["exec_id"], "jahr": z["handelstag"].year,
                "klasse": klasse_je_conid.get(z["conid"], "?"),
                "eur": Decimal(str(z["fifo_pnl_realized"])) * Decimal(str(z["fx_rate_to_base"])),
            }
            for z in v.execute(
                select(flex_ib_realized.c.exec_id, flex_ib_realized.c.handelstag, flex_ib_realized.c.conid,
                       flex_ib_realized.c.fifo_pnl_realized, flex_ib_realized.c.fx_rate_to_base)
            ).mappings()
            if z["fifo_pnl_realized"] is not None and z["fx_rate_to_base"] is not None
        ]
        ereignis_je_exec = {z["exec_id"]: z["ereignistyp"] for z in v.execute(
            select(executions.c.exec_id, executions.c.ereignistyp)).mappings()}
        lieferung, offen = set(), set()
        for z in v.execute(
            select(legs.c.leg_id, legs.c.conid, legs.c.open_exec_id, legs.c.close_exec_id)
            .where(legs.c.sicht == "konto")
        ).mappings():
            if z["close_exec_id"] is None:
                offen.add(z["leg_id"])
            elif klasse_je_conid.get(z["conid"]) == "STK" and (
                ereignis_je_exec.get(z["open_exec_id"]) in _LIEFERUNG_EREIGNISSE
                or ereignis_je_exec.get(z["close_exec_id"]) in _LIEFERUNG_EREIGNISSE
            ):
                lieferung.add(z["close_exec_id"])
    return ib_zeilen, frozenset(lieferung), frozenset(offen)


def ib_ueberleitung_bericht(db_pfad: str | pathlib.Path, ergebnis: SteuerZuflussErgebnis, daten=None) -> dict[int, dict]:
    """Überleitung IB → Station je Jahr (siehe ``analytics.steuer_ueberleitung``). Nur lesend."""
    from analytics.steuer_ueberleitung import ib_ueberleitung

    ib_zeilen, lieferung, offen = daten or ib_daten_laden(db_pfad)
    return ib_ueberleitung(ergebnis, ib_zeilen, lieferung, offen)
