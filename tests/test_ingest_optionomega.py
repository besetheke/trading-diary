"""Abnahmetest für AP-12a, Teil Import: ``ingest.optionomega``.

Fixture ``fixtures/optionomega/oo_beispiel.csv`` (frei erfunden, sieben
Zeilen, UTF-8 mit BOM wie der echte Export; Inhalt im Docstring von
``erzeugen_beispiel.py``).

Von Hand:
- 7 Zeilen, alle neu; derselbe Inhalt ein zweites Mal → kein neuer Lauf.
- R1: Prämie 230, P/L 224, 1 Kontrakt, Eröffnung 2026-03-02 09:32,
  Schluss 2026-03-02 16:00, geschlossen.
- R4 (``Backtest Completed``) gilt als offen.
- R6: Verfall ``Dec 31`` → 2025-12-31, ``Jan 2`` → 2026-01-02 (Eröffnung
  2025-12-30; Januar liegt vor Dezember, also Folgejahr).
- Leere ``Strategy``: Dateiname ohne Endung als Strategie.
- Ein neuerer Export mit R4 geschlossen (Expired, P/L 150) überschreibt die
  Zeile: 0 neu, 1 aktualisiert, R4 danach geschlossen mit P/L 150.
"""

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ingest.optionomega import OoFormatFehler, import_optionomega_file, legs_lesen
from journal.db import create_db_engine
from journal.schema import oo_trades

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "optionomega" / "oo_beispiel.csv"
IC = "-26 -IC Test- 9:32"


def _zeilen(db):
    with create_db_engine(db).connect() as v:
        return [dict(z) for z in v.execute(select(oo_trades)).mappings()]


def test_import_und_idempotenz(migrated_db):
    e = import_optionomega_file(migrated_db, FIXTURE)
    assert (e.zeilen_gesamt, e.zeilen_neu, e.zeilen_aktualisiert, e.schon_importiert) == (
        7, 7, 0, False)
    e2 = import_optionomega_file(migrated_db, FIXTURE)
    assert e2.schon_importiert is True
    assert len(_zeilen(migrated_db)) == 7


def test_werte_einer_zeile(migrated_db):
    import_optionomega_file(migrated_db, FIXTURE)
    r1 = next(z for z in _zeilen(migrated_db)
              if z["strategie"] == IC and z["eroeffnet"] == datetime(2026, 3, 2, 9, 32))
    assert (r1["praemie"], r1["pl"], r1["kontrakte"], r1["basiswert"]) == (
        Decimal("230"), Decimal("224"), 1, "SPX")
    assert r1["geschlossen"] == datetime(2026, 3, 2, 16, 0)
    assert r1["offen"] is False
    assert r1["grund"] == "Expired"
    r4 = next(z for z in _zeilen(migrated_db)
              if z["strategie"] == IC and z["eroeffnet"] == datetime(2026, 3, 5, 9, 32))
    assert r4["offen"] is True


def test_jahreswechsel_im_verfall():
    legs = legs_lesen("1 Dec 31 6000 P STO 10.00 | 1 Jan 2 6000 P BTO 15.00", date(2025, 12, 30))
    assert [(x.menge, x.seite, x.right, x.strike, x.expiry) for x in legs] == [
        (1, "S", "P", Decimal("6000"), date(2025, 12, 31)),
        (1, "B", "P", Decimal("6000"), date(2026, 1, 2)),
    ]


def test_kaputte_leg_grammatik():
    with pytest.raises(OoFormatFehler):
        legs_lesen("1 Mar 2 6800 P XYZ 2.00", date(2026, 3, 2))


def test_leere_strategie_heisst_wie_die_datei(migrated_db, tmp_path):
    with open(FIXTURE, encoding="utf-8-sig", newline="") as f:
        zeilen = list(csv.reader(f))
    for z in zeilen[1:]:
        z[17] = ""
    datei = tmp_path / "trade-log1145.csv"
    with open(datei, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(zeilen)
    import_optionomega_file(migrated_db, datei)
    assert {z["strategie"] for z in _zeilen(migrated_db)} == {"trade-log1145"}


def test_neuerer_export_ueberschreibt(migrated_db, tmp_path):
    import_optionomega_file(migrated_db, FIXTURE)
    with open(FIXTURE, encoding="utf-8-sig", newline="") as f:
        zeilen = list(csv.reader(f))
    for z in zeilen[1:]:
        if z[17] == IC and z[0] == "2026-03-05":
            z[10], z[11], z[7] = "Expired", "150", "16:00:00"
    neu = tmp_path / "oo_neu.csv"
    with open(neu, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, quoting=csv.QUOTE_ALL).writerows(zeilen)
    e = import_optionomega_file(migrated_db, neu)
    assert (e.zeilen_neu, e.zeilen_aktualisiert) == (0, 1)
    r4 = next(z for z in _zeilen(migrated_db)
              if z["strategie"] == IC and z["eroeffnet"] == datetime(2026, 3, 5, 9, 32))
    assert (r4["offen"], r4["pl"], r4["geschlossen"]) == (
        False, Decimal("150"), datetime(2026, 3, 5, 16, 0))
