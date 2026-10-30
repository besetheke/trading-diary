# ruff: noqa: E501
"""AP-19: Jede Position der Shorts-Übersicht bekommt ihre Kette im Journal (`journal`) — auch manuelle Trades
und das Live-Konto, damit beim Aufklappen Kettentrades und Karten erscheinen.

Welt wie tests/test_api_roller_historie.py (fixtures_rebuild, Buchungskurs 1): DAX-Kette, Glied 1 (Put-Vertikale
19000/18900, Verfall 18.9.) geschlossen mit +92.00 EUR, Glied 2 (18800/18700, Verfall 16.10.2026) offen, ein Roll.

Erwartung: Position DAX 20261016 BPS 18800/18700 → journal.anzahl_rolls 1, realisiert_bisher 92.00, zwei Schritte
in Reihenfolge (erst 19000/18900 geschlossen, dann 18800/18700 offen). Kalender (Long anderer Verfall) wird über den
Short gefunden. Ohne Treffer kein `journal`. Dasselbe für `/roller-status-live`.
"""

from decimal import Decimal

import pytest
from fixtures_rebuild import AUSFUEHRUNGEN, befuelle

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402


def _status():
    return {
        "dienst": "options-roller", "spreads": [], "breaches": [],
        "shorts": {"zaehler": {}, "positionen": [
            {"key": "1-2", "symbol": "DAX", "verfall": "20261016", "recht": "P", "art": "BPS",
             "short": 18800.0, "long": 18700.0, "long_verfall": None, "menge": 1},
            {"key": "1-9", "symbol": "DAX", "verfall": "20261016", "recht": "P", "art": "Kalender Put",
             "short": 18800.0, "long": 18800.0, "long_verfall": "20261023", "menge": 1},
            {"key": "3-naked", "symbol": "DAX", "verfall": "20261023", "recht": "P", "art": "Short Put",
             "short": 18500.0, "long": None, "long_verfall": None, "menge": 1},
        ]},
    }


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")} for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)
    return TestClient(erzeuge_app(migrated_db, roller_port=8600, roller_live_port=8601,
                                  hole_roller_status=lambda port: _status()))


def _positionen(klient, weg):
    return klient.get(weg).json()["status"]["shorts"]["positionen"]


def test_position_bekommt_journal_kette_mit_schritten(klient):
    j = _positionen(klient, "/roller-status")[0]["journal"]
    assert j["anzahl_rolls"] == 1 and Decimal(j["realisiert_bisher"]) == Decimal("92.00")
    schritte = j["schritte"]
    assert [(Decimal(s["short"]), Decimal(s["long"])) for s in schritte] == [(Decimal("19000"), Decimal("18900")), (Decimal("18800"), Decimal("18700"))]
    assert schritte[0]["geschlossen_am"] is not None and schritte[1]["geschlossen_am"] is None
    assert [s["sequenz"] for s in schritte] == sorted(s["sequenz"] for s in schritte)


def test_kalender_ueber_den_short_und_ohne_treffer_nichts(klient):
    p = _positionen(klient, "/roller-status")
    assert p[1]["journal"]["chain_id"] == p[0]["journal"]["chain_id"]
    assert "journal" not in p[2]


def test_auch_im_live_status(klient):
    p = _positionen(klient, "/roller-status-live")
    assert p[0]["journal"]["anzahl_rolls"] == 1


def test_jedes_konto_sucht_in_seinem_journal(migrated_db, tmp_path, monkeypatch, alembic_config):
    """Paper-Status sucht in der Paper-Datenbank, Live-Status in der Live-Datenbank — unabhängig davon, mit welcher
    Datenbank das Journal läuft (Server: Paper-Journal mit Live-Ansicht; NOX: echtes Journal mit Paper-Roller)."""
    from alembic import command
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")} for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)                                     # die Welt mit der DAX-Kette
    leer = tmp_path / "leer.sqlite"
    monkeypatch.setenv("JOURNAL_DB", str(leer))
    command.upgrade(alembic_config, "head")                  # zweite, leere Datenbank
    nur_live = TestClient(erzeuge_app(leer, roller_port=8600, roller_live_port=8601, journal_db_live=migrated_db,
                                      hole_roller_status=lambda port: _status()))
    assert "journal" in _positionen(nur_live, "/roller-status-live")[0]
    assert "journal" not in _positionen(nur_live, "/roller-status")[0]      # Paper sucht in der eigenen (leeren) DB
    nur_paper = TestClient(erzeuge_app(leer, roller_port=8600, roller_live_port=8601, journal_db_paper=migrated_db,
                                       hole_roller_status=lambda port: _status()))
    assert "journal" in _positionen(nur_paper, "/roller-status")[0]
    assert "journal" not in _positionen(nur_paper, "/roller-status-live")[0]


def test_kostenbasis_der_position(migrated_db):
    """Von Hand: abgeschlossenes Glied +92,00 EUR. Offenes Glied 18800/18700, 1 Kontrakt, Multiplikator 5,
    Kommission −2,00 je Ausführung: Verkauf 90 × 5 − 2 = +448,00, Kauf −55 × 5 − 2 = −277,00 → Zufluss +171,00.
    Netto 263,00 · je Einheit 263 ÷ 5 = 52,60 · Breakeven 18.800 − 52,60 = 18.747,40
    · höchster Verlust (100 − 52,60) × 5 = 237,00."""
    befuelle(migrated_db, ausfuehrungen=[{**a, "buchungskurs": Decimal("1")} for a in AUSFUEHRUNGEN])
    rebuild(migrated_db)
    status = _status()
    status["shorts"]["positionen"][0]["multiplikator"] = "5"
    k = TestClient(erzeuge_app(migrated_db, roller_port=8600, hole_roller_status=lambda port: status))
    kb = _positionen(k, "/roller-status")[0]["journal"]["kostenbasis"]
    assert {f: Decimal(kb[f]) for f in ("realisiert", "praemien_offen", "netto", "je_einheit", "breakeven", "max_verlust")} == {
        "realisiert": Decimal("92.00"), "praemien_offen": Decimal("171.00"), "netto": Decimal("263.00"),
        "je_einheit": Decimal("52.60"), "breakeven": Decimal("18747.40"), "max_verlust": Decimal("237.00")}
    assert kb["aktien_einstand"] is None and kb["je_aktie"] is None
