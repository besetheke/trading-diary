"""Abnahmetests für die Kampagnenansicht der API (AP-08-kampagnen).

Geschrieben durch das starke Modell (Vorbereitungspaket, CLAUDE.md Regel 1a)
— für die Umsetzung unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-08-kampagnen.md`.

Rein lesend: `GET /kampagnen` und `GET /kampagnen/{campaign_id}` zeigen nur,
was bereits in `campaigns`/`campaign_links` steht (AP-05-Abnahme:
unklassifizierte Kandidaten bleiben unsichtbar für diese Ansicht — sie sind
Sache der CLI-Dateirundreise, nicht dieses Endpunkts). Keine Neuberechnung
der Kandidaten (vgl. AP-07l-Auflage zu Rollkandidaten).

Alle Daten stammen aus `tests/fixtures_rebuild.py`, frei erfunden;
`fixtures/golden/` wird nicht gelesen. Geldbeträge von Hand nachgerechnet
(Regel 8).
"""

from datetime import datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import campaign_links, campaigns  # noqa: E402


def _ketten_je_schluessel(klient) -> dict:
    antwort = klient.get("/ketten", params={"limit": 50})
    assert antwort.status_code == 200
    return {k["natur_schluessel"]: k for k in antwort.json()["treffer"]}


@pytest.fixture
def klient(migrated_db):
    """Bestand aus `fixtures_rebuild`; eine Kampagne aus den beiden
    ESTX50-Ketten (`k:Z1|Z2` als IC-Seite, `k:Z5|Z6` als deren Rollglied-
    Gegenstück) von Hand bestätigt — genau wie die CLI-Dateirundreise es
    täte, nur direkt in die Tabellen geschrieben."""
    befuelle(migrated_db)
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        ketten = _ketten_je_schluessel(klient)
        with engine.begin() as verbindung:
            verbindung.execute(
                insert(campaigns).values(
                    campaign_id=1,
                    underlying="ESTX50",
                    eroeffnet_am=datetime(2026, 9, 1, 9, 0, 0),
                    beendet_am=None,
                    netto_pnl_eur=Decimal("123.45"),
                )
            )
            verbindung.execute(
                insert(campaign_links).values(
                    [
                        dict(
                            campaign_id=1,
                            chain_id=ketten["k:Z1|Z2"]["chain_id"],
                            beziehungstyp="ic_leg",
                            erkennung="manuell",
                            bestaetigt_am=datetime(2026, 9, 1, 9, 5, 0),
                        ),
                        dict(
                            campaign_id=1,
                            chain_id=ketten["k:Z5|Z6"]["chain_id"],
                            beziehungstyp="ic_leg",
                            erkennung="manuell",
                            bestaetigt_am=datetime(2026, 9, 1, 9, 5, 0),
                        ),
                    ]
                )
            )
        yield klient


@pytest.fixture
def leerer_klient(migrated_db):
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


# ---------------------------------------------------------------------------
# Liste
# ---------------------------------------------------------------------------


def test_kampagnen_liste_zeigt_nur_bestaetigte(klient):
    """Vertrag: nur die eine angelegte Kampagne — die drei anderen Ketten
    (`k:E1|E2`, `k:A1`, `k:A2`) haben keine `campaign_links`-Zeile und
    bleiben unsichtbar; sie sind nicht still `independent`."""
    antwort = klient.get("/kampagnen")
    assert antwort.status_code == 200
    daten = antwort.json()

    assert daten["gesamt"] == 1
    assert len(daten["treffer"]) == 1
    kampagne = daten["treffer"][0]
    assert kampagne["campaign_id"] == 1
    assert kampagne["underlying"] == "ESTX50"
    assert kampagne["anzahl_ketten"] == 2


def test_kampagnen_liste_ist_leer_ohne_bestand(leerer_klient):
    antwort = leerer_klient.get("/kampagnen")
    assert antwort.status_code == 200
    assert leerer_klient.get("/kampagnen").json() == {"treffer": [], "gesamt": 0}


def test_geld_ist_zeichenkette_nie_zahl(klient):
    """Regel 5/13: `netto_pnl_eur` ist `"123.45"`, kein JSON-Float — von Hand
    nachgerechnet: der Fixture-Wert wird unverändert durchgereicht."""
    daten = klient.get("/kampagnen").json()
    wert = daten["treffer"][0]["netto_pnl_eur"]
    assert wert == "123.45"
    assert isinstance(wert, str)


def test_filter_underlying(klient):
    assert klient.get("/kampagnen", params={"underlying": "ESTX50"}).json()["gesamt"] == 1
    assert klient.get("/kampagnen", params={"underlying": "DAX"}).json()["gesamt"] == 0


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


def test_kampagne_detail_zeigt_beide_ketten(klient):
    antwort = klient.get("/kampagnen/1")
    assert antwort.status_code == 200
    daten = antwort.json()

    assert daten["campaign_id"] == 1
    assert daten["netto_pnl_eur"] == "123.45"
    schluessel = {k["natur_schluessel"] for k in daten["ketten"]}
    assert schluessel == {"k:Z1|Z2", "k:Z5|Z6"}
    for kette in daten["ketten"]:
        assert kette["beziehungstyp"] == "ic_leg"
        assert kette["erkennung"] == "manuell"


def test_unbekannte_kampagne_ist_404(klient):
    antwort = klient.get("/kampagnen/999")
    assert antwort.status_code == 404


def test_kampagne_detail_mit_ungueltiger_id_ist_422(klient):
    antwort = klient.get("/kampagnen/abc")
    assert antwort.status_code == 422
