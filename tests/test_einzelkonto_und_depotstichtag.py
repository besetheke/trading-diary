# ruff: noqa: E501
"""AP-17e (Review R03 und R04), von Hand definiert.

R04  Zwei Konten in den Ausführungen: der Rebuild bricht benannt ab (kein Leg über Konten), die Datenbank bleibt unverändert.
R03  Stichtag des Depots. Welt: Positionszeilen am 01.01.2026 (eine Aktie, 1.000 EUR).
     A  Kontowert 02.01. mit Aktien 0 und Optionen 0           → leeres Depot, Stichtag 02.01.
     B  Kontowert 02.01. mit Aktien 1.200 (Abschnitt fehlte)    → Bestand vom 01.01. bleibt
     C  Kontowert nur 01.01.                                    → 01.01.
     D  Kontowert 02.01., Aktien unbekannt (leer)               → 01.01. (unbekannt ist nicht leer)
     E  Keine Positionszeile                                    → None
     F  Kontowert 02.01. leer, Fonds 500                        → 01.01.
"""
from datetime import date, datetime
from decimal import Decimal as D

import pytest
from fixtures_rebuild import _VORGABEN, AUSFUEHRUNGEN, INSTRUMENTE, befuelle
from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.depot_stichtag import aktueller_depot_stichtag
from journal.rebuild import rebuild
from journal.schema import executions, flex_nav_tage, flex_open_positions, import_runs, legs


# ------------------------------------------------------------------------------------------------ R04
def test_zwei_konten_brechen_den_rebuild_benannt_ab_und_aendern_nichts(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN[:2], instrumente_=INSTRUMENTE)
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.begin() as v:
        vorher = len(v.execute(select(legs)).all())
        lauf = v.execute(select(executions.c.import_run_id)).scalars().first()
        werte = dict(_VORGABEN) | AUSFUEHRUNGEN[2] | {
            "konto": "U9999999", "import_run_id": lauf, "symbol": "DAX  261016P18800"}
        v.execute(insert(executions).values(**werte))
    with pytest.raises(ValueError, match="Mehrere Konten"):
        rebuild(migrated_db)
    with engine.connect() as v:
        assert len(v.execute(select(legs)).all()) == vorher            # nichts verändert


# ------------------------------------------------------------------------------------------------ R03
def _welt(db, positionen=True):
    engine = create_db_engine(db)
    with engine.begin() as v:
        lauf = v.execute(insert(import_runs).values(
            quelle="flex", datei_hash="x", importiert_am=datetime(2026, 1, 2), qualitaetsstufe="A",
            zeilen_gesamt=0, zeilen_neu=0)).inserted_primary_key[0]
        if positionen:
            v.execute(insert(flex_open_positions).values(
                import_run_id=lauf, konto="U1", quell_schluessel="p1", stichtag=date(2026, 1, 1), conid=1,
                symbol="AAA", asset_class="STK", menge=D("10"), waehrung="EUR", roh_json="{}"))
    return engine, lauf


def _nav(engine, lauf, tag, **bestand):
    werte = dict(aktien=None, optionen=None, rohstoffe=None, fonds=None, anleihen=None) | bestand
    with engine.begin() as v:
        v.execute(insert(flex_nav_tage).values(
            import_run_id=lauf, konto="U1", quell_schluessel=f"nav:{tag}", datum=tag, waehrung="EUR",
            cash=D("1000"), gesamt=D("1000"), roh_json="{}", **werte))


def _stichtag(engine):
    with engine.connect() as v:
        return aktueller_depot_stichtag(v)


def test_a_leeres_depot_setzt_den_stichtag_auf_den_kontowert_tag(migrated_db):
    engine, lauf = _welt(migrated_db)
    _nav(engine, lauf, date(2026, 1, 2), aktien=D("0"), optionen=D("0"))
    assert _stichtag(engine) == date(2026, 1, 2)
    with engine.connect() as v:        # die Positionsabfrage zum Stichtag ist leer: das Depot ist leer
        assert v.execute(select(flex_open_positions).where(flex_open_positions.c.stichtag == date(2026, 1, 2))).all() == []


def test_b_fehlender_abschnitt_leert_das_depot_nicht(migrated_db):
    engine, lauf = _welt(migrated_db)
    _nav(engine, lauf, date(2026, 1, 2), aktien=D("1200"), optionen=D("0"))
    assert _stichtag(engine) == date(2026, 1, 1)


def test_c_kein_neuerer_kontowert(migrated_db):
    engine, lauf = _welt(migrated_db)
    _nav(engine, lauf, date(2026, 1, 1), aktien=D("0"), optionen=D("0"))
    assert _stichtag(engine) == date(2026, 1, 1)


def test_d_unbekannter_aktienwert_ist_nicht_leer(migrated_db):
    engine, lauf = _welt(migrated_db)
    _nav(engine, lauf, date(2026, 1, 2), aktien=None, optionen=D("0"))
    assert _stichtag(engine) == date(2026, 1, 1)


def test_e_ohne_positionszeile_ist_der_stichtag_none(migrated_db):
    engine, lauf = _welt(migrated_db, positionen=False)
    _nav(engine, lauf, date(2026, 1, 2), aktien=D("0"), optionen=D("0"))
    assert _stichtag(engine) is None


def test_f_andere_bestandswerte_verhindern_das_leer(migrated_db):
    engine, lauf = _welt(migrated_db)
    _nav(engine, lauf, date(2026, 1, 2), aktien=D("0"), optionen=D("0"), fonds=D("500"))
    assert _stichtag(engine) == date(2026, 1, 1)


def test_depot_endpunkt_zeigt_das_leere_depot(migrated_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    engine, lauf = _welt(migrated_db)
    d = TestClient(erzeuge_app(migrated_db)).get("/depot").json()
    assert d["stichtag"] == "2026-01-01" and len(d["positionen"]) == 1          # vorher: Aktie vom 01.01.
    _nav(engine, lauf, date(2026, 1, 2), aktien=D("0"), optionen=D("0"))
    d = TestClient(erzeuge_app(migrated_db)).get("/depot").json()
    assert d["stichtag"] == "2026-01-02" and d["positionen"] == []             # jetzt: leer
