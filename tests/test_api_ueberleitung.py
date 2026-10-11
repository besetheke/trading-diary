"""Abnahmetests für `GET /ueberleitung` (AP-08u): vom Ergebnis zum Kontostand.
Unveränderlich — Vertrag in auftraege/AP-08u.md.

Die Überleitung zerlegt IBs Gewinn (Kontowert − Einzahlungen) und stellt das
realisierte Ergebnis des Journals daneben. Jede Zahl hat eine Quelle:

  Kontowert, Einzahlungen kumuliert, Gewinn  — GET /nav (letzter Tag)
  IB realisiert    — Σ `fifoPnlRealized` × Kurs je Ausführung bis zum NAV-Tag
                     (`flex_ib_realized`, AP-02p; netto nach Kommission)
  IB unrealisiert  — Σ unrealisiertes Ergebnis des jüngsten Bestands (GET /depot)
  Sonstige Buchungen — Cash-Posten ohne Ein-/Auszahlungen (Dividenden, Zinsen,
                     Gebühren, Quellensteuer; GET /kapital)
  Rest             — Gewinn − (realisiert + unrealisiert + sonstige): Währung,
                     Abgrenzungen und alles, was IB nicht einzeln ausweist
  Journal realisiert — Equity (GET /equity), Differenz = Journal − IB realisiert

Welt (frei erfunden, EUR, Kurs 1):
  Ausführungen: SELL 10.00 am 02.01., BUY 4.00 am 03.01. (Multiplikator 10,
    Kommission −2.00 je Ausführung) → Equity netto 56.00 (wie test_api_equity).
  Einzahlung 1000.00 am 01.01.; Dividende 5.00 am 04.01.
  NAV am 05.01.: 1100.00 → Gewinn laut IB 1100.00 − 1000.00 = 100.00.
  IB realisiert: +60.00 und −10.00 am 03.01. = 50.00; eine Zeile am 06.01.
    (+999.00) liegt nach dem NAV-Tag und zählt nicht.
  Bestand am 05.01.: unrealisiert −20.00.
Rest = 100.00 − (50.00 − 20.00 + 5.00) = 65.00; Differenz des realisierten
Ergebnisses = 56.00 − 50.00 = 6.00.
"""

import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import (  # noqa: E402
    flex_cash_transactions,
    flex_ib_realized,
    flex_nav_tage,
    flex_open_positions,
    import_runs,
)

