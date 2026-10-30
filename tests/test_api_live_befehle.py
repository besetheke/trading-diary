# ruff: noqa: E501
"""AP-21 (Live-Start DAX, 02.11.2026): Befehle an die Live-Instanz des Rollers.

- Ohne Geldbewegung (schwelle-setzen, strategie-pruefen, auto-aus = Not-Aus) gehen direkt durch.
- Orders und das Einschalten der Automatik (roll-freigabe, oeffnen, kette-aufnehmen, auto-an) nur mit
  bestaetigt=ECHTGELD; sonst 403, der Sender wird nie gerufen. Die Bestätigung wird nicht an den Roller weitergereicht.
- Paper braucht keine Bestätigung.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402


def _klient(db, gerufen):
    def sender(port, ziel):
        gerufen.append((port, ziel))
        return 200, {"ok": True}
    return TestClient(erzeuge_app(db, mit_journal=True, roller_port=8600, roller_live_port=8601, sende_roller_befehl=sender),
                      base_url="http://localhost", headers={"X-Trading-Station": "1"})


def test_live_order_nur_mit_bestaetigung(migrated_db):
    gerufen = []
    k = _klient(migrated_db, gerufen)
    assert k.post("/journal/roller-befehl/roll-freigabe", params={"kette": "K1", "konto": "live"}).status_code == 403
    assert k.post("/journal/roller-befehl/oeffnen", params={"strategie": "DAX: BPS D12 W250 14DTE", "konto": "live", "bestaetigt": "ja"}).status_code == 403
    assert gerufen == []
    r = k.post("/journal/roller-befehl/roll-freigabe", params={"kette": "K1", "konto": "live", "bestaetigt": "ECHTGELD"})
    assert r.status_code == 200
    assert gerufen == [(8601, "roll-freigabe?kette=K1")]


def test_live_ohne_geldbewegung_direkt(migrated_db):
    gerufen = []
    k = _klient(migrated_db, gerufen)
    assert k.post("/journal/roller-befehl/auto-aus", params={"konto": "live"}).status_code == 200
    assert k.post("/journal/roller-befehl/strategie-pruefen", params={"konto": "live"}).status_code == 200
    assert k.post("/journal/roller-befehl/auto-an", params={"konto": "live"}).status_code == 403
    assert gerufen == [(8601, "auto-aus"), (8601, "strategie-pruefen")]


def test_paper_ohne_bestaetigung(migrated_db):
    gerufen = []
    k = _klient(migrated_db, gerufen)
    assert k.post("/journal/roller-befehl/roll-freigabe", params={"kette": "K1"}).status_code == 200
    assert gerufen == [(8600, "roll-freigabe?kette=K1")]
