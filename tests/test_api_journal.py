"""Abnahmetests für AP-07j: Journal-Endpunkte (Notizen und Tags) der API.

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-07j.md`.

Das Modul springt still ab, solange `api/app.py` (oder FastAPI) fehlt.

Alle Daten stammen aus `tests/fixtures_rebuild.py` und sind frei erfunden.
Die Journal-Endpunkte schreiben ausschließlich in `journal_entries`, `tags`
und `entity_tags` (Benutzerdaten, überleben jeden Rebuild).

Bereiche (`scope_typ`): `chain`, `structure`, `campaign` (jeweils die
numerische ID als Text) und `tag` - der **Handelstag** (`scope_id` =
ISO-Datum, z. B. `2026-10-09`): das tägliche Journal.
"""

from datetime import datetime, timedelta

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import func, insert, select

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import campaigns, entity_tags, executions, journal_entries, legs  # noqa: E402


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db, mit_journal=True)) as klient:
        yield klient


def _eine_kette(klient) -> int:
    return klient.get("/ketten").json()["treffer"][0]["chain_id"]


def _eine_struktur(klient) -> int:
    kette = klient.get(f"/ketten/{_eine_kette(klient)}").json()
    return kette["glieder"][0]["struktur"]["structure_id"]


def _zaehlen(db, tabelle) -> int:
    engine = create_db_engine(db)
    with engine.connect() as v:
        return v.execute(select(func.count()).select_from(tabelle)).scalar_one()


# ---------------------------------------------------------------- Notizen


def test_notiz_anlegen_und_lesen(klient):
    kette = _eine_kette(klient)

    antwort = klient.post(f"/journal/chain/{kette}/notizen", json={"text": "Roll vorgezogen"})

    assert antwort.status_code == 201
    notiz = antwort.json()
    assert notiz["scope_typ"] == "chain"
    assert notiz["scope_id"] == str(kette)
    assert notiz["text"] == "Roll vorgezogen"
    assert notiz["geaendert_am"] is None
    jetzt = datetime.now()
    assert abs(datetime.fromisoformat(notiz["erstellt_am"]) - jetzt) < timedelta(minutes=1)
    gelesen = klient.get(f"/journal/chain/{kette}").json()
    assert gelesen["scope_typ"] == "chain"
    assert gelesen["scope_id"] == str(kette)
    assert gelesen["notizen"] == [notiz]
    assert gelesen["tags"] == []


def test_text_bleibt_unveraendert_samt_zeilenumbruch(klient):
    kette = _eine_kette(klient)
    text = "  Erste Zeile\nZweite Zeile "

    notiz = klient.post(f"/journal/chain/{kette}/notizen", json={"text": text}).json()

    assert notiz["text"] == text


def test_notizen_neueste_zuerst(klient):
    kette = _eine_kette(klient)
    erste = klient.post(f"/journal/chain/{kette}/notizen", json={"text": "eins"}).json()
    zweite = klient.post(f"/journal/chain/{kette}/notizen", json={"text": "zwei"}).json()

    notizen = klient.get(f"/journal/chain/{kette}").json()["notizen"]

    # Gleiche Sekunde möglich: bei Gleichstand entscheidet die größere id.
    assert [n["id"] for n in notizen] == [zweite["id"], erste["id"]]


def test_notiz_aendern(klient):
    kette = _eine_kette(klient)
    angelegt = klient.post(f"/journal/chain/{kette}/notizen", json={"text": "alt"}).json()

    antwort = klient.put(f"/journal/notizen/{angelegt['id']}", json={"text": "neu"})

    assert antwort.status_code == 200
    geaendert = antwort.json()
    assert geaendert["id"] == angelegt["id"]
    assert geaendert["text"] == "neu"
    assert geaendert["erstellt_am"] == angelegt["erstellt_am"]
    assert geaendert["geaendert_am"] is not None
    assert klient.get(f"/journal/chain/{kette}").json()["notizen"] == [geaendert]