_INSTRUMENTE = [
    dict(conid=9001, symbol="TST  260320P100", underlying="TST", asset_class="OPT",
         expiry=date(2026, 3, 20), strike=Decimal("100"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
]
_AUSFUEHRUNGEN = [
    dict(exec_id="T1", conid=9001, side="SELL", preis=Decimal("10.00"),
         handelszeit=datetime(2026, 1, 2, 10, 0, 0), buchungskurs=Decimal("1")),
    dict(exec_id="T2", conid=9001, side="BUY", preis=Decimal("4.00"),
         handelszeit=datetime(2026, 1, 3, 10, 0, 0), buchungskurs=Decimal("1")),
]


def _d(text):
    assert isinstance(text, str), text
    return Decimal(text)


def _buchung(lauf, schluessel, tag, typ, betrag):
    return dict(import_run_id=lauf, konto="U1234567", quell_schluessel=schluessel, datum=tag,
                typ=typ, betrag=Decimal(betrag), waehrung="EUR", beschreibung=None,
                roh_json=json.dumps({"fxRateToBase": "1"}))


def _ib(lauf, schluessel, exec_id, tag, pnl):
    return dict(import_run_id=lauf, konto="U1234567", quell_schluessel=schluessel,
                exec_id=exec_id, handelstag=tag, conid=9001, waehrung="EUR",
                fifo_pnl_realized=Decimal(pnl), fx_rate_to_base=Decimal("1"))


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=_AUSFUEHRUNGEN, instrumente_=_INSTRUMENTE)
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(select(import_runs.c.id)).scalars().first()
        verbindung.execute(insert(flex_cash_transactions).values([
            _buchung(lauf, "C1", datetime(2026, 1, 1, 9), "Deposits/Withdrawals", "1000.00"),
            _buchung(lauf, "C2", datetime(2026, 1, 4, 9), "Dividends", "5.00"),
        ]))
        verbindung.execute(insert(flex_nav_tage).values(
            import_run_id=lauf, konto="U1234567", quell_schluessel="nav:2026-01-05",
            datum=date(2026, 1, 5), waehrung="EUR", gesamt=Decimal("1100.00"),
            roh_json="{}"))
        verbindung.execute(insert(flex_ib_realized).values([
            _ib(lauf, "trade:T1", "T1", date(2026, 1, 3), "60.00"),
            _ib(lauf, "trade:T2", "T2", date(2026, 1, 3), "-10.00"),
            _ib(lauf, "trade:T9", "T9", date(2026, 1, 6), "999.00"),
        ]))
        verbindung.execute(insert(flex_open_positions).values(
            import_run_id=lauf, konto="U1234567", quell_schluessel="op:1",
            stichtag=date(2026, 1, 5), conid=9001, symbol="TST  260320P100",
            asset_class="OPT", menge=Decimal("-1"), kostenbasis_preis=Decimal("1.00"),
            fifo_pnl_unrealisiert=Decimal("-20.00"), waehrung="EUR",
            roh_json=json.dumps({
                "levelOfDetail": "SUMMARY", "fxRateToBase": "1", "positionValue": "-30.00",
                "fifoPnlUnrealized": "-20.00", "markPrice": "3.00", "costBasisPrice": "1.00"})))
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


@pytest.fixture
def leerer_klient(migrated_db):
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_kontowert_einzahlungen_gewinn(klient):
    daten = klient.get("/ueberleitung").json()
    assert daten["stichtag"] == "2026-01-05"
    assert _d(daten["kontowert"]) == Decimal("1100.00")
    assert _d(daten["einzahlungen"]) == Decimal("1000.00")
    assert _d(daten["gewinn_ib"]) == Decimal("100.00")


def test_zerlegung_laut_ib(klient):
    ib = klient.get("/ueberleitung").json()["ib"]
    assert _d(ib["realisiert"]) == Decimal("50.00")        # 60 − 10, ohne die Zeile vom 06.01.
    assert _d(ib["unrealisiert"]) == Decimal("-20.00")
    assert _d(ib["sonstige_buchungen"]) == Decimal("5.00")
    assert _d(ib["rest"]) == Decimal("65.00")              # 100 − (50 − 20 + 5)


def test_summe_der_posten_ergibt_den_gewinn(klient):
    daten = klient.get("/ueberleitung").json()
    ib = daten["ib"]
    summe = sum(_d(ib[k]) for k in ("realisiert", "unrealisiert", "sonstige_buchungen", "rest"))
    assert summe == _d(daten["gewinn_ib"])


def test_journal_gegen_ib_realisiert(klient):
    journal = klient.get("/ueberleitung").json()["journal"]
    assert _d(journal["realisiert"]) == Decimal("56.00")
    assert _d(journal["differenz_realisiert"]) == Decimal("6.00")


def test_abdeckung_zeigt_wie_vollstaendig_ibs_wert_vorliegt(klient):
    """Beide Ausführungen der Welt haben einen IB-Wert; T9 gehört zu keiner."""
    abdeckung = klient.get("/ueberleitung").json()["abdeckung"]
    assert abdeckung == {"ausfuehrungen": 2, "mit_ib_wert": 2}


def test_geld_ist_zeichenkette_nie_zahl(klient):
    rohtext = klient.get("/ueberleitung").text.replace(" ", "")
    assert '"kontowert":"' in rohtext
    assert '"kontowert":1' not in rohtext


def test_ohne_kontowert_keine_ueberleitung(leerer_klient):
    daten = leerer_klient.get("/ueberleitung").json()
    assert daten["stichtag"] is None
    assert daten["kontowert"] is None and daten["gewinn_ib"] is None
    assert daten["ib"] is None and daten["journal"] is None
    assert daten["abdeckung"] == {"ausfuehrungen": 0, "mit_ib_wert": 0}
