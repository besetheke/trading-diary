"""Abnahmetest für AP-14e (Station, Roller R3): `POST /journal/roller-befehl/{name}` reicht die
beiden Roller-Befehle (`roll-freigabe`, `strategie-pruefen`) an den Dienst durch.

Die Prüfung (nur Paper, Leitplanken) macht der Roller-Dienst; die Station reicht nur
durch. Ein erfundener Sender ersetzt die HTTP-Anfrage.
- Bekannter Befehl, Dienst antwortet 200: Antwort wird durchgereicht.
- Dienst lehnt ab (409 mit Begründung): dieselbe Begründung kommt mit 409 zurück.
- Dienst nicht erreichbar (503): 503.
- Unbekannter Name: 404, der Sender wird nie gerufen.
- Ohne `mit_journal` gibt es die Route nicht (das Schema bleibt lesend).
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402


def _klient(db, sender, **kw):
    # AP-17c: ein Aufruf der Station — lokale Adresse und Header der Station
    return TestClient(erzeuge_app(db, mit_journal=True, roller_port=8600,
                                  sende_roller_befehl=sender, **kw),
                      base_url="http://localhost", headers={"X-Trading-Station": "1"})


def test_befehl_wird_durchgereicht(migrated_db):
    gerufen = []

    def sender(port, name):
        gerufen.append((port, name))
        return 200, {"gefuellt": True}
    r = _klient(migrated_db, sender).post("/journal/roller-befehl/roll-freigabe")
    assert r.status_code == 200 and r.json() == {"gefuellt": True}
    assert gerufen == [(8600, "roll-freigabe")]


def test_ablehnung_mit_begruendung(migrated_db):
    r = _klient(migrated_db, lambda p, n: (409, {"fehler": "Leitplanke: heute wurde schon gerollt"})
                ).post("/journal/roller-befehl/roll-freigabe")
    assert r.status_code == 409
    assert "heute wurde schon gerollt" in r.json()["detail"]


def test_dienst_nicht_erreichbar(migrated_db):
    r = _klient(migrated_db, lambda p, n: (503, {"fehler": "Roller-Dienst nicht erreichbar"})
                ).post("/journal/roller-befehl/strategie-pruefen")
    assert r.status_code == 503


def test_unbekannter_befehl(migrated_db):
    def sender(port, name):
        raise AssertionError("darf nicht gerufen werden")
    r = _klient(migrated_db, sender).post("/journal/roller-befehl/alles-loeschen")
    assert r.status_code == 404


def test_ohne_journal_keine_route(migrated_db):
    k = TestClient(erzeuge_app(migrated_db, roller_port=8600,
                               sende_roller_befehl=lambda p, n: (200, {})))
    assert k.post("/journal/roller-befehl/roll-freigabe").status_code in (404, 405)
