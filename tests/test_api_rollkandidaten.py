"""Abnahmetests für AP-08r: Durchsicht der Rollkandidaten in der Oberfläche —
`GET /rollkandidaten` und `POST /journal/rollkandidaten/urteil` (schreibende
Routen nur unter /journal, AP-07j). Vertrag: auftraege/AP-08r.md. Geschrieben
durch das starke Modell — für die Umsetzung unveränderlich. Szenarien aus
`tests/fixtures_durchsicht.py` (frei erfunden).

MEHRDEUTIG: Put-Vertikale (Y1|Y2) schließt am 16.09.2026 15:00; neue Vertikalen
öffnen 15:02 (Y5|Y6, Rang 1) und 15:20 (Y7|Y8, Rang 2) → eine Gruppe, zwei
Kandidaten, Abstand 2 und 20 Minuten, Kette „k:Y1|Y2".
DOPPELT: zwei Vertikalen (P, Q) schließen 15:00/15:01, eine neue (N1|N2) öffnet
15:05 → zwei Gruppen mit je dem Kandidaten N1|N2. Beide zu bestätigen hieße,
eine Struktur zwei Ketten zuzuordnen (AP-04v, Vertrag 21) → Konflikt.

Die Urteile landen wie bei der Datei-Rundreise (AP-04d) in `chain_overrides`;
wirksam werden sie beim nächsten Rebuild. Ein Urteil verschwindet sofort aus
der Liste der offenen Kandidaten.
"""

import pytest
from fixtures_durchsicht import DOPPELT, INSTRUMENTE_ESTX, MEHRDEUTIG
from fixtures_rebuild import befuelle
from sqlalchemy import select

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import chain_overrides  # noqa: E402


def _klient(db_pfad, ausfuehrungen):
    befuelle(db_pfad, ausfuehrungen=ausfuehrungen, instrumente_=INSTRUMENTE_ESTX)
    rebuild(db_pfad)
    return TestClient(erzeuge_app(db_pfad, mit_journal=True))


def _overrides(db_pfad):
    with create_db_engine(db_pfad).connect() as verbindung:
        return [dict(z) for z in verbindung.execute(select(chain_overrides)).mappings()]


def test_liste_der_offenen_kandidaten(migrated_db):
    k = _klient(migrated_db, MEHRDEUTIG)
    d = k.get("/rollkandidaten").json()
    assert (d["anzahl_gruppen"], d["anzahl_kandidaten"]) == (1, 2)
    g = d["gruppen"][0]
    assert (g["basiswert"], g["seite"], g["schluessel_kette"]) == ("ESTX50", "Put", "k:Y1|Y2")
    assert g["alt_geschlossen"].startswith("2026-09-16T15:00")
    assert [(c["rang"], c["schluessel_struktur"], c["abstand_minuten"])
            for c in g["kandidaten"]] == [(1, "Y5|Y6", 2), (2, "Y7|Y8", 20)]


def test_urteil_wird_gespeichert_und_verschwindet(migrated_db):
    k = _klient(migrated_db, MEHRDEUTIG)
    r = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:Y1|Y2", "schluessel_struktur": "Y5|Y6",
        "urteil": "bestaetigt", "notiz": "Roll"})
    assert r.status_code == 200
    o = _overrides(migrated_db)
    assert [(x["urteil"], x["notiz"]) for x in o] == [("bestaetigt", "Roll")]
    d = k.get("/rollkandidaten").json()
    assert d["anzahl_kandidaten"] == 1
    assert d["gruppen"][0]["kandidaten"][0]["schluessel_struktur"] == "Y7|Y8"


def test_ablehnen(migrated_db):
    k = _klient(migrated_db, MEHRDEUTIG)
    r = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:Y1|Y2", "schluessel_struktur": "Y7|Y8", "urteil": "abgelehnt"})
    assert r.status_code == 200
    assert [x["urteil"] for x in _overrides(migrated_db)] == ["abgelehnt"]


def test_widerspruch_ist_konflikt_und_aendert_nichts(migrated_db):
    k = _klient(migrated_db, MEHRDEUTIG)
    k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:Y1|Y2", "schluessel_struktur": "Y5|Y6", "urteil": "bestaetigt"})
    r = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:Y1|Y2", "schluessel_struktur": "Y5|Y6", "urteil": "abgelehnt"})
    assert r.status_code == 409
    assert [x["urteil"] for x in _overrides(migrated_db)] == ["bestaetigt"]


def test_eine_struktur_fuer_zwei_ketten_ist_konflikt(migrated_db):
    k = _klient(migrated_db, DOPPELT)
    d = k.get("/rollkandidaten").json()
    assert (d["anzahl_gruppen"], d["anzahl_kandidaten"]) == (2, 2)
    ketten = [g["schluessel_kette"] for g in d["gruppen"]]
    erstes = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": ketten[0], "schluessel_struktur": "N1|N2", "urteil": "bestaetigt"})
    assert erstes.status_code == 200
    zweites = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": ketten[1], "schluessel_struktur": "N1|N2", "urteil": "bestaetigt"})
    assert zweites.status_code == 409
    assert len(_overrides(migrated_db)) == 1


def test_unbekannter_schluessel(migrated_db):
    k = _klient(migrated_db, MEHRDEUTIG)
    r = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:XX", "schluessel_struktur": "Y5|Y6", "urteil": "bestaetigt"})
    assert r.status_code == 404
    r = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:Y1|Y2", "schluessel_struktur": "Y5|Y6", "urteil": "vielleicht"})
    assert r.status_code == 422
    assert _overrides(migrated_db) == []


def test_ohne_journal_kein_schreiben(migrated_db):
    befuelle(migrated_db, ausfuehrungen=MEHRDEUTIG, instrumente_=INSTRUMENTE_ESTX)
    rebuild(migrated_db)
    k = TestClient(erzeuge_app(migrated_db))
    assert k.get("/rollkandidaten").status_code == 200
    r = k.post("/journal/rollkandidaten/urteil", json={
        "schluessel_kette": "k:Y1|Y2", "schluessel_struktur": "Y5|Y6", "urteil": "bestaetigt"})
    assert r.status_code in (404, 405)
    assert _overrides(migrated_db) == []
