"""Abnahmetests für AP-07t: Tagesübersicht und Kalender der Lese-API.

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-07t.md`.

Das Modul springt still ab, solange `api/app.py` (oder FastAPI) fehlt.

Alle Daten stammen aus `tests/fixtures_rebuild.py` und sind frei erfunden.
Der Bestand, Kontosicht, Multiplikator DAX 5 / ESTX50 10, Kommission je
Ausführung -2.00 EUR:

  01.09. 10:00  DAX-Put-Vertikale eröffnet (Kette k:E1|E2)
  02.09. 11:00  ESTX50-Vertikale eröffnet (Kette k:Z1|Z2)
  15.09. 15:00  DAX: die Vertikale wird in einer Order gerollt - Struktur E1|E2
                schließt, Struktur E5|E6 eröffnet (Roll, Kettenglied 2)
                E1|E2: Brutto (100-40)*5 + (20-60)*5 = 300 - 200 = 100.00,
                Kommission 4 * -2.00 = -8.00, Netto 92.00
  16.09. 15:00  ESTX50: Struktur Z1|Z2 schließt
                Brutto (30-12)*10 + (6-18)*10 = 180 - 120 = 60.00,
                Kommission -8.00, Netto 52.00
  16.09. 15:02  ESTX50: neue Kette k:Z5|Z6 (Wiedereinstieg, offen)
  02.03. / 04.05.  zwei Aktientranchen (Ketten k:A1, k:A2), offen

Die Kette k:Z1|Z2 ist mit der Schließung am 16.09. beendet; die DAX-Kette
bleibt offen (Struktur E5|E6 offen).
"""

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def _kette(klient, schluessel) -> dict:
    treffer = klient.get("/ketten", params={"limit": 500}).json()["treffer"]
    return next(k for k in treffer if k["natur_schluessel"] == schluessel)


# ---------------------------------------------------------------- Tagesübersicht


def test_tag_mit_eroeffnung(klient):
    antwort = klient.get("/tage/2026-09-01")

    assert antwort.status_code == 200
    tag = antwort.json()
    assert tag["datum"] == "2026-09-01"
    assert tag["sicht"] == "konto"
    assert [k["chain_id"] for k in tag["eroeffnet"]] == [_kette(klient, "k:E1|E2")["chain_id"]]
    kette = tag["eroeffnet"][0]
    assert (kette["underlying"], kette["asset_class"], kette["seite"], kette["anzahl_rolls"]) == (
        "DAX", "OPT", "Put", 1)
    assert kette["eroeffnet_am"] == "2026-09-01T10:00:00"
    assert kette["beendet_am"] is None
    assert tag["beendet"] == [] and tag["rolls"] == [] and tag["realisiert"] == []


def test_tag_mit_roll_und_realisiertem_ergebnis(klient):
    """15.09.: Das zweite Glied der DAX-Kette entsteht (Roll), die erste
    Struktur schließt mit Brutto 100.00, Kommission -8.00, Netto 92.00."""
    tag = klient.get("/tage/2026-09-15").json()

    assert tag["eroeffnet"] == [] and tag["beendet"] == []
    (roll,) = tag["rolls"]
    assert roll["chain_id"] == _kette(klient, "k:E1|E2")["chain_id"]
    assert roll["underlying"] == "DAX"
    assert roll["sequenz"] == 2
    assert roll["eroeffnet_am"] == "2026-09-15T15:00:00"
    assert tag["realisiert"] == [{
        "waehrung": "EUR", "sicht": "konto", "anzahl_strukturen": 1,
        "brutto": "100.00", "kommission": "-8.00", "netto": "92.00",
    }]


def test_tag_mit_beendeter_kette_und_neuer_kette(klient):
    """16.09.: Z1|Z2 schließt (Netto 52.00) und beendet ihre Kette; zwei
    Minuten später beginnt die neue Kette Z5|Z6."""
    tag = klient.get("/tage/2026-09-16").json()

    assert [k["natur_schluessel"] for k in tag["beendet"]] == ["k:Z1|Z2"]
    assert tag["beendet"][0]["beendet_am"] == "2026-09-16T15:00:00"
    assert [k["natur_schluessel"] for k in tag["eroeffnet"]] == ["k:Z5|Z6"]
    assert tag["realisiert"] == [{
        "waehrung": "EUR", "sicht": "konto", "anzahl_strukturen": 1,
        "brutto": "60.00", "kommission": "-8.00", "netto": "52.00",
    }]


