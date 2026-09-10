"""Flex-Query-XML → Rohdaten (AP-02).

Liest einen Activity-Flex-Export (§6.2) vollständig ein: die Trades-Sektion
nach ``executions`` (Primärschlüssel ``transactionID``, der quellenübergreifende
Schlüssel aus §5) und die Sektionen OpenPositions, CashTransactions,
CorporateActions, Transfers und SecuritiesInfo je in ihre eigene Tabelle.
Dazu die Instrument-Normalisierung: ``instruments`` wird aus Trades und
SecuritiesInfo gefüllt, ``asset_class`` aus der ``assetCategory``.

Grundsätze:

- **Idempotent.** Gleicher Dateiinhalt (SHA-256) wird nicht erneut gelaufen;
  überlappende Dateien und erneute Abrufe vereinigen sich ohne Duplikate —
  ``executions`` über ``exec_id``, die Sektionstabellen über
  ``(konto, quell_schluessel)`` (siehe ``_quell_schluessel_vergeben``, OF-09).
- **Kein stilles Verwerfen.** Unbekannte ``assetCategory``, unbekannte
  Ereigniscodes, fehlende Pflichtfelder und nicht parsbare Werte führen zu
  ``ValueError`` mit Nennung des Werts — Abnahme AP-02. Die Datei wird
  vollständig geparst und geprüft, bevor die erste Zeile geschrieben wird.
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

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from journal.db import create_db_engine
from journal.schema import (
    executions,
    flex_cash_transactions,
    flex_corporate_actions,
    flex_open_positions,
    flex_securities_info,
    flex_transfers,
    import_runs,
    instruments,
)

# Anlageklassen nach §1.1 — der Wertebereich von instruments.asset_class.
BEKANNTE_ASSET_CLASSES = frozenset({"OPT", "FOP", "FUT", "STK", "CASH"})

# Ereigniscodes aus §6.1, Zuordnung nach AP-02-Auftrag. Leer heißt trade.
# Der Code P ist fachlich nicht klassifiziert (OF-07) und trägt 'unbekannt'.
EREIGNISTYPEN = {
    "": "trade",
    "Ep": "expiry",
    "Ex": "exercise",
    "A": "assignment",
    "P": "unbekannt",
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
    """Bericht über einen Importlauf: gelesen, neu, übersprungen (AP-02)."""

    zeilen_gesamt: int
    zeilen_neu: int

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
    # conid → zusammengeführte Instrumentendaten; Trades zuerst, dann
    # SecuritiesInfo (liefert den Multiplikator).
    instruments: dict[int, dict] = field(default_factory=dict)
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


def _zeitpunktwert(rohwert: str, kontext: str) -> datetime:
    try:
        return datetime.strptime(rohwert, "%Y%m%d %H:%M:%S")
    except ValueError as fehler:
        raise ValueError(f"{kontext}: Zeitpunkt unlesbar: {rohwert!r}") from fehler


def _asset_class(attribute: dict, kontext: str) -> str:
    wert = _pflichtwert(attribute, "assetCategory", kontext)
    if wert not in BEKANNTE_ASSET_CLASSES:
        raise ValueError(
            f"{kontext}: unbekannte assetCategory {wert!r} — bekannte Werte: "
            f"{sorted(BEKANNTE_ASSET_CLASSES)}. Abbruch statt stillem Verwerfen."
        )
    return wert


def _ereignistyp_aus_notes(attribute: dict, kontext: str) -> tuple[str, str | None]:
    """Liefert (ereignistyp, ereignis_code) aus ``notes`` (§6.1, OF-07/OF-08)."""
    code = attribute.get("notes", "").strip()
    if code not in EREIGNISTYPEN:
        raise ValueError(
            f"{kontext}: unbekannter Ereigniscode in notes: {code!r} — bekannte "
            f"Codes: {sorted(code for code in EREIGNISTYPEN if code)}. "
            "Abbruch statt stillem Verwerfen (OF-08)."
        )
    return EREIGNISTYPEN[code], (code or None)


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


def _execution_zeile(konto: str, trade: ET.Element) -> dict:
    attribute = dict(trade.attrib)
    exec_id = _pflichtwert(attribute, "transactionID", "Trade")
    kontext = f"Ausführung {exec_id}"
    side = _pflichtwert(attribute, "buySell", kontext)
    if side not in SEITEN:
        raise ValueError(f"{kontext}: unbekannte Seite {side!r} in buySell")
    right = attribute.get("putCall", "").strip() or None
    if right is not None and right not in RECHTE:
        raise ValueError(f"{kontext}: unbekanntes Recht {right!r} in putCall")
    ereignistyp, ereignis_code = _ereignistyp_aus_notes(attribute, kontext)
    handelszeit = _zeitpunktwert(_pflichtwert(attribute, "tradeTime", kontext), kontext)
    ib_exec_id = attribute.get("ibExecID", "").strip() or None
    order_reference = attribute.get("orderReference", "").strip() or None
    expiry = attribute.get("expiry", "").strip()
    return {
        "exec_id": exec_id,
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
        "roh_json": _roh_json(attribute),
        "qualitaetsstufe": "A",
    }


def _quell_id(attribute: dict) -> str | None:
    """``transactionID`` einer Sektionszeile, falls die Quelle eine liefert."""
    return attribute.get("transactionID", "").strip() or None


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
        "quell_id": _quell_id(attribute),
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
    return {
        "konto": konto,
        "quell_id": _quell_id(attribute),
        "datum": _zeitpunktwert(_pflichtwert(attribute, "dateTime", kontext), kontext),
        "typ": _pflichtwert(attribute, "type", kontext),
        "betrag": _pflichtdezimal(attribute, "amount", kontext),
        "waehrung": _pflichtwert(attribute, "currency", kontext),
        "beschreibung": attribute.get("description", "").strip() or None,
        "roh_json": _roh_json(attribute),
    }


def _ereignis_zeile(konto: str, ereignis: ET.Element, sektion: str) -> dict:
    """Gemeinsame Form für CorporateActions und Transfers (Rohdaten, AP-02)."""
    attribute = dict(ereignis.attrib)
    kontext = f"{sektion} {attribute.get('type', '?')}"
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
        "quell_id": _quell_id(attribute),
        "conid": conid_wert,
        "typ": _pflichtwert(attribute, "type", kontext),
        "datum": _zeitpunktwert(_pflichtwert(attribute, "dateTime", kontext), kontext),
        "beschreibung": attribute.get("description", "").strip() or None,
        "roh_json": _roh_json(attribute),
    }


def _securities_info_zeile(info: ET.Element) -> dict:
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
    }


def _instrument_daten(attribute: dict, kontext: str) -> dict:
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
    }


def _instrument_uebernehmen(inhalt: _DateiInhalt, attribute: dict, kontext: str) -> None:
    """Führt Instrumentendaten zusammen: Trades zuerst, SecuritiesInfo danach.

    Neuere Angaben ergänzen leere Felder und überschreiben abweichende —
    der jüngste Stand der Quelle gewinnt (OF-09); ``None`` löscht nichts.
    """
    daten = _instrument_daten(attribute, kontext)
    conid = daten["conid"]
    aktuell = inhalt.instruments.get(conid, {})
    aktuell.update({feld: wert for feld, wert in daten.items() if wert is not None})
    inhalt.instruments[conid] = aktuell


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

        for trade in statement.findall("./Trades/Trade"):
            zeile = _execution_zeile(konto, trade)
            if zeile["exec_id"] in gesehene_exec_ids:
                raise ValueError(
                    f"{datei}: transactionID {zeile['exec_id']} mehrfach in der Datei"
                )
            gesehene_exec_ids.add(zeile["exec_id"])
            inhalt.executions.append(zeile)
            _instrument_uebernehmen(inhalt, dict(trade.attrib), f"Ausführung {zeile['exec_id']}")

        for position in statement.findall("./OpenPositions/OpenPosition"):
            inhalt.open_positions.append(_open_position_zeile(konto, position, bis))
        for buchung in statement.findall("./CashTransactions/CashTransaction"):
            inhalt.cash_transactions.append(_cash_transaction_zeile(konto, buchung))
        for ereignis in statement.findall("./CorporateActions/CorporateAction"):
            inhalt.corporate_actions.append(_ereignis_zeile(konto, ereignis, "CorporateAction"))
        for transfer in statement.findall("./Transfers/Transfer"):
            inhalt.transfers.append(_ereignis_zeile(konto, transfer, "Transfer"))
        for info in statement.findall("./SecuritiesInfo/SecurityInfo"):
            zeile = _securities_info_zeile(info)
            inhalt.securities_info.append(zeile)
            _instrument_uebernehmen(
                inhalt, dict(info.attrib), f"SecurityInfo conid {zeile['conid']}"
            )

    _quell_schluessel_vergeben(inhalt.open_positions, "OpenPositions", datei)
    _quell_schluessel_vergeben(inhalt.cash_transactions, "CashTransactions", datei)
    _quell_schluessel_vergeben(inhalt.corporate_actions, "CorporateActions", datei)
    _quell_schluessel_vergeben(inhalt.transfers, "Transfers", datei)
    return inhalt


def _quell_schluessel_vergeben(zeilen: list[dict], sektion: str, datei: pathlib.Path) -> None:
    """Vergibt je Sektionszeile den Quellschlüssel (eindeutig je Konto, OF-09).

    - Mit ``transactionID``: ``tx:<id>``. Dieselbe ID zweimal in einer Datei
      ist ein Fehler — welche der beiden Zeilen gilt, wäre geraten.
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
                    f"{datei}: transactionID {quell_id} mehrfach in Sektion {sektion} "
                    f"(Konto {konto})"
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


