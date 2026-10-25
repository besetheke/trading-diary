# ruff: noqa: E501
"""Kampagnen-Kandidaten in der Oberfläche entscheiden (AP-17g, M02, zweite Stufe).

Testwelt: eine Put-Seite (XYZ P50/P45, eröffnet 1.10.) und eine Call-Seite (XYZ C60/C65, eröffnet 2.10.), beide offen, gleiche
Expiry — ein IC-Kandidat. Das Bestätigen legt eine Kampagne mit zwei Ketten an (erkennung = manuell), das Verwerfen speichert die Ablehnung.
"""
from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import text

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


def _inst(conid, name, strike, recht):
    return dict(conid=conid, symbol=name, underlying="XYZ", asset_class="OPT", expiry=date(2026, 12, 18),
                strike=Decimal(strike), right=recht, multiplikator=Decimal("100"), waehrung="EUR")


def _ex(eid, conid, seite, preis, wann):
    return dict(exec_id=eid, conid=conid, side=seite, preis=Decimal(preis), handelszeit=wann, buchungskurs=Decimal("1"))


INSTRUMENTE = [_inst(1, "XYZ P50", "50", "P"), _inst(2, "XYZ P45", "45", "P"), _inst(5, "XYZ C60", "60", "C"), _inst(6, "XYZ C65", "65", "C")]
AUSFUEHRUNGEN = [
    _ex("P1", 1, "SELL", "5.00", datetime(2026, 10, 1, 10, 0)), _ex("P2", 2, "BUY", "2.00", datetime(2026, 10, 1, 10, 0)),
    _ex("C1", 5, "SELL", "4.00", datetime(2026, 10, 2, 10, 0)), _ex("C2", 6, "BUY", "1.00", datetime(2026, 10, 2, 10, 0)),
]


@pytest.fixture
def welt(migrated_db):
    befuelle(migrated_db, AUSFUEHRUNGEN, INSTRUMENTE)
    rebuild(migrated_db)
    return TestClient(erzeuge_app(migrated_db, mit_journal=True)), migrated_db


def _paar(c):
    d = c.get("/kampagnen-kandidaten").json()
    assert d["anzahl"] == 1 and d["gruppen"][0]["mehrdeutig"] is False
    k = d["gruppen"][0]["kandidaten"][0]
    assert k["typ"] == "ic" and k["basiswert"] == "XYZ"
    return {"schluessel_a": k["a"]["schluessel"], "schluessel_b": k["b"]["schluessel"], "typ": k["typ"]}


def test_bestaetigen_legt_kampagne_an_und_der_kandidat_verschwindet(welt):
    c, db = welt
    paar = _paar(c)
    antwort = c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "ja"})
    assert antwort.status_code == 200 and antwort.json()["kampagnen_neu"] == 1 and antwort.json()["verknuepfungen_neu"] == 2
    assert c.get("/kampagnen-kandidaten").json()["anzahl"] == 0
    liste = c.get("/kampagnen").json()
    assert liste["gesamt"] == 1 and liste["treffer"][0]["anzahl_ketten"] == 2
    detail = c.get(f"/kampagnen/{liste['treffer'][0]['campaign_id']}").json()
    assert {k["erkennung"] for k in detail["ketten"]} == {"manuell"} and {k["beziehungstyp"] for k in detail["ketten"]} == {"ic_leg"}


def test_verwerfen_speichert_und_ueberlebt_den_rebuild(welt):
    c, db = welt
    paar = _paar(c)
    assert c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "nein", "bemerkung": "kein IC"}).json()["neu_abgelehnt"] == 1
    rebuild(db)
    d = c.get("/kampagnen-kandidaten").json()
    assert d["anzahl"] == 0 and [(v["schluessel_a"], v["schluessel_b"], v["notiz"]) for v in d["verworfen"]] == [(paar["schluessel_a"], paar["schluessel_b"], "kein IC")]


def test_umentscheiden_braucht_ausdruecklich_ueberschreiben_und_loescht_keine_kampagne(welt):
    c, db = welt
    paar = _paar(c)
    c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "nein"})
    ohne = c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "ja"})
    assert ohne.status_code == 409 and "widerspricht der Ablehnung" in ohne.json()["detail"]
    mit = c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "ja", "ueberschreiben": True})
    assert mit.status_code == 200 and c.get("/kampagnen").json()["gesamt"] == 1
    # Nach der Bestätigung darf nicht verworfen werden: eine Ablehnung löscht keine Verknüpfung
    zurueck = c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "nein"})
    assert zurueck.status_code == 409 and c.get("/kampagnen").json()["gesamt"] == 1


def test_eingaben_werden_geprueft_und_bei_fehler_wird_nichts_geschrieben(welt):
    c, db = welt
    paar = _paar(c)
    assert c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "vielleicht"}).status_code == 409
    assert c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "typ": "zz", "urteil": "ja"}).status_code == 409
    assert c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "schluessel_b": "k:gibt-es-nicht", "urteil": "ja"}).status_code == 409
    assert c.post("/journal/kampagnen-kandidaten/entscheiden", json={**paar, "urteil": "ja", "typ_a": "unsinn"}).status_code == 409
    with create_db_engine(db).connect() as v:
        assert v.execute(text("SELECT (SELECT COUNT(*) FROM campaigns) + (SELECT COUNT(*) FROM campaign_links) + (SELECT COUNT(*) FROM campaign_ablehnungen)")).scalar() == 0
    assert c.get("/kampagnen-kandidaten").json()["anzahl"] == 1
