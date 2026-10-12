"""Abnahmetest für AP-14a (Cockpit, Seite „System“): `GET /system`.

Die Station zeigt, welche Dienste laufen und wie frisch die Daten sind. Die
Erreichbarkeit wird über einen TCP-Verbindungsversuch geprüft (keine API-Sitzung,
keine Anmeldung) — im Test durch eine erfundene Prüffunktion ersetzt.

Welt: offen sind nur Port 7497 (TWS Paper) und 8501 (Momentum Lab).
Importläufe: flex am 12.10.2026 03:00 (Zeitraum bis 09.10.), optionomega am
12.10.2026 21:00 (Zeitraum bis 09.10.); optionapp nie.

Erwartung:
- Dienste in dieser Reihenfolge: TWS live (7496) aus, TWS Paper (7497) an,
  IB Gateway live (4001) aus, IB Gateway Paper (4002) aus, Momentum Lab (8501)
  an, Options Roller ohne Port (noch kein Dienst) → erreichbar null.
- Importe: flex 12.10. 03:00 / bis 09.10., optionapp null, optionomega 12.10. 21:00.
"""

from datetime import date, datetime

import pytest
from sqlalchemy import insert

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import import_runs  # noqa: E402

OFFEN = {7497, 8501}


def _lauf(v, quelle, zeit, bis):
    v.execute(insert(import_runs).values(
        quelle=quelle, datei_hash=f"{quelle}-{zeit}", importiert_am=zeit, zeitraum_bis=bis,
        qualitaetsstufe="A", zeilen_gesamt=1, zeilen_neu=1))


@pytest.fixture
def klient(migrated_db):
    with create_db_engine(migrated_db).begin() as v:
        _lauf(v, "flex", datetime(2026, 10, 12, 3, 0), date(2026, 10, 9))
        _lauf(v, "flex", datetime(2026, 10, 11, 3, 0), date(2026, 10, 8))
        _lauf(v, "optionomega", datetime(2026, 10, 12, 21, 0), date(2026, 10, 9))
    return TestClient(erzeuge_app(migrated_db, pruefe_port=lambda port: port in OFFEN))


def test_dienste(klient):
    d = klient.get("/system").json()["dienste"]
    assert [(x["name"], x["port"], x["erreichbar"]) for x in d] == [
        ("TWS live", 7496, False),
        ("TWS Paper", 7497, True),
        ("IB Gateway live", 4001, False),
        ("IB Gateway Paper", 4002, False),
        ("Momentum Lab", 8501, True),
        ("Options Roller", None, None),
    ]
    assert d[-1]["hinweis"]


def test_importe(klient):
    i = {x["quelle"]: x for x in klient.get("/system").json()["importe"]}
    assert (i["flex"]["zuletzt"], i["flex"]["daten_bis"]) == ("2026-10-12T03:00:00",
                                                                "2026-10-09")
    assert i["optionapp"]["zuletzt"] is None
    assert i["optionomega"]["zuletzt"] == "2026-10-12T21:00:00"
