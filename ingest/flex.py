"""Flex-Query-XML → Rohdaten (AP-02, nachgebessert nach AP-02k).

Liest einen Activity-Flex-Export (§6.2) vollständig ein: die Trades-Sektion
nach ``executions`` (Primärschlüssel ``tradeID``, der quellenübergreifende
Schlüssel aus §5) und die Sektionen OpenPositions, CashTransactions,
CorporateActions, Transfers und SecuritiesInfo je in ihre eigene Tabelle —
seit AP-02n auch den Kontowert je Tag (NAV in Base), Change in NAV und den
Cash Report (``flex_nav_tage``, ``flex_change_in_nav``, ``flex_cash_report``).
Dazu die Instrument-Normalisierung: ``instruments`` wird aus Trades und
SecuritiesInfo gefüllt, ``asset_class`` aus der ``assetCategory``, die
Abwicklungsart aus ``settlementPolicyMethod`` (OF-25).

Grundsätze:

- **Echtes IB-Format** (OF-19, AP-02k): Die Handelszeit steht in ``dateTime``
  im Flex-Zeitformat ``JJJJMMTT;HHMMSS`` (reine Datumsform ergibt Mitternacht
  — dokumentierte Annahme); ``tradeTime`` wird nicht gelesen. Jede Zeile trägt
  ``levelOfDetail``; je Sektion bestimmen die erlaubten Ebenen, ob eine Zeile
  gebucht, nur gezählt oder abgelehnt wird.
- **Idempotent.** Gleicher Dateiinhalt (SHA-256) wird nicht erneut gelaufen;
  überlappende Dateien und erneute Abrufe vereinigen sich ohne Duplikate —
  ``executions`` über ``exec_id``, die Sektionstabellen über
  ``(konto, quell_schluessel)`` (siehe ``_quell_schluessel_vergeben``, OF-09).
- **Reihenfolgeunabhängig.** Stammdaten (``instruments``,
  ``flex_securities_info``) tragen das Periodenende ihrer Quelle; überschrieben
  wird nur aus einer jüngeren Quelle, eine ältere ergänzt allein Leerstellen
  (§6.2, ``_stammsatz_verschmelzen``). Bewegungsdaten sind unveränderlich und
  werden bei Schlüsselkollision verworfen, nicht überschrieben.
- **Kein stilles Verwerfen.** Unbekannte ``assetCategory``, unbekannte
  Ereignis- oder Zusatzkennzeichen in ``notes``, unerwartete Ebenen,
  unbekannte Abwicklungsarten, fehlende Pflichtfelder und nicht parsbare
  Werte führen zu ``ValueError`` mit Nennung des Werts — Abnahme AP-02k. Die
  Datei wird vollständig geparst und geprüft, bevor die erste Zeile
  geschrieben wird.
- **Raw erhalten.** Jede Zeile trägt das vollständige Attributbild in
  ``roh_json``; ``order_reference`` wird roh gespeichert und zusätzlich
  geparst (OA-Muster aus §6.1). Passt der Wert nicht auf das Muster — etwa
  generische TWS-Werkzeugnamen —, bleiben die OA-Felder leer. Kein Rateversuch.

Zeitstempel werden naiv gespeichert, so wie die Quelle sie liefert (OF-04).
"""

import hashlib
import json
import pathlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from journal.db import create_db_engine
from journal.schema import (
    executions,
    flex_cash_report,
    flex_cash_transactions,
    flex_change_in_nav,
    flex_corporate_actions,
    flex_ib_realized,
    flex_nav_tage,
    flex_open_positions,
    flex_securities_info,
    flex_transfers,
    import_runs,
    instruments,
)

# Anlageklassen nach §1.1 — der Wertebereich von instruments.asset_class.
BEKANNTE_ASSET_CLASSES = frozenset({"OPT", "FOP", "FUT", "STK", "CASH"})

# Codes in ``notes`` (§6.1, AP-02k Regel 2): ``notes`` ist eine durch ``;``
# getrennte Liste. Ep/Ex/A bestimmen den Ereignistyp, P/IA/FP/L sind
# Zusatzkennzeichen einer gewöhnlichen Ausführung — P etwa eine Teilausführung
# (OF-07, OF-20). Zwei Ereigniscodes in einer Liste sind mehrdeutig und brechen
# ab; jeder andere Code ebenfalls (OF-08).
EREIGNIS_CODES = {"Ep": "expiry", "Ex": "exercise", "A": "assignment"}
ZUSATZ_CODES = frozenset({"P", "IA", "FP", "L"})

# SecurityInfo.settlementPolicyMethod → instruments.abwicklungsart (OF-25,
# AP-02k Regel 6). Fehlt das Feld, bleibt die Spalte leer; ein anderer
# gesetzter Wert bricht ab.
ABWICKLUNGSARTEN = {"Delivery": "lieferung", "Cash": "barausgleich"}

# Ebenen je Sektion (AP-02k Regel 3): gebucht wird nur die Buchungsebene;
# Zusammenfassungen (SUMMARY, CLOSED_LOT) werden gezählt, aber nicht gebucht.
# Alles andere bricht mit Nennung der Sektion und Ebene ab. <Lot>-Elemente
# sind ein eigener Tag und werden von ``./Trades/Trade`` ohnehin nicht
# gefunden; der Abschnitt FIFOPerformanceSummaryInBase wird nicht gelesen.
BUCH_EBENEN = {
    "Trades": frozenset({"EXECUTION"}),
    "OpenPositions": frozenset({"SUMMARY"}),
    "CashTransactions": frozenset({"DETAIL"}),
    "CorporateActions": frozenset({"DETAIL"}),
    "Transfers": frozenset({"TRANSFER"}),
}
ZAEHL_EBENEN = {
    "CashTransactions": frozenset({"SUMMARY"}),
    "CorporateActions": frozenset({"SUMMARY", "CLOSED_LOT"}),
}

# Strukturierte OptionApp-Referenz nach §6.1. Order-Nummern sind nicht global
# eindeutig; Schlüssel ist erst das Paar (oa_trade, oa_order) — AP-04.
OA_REFERENZ_MUSTER = re.compile(
    r"^OptionsApp: Trade (\d+), Leg (\d+), (Open Order|Close Order|Profit Target) (\d+)$"
)

SEITEN = frozenset({"BUY", "SELL"})
RECHTE = frozenset({"P", "C"})


@dataclass(frozen=True)
class ImportErgebnis:
    """Bericht über einen Importlauf: gelesen, neu, übersprungen (AP-02).

    ``nicht_gebuchte_zeilen`` zählt die nach AP-02k Regel 3 gelesenen, aber
    nicht gebuchten Zeilen (SUMMARY, CLOSED_LOT) — sie sind kein Fehler, aber
    auch kein Bestandteil der Rohdaten.
    """

    zeilen_gesamt: int
    zeilen_neu: int
    nicht_gebuchte_zeilen: int = 0

    @property
    def zeilen_uebersprungen(self) -> int:
        return self.zeilen_gesamt - self.zeilen_neu


