# ruff: noqa: E501
"""Wirtschaftliche Beiträge einer Kampagne (AP-17g, M02), von Hand gerechnet.

Geschlossene Kette XYZ (Multiplikator 100, EUR, Kommission je Ausführung -2):
  Eröffnung  SELL 10,00 und BUY 4,00  → (10 - 4) × 100 = +600
  Schließen  BUY 3,00 und SELL 1,00   → (-3 + 1) × 100 = -200
  Brutto 400, Kommission 4 × -2 = -8, Netto 392
Offene Kette ABC (Multiplikator 100):
  Eröffnung  SELL 5,00 und BUY 2,00   → (5 - 2) × 100 = +300, Kommission 2 × -2 = -4, Cash-Flow netto 296 (kein Ergebnis)
Kampagne aus beiden: Ergebnis = 392 (nur geschlossen), offener Cash-Flow 296 getrennt, Status teilweise_offen.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, text

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import campaign_links, campaigns  # noqa: E402


def _inst(conid, name, underlying, strike):
    return dict(conid=conid, symbol=name, underlying=underlying, asset_class="OPT", expiry=date(2026, 12, 18),
                strike=Decimal(strike), right="P", multiplikator=Decimal("100"), waehrung="EUR")


INSTRUMENTE = [_inst(1, "XYZ P50", "XYZ", "50"), _inst(2, "XYZ P45", "XYZ", "45"),
               _inst(3, "ABC P20", "ABC", "20"), _inst(4, "ABC P15", "ABC", "15")]


def _ex(eid, conid, seite, preis, wann):
    return dict(exec_id=eid, conid=conid, side=seite, preis=Decimal(preis), handelszeit=wann, buchungskurs=Decimal("1"))


AUSFUEHRUNGEN = [
    _ex("X1", 1, "SELL", "10.00", datetime(2026, 10, 1, 10, 0)), _ex("X2", 2, "BUY", "4.00", datetime(2026, 10, 1, 10, 0)),
    _ex("X3", 1, "BUY", "3.00", datetime(2026, 10, 8, 10, 0)), _ex("X4", 2, "SELL", "1.00", datetime(2026, 10, 8, 10, 0)),
    _ex("A1", 3, "SELL", "5.00", datetime(2026, 10, 12, 10, 0)), _ex("A2", 4, "BUY", "2.00", datetime(2026, 10, 12, 10, 0)),
]


@pytest.fixture
def welt(migrated_db):
    befuelle(migrated_db, AUSFUEHRUNGEN, INSTRUMENTE)
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.connect() as v:
        ketten = {u: c for c, u, b in v.execute(text("SELECT chain_id, underlying, beendet_am FROM chains WHERE sicht='konto'")).all()}
    return migrated_db, ketten


def _kampagne(db, ketten_ids):
    engine = create_db_engine(db)
    with engine.begin() as v:
        v.execute(insert(campaigns).values(campaign_id=1, underlying="XYZ", eroeffnet_am=datetime(2026, 10, 1, 10, 0),
                                           beendet_am=None, netto_pnl_eur=None))
        for k in ketten_ids:
            v.execute(insert(campaign_links).values(campaign_id=1, chain_id=k, beziehungstyp="ic_leg", erkennung="manuell",
                                                    bestaetigt_am=datetime(2026, 10, 20)))
    return TestClient(erzeuge_app(db)).get("/kampagnen/1").json()["wirtschaft"]


def test_geschlossen_ist_ergebnis_offen_ist_cashflow_getrennt(welt):
    db, ketten = welt
    w = _kampagne(db, [ketten["XYZ"], ketten["ABC"]])
    x, a = w["je_kette"][str(ketten["XYZ"])], w["je_kette"][str(ketten["ABC"])]
    assert (x["stand"], Decimal(x["brutto_eur"]), Decimal(x["kommission_eur"]), Decimal(x["netto_eur"])) == ("geschlossen", Decimal(400), Decimal(-8), Decimal(392))
    assert (a["stand"], Decimal(a["brutto_eur"]), Decimal(a["kommission_eur"]), Decimal(a["netto_eur"])) == ("offen", Decimal(300), Decimal(-4), Decimal(296))
    assert Decimal(w["ergebnis_eur"]) == 392 and w["ergebnis_status"] == "teilweise_offen"
    assert Decimal(w["offener_cashflow_eur"]) == 296 and (w["anzahl_geschlossen"], w["anzahl_offen"]) == (1, 1)


def test_kampagnenergebnis_ist_die_summe_der_angezeigten_einzelbeitraege(welt):
    db, ketten = welt
    w = _kampagne(db, [ketten["XYZ"]])
    assert w["ergebnis_status"] == "abgeschlossen" and w["offener_cashflow_eur"] is None
    assert Decimal(w["ergebnis_eur"]) == sum(Decimal(z["netto_eur"]) for z in w["je_kette"].values() if z["stand"] == "geschlossen")


def test_nur_offene_ketten_haben_kein_ergebnis(welt):
    db, ketten = welt
    w = _kampagne(db, [ketten["ABC"]])
    assert w["ergebnis_eur"] is None and w["ergebnis_status"] == "offen" and Decimal(w["offener_cashflow_eur"]) == 296


def test_fehlender_kurs_laesst_das_ergebnis_leer(welt):
    db, ketten = welt
    with create_db_engine(db).begin() as v:
        v.execute(text("UPDATE executions SET buchungskurs = NULL WHERE exec_id = 'X1'"))
    w = _kampagne(db, [ketten["XYZ"]])
    assert w["ergebnis_eur"] is None and w["ergebnis_status"] == "kurs_fehlt"
