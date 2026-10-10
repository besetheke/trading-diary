"""Abnahmetests für `GET /nav` (AP-06h). Unveränderlich.

Welt aus fixtures/flex/activity_nav.xml (AP-02n, frei erfunden): Kontowert
2025-12-31 3798.15, 2026-01-02 4060.00, 2026-01-05 4077.00; keine
Einzahlungen — Gewinn = Kontowert.
"""

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from ingest.flex import import_flex_file  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "flex"


@pytest.fixture
def klient(migrated_db):
    import_flex_file(migrated_db, FIXTURES / "activity_nav.xml")
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_nav_reihe(klient):
    daten = klient.get("/nav").json()
    assert [(t["datum"], t["gesamt"], t["gewinn"]) for t in daten["tage"]] == [
        ("2025-12-31", "3798.15", "3798.15"),
        ("2026-01-02", "4060.00", "4060.00"),
        ("2026-01-05", "4077.00", "4077.00"),
    ]
    assert daten["tage"][0]["rohstoffe"] is None
    assert daten["anfangswert"] is None
    assert daten["endwert"] == "4077.00"


def test_nav_zeitraum(klient):
    daten = klient.get("/nav", params={"von": "2026-01-02", "bis": "2026-01-04"}).json()
    assert [t["datum"] for t in daten["tage"]] == ["2026-01-02"]
    assert daten["anfangswert"] == "3798.15"
    assert daten["endwert"] == "4060.00"


def test_von_nach_bis_ist_422(klient):
    assert klient.get("/nav", params={"von": "2026-01-05", "bis": "2026-01-01"}).status_code == 422