@dataclass
class _DateiInhalt:
    """Vollständig geparste und geprüfte Datei — erst dann wird geschrieben."""

    executions: list[dict] = field(default_factory=list)
    open_positions: list[dict] = field(default_factory=list)
    cash_transactions: list[dict] = field(default_factory=list)
    corporate_actions: list[dict] = field(default_factory=list)
    transfers: list[dict] = field(default_factory=list)
    securities_info: list[dict] = field(default_factory=list)
    # AP-02n: Kontowert je Tag, Change in NAV, Cash Report.
    nav_tage: list[dict] = field(default_factory=list)
    change_in_nav: list[dict] = field(default_factory=list)
    cash_report: list[dict] = field(default_factory=list)
    # AP-02p: IBs realisiertes Ergebnis je Ausführung (nur Zeilen mit Wert).
    ib_realized: list[dict] = field(default_factory=list)
    # conid → zusammengeführte Instrumentendaten; Trades zuerst, dann
    # SecuritiesInfo (liefert den Multiplikator).
    instruments: dict[int, dict] = field(default_factory=dict)
    # Gezählte, aber nicht gebuchte Zeilen (SUMMARY/CLOSED_LOT, Regel 3).
    nicht_gebuchte_zeilen: int = 0
    # Trägt mindestens eine Zeile ein Modell-Attribut? Dann hat IB jedes Feld
    # zum realisierten Ergebnis abgeschaltet (OF-21, AP-02k Regel 8).
    traegt_modell: bool = False
    zeitraum_von: date | None = None
    zeitraum_bis: date | None = None


# ---------------------------------------------------------------------------
# Elementare Wertumwandlungen — jeder Fehler nennt Feld und Wert
# ---------------------------------------------------------------------------


def _pflichtwert(attribute: dict, name: str, kontext: str) -> str:
    wert = attribute.get(name, "").strip()
    if not wert:
        raise ValueError(f"{kontext}: Pflichtfeld '{name}' fehlt oder ist leer")
    return wert


def _dezimalwert(attribute: dict, name: str, kontext: str) -> Decimal | None:
    rohwert = attribute.get(name, "").strip()
    if not rohwert:
        return None
    try:
        return Decimal(rohwert)
    except InvalidOperation as fehler:
        raise ValueError(f"{kontext}: '{name}' ist keine Zahl: {rohwert!r}") from fehler


def _pflichtdezimal(attribute: dict, name: str, kontext: str) -> Decimal:
    wert = _dezimalwert(attribute, name, kontext)
    if wert is None:
        raise ValueError(f"{kontext}: Pflichtfeld '{name}' fehlt oder ist leer")
    return wert


def _ganzzahlwert(attribute: dict, name: str, kontext: str) -> int:
    rohwert = _pflichtwert(attribute, name, kontext)
    try:
        return int(rohwert)
    except ValueError as fehler:
        raise ValueError(f"{kontext}: '{name}' ist keine ganze Zahl: {rohwert!r}") from fehler


def _datumwert(rohwert: str, kontext: str) -> date:
    try:
        return datetime.strptime(rohwert, "%Y%m%d").date()
    except ValueError as fehler:
        raise ValueError(f"{kontext}: Datum unlesbar: {rohwert!r}") from fehler


def _zeitpunktwert(rohwert: str, feld: str, kontext: str) -> datetime:
    """Flex-Zeitform ``JJJJMMTT;HHMMSS`` (AP-02k Regel 1, OF-19).

    Die reine Datumsform ``JJJJMMTT`` ergibt 00:00:00 — eine dokumentierte
    Annahme, die Quelle liefert keine Uhrzeit dazu. Jede andere Form (etwa
    die ISO-T-Form, die IB in anderen Reporten nutzt) bricht mit Nennung des
    Felds und Werts ab.
    """
    try:
        return datetime.strptime(rohwert, "%Y%m%d;%H%M%S")
    except ValueError:
        pass
    try:
        return datetime.strptime(rohwert, "%Y%m%d")
    except ValueError as fehler:
        raise ValueError(
            f"{kontext}: Feld {feld!r} ist keine der Zeitformen JJJJMMTT;HHMMSS "
            f"oder JJJJMMTT: {rohwert!r}"
        ) from fehler


def _asset_class(attribute: dict, kontext: str) -> str:
    wert = _pflichtwert(attribute, "assetCategory", kontext)
    if wert not in BEKANNTE_ASSET_CLASSES:
        raise ValueError(
            f"{kontext}: unbekannte assetCategory {wert!r} — bekannte Werte: "
            f"{sorted(BEKANNTE_ASSET_CLASSES)}. Abbruch statt stillem Verwerfen."
        )
    return wert


def _ereignistyp_aus_notes(attribute: dict, kontext: str) -> tuple[str, str | None]:
    """Liefert (ereignistyp, ereignis_code) aus ``notes`` (§6.1, AP-02k Regel 2).

    ``notes`` ist eine durch ``;`` getrennte Liste: Ep/Ex/A bestimmen den
    Ereignistyp (höchstens einer), P/IA/FP/L sind Zusatzkennzeichen und
    ergeben ``trade``. ``ereignis_code`` trägt den vollen Rohwert.
    """
    rohwert = attribute.get("notes", "").strip()
    if not rohwert:
        return "trade", None
    ereignisse: list[str] = []
    for code in rohwert.split(";"):
        if code in EREIGNIS_CODES:
            ereignisse.append(code)
        elif code not in ZUSATZ_CODES:
            raise ValueError(
                f"{kontext}: unbekannter Code {code!r} in notes {rohwert!r} — "
                f"Ereigniscodes: {sorted(EREIGNIS_CODES)}, Zusatzkennzeichen: "
                f"{sorted(ZUSATZ_CODES)}. Abbruch statt stillem Verwerfen (OF-08)."
            )
    if len(ereignisse) > 1:
        raise ValueError(
            f"{kontext}: mehrdeutige Ereigniscodes {sorted(ereignisse)} in notes "
            f"{rohwert!r} — nur einer darf gesetzt sein, sonst wäre die Zuordnung geraten."
        )
    if ereignisse:
        return EREIGNIS_CODES[ereignisse[0]], rohwert
    return "trade", rohwert