def _securities_info_schreiben(verbindung, zeilen: list[dict]) -> None:
    """Stammdaten: conid ist der Schlüssel, der jüngste Stand gewinnt (OF-09)."""
    for zeile in zeilen:
        verbindung.execute(
            sqlite_insert(flex_securities_info)
            .values(**zeile)
            .on_conflict_do_update(
                index_elements=[flex_securities_info.c.conid],
                set_={feld: zeile[feld] for feld in zeile if feld != "conid"},
            )
        )


def _instrumente_schreiben(verbindung, daten_je_conid: dict[int, dict]) -> None:
    """``instruments`` anlegen beziehungsweise auf den jüngsten Stand heben."""
    for conid, daten in daten_je_conid.items():
        vorhanden = verbindung.execute(
            select(instruments).where(instruments.c.conid == conid)
        ).mappings().first()
        if vorhanden is None:
            verbindung.execute(insert(instruments).values(**daten))
            continue
        neue_werte = {
            feld: wert
            for feld, wert in daten.items()
            if wert is not None and vorhanden[feld] != wert
        }
        if neue_werte:
            verbindung.execute(
                update(instruments).where(instruments.c.conid == conid).values(**neue_werte)
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
        bekannter_lauf = verbindung.execute(
            select(import_runs.c.id).where(import_runs.c.datei_hash == datei_hash)
        ).first()
        if bekannter_lauf is not None:
            # Gleicher Dateiinhalt: nichts zu tun (P1, Abnahme AP-02).
            return ImportErgebnis(zeilen_gesamt=len(inhalt.executions), zeilen_neu=0)

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
        _securities_info_schreiben(verbindung, inhalt.securities_info)
        _instrumente_schreiben(verbindung, inhalt.instruments)

        return ImportErgebnis(zeilen_gesamt=len(inhalt.executions), zeilen_neu=zeilen_neu)