def test_notiz_loeschen(klient):
    kette = _eine_kette(klient)
    notiz = klient.post(f"/journal/chain/{kette}/notizen", json={"text": "weg"}).json()

    assert klient.delete(f"/journal/notizen/{notiz['id']}").status_code == 204

    assert klient.get(f"/journal/chain/{kette}").json()["notizen"] == []
    assert klient.delete(f"/journal/notizen/{notiz['id']}").status_code == 404


def test_unbekannte_notiz_ist_404(klient):
    assert klient.put("/journal/notizen/99999", json={"text": "x"}).status_code == 404
    assert klient.delete("/journal/notizen/99999").status_code == 404


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_leerer_text_ist_422(klient, text):
    kette = _eine_kette(klient)
    angelegt = klient.post(f"/journal/chain/{kette}/notizen", json={"text": "ok"}).json()

    assert klient.post(f"/journal/chain/{kette}/notizen", json={"text": text}).status_code == 422
    assert klient.put(f"/journal/notizen/{angelegt['id']}", json={"text": text}).status_code == 422
    assert klient.get(f"/journal/chain/{kette}").json()["notizen"][0]["text"] == "ok"


def test_fehlender_text_ist_422(klient):
    kette = _eine_kette(klient)

    assert klient.post(f"/journal/chain/{kette}/notizen", json={}).status_code == 422


# ---------------------------------------------------------------- Bereiche


def test_struktur_und_kette_mit_gleicher_nummer_sind_getrennt(klient):
    kette, struktur = _eine_kette(klient), _eine_struktur(klient)
    klient.post(f"/journal/chain/{kette}/notizen", json={"text": "Kette"})
    klient.post(f"/journal/structure/{struktur}/notizen", json={"text": "Struktur"})

    assert [n["text"] for n in klient.get(f"/journal/chain/{kette}").json()["notizen"]] == ["Kette"]
    assert [n["text"] for n in klient.get(f"/journal/structure/{struktur}").json()["notizen"]] == [
        "Struktur"]


def test_kampagne_als_bereich(klient, migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.begin() as v:
        kid = v.execute(insert(campaigns).values(
            underlying="DAX", eroeffnet_am=datetime(2026, 9, 1, 10, 0))).inserted_primary_key[0]

    antwort = klient.post(f"/journal/campaign/{kid}/notizen", json={"text": "Kampagne"})

    assert antwort.status_code == 201
    assert klient.get(f"/journal/campaign/{kid}").json()["notizen"][0]["text"] == "Kampagne"


def test_tagesjournal_braucht_kein_vorhandenes_objekt(klient):
    antwort = klient.post("/journal/tag/2026-10-09/notizen", json={"text": "Ruhiger Tag"})

    assert antwort.status_code == 201
    gelesen = klient.get("/journal/tag/2026-10-09").json()
    assert (gelesen["scope_typ"], gelesen["scope_id"]) == ("tag", "2026-10-09")
    assert [n["text"] for n in gelesen["notizen"]] == ["Ruhiger Tag"]
    assert klient.get("/journal/tag/2026-10-10").json()["notizen"] == []


def test_unbekannte_objekte_sind_404(klient):
    assert klient.get("/journal/chain/999999").status_code == 404
    assert klient.get("/journal/structure/999999").status_code == 404
    assert klient.get("/journal/campaign/999999").status_code == 404
    assert klient.post("/journal/chain/999999/notizen", json={"text": "x"}).status_code == 404
    assert klient.put("/journal/chain/999999/tags", json={"tags": ["a"]}).status_code == 404


@pytest.mark.parametrize("pfad", [
    "/journal/unsinn/1",
    "/journal/chain/abc",
    "/journal/structure/1.5",
    "/journal/tag/2026-13-40",
    "/journal/tag/heute",
])
def test_ungueltiger_bereich_ist_422(klient, pfad):
    assert klient.get(pfad).status_code == 422
    assert klient.post(pfad + "/notizen", json={"text": "x"}).status_code == 422


# ---------------------------------------------------------------- Tags


def test_tags_ersetzen_und_zaehlen(klient):
    kette = _eine_kette(klient)

    erste = klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["Roll", "IC"]})

    assert erste.status_code == 200
    assert erste.json()["tags"] == ["IC", "Roll"]  # alphabetisch, Groß-/Kleinschreibung egal
    zweite = klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["roll", "Neu"]})
    # "roll" ist der vorhandene Tag "Roll" - dessen Schreibweise gilt.
    assert zweite.json()["tags"] == ["Neu", "Roll"]
    assert klient.get(f"/journal/chain/{kette}").json()["tags"] == ["Neu", "Roll"]
    assert klient.get("/tags").json() == [
        {"name": "IC", "anzahl": 0},
        {"name": "Neu", "anzahl": 1},
        {"name": "Roll", "anzahl": 1},
    ]