def _ebene_pruefen(attribute: dict, sektion: str, kontext: str) -> bool:
    """Prüft ``levelOfDetail`` einer Sektionszeile (AP-02k Regel 3).

    Rückgabe ``True`` heißt buchen (Buchungsebene der Sektion), ``False``
    heißt zählen, aber nicht buchen (Zusammenfassungsebene). Jede andere oder
    fehlende Ebene bricht mit Nennung von Sektion und Ebene ab.
    """
    ebene = attribute.get("levelOfDetail", "").strip()
    if not ebene:
        raise ValueError(
            f"{kontext}: Pflichtfeld 'levelOfDetail' fehlt (Sektion {sektion})"
        )
    if ebene in BUCH_EBENEN[sektion]:
        return True
    if ebene in ZAEHL_EBENEN.get(sektion, frozenset()):
        return False
    raise ValueError(
        f"{kontext}: unerwartete Ebene levelOfDetail={ebene!r} (Sektion {sektion}) — "
        f"gebucht werden {sorted(BUCH_EBENEN[sektion])}"
        + (
            f", gezählt {sorted(ZAEHL_EBENEN[sektion])}"
            if sektion in ZAEHL_EBENEN
            else ""
        )
        + ". Abbruch statt stillem Verwerfen."
    )


def _abwicklungsart(attribute: dict, kontext: str) -> str | None:
    """``settlementPolicyMethod`` → ``abwicklungsart`` (OF-25, AP-02k Regel 6).

    Nur SecurityInfo-Zeilen tragen das Feld; auf Trade-Zeilen bleibt es leer
    und überschreibt dadurch beim Verschmelzen keinen vorhandenen Stand.
    """
    rohwert = attribute.get("settlementPolicyMethod", "").strip()
    if not rohwert:
        return None
    if rohwert not in ABWICKLUNGSARTEN:
        raise ValueError(
            f"{kontext}: unbekannter Wert in settlementPolicyMethod: {rohwert!r} — "
            f"bekannte Werte: {sorted(ABWICKLUNGSARTEN)}. Abbruch statt stillem Verwerfen."
        )
    return ABWICKLUNGSARTEN[rohwert]


def _exec_batch(ib_exec_id: str | None, kontext: str) -> str | None:
    """Erste zwei Punkt-Segmente der ibExecID — Gruppierungsschlüssel (§6.1)."""
    if not ib_exec_id:
        return None
    segmente = ib_exec_id.split(".")
    if len(segmente) < 2:
        raise ValueError(
            f"{kontext}: ibExecID hat nicht das Format <batch>.<order>...: {ib_exec_id!r}"
        )
    return ".".join(segmente[:2])


def _oa_felder(order_reference: str | None) -> dict:
    """Vier OA-Felder aus strukturierter Referenz; sonst leer (kein Rateversuch)."""
    treffer = OA_REFERENZ_MUSTER.match(order_reference or "")
    if treffer is None:
        return {"oa_trade": None, "oa_leg": None, "oa_rolle": None, "oa_order": None}
    trade, leg, rolle, order = treffer.groups()
    return {"oa_trade": trade, "oa_leg": leg, "oa_rolle": rolle, "oa_order": order}


