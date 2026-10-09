"""Abnahmetests für AP-07s: Sortierung der Kettenliste (`GET /ketten`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-07s.md`.

Das Modul springt still ab, solange `api/app.py` (oder FastAPI) fehlt.

Bestand aus `tests/fixtures_rebuild.py` (frei erfunden), fünf Ketten:

  Schlüssel   Basiswert  Klasse  eröffnet         beendet          Rolls
  k:E1|E2     DAX        OPT     01.09. 10:00     offen            1
  k:Z1|Z2     ESTX50     OPT     02.09. 11:00     16.09. 15:00     0
  k:Z5|Z6     ESTX50     OPT     16.09. 15:02     offen            0
  k:A1        IDX9       STK     02.03. 10:00     offen            0
  k:A2        IDX9       STK     04.05. 10:00     offen            0

Zusätzliche Abfrageparameter: `sortierung` (Spalte) und `richtung` (`asc` |
`desc`). Vorgabe unverändert: Eröffnung, absteigend.
"""

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

SORTIERSPALTEN = {
    "eroeffnet_am", "beendet_am", "underlying", "asset_class", "seite",
    "anzahl_rolls", "endzustand", "oa_strategie",
}


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def _schluessel(klient, **parameter) -> list[str]:
    antwort = klient.get("/ketten", params=parameter)
    assert antwort.status_code == 200, antwort.text
    return [k["natur_schluessel"] for k in antwort.json()["treffer"]]


def _treffer(klient, **parameter) -> list[dict]:
    return klient.get("/ketten", params=parameter).json()["treffer"]


def test_vorgabe_bleibt_eroeffnung_absteigend(klient):
    assert _schluessel(klient) == ["k:Z5|Z6", "k:Z1|Z2", "k:E1|E2", "k:A2", "k:A1"]


def test_eroeffnung_aufsteigend(klient):
    assert _schluessel(klient, sortierung="eroeffnet_am", richtung="asc") == [
        "k:A1", "k:A2", "k:E1|E2", "k:Z1|Z2", "k:Z5|Z6"]


def test_richtung_allein_gilt_fuer_die_eroeffnung(klient):
    assert _schluessel(klient, richtung="asc") == [
        "k:A1", "k:A2", "k:E1|E2", "k:Z1|Z2", "k:Z5|Z6"]


def test_sortierung_allein_ist_absteigend(klient):
    assert _schluessel(klient, sortierung="eroeffnet_am") == _schluessel(klient)


def test_basiswert_aufsteigend_und_absteigend_mit_gleichstand_nach_chain_id(klient):
    aufsteigend = _treffer(klient, sortierung="underlying", richtung="asc")
    absteigend = _treffer(klient, sortierung="underlying", richtung="desc")

    assert [k["underlying"] for k in aufsteigend] == ["DAX", "ESTX50", "ESTX50", "IDX9", "IDX9"]
    assert [k["underlying"] for k in absteigend] == ["IDX9", "IDX9", "ESTX50", "ESTX50", "DAX"]
    for liste in (aufsteigend, absteigend):
        for a, b in zip(liste, liste[1:], strict=False):
            if a["underlying"] == b["underlying"]:  # Gleichstand: chain_id aufsteigend
                assert a["chain_id"] < b["chain_id"]


def test_anzahl_rolls_absteigend_die_gerollte_kette_zuerst(klient):
    liste = _treffer(klient, sortierung="anzahl_rolls", richtung="desc")

    assert liste[0]["natur_schluessel"] == "k:E1|E2"
    assert [k["anzahl_rolls"] for k in liste] == [1, 0, 0, 0, 0]
    assert [k["chain_id"] for k in liste[1:]] == sorted(k["chain_id"] for k in liste[1:])


def test_anlageklasse_und_seite(klient):
    assert [k["asset_class"] for k in _treffer(klient, sortierung="asset_class", richtung="asc")] == [
        "OPT", "OPT", "OPT", "STK", "STK"]
    for richtung in ("asc", "desc"):
        seiten = [k["seite"] for k in _treffer(klient, sortierung="seite", richtung=richtung)]
        gefuellt = [s for s in seiten if s is not None]
        # Leere Werte stehen immer zuletzt, in beiden Richtungen.
        assert seiten == sorted(gefuellt, reverse=richtung == "desc") + [None] * (
            len(seiten) - len(gefuellt))


@pytest.mark.parametrize("richtung", ["asc", "desc"])
def test_leere_werte_stehen_in_beiden_richtungen_zuletzt(klient, richtung):
    """Nur k:Z1|Z2 ist beendet. Wer nach Ende sortiert, sieht sie zuerst - die
    vier offenen Ketten (ohne Ende) folgen in chain_id-Reihenfolge."""
    liste = _treffer(klient, sortierung="beendet_am", richtung=richtung)

    assert liste[0]["natur_schluessel"] == "k:Z1|Z2"
    rest = liste[1:]
    assert all(k["beendet_am"] is None for k in rest)
    assert [k["chain_id"] for k in rest] == sorted(k["chain_id"] for k in rest)


def test_oa_strategie_ohne_werte_bleibt_geordnet(klient):
    # Ohne OA-Import tragen alle Ketten keine Strategie: Gleichstand überall,
    # also chain_id aufsteigend.
    liste = _treffer(klient, sortierung="oa_strategie", richtung="desc")

    assert [k["chain_id"] for k in liste] == sorted(k["chain_id"] for k in liste)


def test_sortierung_wirkt_vor_dem_blaettern(klient):
    erste = _schluessel(klient, sortierung="eroeffnet_am", richtung="asc", limit=2, offset=0)
    zweite = _schluessel(klient, sortierung="eroeffnet_am", richtung="asc", limit=2, offset=2)

    assert erste == ["k:A1", "k:A2"]
    assert zweite == ["k:E1|E2", "k:Z1|Z2"]


def test_sortierung_mit_filter(klient):
    assert _schluessel(klient, basiswert="ESTX50", sortierung="eroeffnet_am", richtung="asc") == [
        "k:Z1|Z2", "k:Z5|Z6"]
    antwort = klient.get("/ketten", params={"basiswert": "ESTX50", "sortierung": "beendet_am"})
    assert antwort.json()["gesamt"] == 2


@pytest.mark.parametrize("parameter", [
    {"sortierung": "netto"},
    {"sortierung": "struktur_summe_netto"},
    {"sortierung": "chain_id; drop table chains"},
    {"richtung": "quer"},
    {"sortierung": "underlying", "richtung": "ASC"},
])
def test_ungueltige_sortierung_ist_422(klient, parameter):
    assert klient.get("/ketten", params=parameter).status_code == 422


def test_openapi_nennt_die_erlaubten_spalten(klient):
    schema = klient.get("/openapi.json").json()
    parameter = {p["name"]: p for p in schema["paths"]["/ketten"]["get"]["parameters"]}

    assert set(parameter["sortierung"]["schema"]["enum"]) == SORTIERSPALTEN
    assert set(parameter["richtung"]["schema"]["enum"]) == {"asc", "desc"}
