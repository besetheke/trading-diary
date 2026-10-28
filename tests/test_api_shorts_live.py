# ruff: noqa: E501
"""AP-19: Shorts-Übersicht in der Station — lesende Live-Instanz des Rollers und Befehl `schwelle-setzen`.

- `GET /roller-status-live` reicht den Status der Live-Instanz durch; ohne angebundenen Port `erreichbar: false`.
- `schwelle-setzen` geht mit `ticker`/`position`/`wert` an den Roller (Paper-Port oder mit `konto=live` an den Live-Port).
- An die Live-Instanz darf nur `schwelle-setzen` gehen (403, der Sender wird nie gerufen); unbekanntes Konto 404.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402

STATUS_LIVE = {"dienst": "options-roller", "shorts": {"zaehler": {"rot": 1}, "positionen": []}}


def _klient(db, sender=None, **kw):
    return TestClient(erzeuge_app(db, mit_journal=True, roller_port=8600, sende_roller_befehl=sender,
                                  hole_roller_status=lambda port: STATUS_LIVE if port == 8601 else None, **kw),
                      base_url="http://localhost", headers={"X-Trading-Station": "1"})


def test_live_status_wird_durchgereicht(migrated_db):
    d = _klient(migrated_db, roller_live_port=8601).get("/roller-status-live").json()
    assert d == {"erreichbar": True, "status": STATUS_LIVE}


def test_ohne_live_port_nicht_angebunden(migrated_db):
    assert _klient(migrated_db).get("/roller-status-live").json() == {"erreichbar": False, "status": None}


def test_schwelle_an_paper_und_live(migrated_db):
    gerufen = []

    def sender(port, ziel):
        gerufen.append((port, ziel))
        return 200, {"ok": True}
    k = _klient(migrated_db, sender, roller_live_port=8601)
    assert k.post("/journal/roller-befehl/schwelle-setzen", params={"ticker": "NVDA", "wert": "0.3"}).status_code == 200
    assert k.post("/journal/roller-befehl/schwelle-setzen",
                  params={"position": "5-naked", "konto": "live"}).status_code == 200
    assert gerufen == [(8600, "schwelle-setzen?ticker=NVDA&wert=0.3"), (8601, "schwelle-setzen?position=5-naked")]


def test_live_nur_schwelle(migrated_db):
    def sender(port, ziel):
        raise AssertionError("darf nicht gerufen werden")
    k = _klient(migrated_db, sender, roller_live_port=8601)
    assert k.post("/journal/roller-befehl/roll-freigabe", params={"kette": "K1", "konto": "live"}).status_code == 403
    assert k.post("/journal/roller-befehl/schwelle-setzen", params={"ticker": "X", "konto": "anders"}).status_code == 404


def test_live_ohne_port_503(migrated_db):
    r = _klient(migrated_db, lambda p, z: (200, {})).post("/journal/roller-befehl/schwelle-setzen",
                                                         params={"ticker": "X", "konto": "live"})
    assert r.status_code == 503