def _roh_json(attribute: dict) -> str:
    return json.dumps(dict(attribute), sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Zeilen je Sektion
# ---------------------------------------------------------------------------


def _trade_kontext(attribute: dict, nummer: int) -> str:
    """Benennt eine Trades-Zeile auch dann, wenn ihr Schlüssel fehlt.

    Reihenfolge in der Datei, dazu die Merkmale, an denen die Zeile im Export
    wiederzufinden ist. Ohne das wäre eine Fehlermeldung zur fehlenden
    ``tradeID`` nicht nachverfolgbar.
    """
    kennzeichen = ("transactionID", "ibExecID", "conid", "symbol", "dateTime")
    merkmale = [
        f"{name} {attribute[name]!r}"
        for name in kennzeichen
        if attribute.get(name, "").strip()
    ]
    zusatz = f" ({', '.join(merkmale)})" if merkmale else ""
    return f"Trades-Zeile {nummer}{zusatz}"


def _execution_zeile(konto: str, trade: ET.Element, nummer: int) -> dict:
    attribute = dict(trade.attrib)
    # exec_id ist tradeID, nicht transactionID (§5, OF-10). Fehlt sie, bricht
    # der Import ab: über drei Exporte mit 19.425 Zeilen ist tradeID lückenlos
    # und eindeutig, auch auf allen 5.944 Ereigniszeilen. Eine Lücke wäre ein
    # Defekt des Exports und soll auffallen, nicht kompensiert werden.
    exec_id = attribute.get("tradeID", "").strip()
    if not exec_id:
        raise ValueError(
            f"{_trade_kontext(attribute, nummer)}: Pflichtfeld 'tradeID' fehlt oder ist leer. "
            "tradeID ist der Primärschlüssel von executions (§5) und im Export "
            "lückenlos gefüllt; eine fehlende tradeID ist ein Defekt der Quelle "
            "und kein Fall für einen Ersatzschlüssel."
        )
    kontext = f"Ausführung {exec_id}"
    side = _pflichtwert(attribute, "buySell", kontext)
    if side not in SEITEN:
        raise ValueError(f"{kontext}: unbekannte Seite {side!r} in buySell")
    right = attribute.get("putCall", "").strip() or None
    if right is not None and right not in RECHTE:
        raise ValueError(f"{kontext}: unbekanntes Recht {right!r} in putCall")
    ereignistyp, ereignis_code = _ereignistyp_aus_notes(attribute, kontext)
    # Regel 1: Die Handelszeit steht in dateTime (JJJJMMTT;HHMMSS); das Feld
    # tradeTime existiert im echten Export nicht und wird nicht gelesen (OF-19).
    handelszeit = _zeitpunktwert(
        _pflichtwert(attribute, "dateTime", kontext), "dateTime", kontext
    )
    ib_exec_id = attribute.get("ibExecID", "").strip() or None
    order_reference = attribute.get("orderReference", "").strip() or None
    expiry = attribute.get("expiry", "").strip()
    return {
        "exec_id": exec_id,
        # Sekundär, für die Abstimmung mit dem Broker (§5). Ohne Pflicht: der
        # Schlüssel ist tradeID, transactionID ist Beleg.
        "transaction_id": attribute.get("transactionID", "").strip() or None,
        "konto": konto,
        "conid": _ganzzahlwert(attribute, "conid", kontext),
        "symbol": _pflichtwert(attribute, "symbol", kontext),
        "sec_type": _asset_class(attribute, kontext),
        "expiry": _datumwert(expiry, kontext) if expiry else None,
        "strike": _dezimalwert(attribute, "strike", kontext),
        "right": right,
        "side": side,
        "menge": _pflichtdezimal(attribute, "quantity", kontext),
        "preis": _pflichtdezimal(attribute, "tradePrice", kontext),
        "waehrung": _pflichtwert(attribute, "currency", kontext),
        "multiplikator": _dezimalwert(attribute, "multiplier", kontext),
        "kommission": _dezimalwert(attribute, "ibCommission", kontext),
        "kommission_waehrung": attribute.get("ibCommissionCurrency", "").strip() or None,
        "handelszeit": handelszeit,
        "ib_exec_id": ib_exec_id,
        "exec_batch": _exec_batch(ib_exec_id, kontext),
        "ib_order_id": attribute.get("ibOrderID", "").strip() or None,
        "order_reference": order_reference,
        **_oa_felder(order_reference),
        "boerse": attribute.get("exchange", "").strip() or None,
        "ereignistyp": ereignistyp,
        "ereignis_code": ereignis_code,
        # Regel 6: closePrice ist der Abrechnungskurs von Zuteilung und
        # Ausübung (OF-25); bei gewöhnlichen Ausführungen bleibt er leer.
        "schlusskurs": _dezimalwert(attribute, "closePrice", kontext),
        # fxRateToBase: der Kurs, zu dem IB die Ausführung in die
        # Basiswährung bucht — Grundlage des IB-vergleichbaren Geldtests
        # (OF-23, OF-29). Kein Standardwert, falls die Quelle es
        # ausnahmsweise nicht liefert.
        "buchungskurs": _dezimalwert(attribute, "fxRateToBase", kontext),
        "roh_json": _roh_json(attribute),
        "qualitaetsstufe": "A",
    }


def _quell_id(attribute: dict, typ: str | None) -> str | None:
    """Identität einer Sektionszeile mit ID (AP-02k Regel 4).

    ``transactionID`` **und** ``type`` zusammen — die Interest-Paid/-Received-
    Paare echter Exporte teilen sich eine transactionID und sind doch zwei
    Buchungen. OpenPositions tragen keinen type; dort bleibt er leer. Ohne
    transactionID liefert die Funktion None und die Identität bildet sich aus
    dem Inhalt (``_quell_schluessel_vergeben``).
    """
    transaction_id = attribute.get("transactionID", "").strip()
    if not transaction_id:
        return None
    return f"{transaction_id}|{typ or ''}"


def _open_position_zeile(konto: str, position: ET.Element, statement_bis: date | None) -> dict:
    attribute = dict(position.attrib)
    kontext = f"OpenPosition conid {attribute.get('conid', '?')}"
    report_date = attribute.get("reportDate", "").strip()
    if report_date:
        stichtag = _datumwert(report_date, kontext)
    elif statement_bis is not None:
        stichtag = statement_bis
    else:
        raise ValueError(
            f"{kontext}: weder reportDate noch toDate des FlexStatements — Stichtag unbestimmt"
        )
    return {
        "konto": konto,
        "quell_id": _quell_id(attribute, None),
        "stichtag": stichtag,
        "conid": _ganzzahlwert(attribute, "conid", kontext),
        "symbol": _pflichtwert(attribute, "symbol", kontext),
        "asset_class": _asset_class(attribute, kontext),
        "menge": _pflichtdezimal(attribute, "position", kontext),
        "kostenbasis_preis": _dezimalwert(attribute, "costBasisPrice", kontext),
        "fifo_pnl_unrealisiert": _dezimalwert(attribute, "fifoPnlUnrealized", kontext),
        "waehrung": _pflichtwert(attribute, "currency", kontext),
        "roh_json": _roh_json(attribute),
    }


def _cash_transaction_zeile(konto: str, buchung: ET.Element) -> dict:
    attribute = dict(buchung.attrib)
    kontext = f"CashTransaction {attribute.get('type', '?')}"
    typ = _pflichtwert(attribute, "type", kontext)
    return {
        "konto": konto,
        "quell_id": _quell_id(attribute, typ),
        "datum": _zeitpunktwert(
            _pflichtwert(attribute, "dateTime", kontext), "dateTime", kontext
        ),
        "typ": typ,
        "betrag": _pflichtdezimal(attribute, "amount", kontext),
        "waehrung": _pflichtwert(attribute, "currency", kontext),
        "beschreibung": attribute.get("description", "").strip() or None,
        "roh_json": _roh_json(attribute),
    }


def _ereignis_zeile(konto: str, ereignis: ET.Element, sektion: str) -> dict:
    """Gemeinsame Form für CorporateActions und Transfers (Rohdaten, AP-02)."""
    attribute = dict(ereignis.attrib)
    kontext = f"{sektion} {attribute.get('type', '?')}"
    typ = _pflichtwert(attribute, "type", kontext)
    conid = attribute.get("conid", "").strip()
    if conid:
        try:
            conid_wert = int(conid)
        except ValueError as fehler:
            raise ValueError(f"{kontext}: 'conid' ist keine ganze Zahl: {conid!r}") from fehler
    else:
        conid_wert = None
    return {
        "konto": konto,
        "quell_id": _quell_id(attribute, typ),
        "conid": conid_wert,
        "typ": typ,
        "datum": _zeitpunktwert(
            _pflichtwert(attribute, "dateTime", kontext), "dateTime", kontext
        ),
        "beschreibung": attribute.get("description", "").strip() or None,
        "roh_json": _roh_json(attribute),
    }


def _ib_realized_zeile(konto: str, ausfuehrung: dict, attribute: dict) -> dict | None:
    """IBs ``fifoPnlRealized`` einer Ausführung (AP-02p) oder ``None``, wenn die
    Datei keinen Wert liefert — leer heißt „nicht geliefert", ``0`` ist ein Wert.
    Der Wert steht in Positionswährung, netto nach Kommission; ``fxRateToBase`` ist
    IBs Kurs in die Basiswährung."""
    kontext = f"Ausführung {ausfuehrung['exec_id']}"
    wert = _dezimalwert(attribute, "fifoPnlRealized", kontext)
    if wert is None:
        return None
    return {
        "konto": konto,
        "quell_schluessel": f"trade:{ausfuehrung['exec_id']}",
        "exec_id": ausfuehrung["exec_id"],
        "handelstag": ausfuehrung["handelszeit"].date(),
        "conid": ausfuehrung["conid"],
        "waehrung": ausfuehrung["waehrung"],
        "fifo_pnl_realized": wert,
        "fx_rate_to_base": _dezimalwert(attribute, "fxRateToBase", kontext),
    }


def _nav_zeile(konto: str, element: ET.Element) -> dict:
    """Ein Kontowert je Tag (``EquitySummaryByReportDateInBase``, AP-02n).
    Pflicht sind ``reportDate``, ``currency`` und ``total``; leere
    Teilwerte bleiben leer (keine stille 0)."""
    attribute = dict(element.attrib)
    kontext = f"EquitySummaryByReportDateInBase {attribute.get('reportDate', '?')}"
    datum = _datumwert(_pflichtwert(attribute, "reportDate", kontext), kontext)
    return dict(
        konto=konto,
        quell_schluessel=f"nav:{datum.isoformat()}",
        datum=datum,
        waehrung=_pflichtwert(attribute, "currency", kontext),
        cash=_dezimalwert(attribute, "cash", kontext),
        aktien=_dezimalwert(attribute, "stock", kontext),
        optionen=_dezimalwert(attribute, "options", kontext),
        rohstoffe=_dezimalwert(attribute, "commodities", kontext),
        fonds=_dezimalwert(attribute, "funds", kontext),
        anleihen=_dezimalwert(attribute, "bonds", kontext),
        dividenden_abgrenzung=_dezimalwert(attribute, "dividendAccruals", kontext),
        zins_abgrenzung=_dezimalwert(attribute, "interestAccruals", kontext),
        gesamt=_pflichtdezimal(attribute, "total", kontext),
        roh_json=_roh_json(attribute),
    )


def _change_in_nav_zeile(konto: str, element: ET.Element) -> dict:
    """Überleitung des Kontowerts über den Statementzeitraum (AP-02n)."""
    attribute = dict(element.attrib)
    kontext = "ChangeInNAV"
    von = _datumwert(_pflichtwert(attribute, "fromDate", kontext), kontext)
    bis = _datumwert(_pflichtwert(attribute, "toDate", kontext), kontext)
    return dict(
        konto=konto,
        quell_schluessel=f"cinav:{von.isoformat()}|{bis.isoformat()}",
        von=von,
        bis=bis,
        waehrung=_pflichtwert(attribute, "currency", kontext),
        anfangswert=_pflichtdezimal(attribute, "startingValue", kontext),
        endwert=_pflichtdezimal(attribute, "endingValue", kontext),
        realisiert=_dezimalwert(attribute, "realized", kontext),
        veraenderung_unrealisiert=_dezimalwert(attribute, "changeInUnrealized", kontext),
        marktbewertung=_dezimalwert(attribute, "mtm", kontext),
        ein_auszahlungen=_dezimalwert(attribute, "depositsWithdrawals", kontext),
        dividenden=_dezimalwert(attribute, "dividends", kontext),
        zinsen=_dezimalwert(attribute, "interest", kontext),
        kommissionen=_dezimalwert(attribute, "commissions", kontext),
        waehrungseffekt=_dezimalwert(attribute, "fxTranslation", kontext),
        twr=_dezimalwert(attribute, "twr", kontext),
        roh_json=_roh_json(attribute),
    )


def _cash_report_zeile(konto: str, element: ET.Element) -> dict:
    """Cash je Währung über den Statementzeitraum (AP-02n). Jede Ebene wird
    gespeichert — die Ebene steht im Schlüssel, nichts wird verworfen."""
    attribute = dict(element.attrib)
    kontext = f"CashReportCurrency {attribute.get('currency', '?')}"
    von = _datumwert(_pflichtwert(attribute, "fromDate", kontext), kontext)
    bis = _datumwert(_pflichtwert(attribute, "toDate", kontext), kontext)
    waehrung = _pflichtwert(attribute, "currency", kontext)
    ebene = attribute.get("levelOfDetail", "").strip() or None
    return dict(
        konto=konto,
        quell_schluessel=f"cash:{von.isoformat()}|{bis.isoformat()}|{waehrung}|{ebene or ''}",
        von=von,
        bis=bis,
        waehrung=waehrung,
        ebene=ebene,
        anfangsbestand=_dezimalwert(attribute, "startingCash", kontext),
        endbestand=_dezimalwert(attribute, "endingCash", kontext),
        ein_auszahlungen=_dezimalwert(attribute, "depositWithdrawals", kontext),
        kommissionen=_dezimalwert(attribute, "commissions", kontext),
        dividenden=_dezimalwert(attribute, "dividends", kontext),
        zinsen=_dezimalwert(attribute, "brokerInterest", kontext),
        waehrungseffekt=_dezimalwert(attribute, "fxTranslationGainLoss", kontext),
        roh_json=_roh_json(attribute),
    )


def _securities_info_zeile(info: ET.Element, periodenende: date | None) -> dict:
    attribute = dict(info.attrib)
    kontext = f"SecurityInfo conid {attribute.get('conid', '?')}"
    expiry = attribute.get("expiry", "").strip()
    return {
        "conid": _ganzzahlwert(attribute, "conid", kontext),
        "symbol": _pflichtwert(attribute, "symbol", kontext),
        "underlying": attribute.get("underlyingSymbol", "").strip() or None,
        "asset_class": _asset_class(attribute, kontext),
        "expiry": _datumwert(expiry, kontext) if expiry else None,
        "strike": _dezimalwert(attribute, "strike", kontext),
        "right": attribute.get("putCall", "").strip() or None,
        "multiplikator": _dezimalwert(attribute, "multiplier", kontext),
        "waehrung": attribute.get("currency", "").strip() or None,
        "roh_json": _roh_json(attribute),
        "quell_periodenende": periodenende,
    }


def _instrument_daten(attribute: dict, kontext: str, periodenende: date | None) -> dict:
    """Instrumentenfelder aus Trade- oder SecurityInfo-Attributen."""
    expiry = attribute.get("expiry", "").strip()
    return {
        "conid": _ganzzahlwert(attribute, "conid", kontext),
        "symbol": _pflichtwert(attribute, "symbol", kontext),
        "underlying": attribute.get("underlyingSymbol", "").strip() or None,
        "asset_class": _asset_class(attribute, kontext),
        "expiry": _datumwert(expiry, kontext) if expiry else None,
        "strike": _dezimalwert(attribute, "strike", kontext),
        "right": attribute.get("putCall", "").strip() or None,
        "multiplikator": _dezimalwert(attribute, "multiplier", kontext),
        "waehrung": attribute.get("currency", "").strip() or None,
        "abwicklungsart": _abwicklungsart(attribute, kontext),
        "quell_periodenende": periodenende,
    }


def _ist_aelter(neu: date | None, alt: date | None) -> bool:
    """Liegt das Periodenende von ``neu`` vor dem von ``alt``?

    Ein leeres Periodenende heißt „unbekannt": gegen eine datierte Quelle ist
    es die schwächere Angabe, gegen eine ebenfalls undatierte gleichrangig.
    """
    if alt is None:
        return False
    if neu is None:
        return True
    return neu < alt


def _stammsatz_verschmelzen(vorhanden: dict, neu: dict) -> dict:
    """Führt zwei Stände desselben Stammsatzes zusammen (§6.2, AP-02a).

    Maßgeblich ist das Periodenende der Quelle, nicht die Importreihenfolge:

    - Eine **ältere** Quelle füllt nur, was noch leer ist. Sie überschreibt
      nichts — das ist der Kern der Reihenfolgeunabhängigkeit.
    - Jede andere Quelle setzt ihre besetzten Felder durch.
    - ``None`` löscht nie einen vorhandenen Wert.

    Damit liefern beide Importreihenfolgen dasselbe Ergebnis, solange sich die
    Perioden unterscheiden: Die jüngere Quelle gewinnt, ob sie nun zuerst oder
    zuletzt eingelesen wurde.

    Bei **gleichem** Periodenende gewinnt der spätere Stand. Innerhalb einer
    Datei ist das gewollt: Trades werden zuerst übernommen, die eigens dafür
    vorgesehene Sektion ``SecuritiesInfo`` danach — sie liefert Multiplikator
    und Währung des Instruments und soll die Beifelder der Handelszeile
    ablösen. Über Dateigrenzen hinweg bleibt für gleiche Perioden ein Rest an
    Reihenfolgeabhängigkeit; er ist ohne weitere Grundlage nicht auflösbar und
    in OF-09 festgehalten.
    """
    neu_gewinnt = not _ist_aelter(neu["quell_periodenende"], vorhanden["quell_periodenende"])
    zusammen = dict(vorhanden)
    for feld, wert in neu.items():
        if wert is None or feld == "quell_periodenende":
            continue
        if neu_gewinnt or zusammen.get(feld) is None:
            zusammen[feld] = wert
    if neu_gewinnt:
        zusammen["quell_periodenende"] = neu["quell_periodenende"]
    return zusammen


def _instrument_uebernehmen(
    inhalt: _DateiInhalt, attribute: dict, kontext: str, periodenende: date | None
) -> None:
    """Führt Instrumentendaten innerhalb einer Datei zusammen.

    Dieselbe Regel wie gegen die Datenbank (``_stammsatz_verschmelzen``): eine
    Datei kann mehrere FlexStatements mit verschiedenen Perioden enthalten.
    """
    daten = _instrument_daten(attribute, kontext, periodenende)
    conid = daten["conid"]
    vorhanden = inhalt.instruments.get(conid)
    inhalt.instruments[conid] = (
        daten if vorhanden is None else _stammsatz_verschmelzen(vorhanden, daten)
    )


# ---------------------------------------------------------------------------
# Datei parsen
# ---------------------------------------------------------------------------


def _parse_datei(datei: pathlib.Path) -> _DateiInhalt:
    inhalt = _DateiInhalt()
    try:
        wurzel = ET.parse(datei).getroot()
    except ET.ParseError as fehler:
        raise ValueError(f"{datei}: kein lesbares XML — {fehler}") from fehler
    statements = wurzel.findall("./FlexStatements/FlexStatement")
    if not statements:
        raise ValueError(f"{datei}: kein FlexStatement gefunden")

    # Regel 8: Sobald eine einzige Zeile ein Modell trägt, hat IB für die
    # ganze Abfrage jedes Realized-P&L-Feld genullt (OF-21). Maßgeblich ist
    # der Export, nicht die Zeile — ein Lauf ist entweder brauchbar oder nicht.
    inhalt.traegt_modell = any(
        (element.get("model") or "").strip() for element in wurzel.iter()
    )

    gesehene_exec_ids: set[str] = set()
    for statement in statements:
        konto = (statement.get("accountId") or "").strip()
        if not konto:
            raise ValueError(f"{datei}: FlexStatement ohne accountId")
        von = _stichtag(statement, "fromDate", datei)
        bis = _stichtag(statement, "toDate", datei)
        if von is not None:
            inhalt.zeitraum_von = (
                von if inhalt.zeitraum_von is None else min(inhalt.zeitraum_von, von)
            )
        if bis is not None:
            inhalt.zeitraum_bis = (
                bis if inhalt.zeitraum_bis is None else max(inhalt.zeitraum_bis, bis)
            )

        for nummer, trade in enumerate(statement.findall("./Trades/Trade"), start=1):
            # <Lot>-Elemente sind ein eigener Tag und werden hier nicht
            # gefunden; eine <Trade>-Zeile unerwarteter Ebene bricht ab.
            attribute = dict(trade.attrib)
            _ebene_pruefen(attribute, "Trades", _trade_kontext(attribute, nummer))
            zeile = _execution_zeile(konto, trade, nummer)
            if zeile["exec_id"] in gesehene_exec_ids:
                raise ValueError(f"{datei}: tradeID {zeile['exec_id']} mehrfach in der Datei")
            gesehene_exec_ids.add(zeile["exec_id"])
            inhalt.executions.append(zeile)
            ib_zeile = _ib_realized_zeile(konto, zeile, attribute)
            if ib_zeile is not None:
                inhalt.ib_realized.append(ib_zeile)
            _instrument_uebernehmen(
                inhalt, dict(trade.attrib), f"Ausführung {zeile['exec_id']}", bis
            )

        for position in statement.findall("./OpenPositions/OpenPosition"):
            attribute = dict(position.attrib)
            kontext = f"OpenPosition conid {attribute.get('conid', '?')}"
            _ebene_pruefen(attribute, "OpenPositions", kontext)
            inhalt.open_positions.append(_open_position_zeile(konto, position, bis))
        for buchung in statement.findall("./CashTransactions/CashTransaction"):
            attribute = dict(buchung.attrib)
            kontext = f"CashTransaction {attribute.get('type', '?')}"
            if _ebene_pruefen(attribute, "CashTransactions", kontext):
                inhalt.cash_transactions.append(_cash_transaction_zeile(konto, buchung))
            else:
                inhalt.nicht_gebuchte_zeilen += 1
        for ereignis in statement.findall("./CorporateActions/CorporateAction"):
            attribute = dict(ereignis.attrib)
            kontext = f"CorporateAction {attribute.get('type', '?')}"
            if _ebene_pruefen(attribute, "CorporateActions", kontext):
                inhalt.corporate_actions.append(_ereignis_zeile(konto, ereignis, "CorporateAction"))
            else:
                inhalt.nicht_gebuchte_zeilen += 1
        for transfer in statement.findall("./Transfers/Transfer"):
            attribute = dict(transfer.attrib)
            kontext = f"Transfer {attribute.get('type', '?')}"
            _ebene_pruefen(attribute, "Transfers", kontext)
            inhalt.transfers.append(_ereignis_zeile(konto, transfer, "Transfer"))
        for info in statement.findall("./SecuritiesInfo/SecurityInfo"):
            zeile = _securities_info_zeile(info, bis)
            inhalt.securities_info.append(zeile)
            _instrument_uebernehmen(
                inhalt, dict(info.attrib), f"SecurityInfo conid {zeile['conid']}", bis
            )
        for element in statement.findall("./EquitySummaryInBase/EquitySummaryByReportDateInBase"):
            inhalt.nav_tage.append(_nav_zeile(konto, element))
        for element in statement.findall("./ChangeInNAV"):
            inhalt.change_in_nav.append(_change_in_nav_zeile(konto, element))
        for element in statement.findall("./CashReport/CashReportCurrency"):
            inhalt.cash_report.append(_cash_report_zeile(konto, element))

    _quell_schluessel_vergeben(inhalt.open_positions, "OpenPositions", datei)
    _quell_schluessel_vergeben(inhalt.cash_transactions, "CashTransactions", datei)
    _quell_schluessel_vergeben(inhalt.corporate_actions, "CorporateActions", datei)
    _quell_schluessel_vergeben(inhalt.transfers, "Transfers", datei)
    return inhalt


def _quell_schluessel_vergeben(zeilen: list[dict], sektion: str, datei: pathlib.Path) -> None:
    """Vergibt je Sektionszeile den Quellschlüssel (eindeutig je Konto, OF-09).

    - Mit ``transactionID``: ``tx:<id>|<typ>`` — Identität ist das Paar aus
      transactionID und type (AP-02k Regel 4). Dieselbe Kombination zweimal
      in einer Datei ist ein Fehler — welche der beiden Zeilen gilt, wäre
      geraten.
    - Ohne: ``inhalt:<sha256>#<n>`` über ``roh_json`` (bei offenen Positionen
      zusätzlich über den Stichtag). ``n`` zählt inhaltsgleiche Zeilen
      derselben Datei durch: Zwei gleiche Gebühren bleiben zwei Buchungen, ein
      erneuter Abruf trifft dieselben Schlüssel und legt nichts doppelt an.
    """
    gesehene_ids: set[tuple[str, str]] = set()
    inhaltszaehler: dict[tuple[str, str], int] = {}
    for zeile in zeilen:
        konto = zeile["konto"]
        quell_id = zeile.pop("quell_id")
        if quell_id is not None:
            if (konto, quell_id) in gesehene_ids:
                raise ValueError(
                    f"{datei}: Identität {quell_id!r} (transactionID|type) mehrfach "
                    f"in Sektion {sektion} (Konto {konto})"
                )
            gesehene_ids.add((konto, quell_id))
            zeile["quell_schluessel"] = f"tx:{quell_id}"
            continue
        basis = zeile["roh_json"]
        if "stichtag" in zeile:
            basis = f"{zeile['stichtag'].isoformat()}|{basis}"
        inhalt_hash = hashlib.sha256(basis.encode("utf-8")).hexdigest()
        laufende_nummer = inhaltszaehler.get((konto, inhalt_hash), 0) + 1
        inhaltszaehler[(konto, inhalt_hash)] = laufende_nummer
        zeile["quell_schluessel"] = f"inhalt:{inhalt_hash}#{laufende_nummer}"


def _stichtag(statement: ET.Element, attribut: str, datei: pathlib.Path) -> date | None:
    rohwert = (statement.get(attribut) or "").strip()
    if not rohwert:
        return None
    return _datumwert(rohwert, f"{datei.name}, FlexStatement/{attribut}")


# ---------------------------------------------------------------------------
# Schreiben
# ---------------------------------------------------------------------------


def _import_run_anlegen(verbindung, datei_hash: str, inhalt: _DateiInhalt) -> int:
    # importiert_am ist ein lokaler Vorgangszeitpunkt (naiv, wie alle
    # Zeitstempel der Datenbank, OF-04) — der nächtliche Lauf des Task
    # Schedulers (§3) lässt sich so in Ortszeit lesen.
    ergebnis = verbindung.execute(
        insert(import_runs).values(
            quelle="flex",
            datei_hash=datei_hash,
            importiert_am=datetime.now(),
            zeitraum_von=inhalt.zeitraum_von,
            zeitraum_bis=inhalt.zeitraum_bis,
            qualitaetsstufe="A",
            # Modell-Exporte tragen keine brauchbaren Realized-P&L-Werte
            # (OF-21, Regel 8); jeder Vergleich muss sie verweigern.
            realized_pnl_verfuegbar=not inhalt.traegt_modell,
            zeilen_gesamt=len(inhalt.executions),
            zeilen_neu=0,
        )
    )
    return ergebnis.inserted_primary_key[0]


def _executions_schreiben(verbindung, inhalt: _DateiInhalt, lauf_id: int) -> int:
    """Fügt neue Ausführungen ein; Rückgabe: Anzahl der eingefügten Zeilen."""
    ids = [zeile["exec_id"] for zeile in inhalt.executions]
    vorhandene = set()
    if ids:
        vorhandene = set(
            verbindung.execute(
                select(executions.c.exec_id).where(executions.c.exec_id.in_(ids))
            ).scalars()
        )
    neue = [
        {**zeile, "import_run_id": lauf_id}
        for zeile in inhalt.executions
        if zeile["exec_id"] not in vorhandene
    ]
    # Sammel-Insert statt Zeile für Zeile: hält die Schreibsperre kurz (Regel 9).
    if neue:
        verbindung.execute(insert(executions), neue)
    return len(neue)


def _sektionszeilen_schreiben(verbindung, tabelle, zeilen: list[dict], lauf_id: int) -> None:
    """Fügt nur Zeilen ein, deren (konto, quell_schluessel) noch unbekannt ist.

    Vorhandene Rohzeilen werden nie überschrieben; ``import_run_id`` bleibt beim
    Lauf, der die Zeile zuerst sah.
    """
    if not zeilen:
        return
    anweisung = sqlite_insert(tabelle).on_conflict_do_nothing(
        index_elements=[tabelle.c.konto, tabelle.c.quell_schluessel]
    )
    verbindung.execute(anweisung, [{**zeile, "import_run_id": lauf_id} for zeile in zeilen])


def _stammsatz_schreiben(verbindung, tabelle, daten: dict) -> None:
    """Legt einen Stammsatz an oder schreibt ihn nach §6.2 fort.

    Der vorhandene Satz wird gelesen, mit dem neuen verschmolzen
    (``_stammsatz_verschmelzen``) und nur bei tatsächlicher Änderung
    geschrieben — die Importreihenfolge bleibt dadurch beliebig. Felder,
    die die Flex-Quelle gar nicht liefert (etwa ``instruments.tickwert``),
    bleiben unangetastet: sie stehen nicht in ``daten``.
    """
    conid = daten["conid"]
    vorhanden = verbindung.execute(
        select(tabelle).where(tabelle.c.conid == conid)
    ).mappings().first()
    if vorhanden is None:
        verbindung.execute(insert(tabelle).values(**daten))
        return
    alter_stand = {feld: vorhanden[feld] for feld in daten}
    neuer_stand = _stammsatz_verschmelzen(alter_stand, daten)
    aenderungen = {
        feld: wert for feld, wert in neuer_stand.items() if wert != alter_stand[feld]
    }
    if aenderungen:
        verbindung.execute(
            update(tabelle).where(tabelle.c.conid == conid).values(**aenderungen)
        )


def _securities_info_schreiben(verbindung, zeilen: list[dict]) -> None:
    """Stammdaten: conid ist der Schlüssel, die jüngere Quelle gewinnt (§6.2)."""
    for zeile in zeilen:
        _stammsatz_schreiben(verbindung, flex_securities_info, zeile)


def _instrumente_schreiben(verbindung, daten_je_conid: dict[int, dict]) -> None:
    """``instruments`` anlegen beziehungsweise auf den jüngeren Stand heben."""
    for daten in daten_je_conid.values():
        _stammsatz_schreiben(verbindung, instruments, daten)


def nachtragen_realisiert(db_pfad: str | pathlib.Path, datei_pfad: str | pathlib.Path) -> int:
    """Trägt IBs ``fifoPnlRealized`` aus einer **bereits importierten** Datei nach
    (AP-02p). Der Import überspringt eine bekannte Datei vollständig; für Dateien,
    die vor Einführung der Tabelle ``flex_ib_realized`` eingelesen wurden, liest
    dieser Weg nur dieses Feld und ergänzt, was fehlt. Nichts anderes wird
    geschrieben, vorhandene Zeilen bleiben (Regel 4); wiederholbar.

    Rückgabe: Zahl der neu eingefügten Zeilen.
    """
    datei = pathlib.Path(datei_pfad)
    if not datei.is_file():
        raise FileNotFoundError(f"Importdatei nicht gefunden: {datei}")
    datei_hash = hashlib.sha256(datei.read_bytes()).hexdigest()
    inhalt = _parse_datei(datei)
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(
            select(import_runs.c.id).where(import_runs.c.datei_hash == datei_hash)
        ).first()
        if lauf is None:
            raise ValueError(
                f"{datei.name}: Datei ist noch nicht importiert — erst `journal import`, "
                "dann nachtragen"
            )
        vorher = verbindung.execute(
            select(func.count()).select_from(flex_ib_realized)
        ).scalar_one()
        _sektionszeilen_schreiben(verbindung, flex_ib_realized, inhalt.ib_realized, lauf[0])
        nachher = verbindung.execute(
            select(func.count()).select_from(flex_ib_realized)
        ).scalar_one()
    return nachher - vorher


def _fremdes_konto_ablehnen(verbindung, inhalt: "_DateiInhalt", datei: pathlib.Path) -> None:
    """Einzelkonto-Grenze schon am Import (AP-17e, R04): Kennt die Datenbank ein Konto, wird eine
    Datei eines anderen Kontos (z. B. Paper, DU...) abgelehnt, bevor etwas geschrieben wird. Ein
    gemischter Bestand verfälscht Matching, NAV und Steuer; ein anderes Konto braucht eine eigene
    Datenbank."""
    listen = (
        inhalt.executions, inhalt.open_positions, inhalt.cash_transactions,
        inhalt.corporate_actions, inhalt.transfers, inhalt.nav_tage, inhalt.change_in_nav,
        inhalt.cash_report, inhalt.ib_realized,
    )
    in_datei = {zeile["konto"] for liste in listen for zeile in liste}
    bekannt = {z[0] for z in verbindung.execute(select(executions.c.konto).distinct()) if z[0]}
    fremd = sorted(in_datei - bekannt) if bekannt else []
    if fremd:
        raise ValueError(
            f"{datei.name}: Konto {', '.join(fremd)} gehört nicht zu dieser Datenbank "
            f"(bekannt: {', '.join(sorted(bekannt))}) — nicht importiert. Ein zweites Konto "
            "(z. B. Paper) braucht eine eigene Datenbank (Einzelkonto-Grenze, AP-17e)."
        )


def import_flex_file(db_pfad: str | pathlib.Path, datei_pfad: str | pathlib.Path) -> ImportErgebnis:
    """Importiert eine Flex-XML-Datei idempotent in die Datenbank (AP-02).

    Rückgabe: ``ImportErgebnis`` mit ``zeilen_gesamt`` (gelesene Trade-Zeilen)
    und ``zeilen_neu`` (eingefügte). Doppelter Import derselben Datei liefert
    null neue Zeilen; überlappende Dateien vereinigen sich über ``exec_id``.
    """
    datei = pathlib.Path(datei_pfad)
    if not datei.is_file():
        raise FileNotFoundError(f"Importdatei nicht gefunden: {datei}")

    datei_hash = hashlib.sha256(datei.read_bytes()).hexdigest()
    # Vollständig parsen und prüfen — erst danach beginnt die Transaktion.
    inhalt = _parse_datei(datei)

    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        _fremdes_konto_ablehnen(verbindung, inhalt, datei)
        bekannter_lauf = verbindung.execute(
            select(import_runs.c.id).where(import_runs.c.datei_hash == datei_hash)
        ).first()
        if bekannter_lauf is not None:
            # Gleicher Dateiinhalt: nichts zu tun (P1, Abnahme AP-02).
            return ImportErgebnis(
                zeilen_gesamt=len(inhalt.executions),
                zeilen_neu=0,
                nicht_gebuchte_zeilen=inhalt.nicht_gebuchte_zeilen,
            )

        lauf_id = _import_run_anlegen(verbindung, datei_hash, inhalt)
        zeilen_neu = _executions_schreiben(verbindung, inhalt, lauf_id)
        verbindung.execute(
            update(import_runs).where(import_runs.c.id == lauf_id).values(zeilen_neu=zeilen_neu)
        )
        _sektionszeilen_schreiben(verbindung, flex_open_positions, inhalt.open_positions, lauf_id)
        _sektionszeilen_schreiben(
            verbindung, flex_cash_transactions, inhalt.cash_transactions, lauf_id
        )
        _sektionszeilen_schreiben(
            verbindung, flex_corporate_actions, inhalt.corporate_actions, lauf_id
        )
        _sektionszeilen_schreiben(verbindung, flex_transfers, inhalt.transfers, lauf_id)
        _sektionszeilen_schreiben(verbindung, flex_nav_tage, inhalt.nav_tage, lauf_id)
        _sektionszeilen_schreiben(verbindung, flex_change_in_nav, inhalt.change_in_nav, lauf_id)
        _sektionszeilen_schreiben(verbindung, flex_cash_report, inhalt.cash_report, lauf_id)
        _sektionszeilen_schreiben(verbindung, flex_ib_realized, inhalt.ib_realized, lauf_id)
        _securities_info_schreiben(verbindung, inhalt.securities_info)
        _instrumente_schreiben(verbindung, inhalt.instruments)

        return ImportErgebnis(
            zeilen_gesamt=len(inhalt.executions),
            zeilen_neu=zeilen_neu,
            nicht_gebuchte_zeilen=inhalt.nicht_gebuchte_zeilen,
        )
