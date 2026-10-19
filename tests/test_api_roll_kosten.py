# ruff: noqa: E501
"""AP-17g (Review M01): GET /roll-kosten-auswertung reicht die Rechenkerne unverändert weiter."""
import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from analytics.degradation import degradations_bericht  # noqa: E402
from analytics.kommission import kommissions_bericht  # noqa: E402
from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    return TestClient(erzeuge_app(migrated_db, mit_journal=True)), migrated_db


def test_kettensicht_entspricht_den_kernen(klient):
    c, db = klient
    d = c.get("/roll-kosten-auswertung").json()
    kern = kommissions_bericht(db, sicht="kette")
    assert d["sicht"] == "kette" and d["anzahl_ketten_gesamt"] == kern.anzahl_ketten_gesamt
    assert [(g["dimension"], g["schluessel"], g["kommission_eur"]) for g in d["kommission"]] == [
        (g.dimension, g.schluessel, str(g.kommission_eur)) for g in kern.gruppen]
    deg = degradations_bericht(db)
    assert [(g["modus"], g["roll_gruppe"], g["anzahl_ketten"]) for g in d["degradation"]] == [
        (g.modus, g.roll_gruppe, g.anzahl_ketten) for g in deg.gruppen]
    assert len(d["degradation_abdeckung"]) == len(deg.abdeckung)


def test_kontosicht_hat_keine_degradation(klient):
    c, _ = klient
    d = c.get("/roll-kosten-auswertung", params={"sicht": "konto"}).json()
    assert d["sicht"] == "konto" and d["degradation"] is None and d["degradation_abdeckung"] == []


def test_unbekannte_sicht_ist_422(klient):
    c, _ = klient
    assert c.get("/roll-kosten-auswertung", params={"sicht": "x"}).status_code == 422
