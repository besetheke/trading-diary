"""Abnahmetests für die Menge einer Position in `GET /ketten` (Spalte „Anzahl").
Unveränderlich.

Die Menge ist die der **Eröffnung**: die `menge` des ersten Glieds der Kette
(kleinste `sequenz`, bei Gleichstand die kleinste `structure_id`, wie bei den
Prämien in AP-07pv) — Kontrakte bei Optionen, Stück bei Aktien. Reines
Durchreichen des Strukturwerts, kein Rechnen; Text wie jeder Zahlenwert der
API.

Welt aus tests/fixtures_rebuild.py (frei erfunden, dort nachzulesen):

  DAX     Put-Vertikale, je Ausführung menge 1, in einer Order gerollt
          → eine Kette mit zwei Strukturen (Roll belegt), erstes Glied
          menge 1 → "1"
  ESTX50  dieselbe Bewegung in zwei Orders: die Heuristik bleibt ein
          Vorschlag (Regel 7), es entstehen zwei Ketten, je menge 1 →
          "1", "1"
  IDX9    zwei Aktientranchen zu je 100 Stück, nie automatisch verkettet
          → zwei Ketten, je "100"
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


def _menge_je_basiswert(klient):
    treffer = klient.get("/ketten").json()["treffer"]
    je_basiswert: dict[str, list[str | None]] = {}
    for kette in treffer:
        je_basiswert.setdefault(kette["underlying"], []).append(kette["menge"])
    return je_basiswert


def test_menge_der_eroeffnung_je_basiswert(klient):
    je_basiswert = _menge_je_basiswert(klient)
    assert je_basiswert["DAX"] == ["1"]
    assert je_basiswert["ESTX50"] == ["1", "1"]
    assert je_basiswert["IDX9"] == ["100", "100"]


def test_menge_ist_text_nie_zahl(klient):
    rohtext = klient.get("/ketten").text.replace(" ", "")
    assert '"menge":"100"' in rohtext
    assert '"menge":100' not in rohtext


def test_menge_in_der_einzelansicht(klient):
    kette = next(k for k in klient.get("/ketten").json()["treffer"] if k["underlying"] == "DAX")
    einzeln = klient.get(f"/ketten/{kette['chain_id']}").json()
    assert einzeln["menge"] == "1"