def test_tag_ohne_ereignisse_ist_leer_aber_kein_fehler(klient):
    tag = klient.get("/tage/2026-12-24").json()

    assert tag == {"datum": "2026-12-24", "sicht": "konto", "eroeffnet": [], "beendet": [],
                   "rolls": [], "realisiert": []}


def test_ungueltiges_datum_ist_422(klient):
    assert klient.get("/tage/2026-13-40").status_code == 422
    assert klient.get("/tage/heute").status_code == 422


def test_zwei_ketten_am_selben_tag_stehen_in_zeitlicher_ordnung(klient):
    """Auf 02.03. und 04.05. liegt je eine Aktientranche; über die Liste
    /ketten ist die Reihenfolge nach Eröffnung abgesichert, hier die der
    Tagesliste: nach Eröffnungszeit, dann chain_id."""
    tag = klient.get("/tage/2026-03-02").json()

    assert [k["natur_schluessel"] for k in tag["eroeffnet"]] == ["k:A1"]
    assert tag["eroeffnet"][0]["asset_class"] == "STK"


# ---------------------------------------------------------------- Kalender


def test_kalender_september_nennt_nur_tage_mit_ereignissen(klient):
    antwort = klient.get("/kalender", params={"monat": "2026-09"})

    assert antwort.status_code == 200
    kalender = antwort.json()
    assert kalender["monat"] == "2026-09"
    assert kalender["sicht"] == "konto"
    assert [t["datum"] for t in kalender["tage"]] == [
        "2026-09-01", "2026-09-02", "2026-09-15", "2026-09-16"]


def test_kalender_zaehlt_und_summiert_je_tag(klient):
    tage = {t["datum"]: t for t in klient.get("/kalender", params={"monat": "2026-09"}).json()["tage"]}

    assert tage["2026-09-01"] == {
        "datum": "2026-09-01", "eroeffnet": 1, "beendet": 0, "rolls": 0, "realisiert": []}
    assert tage["2026-09-15"] == {
        "datum": "2026-09-15", "eroeffnet": 0, "beendet": 0, "rolls": 1,
        "realisiert": [{"waehrung": "EUR", "sicht": "konto", "netto": "92.00"}]}
    assert tage["2026-09-16"] == {
        "datum": "2026-09-16", "eroeffnet": 1, "beendet": 1, "rolls": 0,
        "realisiert": [{"waehrung": "EUR", "sicht": "konto", "netto": "52.00"}]}


def test_kalender_maerz_hat_nur_die_aktientranche(klient):
    kalender = klient.get("/kalender", params={"monat": "2026-03"}).json()

    assert kalender["tage"] == [
        {"datum": "2026-03-02", "eroeffnet": 1, "beendet": 0, "rolls": 0, "realisiert": []}]


def test_kalender_leerer_monat(klient):
    kalender = klient.get("/kalender", params={"monat": "2026-01"}).json()

    assert kalender == {"monat": "2026-01", "sicht": "konto", "tage": []}


@pytest.mark.parametrize("monat", ["2026-13", "2026-9", "September", "2026-09-01", ""])
def test_ungueltiger_monat_ist_422(klient, monat):
    assert klient.get("/kalender", params={"monat": monat}).status_code == 422


def test_kalender_ohne_monat_ist_422(klient):
    assert klient.get("/kalender").status_code == 422


def test_neue_endpunkte_sind_rein_lesend_und_im_schema(klient):
    schema = klient.get("/openapi.json").json()

    assert {"/tage/{datum}", "/kalender"} <= set(schema["paths"])
    methoden = {m for pfad in schema["paths"].values() for m in pfad}
    assert methoden == {"get"}
