"""Abnahmetests für die Lese-API (AP-07l).

Geschrieben nach §11.2 des Plans durch das starke Modell (AP-07lv) — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-07lv.md`.

Das Modul springt still ab, solange `api/app.py` (oder FastAPI) fehlt.

Alle Daten stammen aus `tests/fixtures_rebuild.py` und sind frei erfunden;
`fixtures/golden/` wird nicht gelesen. **Die Geldbeträge sind von Hand
nachgerechnet** (Regel 8) — siehe `test_geld_ist_zeichenkette_nie_zahl`.
"""

from datetime import datetime

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import chain_overrides, structures  # noqa: E402

GELDFELDER_STRUKTUR = ("brutto_pnl", "kommission", "netto_pnl")


@pytest.fixture
def klient(migrated_db):
    """Bestand aus `fixtures_rebuild`, gerechnet und geschrieben."""
    befuelle(migrated_db)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


@pytest.fixture
def leerer_klient(migrated_db):
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def _ketten(klient, **parameter) -> dict:
    antwort = klient.get("/ketten", params=parameter)
    assert antwort.status_code == 200
    return antwort.json()


def _kette_je_schluessel(klient) -> dict:
    return {k["natur_schluessel"]: k for k in _ketten(klient)["treffer"]}


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------


def test_ketten_liste_liefert_alle_mit_gesamtzahl(klient):
    """Vertrag 4: Der Bestand ergibt fünf Ketten — die DAX-Kette mit ihrem
    belegten Roll, die beiden ESTX50-Ketten (seit AP-04k getrennt) und die
    zwei Aktientranchen."""
    daten = _ketten(klient)

    assert daten["gesamt"] == 5
    assert len(daten["treffer"]) == 5
    assert {k["natur_schluessel"] for k in daten["treffer"]} == {
        "k:E1|E2", "k:Z1|Z2", "k:Z5|Z6", "k:A1", "k:A2",
    }


def test_ketten_liste_ist_absteigend_sortiert(klient):
    """Vertrag 4: Das Neueste zuerst — eine Oberfläche zeigt zuerst, was
    gerade passiert ist."""
    zeiten = [k["eroeffnet_am"] for k in _ketten(klient)["treffer"]]

    assert zeiten == sorted(zeiten, reverse=True)


def test_filter_basiswert(klient):
    daten = _ketten(klient, basiswert="ESTX50")

    assert daten["gesamt"] == 2
    assert {k["natur_schluessel"] for k in daten["treffer"]} == {"k:Z1|Z2", "k:Z5|Z6"}


def test_filter_min_rolls(klient):
    """Nur die DAX-Kette ist gerollt — und zwar über die Order-Nummer
    belegt."""
    daten = _ketten(klient, min_rolls=1)

    assert daten["gesamt"] == 1
    assert daten["treffer"][0]["natur_schluessel"] == "k:E1|E2"
    assert daten["treffer"][0]["anzahl_rolls"] == 1


def test_filter_anlageklasse_und_seite(klient):
    aktien = _ketten(klient, anlageklasse="STK")
    puts = _ketten(klient, seite="Put")

    assert {k["natur_schluessel"] for k in aktien["treffer"]} == {"k:A1", "k:A2"}
    # Eine Aktienkette hat keine Seite — sie ist leer, nicht "n.a.".
    # "n.a." trägt nur, wer Calls und Puts zugleich hält.
    assert aktien["treffer"][0]["seite"] is None
    assert puts["gesamt"] == 3


def test_blaettern_mit_limit_und_offset(klient):
    """Vertrag 4: `gesamt` zählt vor der Begrenzung, sonst könnte eine
    Oberfläche nicht blättern."""
    erste = _ketten(klient, limit=2)
    zweite = _ketten(klient, limit=2, offset=2)

    assert erste["gesamt"] == 5
    assert zweite["gesamt"] == 5
    assert len(erste["treffer"]) == 2
    assert len(zweite["treffer"]) == 2
    assert {k["chain_id"] for k in erste["treffer"]}.isdisjoint(
        {k["chain_id"] for k in zweite["treffer"]}
    )


