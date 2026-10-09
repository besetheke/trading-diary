"""Abnahmetest für AP-08j2: Keine Adresse der Oberfläche darf von einer
API-Route verdeckt werden.

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-08j2.md`.

Der Fehler (Probelauf 09.10.2026): Die Oberfläche kennt die Seite
`/kalender`, die API den Endpunkt `GET /kalender?monat=…`. Wer die Seite
neu lädt oder als Lesezeichen öffnet, erreicht den Endpunkt statt der
Oberfläche und sieht einen JSON-Fehler (422). Innerhalb der Anwendung
(Verweise der Einzelseitenanwendung) fällt das nicht auf.

Der Test liest die Routen der Oberfläche aus `ui/src/main.tsx`
(`<Route path="…">`), setzt für Parameter (`:name`) Beispielwerte ein und
verlangt für jede Adresse die Oberfläche (`index.html`), nicht die API. Er
braucht keinen Build und keinen Browser.
"""

import pathlib
import re

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402

MAIN = pathlib.Path(__file__).resolve().parents[1] / "ui" / "src" / "main.tsx"
MARKE = "<!-- oberflaeche-testmarke -->"

BEISPIELWERTE = {"datum": "2026-09-15"}


def _routen_der_oberflaeche() -> list[str]:
    text = MAIN.read_text(encoding="utf-8")
    pfade = re.findall(r'<Route\s+path="([^"]+)"', text)
    return [p for p in pfade if p != "*"]


def _beispieladresse(pfad: str) -> str:
    def ersetze(treffer: re.Match) -> str:
        return BEISPIELWERTE.get(treffer.group(1), "1")

    return re.sub(r":([A-Za-z0-9_]+)", ersetze, pfad)


@pytest.fixture
def klient(migrated_db, tmp_path):
    ui = tmp_path / "dist"
    ui.mkdir()
    (ui / "index.html").write_text(f"<html><body>{MARKE}</body></html>", encoding="utf-8")
    with TestClient(erzeuge_app(migrated_db, ui_verzeichnis=ui, mit_journal=True)) as klient:
        yield klient


def test_die_routen_der_oberflaeche_werden_gefunden():
    routen = _routen_der_oberflaeche()

    assert "/" in routen
    assert any(p.startswith("/positionen/") for p in routen)
    assert any(p.startswith("/tag/") for p in routen)


def test_jede_adresse_der_oberflaeche_liefert_die_oberflaeche(klient):
    for pfad in _routen_der_oberflaeche():
        adresse = _beispieladresse(pfad)

        antwort = klient.get(adresse)

        assert antwort.status_code == 200, (adresse, antwort.status_code, antwort.text[:120])
        assert MARKE in antwort.text, (adresse, "von einer API-Route verdeckt")


def test_die_adressen_der_oberflaeche_stehen_nicht_im_openapi_schema(klient):
    schema = klient.get("/openapi.json").json()
    api_anfaenge = {p.strip("/").split("/")[0] for p in schema["paths"]}

    for pfad in _routen_der_oberflaeche():
        anfang = pfad.strip("/").split("/")[0]
        if anfang:  # "/" ist die Startseite
            assert anfang not in api_anfaenge, (pfad, "kollidiert mit einer API-Route")
