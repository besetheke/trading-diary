"""Abnahmetests für AP-13r2: laufende OA-Trades fortschreiben, Ordnerimport,
`GET /oa-stand`. Vertrag: auftraege/AP-13r2.md. Geschrieben durch das starke
Modell — für die Umsetzung unveränderlich. Erwartungen von Hand gerechnet.

Fixtures (frei erfunden, `fixtures/optionapp/erzeugen_fortschreibung.py`):
  Stand 1: 6001 RUNNING (Profit 0,00 $), 6002 CLOSED 48,48 $.
  Stand 2: 6001 EXPIRED, Schluss 0, Profit 174,24 $, Schluss 06.03.2026 16:00;
           6002 unverändert; 6003 neu EXPIRED 118,48 $.
  Andere Strategie: 6001 unter „SPX: IC" statt „XSP: IF7" → Abbruch, 6003 wird
           nicht gebucht (die Datei wird ganz oder gar nicht übernommen).

Regel (Vertrag 1): Nur ein gespeicherter Trade mit Status RUNNING darf
fortgeschrieben werden, und nur bei gleicher Eröffnungszeit und Strategie. Der
vorige Rohstand bleibt erhalten: `roh_json` wird zu {"zeile": …, "_vorher": …}
(Zeilenbild als Liste, Spalte 10 = Status).
Vertrag 2: Kommt nach einem abgeschlossenen Stand ein RUNNING-Stand derselben
Nummer (älterer Export), bleibt der abgeschlossene stehen — kein Fehler.
Vertrag 3: Zwei verschiedene abgeschlossene Stände bleiben ein Fehler
(bestehender Test test_doppelte_nummer_mit_abweichendem_inhalt_bricht_ab).
"""

import json
import shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

from ingest.optionapp import import_optionapp_file, import_optionapp_ordner
from journal.db import create_db_engine
from journal.schema import optionapp_legs, optionapp_trades

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optionapp"


def _trades(db_pfad) -> dict:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        zeilen = verbindung.execute(select(optionapp_trades)).mappings().all()
    return {z["oa_trade"]: dict(z) for z in zeilen}


def _anzahl_legs(db_pfad, trade_id) -> int:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return len(
            verbindung.execute(
                select(optionapp_legs).where(optionapp_legs.c.optionapp_trade_id == trade_id)
            ).all()
        )


def test_laufender_trade_wird_fortgeschrieben(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_1.xlsx")
    e = import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_2.xlsx")
    t = _trades(migrated_db)
    assert sorted(t) == ["6001", "6002", "6003"]
    assert (e.zeilen_gesamt, e.zeilen_neu, e.zeilen_fortgeschrieben) == (3, 1, 1)
    assert e.zeilen_uebersprungen == 1
    neu = t["6001"]
    assert neu["status"] == "EXPIRED"
    assert neu["profit"] == Decimal("174.24")
    assert neu["schluss_preis"] == Decimal("0")
    assert neu["schluss_zeit"] == datetime(2026, 3, 6, 16, 0)
    assert _anzahl_legs(migrated_db, neu["id"]) == 2
    roh = json.loads(neu["roh_json"])
    assert roh["zeile"][10] == "EXPIRED"   # Spalte Status
    assert roh["_vorher"][10] == "RUNNING"


def test_aelterer_laufender_stand_ueberschreibt_nicht(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_2.xlsx")
    e = import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_1.xlsx")
    t = _trades(migrated_db)
    assert t["6001"]["status"] == "EXPIRED"
    assert t["6001"]["profit"] == Decimal("174.24")
    assert (e.zeilen_neu, e.zeilen_fortgeschrieben) == (0, 0)


def test_andere_strategie_bricht_ab_und_bucht_nichts(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_1.xlsx")
    with pytest.raises(ValueError) as fehler:
        import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_andere_strategie.xlsx")
    assert "6001" in str(fehler.value)
    t = _trades(migrated_db)
    assert "6003" not in t
    assert t["6001"]["status"] == "RUNNING"


def test_ordnerimport(migrated_db, tmp_path):
    for name in ("oa_fortschreibung_1.xlsx", "oa_fortschreibung_2.xlsx"):
        shutil.copy(FIXTURES / name, tmp_path / name)
    (tmp_path / "notiz.txt").write_text("kein Export", encoding="utf-8")
    ergebnisse = import_optionapp_ordner(migrated_db, tmp_path)
    assert [name for name, _ in ergebnisse] == [
        "oa_fortschreibung_1.xlsx", "oa_fortschreibung_2.xlsx"]
    t = _trades(migrated_db)
    assert sorted(t) == ["6001", "6002", "6003"]
    assert t["6001"]["status"] == "EXPIRED"
    # Zweiter Lauf: beide Dateien bekannt, nichts Neues.
    zweiter = import_optionapp_ordner(migrated_db, tmp_path)
    assert [e.zeilen_neu + e.zeilen_fortgeschrieben for _, e in zweiter] == [0, 0]


def test_ordnerimport_ohne_ordner(migrated_db, tmp_path):
    with pytest.raises(FileNotFoundError):
        import_optionapp_ordner(migrated_db, tmp_path / "fehlt")
    assert import_optionapp_ordner(migrated_db, tmp_path) == []


def test_oa_stand(migrated_db):
    """`GET /oa-stand`: letzter Exporttag und OA-Trades aus den IB-Daten, für
    die kein Export vorliegt. Welt: Export Stand 2 (Zeitraum bis 13.03.2026);
    Ausführungen mit OA-Nummern 6001 (im Export), 7001 und 7002 (nicht im
    Export, ältester am 16.03.2026). Erwartet: bis 2026-03-13, 2 ohne Export,
    ältester 2026-03-16."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from fixtures_rebuild import befuelle

    from api.app import erzeuge_app

    import_optionapp_file(migrated_db, FIXTURES / "oa_fortschreibung_2.xlsx")
    instrument = dict(conid=9101, symbol="XSP  260320P520", underlying="XSP",
                      asset_class="OPT", expiry=date(2026, 3, 20), strike=Decimal("520"),
                      right="P", multiplikator=Decimal("100"), waehrung="USD")

    def ausf(exec_id, oa, zeit):
        return dict(exec_id=exec_id, conid=9101, side="SELL", preis=Decimal("1"),
                    handelszeit=zeit, waehrung="USD", kommission_waehrung="USD",
                    buchungskurs=Decimal("1"), oa_trade=oa)

    befuelle(migrated_db, instrumente_=[instrument], ausfuehrungen=[
        ausf("X1", "6001", datetime(2026, 3, 2, 11, 21)),
        ausf("X2", "7001", datetime(2026, 3, 16, 11, 21)),
        ausf("X3", "7002", datetime(2026, 3, 17, 11, 21)),
        ausf("X4", "7002", datetime(2026, 3, 17, 11, 22)),
        ausf("X5", None, datetime(2026, 3, 18, 11, 22)),
    ])
    d = TestClient(erzeuge_app(migrated_db)).get("/oa-stand").json()
    assert d == {"export_bis": "2026-03-13", "ohne_export": 2,
                 "ohne_export_ab": "2026-03-16"}


def test_oa_stand_leer(migrated_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    d = TestClient(erzeuge_app(migrated_db)).get("/oa-stand").json()
    assert d == {"export_bis": None, "ohne_export": 0, "ohne_export_ab": None}
