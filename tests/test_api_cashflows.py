"""Abnahmetests für `GET /cashflows` (AP-06f). Unveränderlich.

Kleine Welt: eine Dividende 10.00 USD mit fxRateToBase 0.90 (= 9.00 EUR) am
2026-01-10 und eine Einzahlung 1000.00 EUR (Kurs 1) am 2026-02-10 —
keine Ausführungen.
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
        roh_json=json.dumps({"fxRateToBase": kurs, "amount": betrag}),
    )


@pytest.fixture
def klient(migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(
            insert(import_runs).values(
                quelle="flex", datei_hash="cash-test", importiert_am=datetime(2026, 3, 1),
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


def test_kategorien_und_geld_als_text(klient):
    daten = klient.get("/cashflows").json()
    je = {k["kategorie"]: k for k in daten["kategorien"]}
    assert je["dividenden"]["summe_eur"] == "9.0000"
    assert je["dividenden"]["anzahl"] == 1
    assert je["ein_auszahlungen"]["summe_eur"] == "1000.00"
    assert je["kommissionen"] == {
        "kategorie": "kommissionen", "anzahl": 0, "summe_eur": "0",
        "anzahl_kurs_fehlt": 0, "im_ergebnis_enthalten": True,
    }
    assert [(m["monat"], m["kategorie"]) for m in daten["monate"]] == [
        ("2026-01", "dividenden"), ("2026-02", "ein_auszahlungen"),
    ]


def test_zeitraum(klient):
    daten = klient.get("/cashflows", params={"von": "2026-02-01"}).json()
    je = {k["kategorie"]: k for k in daten["kategorien"]}
    assert je["dividenden"]["anzahl"] == 0
    assert je["ein_auszahlungen"]["anzahl"] == 1


def test_von_nach_bis_ist_422(klient):
    antwort = klient.get("/cashflows", params={"von": "2026-02-01", "bis": "2026-01-01"})
    assert antwort.status_code == 422
