"""Abnahmetest für `GET /depot/einkauf` (Aktien in den Positionen, 16.10.2026).

Einkaufskurs der gehaltenen Aktien aus den offenen Aktien-Legs des Journals, neben IBs Einstand,
der um die Prämien der zugeteilten Optionen gekürzt ist.

Testwelt (von Hand gerechnet, KNSL-ähnlich, frei erfunden):
  Offene Aktien-Legs: 100 Stück zu 370 (Zuteilung), 100 Stück zu 360 (Zuteilung)
    → Einkauf Ø = (370·100 + 360·100) / 200 = 365,00; 100 % aus Zuteilung.
  Aktie B: 50 Stück gekauft zu 20,00 (normaler Handel) → Einkauf 20,00; 0 % Zuteilung.
  Aktie C: im Journal geschlossen (kein offener Leg) → fehlt in der Liste.
  IB (Stichtag 2026-10-12): A 200 Stück, Kostenbasis 347,565, Kurs 341,12;
                            B 50 Stück, Basis 20,00, Kurs 22,00
    → Prämien je Aktie A = 365,00 − 347,565 = 17,435; B = 0
    → Unrealisiert (Einkauf) A = (341,12 − 365,00) · 200 = −4776,00;
      B = (22,00 − 20,00) · 50 = 100,00
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import insert

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import flex_open_positions, legs  # noqa: E402


def _leg(v, leg_id, conid, exec_id, menge, offen=True):
    v.execute(insert(legs).values(
        leg_id=leg_id, conid=conid, open_exec_id=exec_id, menge=Decimal(menge),
        matching_methode="fifo", offen_ja_nein=offen, structure_id=None, sicht="konto"))


def _bestand(v, run, conid, symbol, menge, basis, kurs):
    roh = (f'{{"levelOfDetail": "SUMMARY", "position": "{menge}", "costBasisPrice": "{basis}", '
           f'"markPrice": "{kurs}"}}')
    v.execute(insert(flex_open_positions).values(
        import_run_id=run, conid=conid, symbol=symbol, asset_class="STK", menge=Decimal(menge),
        waehrung="USD", roh_json=roh, konto="U1", quell_schluessel=f"{conid}-1",
        stichtag=date(2026, 10, 12)))


@pytest.fixture
def klient(migrated_db, sample_execution):
    from conftest import insert_import_run
    engine = create_db_engine(migrated_db)
    with engine.begin() as v:
        run = insert_import_run(v)
        stamm = {"sec_type": "STK", "symbol": "AAA", "waehrung": "USD", "import_run_id": run}
        sample_execution(v, exec_id="A1", conid=1, preis=Decimal("370"), menge=Decimal("100"),
                         ereignistyp="assignment", handelszeit=datetime(2026, 5, 4, 16, 20),
                         **stamm)
        sample_execution(v, exec_id="A2", conid=1, preis=Decimal("360"), menge=Decimal("100"),
                         ereignistyp="assignment", handelszeit=datetime(2026, 10, 7, 16, 20),
                         **stamm)
        sample_execution(v, exec_id="B1", conid=2, preis=Decimal("20"), menge=Decimal("50"),
                         ereignistyp="trade", handelszeit=datetime(2026, 9, 1, 15, 0),
                         **{**stamm, "symbol": "BBB"})
        sample_execution(v, exec_id="C1", conid=3, preis=Decimal("9"), menge=Decimal("10"),
                         ereignistyp="trade", handelszeit=datetime(2026, 1, 5, 15, 0),
                         **{**stamm, "symbol": "CCC"})
        _leg(v, 1, 1, "A1", "100")
        _leg(v, 2, 1, "A2", "100")
        _leg(v, 3, 2, "B1", "50")
        _leg(v, 4, 3, "C1", "10", offen=False)
        _bestand(v, run, 1, "AAA", "200", "347.565", "341.12")
        _bestand(v, run, 2, "BBB", "50", "20", "22")
    return TestClient(erzeuge_app(migrated_db))


def test_einkauf_ist_der_preis_der_ausfuehrung_nicht_ibs_gekuerzter_einstand(klient):
    d = klient.get("/depot/einkauf").json()
    assert d["stichtag"] == "2026-10-12"
    a, b = d["aktien"]                                # nach Symbol: AAA, BBB
    assert (a["symbol"], a["menge_journal"], a["menge_ib"]) == ("AAA", "200", "200")
    assert Decimal(a["einkaufskurs"]) == Decimal("365")
    assert Decimal(a["ib_einstand"]) == Decimal("347.565")
    assert Decimal(a["praemien_je_aktie"]) == Decimal("17.435")
    assert Decimal(a["anteil_zuteilung"]) == Decimal("1")
    assert Decimal(a["unrealisiert_einkauf"]) == Decimal("-4776")
    assert (b["symbol"], Decimal(b["einkaufskurs"])) == ("BBB", Decimal("20"))
    assert Decimal(b["praemien_je_aktie"]) == 0
    assert Decimal(b["anteil_zuteilung"]) == 0
    assert Decimal(b["unrealisiert_einkauf"]) == Decimal("100")


def test_geschlossene_aktie_fehlt(klient):
    symbole = [a["symbol"] for a in klient.get("/depot/einkauf").json()["aktien"]]
    assert "CCC" not in symbole


def test_ohne_bestand_bleibt_der_einkauf_stehen(migrated_db, sample_execution):
    engine = create_db_engine(migrated_db)
    with engine.begin() as v:
        sample_execution(v, exec_id="D1", conid=7, preis=Decimal("10"), menge=Decimal("5"),
                         sec_type="STK", symbol="DDD", ereignistyp="trade")
        _leg(v, 1, 7, "D1", "5")
    d = TestClient(erzeuge_app(migrated_db)).get("/depot/einkauf").json()
    assert d["stichtag"] is None
    z = d["aktien"][0]
    assert (z["symbol"], Decimal(z["einkaufskurs"])) == ("DDD", Decimal("10"))
    assert z["ib_einstand"] is None
    assert z["praemien_je_aktie"] is None
    assert z["unrealisiert_einkauf"] is None
