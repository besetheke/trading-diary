# ruff: noqa: E501
"""AP-17c (Review R01): Trading-Befehle und Momentum-Schalter nur aus der Station.

Der Nachweis des Reviews: Ein POST mit fremdem Origin, Sec-Fetch-Site cross-site und Formular-Content-Type
erreichte den Roller-Sender (HTTP 200). Jetzt gilt, jeweils BEVOR der Sender oder der Prozess angefasst wird:
erlaubter Host, Header der Station, gleiche Herkunft (Origin) und Sec-Fetch-Site same-origin/none.
"""
import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api import momentum_steuerung  # noqa: E402
from api.app import erzeuge_app  # noqa: E402

STATION = {"X-Trading-Station": "1"}
URL = "/journal/roller-befehl/auto-an"


@pytest.fixture
def aufbau(migrated_db):
    gerufen = []

    def sender(port, ziel):
        gerufen.append((port, ziel))
        return 200, {"ok": True}

    klient = TestClient(erzeuge_app(migrated_db, mit_journal=True, roller_port=8600, sende_roller_befehl=sender),
                        base_url="http://localhost:8000")
    return klient, gerufen


def test_der_angriff_aus_dem_review_wird_abgelehnt_bevor_der_sender_laeuft(aufbau):
    klient, gerufen = aufbau
    r = klient.post(URL, headers={"Origin": "https://foreign.example", "Sec-Fetch-Site": "cross-site",
                                  "Content-Type": "application/x-www-form-urlencoded"})
    assert r.status_code == 403 and gerufen == []


def test_fremde_herkunft_wird_auch_mit_header_abgelehnt(aufbau):
    klient, gerufen = aufbau
    r = klient.post(URL, headers={**STATION, "Origin": "https://foreign.example"})
    assert r.status_code == 403 and gerufen == []


def test_ohne_header_der_station_wird_abgelehnt(aufbau):
    klient, gerufen = aufbau
    assert klient.post(URL).status_code == 403 and gerufen == []


def test_fremder_host_dns_rebinding_wird_abgelehnt(aufbau):
    klient, gerufen = aufbau
    r = klient.post(URL, headers={**STATION, "Host": "boese.example:8000", "Origin": "http://boese.example:8000"})
    assert r.status_code == 403 and gerufen == []


@pytest.mark.parametrize("seite", ["cross-site", "same-site"])
def test_sec_fetch_site_muss_same_origin_sein(aufbau, seite):
    klient, gerufen = aufbau                     # same-site = z. B. eine andere Seite auf localhost, anderer Port
    r = klient.post(URL, headers={**STATION, "Sec-Fetch-Site": seite})
    assert r.status_code == 403 and gerufen == []


def test_aufruf_der_station_funktioniert(aufbau):
    klient, gerufen = aufbau
    r = klient.post(URL, headers={**STATION, "Origin": "http://localhost:8000", "Sec-Fetch-Site": "same-origin"})
    assert r.status_code == 200 and gerufen == [(8600, "auto-an")]
    assert klient.post(URL, headers=STATION).status_code == 200                   # ohne Origin, z. B. Skript


def test_zusaetzlicher_host_nur_ueber_die_umgebung(aufbau, monkeypatch):
    klient, gerufen = aufbau
    kopf = {**STATION, "Host": "server01:8000", "Origin": "http://server01:8000"}
    assert klient.post(URL, headers=kopf).status_code == 403
    monkeypatch.setenv("STATION_ERLAUBTE_HOSTS", "server01, nox")
    assert klient.post(URL, headers=kopf).status_code == 200 and gerufen == [(8600, "auto-an")]


def test_momentum_schalter_ist_gleich_geschuetzt(aufbau, monkeypatch):
    klient, _ = aufbau
    aufrufe = []
    monkeypatch.setattr(momentum_steuerung, "starten", lambda: aufrufe.append("start") or (True, "ok"))
    monkeypatch.setattr(momentum_steuerung, "beenden", lambda: aufrufe.append("stop") or (True, "ok"))
    fremd = {"Origin": "https://foreign.example", "Sec-Fetch-Site": "cross-site"}
    assert klient.post("/journal/momentum/start", headers=fremd).status_code == 403
    assert klient.post("/journal/momentum/stop", headers=STATION | fremd).status_code == 403
    assert aufrufe == []
    assert klient.post("/journal/momentum/start", headers=STATION).status_code == 200
    assert aufrufe == ["start"]
