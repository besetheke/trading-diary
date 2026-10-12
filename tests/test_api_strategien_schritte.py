"""Abnahmetest für AP-06sd: `GET /strategien?ansicht=schritte` und die neuen
Felder der Kettenansicht. Welt: tests/fixtures_rebuild (DAX und ESTX50, je eine
Put-Vertikale mit einem Roll; der zweite Glied ist offen; dazu Aktien offen).

Von Hand (EUR, Buchungskurs 1, Kommission −2.00 je Ausführung):
  DAX, Glied 1: (100−40 + 20−60) · 5 = 100 − 8 Kommission = 92.00 (wie
    tests/test_rebuild.py); Glied 2 offen — eine Kette (1 Roll).
  ESTX50, Glied 1: (30−12 + 6−18) · 10 = 60 − 8 = 52.00. Der zweite Roll ist
    hier nur erschlossen und die Kette bleibt getrennt (siehe fixtures_rebuild):
    eine geschlossene Kette +52.00 und eine offene mit offenem Glied.
  Dazu zwei offene Aktien-Tranchen.
Kettenansicht: 1 geschlossene Position (+52.00), 4 offene Ketten;
  `bisher_offene_eur` = 92.00 (nur DAX hat ein geschlossenes Glied in einer
  offenen Kette), `max_drawdown_schritte_eur` 0 (nur Gewinne).
Schrittansicht: zwei geschlossene Glieder (92.00, 52.00): anzahl 2, Summe
  144.00, Trefferquote 1.0000; offen: DAX-Glied 2, ESTX50-Glied 2, zwei
  Aktien = 4.
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
    # Buchungskurs 1: ohne Umrechnung gibt es bewusst keinen EUR-Betrag.
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")}
                                         for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)
    return TestClient(erzeuge_app(migrated_db))


def _ohne_strategie(d):
    return next(z for z in d["zeilen"] if z["strategie"] is None)


def test_kettenansicht_zeigt_bisher_realisiertes(klient):
    z = _ohne_strategie(klient.get("/strategien").json())
    assert (z["anzahl"], z["offen"], Decimal(z["summe_eur"])) == (1, 4, Decimal("52.00"))
    assert Decimal(z["bisher_offene_eur"]) == Decimal("92.00")
    assert Decimal(z["max_drawdown_schritte_eur"]) == 0


def test_schrittansicht(klient):
    d = klient.get("/strategien", params={"ansicht": "schritte"}).json()
    z = _ohne_strategie(d)
    assert (z["anzahl"], Decimal(z["summe_eur"]), z["trefferquote"]) == (
        2, Decimal("144.00"), "1.0000")
    assert z["offen"] == 4


def test_unbekannte_ansicht_ist_422(klient):
    assert klient.get("/strategien", params={"ansicht": "x"}).status_code == 422
