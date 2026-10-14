"""Abnahmetest für AP-14f: `POST /journal/roller-befehl/kette-aufnehmen?kette=K003` nimmt eine
angehaltene Roller-Kette wieder auf. Die Station reicht Name und Parameter unverändert durch;
die Prüfung (Bestand passt zur Kette) macht der Roller-Dienst.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402


def test_kette_aufnehmen_reicht_parameter_durch(migrated_db):
    gerufen = []

    def sender(port, ziel):
        gerufen.append((port, ziel))
        return 200, {"ok": True, "kette": "K003"}
    klient = TestClient(erzeuge_app(migrated_db, mit_journal=True, roller_port=8600,
                                    sende_roller_befehl=sender))
    r = klient.post("/journal/roller-befehl/kette-aufnehmen?kette=K003")
    assert r.status_code == 200 and r.json() == {"ok": True, "kette": "K003"}
    assert gerufen == [(8600, "kette-aufnehmen?kette=K003")]


def test_ablehnung_des_dienstes_kommt_mit_begruendung(migrated_db):
    klient = TestClient(erzeuge_app(
        migrated_db, mit_journal=True, roller_port=8600,
        sende_roller_befehl=lambda p, z: (409, {"fehler": "Bestand passt weiterhin nicht"})))
    r = klient.post("/journal/roller-befehl/kette-aufnehmen?kette=K003")
    assert r.status_code == 409 and "weiterhin nicht" in r.json()["detail"]
