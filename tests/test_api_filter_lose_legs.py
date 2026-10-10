"""Abnahmetests für AP-07f, Teil 2: lose Legs unter Filtern. Unveränderlich.

Regel (Nutzer, 10.10.2026): Ein Filter, den ein loses Leg kennt (Basiswert,
Anlageklasse, Währung, Schließungszeitraum), gilt auch für das lose Leg. Ein
Filter, den es nicht kennt (Strategie, Seite, Endzustand, Rolls), schließt es
aus. Ohne Filter zählt es mit (AP-06i).

Testwelt (Rebuild, frei erfunden, Kommission -2.00 je Ausführung):

  AAA  EUR  Option, Multiplikator 10: SELL 10.00 am 2026-01-02, BUY 4.00 am
            2026-01-03 → (60) - 4 = 56.00, geschlossen 2026-01-03.
  XXX  USD  Aktie, Zuteilung ohne Optionsstruktur (loses Leg), Kurs 2:
            BUY 100 zu 50.00 (Zuteilung) am 2026-01-02 22:00,
            SELL 100 zu 45.00 am 2026-01-05 15:00
            → ((45 - 50) * 100 - 4) * 2 = -1008.00, geschlossen 2026-01-05.

Kurve ohne Filter: 01-03 +56.00 (kum 56.00) | 01-05 -1008.00 (kum -952.00,
DD -1008.00). `chains.oa_strategie` von AAA wird direkt auf "IC1" gesetzt.
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


def _tage(klient, **params):
    daten = klient.get("/auswertung", params=params).json()
    return [(t["datum"], t["netto_eur"]) for t in daten["tage"]], daten["ergebnis"]


def test_ohne_filter_zaehlt_das_lose_leg_mit(klient):
    tage, ergebnis = _tage(klient)
    assert tage == [("2026-01-03", "56.00"), ("2026-01-05", "-1008.00")]
    assert ergebnis["summe_netto_eur"] == "-952.00"
    assert ergebnis["lose_legs_eingeschlossen"] is True
    daten = klient.get("/auswertung").json()
    assert daten["max_drawdown_eur"] == "-1008.00"
    assert daten["max_drawdown_datum"] == "2026-01-05"


def test_basiswert_gilt_auch_fuer_das_lose_leg(klient):
    """Ticker XXX: nur das lose Leg, keine Kette."""
    tage, ergebnis = _tage(klient, basiswert="XXX")
    assert tage == [("2026-01-05", "-1008.00")]
    assert ergebnis["anzahl_ketten"] == 0
    assert ergebnis["summe_netto_eur"] == "-1008.00"
    assert ergebnis["lose_legs_eingeschlossen"] is True
    """Ticker AAA: das lose Leg gehört einem anderen Basiswert und fällt weg."""
    tage, ergebnis = _tage(klient, basiswert="AAA")
    assert tage == [("2026-01-03", "56.00")]
    assert ergebnis["anzahl_ketten"] == 1


def test_anlageklasse_gilt_auch_fuer_das_lose_leg(klient):
    assert _tage(klient, anlageklasse="STK")[0] == [("2026-01-05", "-1008.00")]
    assert _tage(klient, anlageklasse="OPT")[0] == [("2026-01-03", "56.00")]


def test_waehrung_gilt_auch_fuer_das_lose_leg(klient):
    """Die Währung des losen Legs ist die der schließenden Ausführung."""
    assert _tage(klient, waehrung="USD")[0] == [("2026-01-05", "-1008.00")]
    assert _tage(klient, waehrung="EUR")[0] == [("2026-01-03", "56.00")]


def test_schliessungszeitraum_gilt_auch_fuer_das_lose_leg(klient):
    assert _tage(klient, geschlossen_ab="2026-01-04")[0] == [("2026-01-05", "-1008.00")]
    assert _tage(klient, geschlossen_bis="2026-01-03")[0] == [("2026-01-03", "56.00")]
    # Der Tag der Schließung (15:00) zählt einschließlich dazu.
    assert _tage(klient, geschlossen_bis="2026-01-05")[0] == [
        ("2026-01-03", "56.00"), ("2026-01-05", "-1008.00")]


@pytest.mark.parametrize("params", [
    {"strategie": "IC1"},
    {"endzustand": "Geschlossen"},
    {"min_rolls": 0},
    {"max_rolls": 5},
    {"seite": "short"},
])
def test_filter_ohne_wert_fuer_lose_legs_schliessen_sie_aus(klient, params):
    """Strategie, Endzustand, Rolls und Seite kennt ein loses Leg nicht."""
    tage, ergebnis = _tage(klient, **params)
    assert ("2026-01-05", "-1008.00") not in tage
    assert ergebnis["lose_legs_eingeschlossen"] is False


def test_strategie_laesst_nur_die_kette_uebrig(klient):
    tage, ergebnis = _tage(klient, strategie="IC1")
    assert tage == [("2026-01-03", "56.00")]
    assert ergebnis["summe_netto_eur"] == "56.00"
    assert ergebnis["anzahl_ketten"] == 1


def test_zeitraum_von_bis_gilt_fuer_das_lose_leg(klient):
    """Z2/Z4: von=2026-01-04 → nur das lose Leg, die Kurve beginnt bei 0."""
    daten = klient.get("/auswertung", params={"von": "2026-01-04"}).json()
    assert [(t["datum"], t["kumuliert_eur"], t["drawdown_eur"]) for t in daten["tage"]] == [
        ("2026-01-05", "-1008.00", "-1008.00")]


def test_ketten_liste_kennt_keine_losen_legs(klient):
    daten = klient.get("/ketten").json()
    assert [k["underlying"] for k in daten["treffer"]] == ["AAA"]
