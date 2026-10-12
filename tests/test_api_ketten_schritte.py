"""Abnahmetest für AP-06se: `GET /ketten?ansicht=schritte` — die Positionsliste
mit jedem Kettenglied als eigener Zeile, damit sich Strategien gezielt mit
OptionApp vergleichen lassen (Nutzerwunsch 12.10.2026).

Welt: tests/fixtures_rebuild, Buchungskurs 1. Die DAX-Kette hat zwei Glieder:
Glied 1 eröffnet 01.09. 10:00, geschlossen 15.09. 15:00, Ergebnis +92.00
(Rechnung: tests/test_rebuild.py); Glied 2 offen.
Erwartung `basiswert=DAX`: gesamt 2 Zeilen, beide mit derselben chain_id,
  Zeile 1: schritt 1 von 2, beendet 15.09. 15:00, Summe 92.00, 1 Glied
  Zeile 2: schritt 2 von 2, beendet leer, Summe leer, eröffnet 15.09. 15:00
Ohne `ansicht` (Ketten): eine Zeile DAX. Filter wirken auf die Kette: eine
Kette, die nicht passt, liefert keines ihrer Glieder (`strategie=X` → 0).
"""

from decimal import Decimal

import pytest
from fixtures_rebuild import AUSFUEHRUNGEN, befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")}
                                         for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)
    return TestClient(erzeuge_app(migrated_db))


def test_schritte(klient):
    d = klient.get("/ketten", params={"basiswert": "DAX", "ansicht": "schritte",
                                      "sortierung": "eroeffnet_am"}).json()
    assert d["gesamt"] == 2
    a, b = d["treffer"]
    assert a["chain_id"] == b["chain_id"]
    assert (a["schritt"], a["schritte_gesamt"], a["anzahl_glieder"]) == (1, 2, 1)
    assert a["eroeffnet_am"].startswith("2026-09-01T10:00")
    assert a["beendet_am"].startswith("2026-09-15T15:00")
    assert Decimal(a["struktur_summe_netto"]) == Decimal("92.00")
    assert (b["schritt"], b["schritte_gesamt"]) == (2, 2)
    assert b["eroeffnet_am"].startswith("2026-09-15T15:00")
    assert b["beendet_am"] is None and b["struktur_summe_netto"] is None


def test_ketten_unveraendert(klient):
    d = klient.get("/ketten", params={"basiswert": "DAX"}).json()
    assert d["gesamt"] == 1
    assert d["treffer"][0]["schritt"] is None


def test_filter_wirken_auf_die_kette(klient):
    d = klient.get("/ketten", params={"basiswert": "DAX", "strategie": "X",
                                      "ansicht": "schritte"}).json()
    assert d["gesamt"] == 0 and d["treffer"] == []


def test_unbekannte_ansicht_ist_422(klient):
    assert klient.get("/ketten", params={"ansicht": "x"}).status_code == 422
