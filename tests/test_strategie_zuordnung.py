# ruff: noqa: E501
"""Manuelle Strategiezuordnung (AP-17g, M03): dauerhaft, überlebt Rebuild, wirkt in Filtern, Rücknahme löscht nichts.

Abnahme aus dem Review: einer diskretionären Position eine Strategie geben, neu aufbauen; die Zuordnung bleibt bestehen und
wirkt in den Filtern und Auswertungen.
"""
import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import text

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.datenqualitaet import arbeitsliste  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

STRATEGIE = "Diskretionär Test"


@pytest.fixture
def welt(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with create_db_engine(migrated_db).connect() as v:
        kette = v.execute(text("SELECT chain_id FROM chains WHERE sicht='konto' ORDER BY chain_id LIMIT 1")).scalar()
    return TestClient(erzeuge_app(migrated_db, mit_journal=True)), kette, migrated_db


def sql(db, abfrage, **p):
    with create_db_engine(db).begin() as v:
        ergebnis = v.execute(text(abfrage), p)
        return ergebnis.all() if ergebnis.returns_rows else []


def test_zuordnung_wirkt_sofort_in_filtern_und_herkunft(welt):
    c, kette, db = welt
    antwort = c.put(f"/journal/strategie-zuordnung/{kette}", json={"strategie": STRATEGIE, "begruendung": "eigene Idee, kein OA-Trade"})
    assert antwort.status_code == 200
    d = antwort.json()
    assert (d["strategie"], d["herkunft"], d["manuell"]["begruendung"]) == (STRATEGIE, "manuell", "eigene Idee, kein OA-Trade")
    daten = c.get("/ketten", params={"strategie": STRATEGIE}).json()
    liste = daten["treffer"]
    assert [k["chain_id"] for k in liste] == [kette]                 # wirkt sofort im Strategiefilter


def test_zuordnung_ueberlebt_import_und_rebuild(welt):
    c, kette, db = welt
    c.put(f"/journal/strategie-zuordnung/{kette}", json={"strategie": STRATEGIE})
    ergebnis = rebuild(db)
    assert (ergebnis.strategie_manuell, ergebnis.strategie_widerspruch, ergebnis.strategie_verwaist) == (1, 0, 0)
    # nach dem Rebuild gibt es dieselbe Kette (Naturschlüssel), und sie trägt die Strategie in beiden Sichten
    zeilen = sql(db, "SELECT sicht, oa_strategie FROM chains WHERE natur_schluessel = (SELECT natur_schluessel FROM strategie_zuordnungen)")
    assert {s for s, _ in zeilen} == {"konto", "kette"} and {n for _, n in zeilen} == {STRATEGIE}
    neue_id = sql(db, "SELECT chain_id FROM chains WHERE sicht='konto' AND natur_schluessel = (SELECT natur_schluessel FROM strategie_zuordnungen)")[0][0]
    d = c.get(f"/strategie-zuordnung/{neue_id}").json()
    assert d["herkunft"] == "manuell" and d["strategie"] == STRATEGIE


def test_ruecknahme_stellt_den_stand_vorher_wieder_her_und_loescht_nichts(welt):
    c, kette, db = welt
    sql(db, "UPDATE chains SET oa_strategie='OA: Alt', oa_erkennung='heuristik' WHERE chain_id = :k", k=kette)
    c.put(f"/journal/strategie-zuordnung/{kette}", json={"strategie": STRATEGIE})
    d = c.post(f"/journal/strategie-zuordnung/{kette}/zuruecknehmen").json()
    assert d["strategie"] == "OA: Alt" and d["herkunft"] == "heuristik" and d["manuell"] is None and d["zurueckgenommen_am"]
    zeile = sql(db, "SELECT strategie, zurueckgenommen_am FROM strategie_zuordnungen")
    assert len(zeile) == 1 and zeile[0][1] is not None                      # die Zeile bleibt (Regel 4)
    rebuild(db)
    assert sql(db, "SELECT COUNT(*) FROM chains WHERE oa_strategie = :s", s=STRATEGIE)[0][0] == 0      # zurückgenommen: nicht erneut angewandt


def test_widerspruch_zu_oa_wird_gemerkt_gezeigt_und_nicht_still_ueberschrieben(welt):
    c, kette, db = welt
    sql(db, "UPDATE chains SET oa_strategie='OA: Iron Condor', oa_erkennung='auto' WHERE chain_id = :k", k=kette)
    d = c.put(f"/journal/strategie-zuordnung/{kette}", json={"strategie": STRATEGIE}).json()
    assert d["manuell"]["oa_widerspricht"] == "OA: Iron Condor" and d["manuell"]["stand_vorher"] == "OA: Iron Condor"
    punkte = {p["id"]: p for p in arbeitsliste(db, __import__("datetime").date(2026, 10, 25), mit_abgleich=False)["punkte"]}
    assert punkte["strategie-widerspruch"]["anzahl"] == 1 and "OA: Iron Condor" in punkte["strategie-widerspruch"]["betroffen"][0]


def test_zuordnung_ohne_kette_bleibt_stehen_und_wird_gemeldet(welt):
    c, kette, db = welt
    c.put(f"/journal/strategie-zuordnung/{kette}", json={"strategie": STRATEGIE})
    sql(db, "UPDATE strategie_zuordnungen SET natur_schluessel = 'k:gibt-es-nicht'")
    ergebnis = rebuild(db)
    assert ergebnis.strategie_verwaist == 1 and ergebnis.strategie_manuell == 0
    assert sql(db, "SELECT natur_schluessel, strategie FROM strategie_zuordnungen") == [("k:gibt-es-nicht", STRATEGIE)]
    from datetime import date
    assert any(p["id"] == "strategie-verwaist" for p in arbeitsliste(db, date(2026, 10, 25), mit_abgleich=False)["punkte"])


def test_eingaben_werden_geprueft(welt):
    c, kette, _ = welt
    assert c.put(f"/journal/strategie-zuordnung/{kette}", json={"strategie": "   "}).status_code == 422
    assert c.put("/journal/strategie-zuordnung/999999", json={"strategie": "x"}).status_code == 404
    assert c.get("/strategie-zuordnung/999999").status_code == 404
    assert c.post("/journal/strategie-zuordnung/999999/zuruecknehmen").status_code == 404
    assert c.post(f"/journal/strategie-zuordnung/{kette}/zuruecknehmen").status_code == 404        # nichts zurückzunehmen
