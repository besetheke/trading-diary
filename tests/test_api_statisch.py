"""Abnahmetests für die statische Auslieferung der Oberfläche (AP-08l).

Geschrieben nach §11.2 des Plans durch das starke Modell (AP-08lv) — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-08lv.md`.

**Was diese Datei prüft und was nicht.** Die erste Fassung der Oberfläche
kommt bewusst ohne Frontend-Testwerkzeug (Entscheidung des Nutzers,
22.09.2026): Vitest gegen Playwright wird später verglichen, wenn die
Oberfläche eigene Logik trägt. Maschinell geprüft wird deshalb nur die
Naht zwischen API und gebautem Frontend — sie liegt in Python und ist die
Stelle, an der ein Fehler still wäre: Eine Oberfläche, die eine API-Route
verschluckt, fällt beim Durchklicken nicht auf, aber später in jeder
zweiten Anfrage.

Das Aussehen und die Bedienbarkeit werden im Browser begutachtet, nicht
hier — siehe AP-08lv, Abschnitt „Abnahme".

Das Modul springt still ab, solange FastAPI oder `api/app.py` fehlen.
"""

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

INDEX = "<!doctype html><html><body><div id='wurzel'></div></body></html>"
SKRIPT = "console.log('Positionsliste');"


@pytest.fixture
def oberflaeche(tmp_path):
    """Ein gebautes Frontend, wie `npm run build` es hinterlässt."""
    verzeichnis = tmp_path / "dist"
    (verzeichnis / "assets").mkdir(parents=True)
    (verzeichnis / "index.html").write_text(INDEX, encoding="utf-8")
    (verzeichnis / "assets" / "app.js").write_text(SKRIPT, encoding="utf-8")
    return verzeichnis


@pytest.fixture
def klient(migrated_db, oberflaeche):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db, ui_verzeichnis=oberflaeche)) as klient:
        yield klient


@pytest.fixture
def klient_ohne_oberflaeche(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_wurzel_liefert_die_oberflaeche(klient):
    """Vertrag 1: Im Betrieb liefert FastAPI das gebaute Frontend aus
    (Plan §3) — kein Node-Server während der Handelszeiten."""
    antwort = klient.get("/")

    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("text/html")
    assert antwort.text == INDEX


def test_beiwerk_wird_ausgeliefert(klient):
    """Vertrag 1: Vite legt JavaScript und CSS unter `assets/` ab."""
    antwort = klient.get("/assets/app.js")

    assert antwort.status_code == 200
    assert antwort.text == SKRIPT


def test_unbekannter_pfad_faellt_auf_die_oberflaeche_zurueck(klient):
    """Vertrag 2: Eine Einzelseitenanwendung führt ihre Wege selbst. Ein
    Aufruf direkt auf `/positionen/17` — etwa aus einem Lesezeichen — muss
    die Oberfläche liefern, nicht 404, sonst sind tiefe Verweise wertlos."""
    antwort = klient.get("/positionen/17")

    assert antwort.status_code == 200
    assert antwort.text == INDEX


def test_die_api_geht_vor(klient):
    """Vertrag 3: Der Rückfall darf keine API-Route verschlucken — der
    Fehler, der beim Durchklicken nicht auffällt."""
    ketten = klient.get("/ketten")
    schema = klient.get("/openapi.json")

    assert ketten.status_code == 200
    assert ketten.json()["gesamt"] == 5
    assert schema.status_code == 200
    assert "/ketten" in schema.json()["paths"]


def test_fehlerhafter_api_aufruf_bleibt_ein_fehler(klient):
    """Vertrag 3: `/ketten/abc` ist eine kaputte API-Anfrage, kein
    unbekannter Weg der Oberfläche. Wer hier auf die Oberfläche zurückfällt,
    verwandelt jeden Tippfehler in eine leere Seite statt in eine Meldung."""
    antwort = klient.get("/ketten/abc")

    assert antwort.status_code == 422


def test_unbekannte_struktur_bleibt_404(klient):
    """Vertrag 3: Auch ein gültig geformter, aber unbekannter Bezeichner
    behält seine Antwort aus der API."""
    assert klient.get("/strukturen/999999").status_code == 404


def test_ohne_gebaute_oberflaeche_bleibt_die_api_nutzbar(klient_ohne_oberflaeche):
    """Vertrag 4: Ohne `npm run build` gibt es keine Oberfläche — die API
    muss trotzdem laufen, und die Wurzel sagt, was fehlt, statt abzustürzen.
    Das ist der Normalzustand auf einem frisch geklonten Rechner."""
    ketten = klient_ohne_oberflaeche.get("/ketten")
    wurzel = klient_ohne_oberflaeche.get("/")

    assert ketten.status_code == 200
    assert wurzel.status_code == 404
    assert "ui" in wurzel.text.lower() or "build" in wurzel.text.lower()


@pytest.mark.parametrize(
    "pfad",
    ["/../pyproject.toml", "/assets/../../pyproject.toml", "/%2e%2e/pyproject.toml"],
)
def test_kein_ausbruch_aus_dem_oberflaechenverzeichnis(klient, pfad):
    """Vertrag 5: Ausgeliefert wird nur, was unter dem Bauverzeichnis liegt.
    Ein Pfad, der daraus ausbricht, liefert niemals eine Datei des
    Projekts — auch wenn das Journal lokal läuft."""
    antwort = klient.get(pfad)

    assert "[project]" not in antwort.text
    assert antwort.status_code in (200, 400, 404)
