"""Import des Option-Omega-Backtest-Exports (AP-12a).

Format: ``auftraege/AP-12-anhang-oo-format.md`` — CSV, 28 Spalten, jedes Feld
in Anführungszeichen, UTF-8 (mit oder ohne BOM). Eine Zeile = ein
Backtest-Trade mit den Legs seiner Eröffnung.

- Schlüssel einer Zeile: (``Strategy``, Eröffnung, ``Legs``) — mehrere
  Strategien öffnen zum selben Scan-Zeitpunkt (OF-76, Punkt 1).
- Zeiten sind US-Ostküstenzeit; belegt am Echtbestand: OO-Eröffnungen fallen
  minutengenau auf die IB-Ausführungen der Bots (OF-76, Punkt 4).
- Dieselbe Datei zweimal: kein zweiter Lauf (Hash in ``import_runs``).
- Ein **neuerer Export** überschreibt die Werte einer bekannten Zeile — ein
  Backtest ist eine Rechnung, keine Buchung (Annahme, OF-83). Der Lauf, der
  zuletzt geschrieben hat, steht in ``import_run_id``.
- ``Reason For Close = Backtest Completed``: am Ende des Backtests noch offen.
- Leere ``Strategy`` (OO exportiert einen unbenannten Backtest so): der
  Dateiname ohne Endung steht als Strategie (Annahme, OF-83).
"""

import csv
import hashlib
import json
import pathlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import insert, select, update

from engine.oo_zuordnung import Leg, kontrakte
from journal.db import create_db_engine
from journal.schema import import_runs, oo_trades

QUELLE = "optionomega"
OFFEN_GRUND = "Backtest Completed"
KOPF_PFLICHT = ("Date Opened", "Time Opened", "Legs", "Premium", "Date Closed", "Time Closed",
                "Reason For Close", "P/L", "No. of Contracts", "Underlying", "Strategy")
MONATE = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_LEG = re.compile(
    r"^(\d+) ([A-Z][a-z]{2}) (\d{1,2}) (\d+(?:\.\d+)?) ([CP]) (STO|BTO) (-?\d+(?:\.\d+)?)$")


class OoFormatFehler(ValueError):
    """Die Datei entspricht nicht dem OO-Format — Abbruch mit Zeilenangabe."""


@dataclass
class OoImportErgebnis:
    zeilen_gesamt: int = 0
    zeilen_neu: int = 0
    zeilen_aktualisiert: int = 0
    schon_importiert: bool = False


def legs_lesen(text: str, eroeffnet: date) -> list[Leg]:
    """Leg-Grammatik ``<Menge> <Mon> <Tag> <Strike> <C|P> <STO|BTO> <Preis>``.
    Das Jahr fehlt: Jahr der Eröffnung, liegt der Monat davor, das Folgejahr."""
    legs = []
    for teil in text.split("|"):
        m = _LEG.match(teil.strip())
        if not m or m.group(2) not in MONATE:
            raise OoFormatFehler(f"Leg nicht lesbar: {teil.strip()!r}")
        menge, mon, tag, strike, right, aktion, _ = m.groups()
        monat = MONATE[mon]
        jahr = eroeffnet.year + (1 if monat < eroeffnet.month else 0)
        legs.append(Leg(int(menge), "S" if aktion == "STO" else "B", right, Decimal(strike),
                        date(jahr, monat, int(tag))))
    return legs


def _zahl(wert: str, feld: str, kontext: str, pflicht: bool = True) -> Decimal | None:
    if wert in (None, ""):
        if pflicht:
            raise OoFormatFehler(f"{kontext}: {feld} fehlt")
        return None
    try:
        return Decimal(wert)
    except InvalidOperation as e:
        raise OoFormatFehler(f"{kontext}: {feld} ist keine Zahl: {wert!r}") from e