def test_leere_datenbank_liefert_leere_liste(leerer_klient):
    """Vertrag 15: kein Fehler, nur nichts."""
    assert _ketten(leerer_klient) == {"gesamt": 0, "treffer": []}


# ---------------------------------------------------------------------------
# Einzelabruf und Drilldown
# ---------------------------------------------------------------------------


def test_kette_einzeln_mit_gliedern_in_sequenz(klient):
    """Vertrag 5 und 9: Die DAX-Kette trägt zwei Glieder — Eröffnung und
    Roll, beide über die Order-Nummer belegt."""
    kette = _kette_je_schluessel(klient)["k:E1|E2"]

    antwort = klient.get(f"/ketten/{kette['chain_id']}")

    assert antwort.status_code == 200
    daten = antwort.json()
    assert [g["sequenz"] for g in daten["glieder"]] == [1, 2]
    assert [g["verknuepfungstyp"] for g in daten["glieder"]] == ["open", "roll"]
    assert [g["erkennung"] for g in daten["glieder"]] == ["auto", "auto"]
    assert [g["struktur"]["natur_schluessel"] for g in daten["glieder"]] == [
        "E1|E2", "E5|E6",
    ]


def test_unbekannte_kette_ist_404(klient):
    assert klient.get("/ketten/999999").status_code == 404


def test_struktur_einzeln_mit_legs(klient):
    """Vertrag 6 und 11: Die geschlossene DAX-Vertikale hat zwei Legs."""
    kette = klient.get(
        f"/ketten/{_kette_je_schluessel(klient)['k:E1|E2']['chain_id']}"
    ).json()
    struktur_id = kette["glieder"][0]["struktur"]["structure_id"]

    daten = klient.get(f"/strukturen/{struktur_id}").json()

    assert daten["natur_schluessel"] == "E1|E2"
    assert daten["typ"] == "BPS"
    assert daten["status"] == "geschlossen"
    assert daten["erkennung"] == "order_id"
    assert sorted(leg["open_exec_id"] for leg in daten["legs"]) == ["E1", "E2"]
    assert all(leg["offen_ja_nein"] is False for leg in daten["legs"])


def test_unbekannte_struktur_ist_404(klient):
    assert klient.get("/strukturen/999999").status_code == 404
    assert klient.get("/strukturen/999999/ausfuehrungen").status_code == 404


def test_drilldown_liefert_ausfuehrungen_mit_rolle(klient):
    """Vertrag 7: bis auf die Ausführung hinunter, zeitlich geordnet, je mit
    der Rolle. Die ESTX50-Struktur `Z1|Z2` wurde von `Z3`/`Z4` geschlossen."""
    kette = klient.get(
        f"/ketten/{_kette_je_schluessel(klient)['k:Z1|Z2']['chain_id']}"
    ).json()
    struktur_id = kette["glieder"][0]["struktur"]["structure_id"]

    daten = klient.get(f"/strukturen/{struktur_id}/ausfuehrungen").json()

    assert [a["exec_id"] for a in daten] == ["Z1", "Z2", "Z3", "Z4"]
    assert [a["rolle"] for a in daten] == [
        "eroeffnung", "eroeffnung", "schliessung", "schliessung",
    ]
    assert daten[0]["handelszeit"] == datetime(2026, 9, 2, 11, 0).isoformat()


# ---------------------------------------------------------------------------
# Geld (Entscheidungen 1 bis 4)
# ---------------------------------------------------------------------------


