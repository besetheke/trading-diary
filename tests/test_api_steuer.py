"""Steuer-Seite: Endpunkte auf leerer Datenbank und CSV-Export."""
import pytest


@pytest.fixture
def klient(migrated_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    return TestClient(erzeuge_app(migrated_db))


def test_steuer_auswertung_leer(klient):
    d = klient.get("/steuer-auswertung").json()
    assert d == {"jahre": [], "toepfe": [], "fehler": []}


def test_steuer_csv_ist_ein_download(klient):
    r = klient.get("/steuer-csv?jahr=2025")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="steuer-2025.csv"' in r.headers["content-disposition"]
    assert klient.get("/steuer-csv").headers["content-disposition"].endswith('"steuer.csv"')