def _zeile_lesen(z: dict, nr: int, ersatzname: str) -> dict:
    kontext = f"Zeile {nr}"
    try:
        eroeffnet = datetime.fromisoformat(f"{z['Date Opened']} {z['Time Opened']}")
        geschlossen = (datetime.fromisoformat(f"{z['Date Closed']} {z['Time Closed']}")
                       if z["Date Closed"] else None)
    except ValueError as e:
        raise OoFormatFehler(f"{kontext}: Datum/Uhrzeit nicht lesbar") from e
    try:
        legs = legs_lesen(z["Legs"], eroeffnet.date())
    except OoFormatFehler as e:
        raise OoFormatFehler(f"{kontext}: {e}") from e
    offen = z["Reason For Close"] == OFFEN_GRUND
    return dict(
        strategie=z["Strategy"] or ersatzname, eroeffnet=eroeffnet,
        geschlossen=None if offen else geschlossen,
        basiswert=z["Underlying"], legs_roh=z["Legs"], kontrakte=kontrakte(legs),
        praemie=_zahl(z["Premium"], "Premium", kontext),
        pl=_zahl(z["P/L"], "P/L", kontext),
        kommission_eroeffnung=_zahl(z.get("Opening Commissions + Fees"), "Kommission", kontext,
                                    pflicht=False),
        kommission_schluss=_zahl(z.get("Closing Commissions + Fees"), "Kommission", kontext,
                                 pflicht=False),
        eroeffnungskurs=_zahl(z.get("Opening Price"), "Opening Price", kontext, pflicht=False),
        schlusskurs=_zahl(z.get("Closing Price"), "Closing Price", kontext, pflicht=False),
        grund=z["Reason For Close"], offen=offen,
        roh_json=json.dumps(z, ensure_ascii=False, sort_keys=True),
    )


def _datei_lesen(datei: pathlib.Path) -> list[dict]:
    with open(datei, encoding="utf-8-sig", newline="") as f:
        leser = csv.DictReader(f)
        fehlt = [k for k in KOPF_PFLICHT if k not in (leser.fieldnames or [])]
        if fehlt:
            raise OoFormatFehler(f"{datei.name}: Spalten fehlen: {', '.join(fehlt)}")
        return [_zeile_lesen(z, nr, datei.stem) for nr, z in enumerate(leser, start=2)]


def import_optionomega_file(db_pfad, datei) -> OoImportErgebnis:
    datei = pathlib.Path(datei)
    inhalt = datei.read_bytes()
    datei_hash = hashlib.sha256(inhalt).hexdigest()
    zeilen = _datei_lesen(datei)
    ergebnis = OoImportErgebnis(zeilen_gesamt=len(zeilen))
    engine = create_db_engine(db_pfad)
    with engine.begin() as v:
        if v.execute(select(import_runs.c.id).where(
                import_runs.c.quelle == QUELLE, import_runs.c.datei_hash == datei_hash)).first():
            ergebnis.schon_importiert = True
            return ergebnis
        tage = [z["eroeffnet"].date() for z in zeilen]
        lauf = v.execute(insert(import_runs).values(
            quelle=QUELLE, datei_hash=datei_hash, importiert_am=datetime.now(),
            zeitraum_von=min(tage) if tage else None, zeitraum_bis=max(tage) if tage else None,
            qualitaetsstufe="B", zeilen_gesamt=len(zeilen), zeilen_neu=0,
        )).inserted_primary_key[0]
        felder = [k for k in zeilen[0] if k not in ("strategie", "eroeffnet", "legs_roh")] \
            if zeilen else []
        for z in zeilen:
            alt = v.execute(select(oo_trades).where(
                oo_trades.c.strategie == z["strategie"], oo_trades.c.eroeffnet == z["eroeffnet"],
                oo_trades.c.legs_roh == z["legs_roh"])).mappings().first()
            if alt is None:
                v.execute(insert(oo_trades).values(import_run_id=lauf, **z))
                ergebnis.zeilen_neu += 1
            elif any(alt[k] != z[k] for k in felder if k != "roh_json"):
                v.execute(update(oo_trades).where(oo_trades.c.id == alt["id"]).values(
                    import_run_id=lauf, **{k: z[k] for k in felder}))
                ergebnis.zeilen_aktualisiert += 1
        v.execute(update(import_runs).where(import_runs.c.id == lauf).values(
            zeilen_neu=ergebnis.zeilen_neu))
    return ergebnis


def import_optionomega_ordner(db_pfad, ordner) -> list[tuple[str, OoImportErgebnis]]:
    """Alle ``*.csv`` eines Ordners, nach Änderungszeit (ältester zuerst) — der
    neueste Export schreibt zuletzt."""
    dateien = sorted(pathlib.Path(ordner).glob("*.csv"), key=lambda p: p.stat().st_mtime)
    return [(d.name, import_optionomega_file(db_pfad, d)) for d in dateien]