def test_geld_ist_zeichenkette_nie_zahl(klient):
    """Entscheidung 1: JSON kennt nur Gleitkommazahlen — Geld als Zahl wäre
    der stille Genauigkeitsverlust, den Regel 5 verbietet.

    Von Hand für die DAX-Vertikale (Multiplikator 5, Menge 1): Brutto
    300 − 200 = **100,00**, Kommission vier Ausführungen zu −2,00 =
    **−8,00**, Netto 100 + (−8) = **92,00**.
    """
    kette = klient.get(
        f"/ketten/{_kette_je_schluessel(klient)['k:E1|E2']['chain_id']}"
    ).json()
    struktur = kette["glieder"][0]["struktur"]

    assert struktur["brutto_pnl"] == "100.00"
    assert struktur["kommission"] == "-8.00"
    assert struktur["netto_pnl"] == "92.00"
    for feld in GELDFELDER_STRUKTUR:
        assert isinstance(struktur[feld], str)


def test_offene_struktur_traegt_kein_ergebnis(klient):
    """Vertrag 13: Leeres bleibt leer und wird nie zu `"0"` — sonst sähe
    eine offene Position wie ein Nullergebnis aus."""
    kette = klient.get(
        f"/ketten/{_kette_je_schluessel(klient)['k:E1|E2']['chain_id']}"
    ).json()
    offen = kette["glieder"][1]["struktur"]

    assert offen["status"] == "offen"
    assert offen["brutto_pnl"] is None
    assert offen["netto_pnl"] is None


def test_jede_geldangabe_nennt_waehrung_und_sicht(klient):
    """Entscheidung 2: Ohne Währung ist die Zahl nicht verwendbar, solange
    AP-06 nicht umrechnet — und ohne Sicht wäre später nicht erkennbar, ob
    eine Zahl aus der Konto- oder der Kettensicht stammt (OF-36)."""
    geschlossen = _kette_je_schluessel(klient)["k:Z1|Z2"]

    assert geschlossen["sicht"] == "konto"
    assert geschlossen["waehrung"] == "EUR"
    # Von Hand: Brutto 180 − 120 = 60,00; Kommission −8,00; Netto 52,00.
    assert geschlossen["struktur_summe_netto"] == "52.00"
    assert all(k["sicht"] == "konto" for k in _ketten(klient)["treffer"])


def test_mehrere_waehrungen_lassen_die_summe_leer(klient, migrated_db):
    """Entscheidung 3: Eine Zahl, die USD und EUR addiert, wäre falsch.

    Aufgebaut über einen Override, der die Aktientranche (USD) in die
    DAX-Kette (EUR) hängt — genau das, was ein Nutzer von Hand tun kann.
    """
    ketten = _kette_je_schluessel(klient)
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        struktur_id = verbindung.execute(
            select(structures.c.structure_id).where(
                structures.c.natur_schluessel == "A1", structures.c.sicht == "konto"
            )
        ).scalar_one()
        verbindung.execute(
            insert(chain_overrides).values(
                chain_id=ketten["k:E1|E2"]["chain_id"],
                structure_id=struktur_id,
                notiz=None,
                erstellt_am=datetime(2026, 9, 22, 9, 0, 0),
                urteil="bestaetigt",
            )
        )
    rebuild(migrated_db)

    gemischt = _kette_je_schluessel(klient)["k:E1|E2"]

    assert gemischt["waehrungen"] == ["EUR", "USD"]
    assert gemischt["waehrung"] is None
    assert gemischt["struktur_summe_netto"] is None


# ---------------------------------------------------------------------------
# Vertrag der Schnittstelle
# ---------------------------------------------------------------------------


def test_ungueltige_parameter_sind_422(klient):
    """Vertrag 16 und 17: nicht stillschweigend zurechtbiegen."""
    assert klient.get("/ketten", params={"limit": -1}).status_code == 422
    assert klient.get("/ketten", params={"limit": 10_000}).status_code == 422
    assert klient.get("/ketten", params={"min_rolls": "viele"}).status_code == 422