def test_tags_dieselbe_schreibweise_in_einer_anfrage_zaehlt_einmal(klient):
    kette = _eine_kette(klient)

    antwort = klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["a", "A", " a "]})

    assert antwort.json()["tags"] == ["a"]  # erste Schreibweise, ohne Leerzeichen


def test_tags_leere_liste_entfernt_alle(klient):
    kette = _eine_kette(klient)
    klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["x"]})

    antwort = klient.put(f"/journal/chain/{kette}/tags", json={"tags": []})

    assert antwort.status_code == 200
    assert antwort.json()["tags"] == []


def test_leerer_tagname_ist_422(klient):
    kette = _eine_kette(klient)
    klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["x"]})

    assert klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["  "]}).status_code == 422
    assert klient.get(f"/journal/chain/{kette}").json()["tags"] == ["x"]  # nichts verändert


def test_tags_je_bereich_getrennt_auch_am_tag(klient):
    kette = _eine_kette(klient)
    klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["Roll"]})
    klient.put("/journal/tag/2026-10-09/tags", json={"tags": ["Verlusttag"]})

    assert klient.get("/journal/tag/2026-10-09").json()["tags"] == ["Verlusttag"]
    assert klient.get(f"/journal/chain/{kette}").json()["tags"] == ["Roll"]


# ---------------------------------------------------------------- Rebuild, Grenzen


def test_notizen_und_tags_ueberleben_den_rebuild(klient, migrated_db):
    kette = _eine_kette(klient)
    klient.post(f"/journal/chain/{kette}/notizen", json={"text": "bleibt"})
    klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["Roll"]})
    vorher = klient.get(f"/journal/chain/{kette}").json()

    rebuild(migrated_db)

    assert klient.get(f"/journal/chain/{kette}").json() == vorher


def test_journal_schreibt_nur_in_seine_tabellen(klient, migrated_db):
    kette = _eine_kette(klient)
    ausfuehrungen = _zaehlen(migrated_db, executions)
    legs_vorher = _zaehlen(migrated_db, legs)

    klient.post(f"/journal/chain/{kette}/notizen", json={"text": "n"})
    klient.put(f"/journal/chain/{kette}/tags", json={"tags": ["t"]})

    assert _zaehlen(migrated_db, executions) == ausfuehrungen
    assert _zaehlen(migrated_db, legs) == legs_vorher
    assert _zaehlen(migrated_db, journal_entries) == 1
    assert _zaehlen(migrated_db, entity_tags) == 1


# ---------------------------------------------------------------- OpenAPI


def test_ohne_journal_bleibt_die_api_rein_lesend(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        schema = klient.get("/openapi.json").json()

    methoden = {m for pfad in schema["paths"].values() for m in pfad}
    assert methoden == {"get"}


def test_schreibende_methoden_gibt_es_nur_unter_journal(klient):
    schema = klient.get("/openapi.json").json()

    for pfad, methoden in schema["paths"].items():
        schreibend = set(methoden) - {"get"}
        if pfad.startswith("/journal"):
            continue
        assert not schreibend, (pfad, schreibend)
    assert {"/journal/{scope_typ}/{scope_id}", "/journal/{scope_typ}/{scope_id}/notizen",
            "/journal/notizen/{notiz_id}", "/journal/{scope_typ}/{scope_id}/tags",
            "/tags"} <= set(schema["paths"])
