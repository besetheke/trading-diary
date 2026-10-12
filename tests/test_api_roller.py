"""Abnahmetest für AP-14b (Station, Roller R2): `GET /roller-status` reicht den Status
des Roller-Dienstes durch, und `GET /system` führt den Roller als Dienst mit Port.

Der Roller-Dienst (Projekt options-roller, `python -m roller.dienst`) liefert
`GET http://127.0.0.1:8600/status`. Die Station fragt ihn nur lesend ab; ist er
nicht erreichbar, antwortet `/roller-status` mit `erreichbar: false` und ohne Status —
nie mit einem Fehler (Fall: Dienst aus, Server neu gestartet).

Test: ein erfundener Status-Lieferant ersetzt die HTTP-Abfrage.
- Erreichbar: `/roller-status` → erreichbar true, status wie geliefert.
- Nicht erreichbar (Lieferant meldet None): erreichbar false, status null.
- `/system`: Zeile „Options Roller" mit Port 8600 und Zustand je nach Erreichbarkeit.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402

STATUS = {"dienst": "options-roller", "stufe": "R2", "breaches": [{"symbol": "DAX"}]}


def _klient(db, status, offene_ports=()):
    return TestClient(erzeuge_app(
        db, roller_port=8600, hole_roller_status=lambda port: status,
        pruefe_port=lambda p: p in offene_ports))


def test_roller_erreichbar(migrated_db):
    d = _klient(migrated_db, STATUS).get("/roller-status").json()
    assert d["erreichbar"] is True
    assert d["status"]["breaches"] == [{"symbol": "DAX"}]


def test_roller_nicht_erreichbar(migrated_db):
    d = _klient(migrated_db, None).get("/roller-status").json()
    assert d == {"erreichbar": False, "status": None}


def test_ohne_konfigurierten_port(migrated_db):
    k = TestClient(erzeuge_app(migrated_db))
    assert k.get("/roller-status").json() == {"erreichbar": False, "status": None}


def test_system_fuehrt_den_roller_mit_port(migrated_db):
    d = _klient(migrated_db, STATUS, offene_ports={8600}).get("/system").json()["dienste"]
    roller = next(x for x in d if x["name"] == "Options Roller")
    assert (roller["port"], roller["erreichbar"]) == (8600, True)
    d = _klient(migrated_db, None).get("/system").json()["dienste"]
    roller = next(x for x in d if x["name"] == "Options Roller")
    assert (roller["port"], roller["erreichbar"]) == (8600, False)
