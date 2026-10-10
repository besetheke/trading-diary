"""Abnahmetests für AP-07fw: `GET /filterwerte` — die wählbaren Werte der
Positionsfilter. Unveränderlich.

Testwelt wie tests/test_api_filter_lose_legs.py (Rebuild, frei erfunden):

  AAA  EUR  Option-Kette, geschlossen (Strategie "IC1" direkt gesetzt)
  XXX  USD  Aktie, loses Leg (Zuteilung ohne Optionsstruktur), geschlossen

Auswahlwerte kommen aus dem Bestand der Kontosicht und schließen die Werte
loser Legs ein — sonst wäre ihr Basiswert im Filter nicht wählbar, obwohl
der Filter für sie gilt (AP-07f).
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import update

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import chains  # noqa: E402

_INSTRUMENTE = [
    dict(conid=9001, symbol="AAA  260320P100", underlying="AAA", asset_class="OPT",
         expiry=date(2026, 3, 20), strike=Decimal("100"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
    dict(conid=9100, symbol="XXX", underlying="XXX", asset_class="STK",
         expiry=None, strike=None, right=None,
         multiplikator=Decimal("1"), waehrung="USD"),
]

_AUSFUEHRUNGEN = [
    dict(exec_id="A1", conid=9001, side="SELL", preis=Decimal("10.00"),
         handelszeit=datetime(2026, 1, 2, 10, 0), buchungskurs=Decimal("1")),
    dict(exec_id="A2", conid=9001, side="BUY", preis=Decimal("4.00"),
         handelszeit=datetime(2026, 1, 3, 10, 0), buchungskurs=Decimal("1")),
    dict(exec_id="X1", conid=9100, side="BUY", menge=Decimal("100"),
         preis=Decimal("50.00"), waehrung="USD", kommission_waehrung="USD",
         ereignistyp="assignment", handelszeit=datetime(2026, 1, 2, 22, 0),
         buchungskurs=Decimal("2")),
    dict(exec_id="X2", conid=9100, side="SELL", menge=Decimal("-100"),
         preis=Decimal("45.00"), waehrung="USD", kommission_waehrung="USD",
         handelszeit=datetime(2026, 1, 5, 15, 0), buchungskurs=Decimal("2")),
]


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=_AUSFUEHRUNGEN, instrumente_=_INSTRUMENTE)
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        verbindung.execute(
            update(chains).where(chains.c.underlying == "AAA").values(oa_strategie="IC1")
        )
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


@pytest.fixture
def leerer_klient(migrated_db):
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_schluessel_und_werte(klient):
    daten = klient.get("/filterwerte").json()
    assert sorted(daten) == [
        "anlageklassen", "basiswerte", "endzustaende", "seiten", "strategien", "waehrungen",
    ]
    assert daten["basiswerte"] == ["AAA", "XXX"]       # XXX nur als loses Leg
    assert daten["anlageklassen"] == ["OPT", "STK"]
    assert daten["waehrungen"] == ["EUR", "USD"]       # USD nur am losen Leg
    assert daten["strategien"] == ["IC1"]
    assert daten["endzustaende"] == ["Geschlossen"]


def test_seiten_sind_die_der_ketten(klient):
    """Die Seite kennt nur die Kette (das lose Leg hat keine): die Liste
    enthält genau die Werte, die `/ketten` ausgibt, ohne leere Einträge."""
    daten = klient.get("/filterwerte").json()
    erwartet = sorted({k["seite"] for k in klient.get("/ketten").json()["treffer"]
                       if k["seite"] is not None})
    assert daten["seiten"] == erwartet
    assert daten["seiten"]  # AAA wurde mit SELL eröffnet, hat also eine Seite


def test_listen_sind_aufsteigend_ohne_doppelte_und_ohne_leere(klient):
    daten = klient.get("/filterwerte").json()
    for name, werte in daten.items():
        assert werte == sorted(set(werte)), name
        assert all(isinstance(w, str) and w for w in werte), name


def test_leerer_bestand(leerer_klient):
    daten = leerer_klient.get("/filterwerte").json()
    assert daten == {
        "basiswerte": [], "anlageklassen": [], "waehrungen": [],
        "strategien": [], "seiten": [], "endzustaende": [],
    }


def test_strategie_leer_taucht_nicht_auf(migrated_db):
    """Ohne OA-Zuordnung (oa_strategie NULL) gibt es keine Strategie zu wählen."""
    befuelle(migrated_db, ausfuehrungen=_AUSFUEHRUNGEN, instrumente_=_INSTRUMENTE)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        assert klient.get("/filterwerte").json()["strategien"] == []
