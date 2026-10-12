"""Abnahmetest für AP-14d: `GET /roller-status` ergänzt jede Position des Rollers
um die Geschichte ihrer Kette im Journal (`kette`) — „was hat diese Position
schon gekostet, bevor ich sie wieder rolle?"

Der Roller meldet Spreads (Basiswert, Verfall, Short, Long) und Breaches
(Basiswert, Verfall, Short). Das Journal kennt die offene Struktur der Kette
(Kontosicht, Stand des letzten Flex-Imports). Zuordnung: Basiswert (ein
angehängtes „W" wie bei SPXW/RUTW zählt zum Index), Verfall, Short-Strike, bei
Spreads auch der Long-Strike.

Welt: tests/fixtures_rebuild, Buchungskurs 1. DAX-Kette: Glied 1 (Put-Vertikale
19000/18900, Verfall 18.9.) geschlossen mit +92.00 EUR (Rechnung:
tests/test_rebuild.py), Glied 2 (18800/18700, Verfall 16.10.2026) offen, ein
belegter Roll. Prämie des offenen Glieds: ohne Bestand laut IB nur „bei
Eröffnung" bekannt: (verkauft 90 − gekauft 55) · Menge 1 · Multiplikator 5 =
175.00 EUR.

Erwartung für den Roller-Spread DAX 20261016 18800/18700: kette.chain_id die der
DAX-Kette, anzahl_rolls 1, realisiert_bisher 92.00, praemie_offen_eur 175.00.
Breach DAX 20261016 Short 18800 trifft dieselbe Kette. Ein Spread mit anderem
Verfall oder Strike: kein `kette`. SPXW wird als SPX gesucht (kein SPX im Journal →
kein `kette`, aber ohne Fehler).
"""

from decimal import Decimal

import pytest
from fixtures_rebuild import AUSFUEHRUNGEN, befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


def _status():
    return {
        "dienst": "options-roller", "stufe": "R2",
        "spreads": [
            {"key": "a", "typ": "BPS", "symbol": "DAX", "expiration": "20261016",
             "short": 18800.0, "long": 18700.0, "menge": 1},
            {"key": "b", "typ": "BPS", "symbol": "DAX", "expiration": "20261023",
             "short": 18800.0, "long": 18700.0, "menge": 1},
            {"key": "c", "typ": "BPS", "symbol": "SPXW", "expiration": "20261016",
             "short": 7700.0, "long": 7650.0, "menge": 1},
        ],
        "breaches": [
            {"position_key": "p", "symbol": "DAX", "expiration": "20261016", "right": "P",
             "short_strike": 18800.0},
        ],
    }


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")}
                                         for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)
    return TestClient(erzeuge_app(migrated_db, roller_port=8600,
                                  hole_roller_status=lambda port: _status()))


def test_spread_mit_kette(klient):
    s = klient.get("/roller-status").json()["status"]
    a = s["spreads"][0]["kette"]
    assert a["anzahl_rolls"] == 1
    assert Decimal(a["realisiert_bisher"]) == Decimal("92.00")
    assert Decimal(a["praemie_offen_eur"]) == Decimal("175.00")
    assert isinstance(a["chain_id"], int)


def test_breach_trifft_dieselbe_kette(klient):
    s = klient.get("/roller-status").json()["status"]
    assert s["breaches"][0]["kette"]["chain_id"] == s["spreads"][0]["kette"]["chain_id"]


def test_ohne_treffer_kette_null(klient):
    s = klient.get("/roller-status").json()["status"]
    assert "kette" not in s["spreads"][1]
    assert "kette" not in s["spreads"][2]


def test_roller_aus_bleibt_ohne_fehler(migrated_db):
    k = TestClient(erzeuge_app(migrated_db, roller_port=8600,
                               hole_roller_status=lambda port: None))
    assert k.get("/roller-status").json() == {"erreichbar": False, "status": None}


def test_gleiche_ketten_werden_zusammengefasst():
    """Zwei offene Ketten mit denselben Strikes (z. B. in zwei Orders eröffnet) sind
    für den Roller eine Position. Zusammenfassung: Rolls = das Maximum, Beträge =
    Summen, `ketten` = Anzahl, `chain_id` = die kleinere.
    Von Hand: Rolls 2 und 4 → 4; bisher −100.00 + −250.50 = −350.50; Prämie offen
    300.00 + 120.00 = 420.00; aktuell 200.00 + (leer) = 200.00; leer bleibt leer."""
    from api.app import _fasse_ketten_zusammen
    a = {"chain_id": 7, "anzahl_rolls": 2, "strategie": "S", "eroeffnet_am": "2026-09-01",
         "realisiert_bisher": "-100.00", "praemie_offen_eur": "300.00",
         "praemie_aktuell_eur": "200.00", "unrealisiert_eur": None}
    b = {"chain_id": 5, "anzahl_rolls": 4, "strategie": "S", "eroeffnet_am": "2026-09-15",
         "realisiert_bisher": "-250.50", "praemie_offen_eur": "120.00",
         "praemie_aktuell_eur": None, "unrealisiert_eur": None}
    z = _fasse_ketten_zusammen([a, b])
    assert (z["chain_id"], z["ketten"], z["anzahl_rolls"]) == (5, 2, 4)
    assert z["realisiert_bisher"] == "-350.50"
    assert z["praemie_offen_eur"] == "420.00"
    assert z["praemie_aktuell_eur"] == "200.00"
    assert z["unrealisiert_eur"] is None
    assert z["eroeffnet_am"] == "2026-09-01"
    assert _fasse_ketten_zusammen([a])["ketten"] == 1


def test_calls_stehen_im_journal_als_vertical(migrated_db):
    """Call-Spreads heißen im Journal teils „Vertical“ statt „BCS" — sie werden
    trotzdem zugeordnet (Typ ist kein Zuordnungsmerkmal, nur Vertikale überhaupt)."""
    from api.app import _VERTIKALEN
    assert {"BPS", "BCS", "Vertical"} <= set(_VERTIKALEN)