def test_openapi_kennt_nur_lesende_methoden(klient):
    """Vertrag 2: Die Lese-API schreibt nicht. Das steht nicht nur im
    Auftrag, es muss am Schema ablesbar sein."""
    schema = klient.get("/openapi.json").json()

    methoden = {
        methode for pfad in schema["paths"].values() for methode in pfad
    }
    assert methoden == {"get"}
    assert {"/ketten", "/ketten/{chain_id}", "/strukturen/{structure_id}",
            "/strukturen/{structure_id}/ausfuehrungen"} <= set(schema["paths"])


def test_kette_ohne_ergebnis_bleibt_ohne_summe(klient):
    """Entscheidung 4: `struktur_summe_netto` ist die Summe der
    Strukturergebnisse — trägt eine Struktur noch keines, weil sie offen
    ist, gibt es keine Summe. Die DAX-Kette hat ein offenes zweites Glied."""
    dax = _kette_je_schluessel(klient)["k:E1|E2"]

    assert dax["anzahl_glieder"] == 2
    assert dax["struktur_summe_netto"] is None
    assert dax["waehrung"] == "EUR"
    assert dax["waehrungen"] == ["EUR"]


# ---------------------------------------------------------------------------
# Prämien in der Lese-API (AP-07p)
# ---------------------------------------------------------------------------


def test_struktur_traegt_die_praemien(klient):
    """Vertrag P4: Die Struktur liefert Eröffnungs- und Schlussprämie je
    Kontrakt — als Zeichenkette wie jeder andere Betrag (Entscheidung 1).

    Von Hand für die DAX-Vertikale: eröffnet zu +40,00 eingenommen,
    geschlossen zu −20,00 gezahlt. Geschrieben mit mindestens zwei und
    höchstens acht Nachkommastellen, überzählige Nullen entfallen
    (Vertrag P3).
    """
    kette = klient.get(
        f"/ketten/{_kette_je_schluessel(klient)['k:E1|E2']['chain_id']}"
    ).json()
    struktur = kette["glieder"][0]["struktur"]

    assert struktur["eroeffnungspreis"] == "40.00"
    assert struktur["schlusspreis"] == "-20.00"
    assert isinstance(struktur["eroeffnungspreis"], str)


def test_offene_struktur_ohne_schlusspreis(klient):
    """Vertrag P2: Eine offene Struktur hat keinen Schlusspreis — und
    bekommt keine Null, die wie ein Rückkauf zum Nulltarif aussähe."""
    kette = klient.get(
        f"/ketten/{_kette_je_schluessel(klient)['k:E1|E2']['chain_id']}"
    ).json()
    offen = kette["glieder"][1]["struktur"]

    assert offen["eroeffnungspreis"] == "35.00"
    assert offen["schlusspreis"] is None


def test_kette_zeigt_eroeffnung_und_schluss(klient):
    """Vertrag P5: Die Kette reicht die Prämie ihres **ersten** und ihres
    **letzten** Glieds durch — das ist, woran man einen Vorgang in der
    Positionsliste wiedererkennt, ohne ihn zu öffnen.

    Von Hand: Die ESTX50-Kette besteht aus einer geschlossenen Struktur,
    eröffnet zu +12,00 und geschlossen zu −6,00.
    """
    geschlossen = _kette_je_schluessel(klient)["k:Z1|Z2"]

    assert geschlossen["eroeffnungspreis"] == "12.00"
    assert geschlossen["schlusspreis"] == "-6.00"


def test_kette_mit_offenem_schlussglied_hat_keinen_schlusspreis(klient):
    """Vertrag P5: Endet die Kette auf einer offenen Struktur, gibt es
    keinen Schlusspreis. Die DAX-Kette wurde gerollt; ihr letztes Glied
    läuft noch."""
    dax = _kette_je_schluessel(klient)["k:E1|E2"]

    assert dax["eroeffnungspreis"] == "40.00"
    assert dax["schlusspreis"] is None
