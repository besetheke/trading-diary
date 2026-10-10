"""Abnahmetests für `GET /kapital` (AP-06g). Unveränderlich.

Welt ohne Ausführungen: Dividende 10.00 USD × 0.90 = 9.0000 EUR am
2026-01-10, Einzahlung 1000.00 EUR am 2026-02-10. Kapital: 01-10 9.0000,
02-10 1009.0000. Zeitraum ab 2026-02-01: Anfangskapital 9.0000, im Zeitraum
Einzahlungen 1000.00.
"""

import json
from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import insert

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import flex_cash_transactions, import_runs  # noqa: E402


def _buchung(lauf, schluessel, datum, typ, betrag, waehrung, kurs):
    return dict(
        import_run_id=lauf, konto="U1234567", quell_schluessel=schluessel, datum=datum,
        typ=typ, betrag=Decimal(betrag), waehrung=waehrung, beschreibung=None,
        roh_json=json.dumps({"fxRateToBase": kurs}),
    )


@pytest.fixture
def klient(migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(
            insert(import_runs).values(
                quelle="flex", datei_hash="kapital-test", importiert_am=datetime(2026, 3, 1),
                qualitaetsstufe="A", zeilen_gesamt=2, zeilen_neu=2,
            )
        ).inserted_primary_key[0]
        verbindung.execute(insert(flex_cash_transactions).values([
            _buchung(lauf, "C1", datetime(2026, 1, 10, 20), "Dividends", "10.00", "USD", "0.90"),
            _buchung(lauf, "C2", datetime(2026, 2, 10), "Deposits/Withdrawals", "1000.00",
                     "EUR", "1"),
        ]))
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_kapital_gesamt(klient):
    daten = klient.get("/kapital").json()
    assert [(t["datum"], t["kapital"]) for t in daten["tage"]] == [
        ("2026-01-10", "9.0000"), ("2026-02-10", "1009.0000"),
    ]
    assert daten["anfangskapital"] == "0"
    assert daten["endkapital"] == "1009.0000"


def test_kapital_zeitraum_beginnt_beim_bestand(klient):
    daten = klient.get("/kapital", params={"von": "2026-02-01"}).json()
    assert [t["datum"] for t in daten["tage"]] == ["2026-02-10"]
    assert daten["anfangskapital"] == "9.0000"
    assert daten["einzahlungen_im_zeitraum"] == "1000.00"


def test_von_nach_bis_ist_422(klient):
    assert klient.get("/kapital", params={"von": "2026-02-02", "bis": "2026-02-01"}).status_code \
        == 422
