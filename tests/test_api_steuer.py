"""Steuer-Seite (AP-10b/10c): Endpunkte auf leerer Datenbank, CSV, Altverfahren-Kennzeichnung."""
import pytest

pytest.importorskip("analytics.steuer_zufluss")


@pytest.fixture
def klient(migrated_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    return TestClient(erzeuge_app(migrated_db))


def test_steuer_auswertung_leer_hat_methode_und_warnung(klient):
    d = klient.get("/steuer-auswertung").json()
    assert d["jahre"] == [] and d["datenluecken"] == [] and d["regeln_offen"] == []
    assert d["methode"]["kursquelle"] == "IB fxRateToBase je Ausführung"
    assert d["methode"]["pruefstatus"] == "regelweise"
    assert d["methode"]["regeln"] and d["methode"]["quellenhierarchie"][0] == "Gesetz"
    assert any("Anfangsbestand" in w for w in d["warnungen"])


def test_steuer_csv_ist_ein_download(klient):
    r = klient.get("/steuer-csv?jahr=2025")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'filename="steuer-2025.csv"' in r.headers["content-disposition"]
    assert klient.get("/steuer-csv").headers["content-disposition"].endswith('"steuer.csv"')


def test_altverfahren_ist_gekennzeichnet(klient):
    r = klient.get("/steuer-csv?methode=alt&jahr=2025")
    assert r.status_code == 200
    assert "ALTVERFAHREN" in r.text.splitlines()[0]
    assert 'filename="steuer-alt-2025.csv"' in r.headers["content-disposition"]
