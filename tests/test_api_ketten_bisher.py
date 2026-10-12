"""Abnahmetest für AP-06sd: `GET /ketten` trägt bei offenen Ketten das bereits
realisierte Ergebnis ihrer geschlossenen Glieder (`realisiert_bisher`).

Welt: tests/fixtures_rebuild, Buchungskurs 1. Die DAX-Kette ist offen; ihr erstes
Glied ist mit +92.00 geschlossen (Rechnung: tests/test_rebuild.py), das zweite
offen → `realisiert_bisher` 92.00, `struktur_summe_netto` bleibt leer (Entscheidung
4: eine offene Struktur ist kein Nullergebnis). Die geschlossene ESTX50-Kette
(+52.00) hat keinen Wert (steht in `struktur_summe_netto`); die offene ESTX50-Kette
und die Aktien haben noch kein geschlossenes Glied → kein Wert.
"""

from decimal import Decimal

import pytest
from fixtures_rebuild import AUSFUEHRUNGEN, befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


def test_bisher_realisiert(migrated_db):
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")}
                                         for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)
    treffer = TestClient(erzeuge_app(migrated_db)).get("/ketten").json()["treffer"]
    je = {(k["underlying"], k["beendet_am"] is None): k for k in treffer}
    dax = je[("DAX", True)]
    assert Decimal(dax["realisiert_bisher"]) == Decimal("92.00")
    assert dax["struktur_summe_netto"] is None
    assert je[("ESTX50", False)]["realisiert_bisher"] is None
    assert Decimal(je[("ESTX50", False)]["struktur_summe_netto"]) == Decimal("52.00")
    assert je[("ESTX50", True)]["realisiert_bisher"] is None
    assert all(k["realisiert_bisher"] is None for k in treffer if k["underlying"] == "IDX9")
