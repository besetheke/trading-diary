# ruff: noqa: E501
"""AP-17f (Review R07): Ende und Art des Endes einer Live-Eröffnung kommen aus den gematchten Legs,
nicht aus der Zeitnähe. Jeder Fall mit Hand-Erwartung (Zeiten am 2.3.2026, Verfall-Expiry 2.3.).

  F1 Rückkauf     Short Put 100 verkauft 10:00, zurückgekauft 10:30 (Rückkauf ohne OA-Nummer)  → ende 10:30, nicht ausgelaufen
  F2 Verfall      verkauft 10:00, Verfallszeile 16:00 ohne OA-Nummer                           → ende 16:00, ausgelaufen
  F3 Verfall mit  verkauft 10:00, Verfallszeile 16:00 mit OA-Nummer                            → ende 16:00, ausgelaufen
  F4 Teilschluss  zwei Legs, eines 10:30 zurückgekauft, das andere noch offen                  → ende 10:30, nicht ausgelaufen
  F5 Roundtrip    verkauft 10:00, nach 1 Minute zurückgekauft (gleiche OA-Nummer, im Fenster)   → Eröffnung nur das Verkaufsbein, ende 10:01
  F6 Offen        verkauft 10:00, nichts geschlossen                                           → ende None, ausgelaufen None
"""
from datetime import date, datetime
from decimal import Decimal as D

from fixtures_rebuild import befuelle
from sqlalchemy import insert

from analytics.backtest import _live_laden
from journal.db import create_db_engine
from journal.schema import import_runs, legs, optionapp_trades

TAG = date(2026, 3, 2)


def _zeit(h, m):
    return datetime(2026, 3, 2, h, m)


def _instrument(conid, strike):
    return dict(conid=conid, symbol=f"SPX P{strike}", underlying="SPX", asset_class="OPT",
                expiry=TAG, strike=D(strike), right="P", multiplikator=D("100"), waehrung="USD")


def _exec(exec_id, conid, side, zeit, oa="OA1", ereignistyp="trade"):
    return dict(exec_id=exec_id, conid=conid, side=side, menge=D("1"), preis=D("1"),
                handelszeit=zeit, waehrung="USD", kommission_waehrung="USD",
                buchungskurs=D("0.9"), oa_trade=oa, ereignistyp=ereignistyp)


def _welt(db, ausfuehrungen, leg_paare):
    befuelle(db, instrumente_=[_instrument(1, 100), _instrument(2, 90)], ausfuehrungen=ausfuehrungen)
    engine = create_db_engine(db)
    with engine.begin() as v:
        lauf = v.execute(insert(import_runs).values(
            quelle="optionapp", datei_hash="oa-ende", importiert_am=datetime(2026, 3, 9),
            qualitaetsstufe="B", zeilen_gesamt=1, zeilen_neu=1)).inserted_primary_key[0]
        v.execute(insert(optionapp_trades).values(
            import_run_id=lauf, oa_trade="OA1", entry_zeit=_zeit(10, 0), schluss_zeit=_zeit(16, 0),
            strategie="S", name_roh="Bot [OA1]", strikes_roh="-", menge_zaehler=D("1"),
            menge_nenner=D("1"), stop_roh="-", profit=D("10"), profit_waehrung="$",
            status="EXPIRED", roh_json="{}"))
        for conid, auf, zu, offen in leg_paare:
            v.execute(insert(legs).values(
                conid=conid, open_exec_id=auf, close_exec_id=zu, menge=D("1"),
                matching_methode="fifo", offen_ja_nein=offen, sicht="konto"))
    with engine.connect() as v:
        return _live_laden(v)


def _eine(zeilen):
    assert len(zeilen) == 1
    return zeilen[0]


def test_f1_rueckkauf(migrated_db):
    z = _eine(_welt(migrated_db,
                    [_exec("E1", 1, "SELL", _zeit(10, 0)), _exec("C1", 1, "BUY", _zeit(10, 30), oa=None)],
                    [(1, "E1", "C1", False)]))
    assert z.ende == _zeit(10, 30) and z.ausgelaufen is False
    assert len(z.eroeffnung.legs) == 1


def test_f2_verfall_ohne_oa_nummer_an_der_ereigniszeile(migrated_db):
    z = _eine(_welt(migrated_db,
                    [_exec("E1", 1, "SELL", _zeit(10, 0)),
                     _exec("X1", 1, "BUY", _zeit(16, 0), oa=None, ereignistyp="expiry")],
                    [(1, "E1", "X1", False)]))
    assert z.ende == _zeit(16, 0) and z.ausgelaufen is True


def test_f3_verfall_mit_oa_nummer_ohne_leg(migrated_db):
    z = _eine(_welt(migrated_db,
                    [_exec("E1", 1, "SELL", _zeit(10, 0)),
                     _exec("X1", 1, "BUY", _zeit(16, 0), ereignistyp="expiry")], []))
    assert z.ende == _zeit(16, 0) and z.ausgelaufen is True


def test_f4_teilschliessung(migrated_db):
    z = _eine(_welt(migrated_db,
                    [_exec("E1", 1, "SELL", _zeit(10, 0)), _exec("E2", 2, "BUY", _zeit(10, 0)),
                     _exec("C1", 1, "BUY", _zeit(10, 30), oa=None)],
                    [(1, "E1", "C1", False), (2, "E2", None, True)]))
    assert z.ende == _zeit(10, 30) and z.ausgelaufen is False
    assert len(z.eroeffnung.legs) == 2


def test_f5_schneller_roundtrip_zaehlt_den_rueckkauf_nicht_als_eroeffnung(migrated_db):
    z = _eine(_welt(migrated_db,
                    [_exec("E1", 1, "SELL", _zeit(10, 0)), _exec("C1", 1, "BUY", _zeit(10, 1))],
                    [(1, "E1", "C1", False)]))
    assert len(z.eroeffnung.legs) == 1 and z.eroeffnung.legs[0].seite == "S"
    assert z.ende == _zeit(10, 1) and z.ausgelaufen is False


def test_f6_offen(migrated_db):
    z = _eine(_welt(migrated_db, [_exec("E1", 1, "SELL", _zeit(10, 0))], [(1, "E1", None, True)]))
    assert z.ende is None and z.ausgelaufen is None
