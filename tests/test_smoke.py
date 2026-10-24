# ruff: noqa: E501
"""Smoke-Test (AP-17g, M08): alle Seiten und lesenden API-Wege der Oberfläche antworten mit 200."""
import importlib.util
import pathlib

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[1]
spezifikation = importlib.util.spec_from_file_location("smoke", WURZEL / "werkzeuge" / "smoke.py")
smoke = importlib.util.module_from_spec(spezifikation)
spezifikation.loader.exec_module(smoke)


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    dist = WURZEL / "ui" / "dist"
    if not dist.is_dir():
        pytest.skip("ui/dist nicht gebaut")
    return TestClient(erzeuge_app(migrated_db, mit_journal=True, ui_verzeichnis=dist))


def test_alle_seiten_und_api_wege_antworten(klient):
    abweichungen = smoke.smoke(lambda pfad: klient.get(pfad).status_code)
    assert abweichungen == []


def test_der_test_findet_seiten_und_wege_und_erkennt_einen_fehlenden_weg(klient):
    assert len(smoke.seiten()) >= 15 and len(smoke.api_wege()) >= 15
    assert "/roll-kosten" in smoke.seiten() and "/roll-kosten-auswertung" in smoke.api_wege()
    # Ein Weg, den die API nicht kennt, ist ein Befund (R11-Fall: Oberfläche ruft etwas, das fehlt)
    def mit_luecke(pfad):
        return 404 if pfad.startswith("/titel-auswertung") else klient.get(pfad).status_code
    assert ("/titel-auswertung", 404) in smoke.smoke(mit_luecke)


def test_kein_api_weg_der_oberflaeche_fehlt_in_der_api(klient):
    """Jeder Weg aus api.ts ist ein API-Weg: keiner fällt auf die Einstiegsseite zurück."""
    for weg in smoke.api_wege():
        antwort = klient.get(weg + smoke.PFLICHTPARAMETER.get(weg, ""))
        assert "text/html" not in antwort.headers.get("content-type", ""), f"{weg} liefert HTML statt JSON"
