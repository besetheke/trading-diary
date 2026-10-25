# ruff: noqa: E501
"""Journal-Suche, Tag-Filter und Anhänge (AP-17g, M05).

Welt: drei Ketten mit Notizen und Tags.
  A: Notiz „Roll zu spät, Delta schon 0,45“, Tags {schlecht getimt, Roll}, ein Anhang (png)
  B: Notiz „sauberer Verfall“, Tags {Roll}
  C: Notiz „zu spät eingestiegen“, Tags {schlecht getimt}
Erwartung: Suche „zu spät“ → A und C; Tags alle {schlecht getimt, Roll} → nur A; irgendeines → A, B, C; mit Anhang → nur A;
ohne Filter alle drei (zentrale Liste); nach einem Rebuild bleiben Treffer erreichbar.
"""
import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import text

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def welt(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with create_db_engine(migrated_db).connect() as v:
        ids = [str(r[0]) for r in v.execute(text("SELECT chain_id FROM chains WHERE sicht='konto' ORDER BY chain_id LIMIT 3"))]
    assert len(ids) == 3
    c = TestClient(erzeuge_app(migrated_db, mit_journal=True), base_url="http://localhost", headers={"X-Trading-Station": "1"})
    a, b, d = ids
    for kette, notiz, tag_liste in ((a, "Roll zu spät, Delta schon 0,45", ["schlecht getimt", "Roll"]),
                                    (b, "sauberer Verfall", ["Roll"]), (d, "zu spät eingestiegen", ["schlecht getimt"])):
        assert c.post(f"/journal/chain/{kette}/notizen", json={"text": notiz}).status_code == 201
        assert c.put(f"/journal/chain/{kette}/tags", json={"tags": tag_liste}).status_code == 200
    assert c.post(f"/journal/chain/{a}/anhaenge?name=screenshot.png", content=PNG, headers={"Content-Type": "image/png"}).status_code == 201
    return c, ids, migrated_db


def treffer_ids(antwort):
    return sorted(t["scope_id"] for t in antwort.json())


def test_suche_ueber_notiztexte(welt):
    c, (a, b, d), _ = welt
    assert treffer_ids(c.get("/journal-suche", params={"q": "zu spät"})) == sorted([a, d])
    assert treffer_ids(c.get("/journal-suche", params={"q": "ZU SPÄT"})) == sorted([a, d])            # ohne Beachtung der Schreibweise
    erster = c.get("/journal-suche", params={"q": "sauberer"}).json()[0]
    assert erster["scope_id"] == b and "sauberer Verfall" in erster["notizen"][0]["snippet"]
    assert erster["kontext"]["text"].startswith(f"Kette {b}") and erster["kontext"]["link"] == f"/positionen/{b}"


def test_tag_filter_alle_oder_irgendeines(welt):
    c, (a, b, d), _ = welt
    assert treffer_ids(c.get("/journal-suche", params={"tags": ["schlecht getimt", "Roll"], "modus": "alle"})) == [a]
    assert treffer_ids(c.get("/journal-suche", params={"tags": ["schlecht getimt", "roll"], "modus": "irgendeines"})) == sorted([a, b, d])
    assert treffer_ids(c.get("/journal-suche", params={"tags": ["gibt es nicht"], "modus": "alle"})) == []


def test_anhang_filter_und_zentrale_liste(welt):
    c, (a, b, d), _ = welt
    assert treffer_ids(c.get("/journal-suche", params={"mit_anhang": "true"})) == [a]
    assert treffer_ids(c.get("/journal-suche")) == sorted([a, b, d])                       # zentrale Liste ohne Filter
    # die gesuchte Abfrage „alle schlecht getimten Rolls mit Screenshot“
    antwort = c.get("/journal-suche", params={"tags": ["schlecht getimt", "Roll"], "modus": "alle", "mit_anhang": "true"})
    assert treffer_ids(antwort) == [a] and antwort.json()[0]["anzahl_anhaenge"] == 1


def test_treffer_bleiben_nach_dem_rebuild_erreichbar(welt):
    c, (a, b, d), db = welt
    rebuild(db)
    assert treffer_ids(c.get("/journal-suche", params={"tags": ["Roll"], "modus": "alle"})) == sorted([a, b])


def test_anhang_liste_und_datei(welt):
    c, (a, *_), _ = welt
    liste = c.get(f"/journal/chain/{a}/anhaenge").json()
    assert len(liste) == 1 and liste[0]["name"] == "screenshot.png" and liste[0]["mime"] == "image/png" and liste[0]["groesse"] == len(PNG)
    datei = c.get(f"/anhang/{liste[0]['id']}")
    assert datei.status_code == 200 and datei.content == PNG and datei.headers["content-type"] == "image/png"
    assert datei.headers["x-content-type-options"] == "nosniff"
    assert c.get("/anhang/99999").status_code == 404


def test_anhang_grenzen_und_schutz(welt):
    c, (a, *_), _ = welt
    pfad = f"/journal/chain/{a}/anhaenge"
    assert c.post(pfad, content=b"x", headers={"Content-Type": "application/x-msdownload"}).status_code == 422       # Typ
    assert c.post(pfad, content=b"", headers={"Content-Type": "image/png"}).status_code == 422                       # leer
    assert c.post(pfad, content=b"0" * (5 * 1024 * 1024 + 1), headers={"Content-Type": "image/png"}).status_code == 413    # zu groß
    assert c.post("/journal/chain/999999/anhaenge", content=PNG, headers={"Content-Type": "image/png"}).status_code == 404
    fremd = TestClient(c.app, base_url="http://localhost")                                   # ohne Station-Header
    assert fremd.post(pfad, content=PNG, headers={"Content-Type": "image/png"}).status_code == 403
    # Dateiname mit Pfadtricks landet harmlos im Anhang-Ordner
    antwort = c.post(pfad + "?name=../../boese.png", content=PNG, headers={"Content-Type": "image/png"})
    assert antwort.status_code == 201 and "/" not in antwort.json()["name"] and ".." not in antwort.json()["name"]


def test_anzahlgrenze_und_kein_loeschweg(welt):
    c, (a, *_), _ = welt
    pfad = f"/journal/chain/{a}/anhaenge"
    for _ in range(19):                       # einer liegt schon: 20 ist die Grenze
        assert c.post(pfad, content=PNG, headers={"Content-Type": "image/png"}).status_code == 201
    assert c.post(pfad, content=PNG, headers={"Content-Type": "image/png"}).status_code == 422
    assert c.delete("/anhang/1").status_code == 405                                         # Benutzerdaten werden nicht gelöscht
