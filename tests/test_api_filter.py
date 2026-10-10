"""Abnahmetests für AP-07f: Filter an `GET /ketten` und `GET /auswertung`.

Vertrag: auftraege/AP-07f.md. Geschrieben durch das starke Modell — für die
Umsetzung unveränderlich. Alle Erwartungen von Hand gerechnet (Regel 8).

Testwelt (Rebuild, frei erfunden, Multiplikator 10, Kommission -2.00 je
Ausführung, vier Basiswerte = vier Ketten mit je einer Struktur):

  AAA  EUR  SELL 10.00 am 2026-01-02, BUY 4.00 am 2026-01-03 (10:00)
            brutto 60.00, netto 56.00, geschlossen 2026-01-03
  BBB  EUR  SELL  9.00 am 2026-02-02, BUY 10.00 am 2026-02-05 (10:00)
            brutto -10.00, netto -14.00, geschlossen 2026-02-05
  CCC  USD  SELL  5.00 am 2026-01-10, BUY  2.00 am 2026-03-01 (10:00), Kurs 2
            (ganzzahlig, damit die Nachkommastellen stabil bleiben: Decimal
            rundet nie, ein Kurs 0.5 ergäbe 13.000)
            netto EUR (50 - 2) * 2 + (-20 - 2) * 2 = 52.00, geschlossen 2026-03-01
  DDD  EUR  SELL  3.00 am 2026-03-05, offen

Equity ohne Filter: 01-03 +56.00 (kum 56.00) | 02-05 -14.00 (kum 42.00,
DD -14.00) | 03-01 +52.00 (kum 94.00, neues Hoch, DD 0.00). Maximaler Drawdown -14.00
am 2026-02-05.

Die Strategie steht nach dem Rebuild nicht in der Welt (OA-Import fehlt);
der Test setzt `chains.oa_strategie` für AAA und CCC auf "IC1" direkt.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import update

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import chains  # noqa: E402


def _instrument(conid, basis, waehrung):
    return dict(conid=conid, symbol=f"{basis}  260320P100", underlying=basis,
                asset_class="OPT", expiry=date(2026, 3, 20), strike=Decimal("100"),
                right="P", multiplikator=Decimal("10"), waehrung=waehrung)


def _ausf(exec_id, conid, side, preis, zeit, waehrung="EUR", kurs="1"):
    return dict(exec_id=exec_id, conid=conid, side=side, preis=Decimal(preis),
                handelszeit=zeit, waehrung=waehrung, kommission_waehrung=waehrung,
                buchungskurs=Decimal(kurs))


_INSTRUMENTE = [
    _instrument(9001, "AAA", "EUR"),
    _instrument(9002, "BBB", "EUR"),
    _instrument(9003, "CCC", "USD"),
    _instrument(9004, "DDD", "EUR"),
]

_AUSFUEHRUNGEN = [
    _ausf("A1", 9001, "SELL", "10.00", datetime(2026, 1, 2, 10, 0)),
    _ausf("A2", 9001, "BUY", "4.00", datetime(2026, 1, 3, 10, 0)),
    _ausf("B1", 9002, "SELL", "9.00", datetime(2026, 2, 2, 10, 0)),
    _ausf("B2", 9002, "BUY", "10.00", datetime(2026, 2, 5, 10, 0)),
    _ausf("C1", 9003, "SELL", "5.00", datetime(2026, 1, 10, 10, 0), "USD", "2"),
    _ausf("C2", 9003, "BUY", "2.00", datetime(2026, 3, 1, 10, 0), "USD", "2"),
    _ausf("D1", 9004, "SELL", "3.00", datetime(2026, 3, 5, 10, 0)),
]


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=_AUSFUEHRUNGEN, instrumente_=_INSTRUMENTE)
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        verbindung.execute(
            update(chains).where(chains.c.underlying.in_(["AAA", "CCC"]))
            .values(oa_strategie="IC1")
        )
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def _basiswerte(antwort):
    assert antwort.status_code == 200, antwort.text
    return sorted(k["underlying"] for k in antwort.json()["treffer"])


# ------------------------------------------------------------------ /ketten


def test_ohne_filter_alle_vier(klient):
    assert _basiswerte(klient.get("/ketten")) == ["AAA", "BBB", "CCC", "DDD"]


def test_geschlossen_ab(klient):
    """A schließt 01-03, B 02-05, C 03-01; D ist offen (kein Ende)."""
    antwort = klient.get("/ketten", params={"geschlossen_ab": "2026-02-01"})
    assert _basiswerte(antwort) == ["BBB", "CCC"]


def test_geschlossen_bis_ist_einschliesslich(klient):
    """B schließt 2026-02-05 um 10:00 — der Tag zählt noch dazu."""
    antwort = klient.get("/ketten", params={"geschlossen_bis": "2026-02-05"})
    assert _basiswerte(antwort) == ["AAA", "BBB"]


def test_waehrung(klient):
    assert _basiswerte(klient.get("/ketten", params={"waehrung": "USD"})) == ["CCC"]
    assert _basiswerte(klient.get("/ketten", params={"waehrung": "EUR"})) == [
        "AAA", "BBB", "DDD"]


def test_strategie(klient):
    antwort = klient.get("/ketten", params={"strategie": "IC1"})
    assert _basiswerte(antwort) == ["AAA", "CCC"]


def test_filter_kombiniert(klient):
    antwort = klient.get(
        "/ketten", params={"waehrung": "EUR", "geschlossen_ab": "2026-01-01"})
    assert _basiswerte(antwort) == ["AAA", "BBB"]


def test_gesamt_zaehlt_vor_der_begrenzung(klient):
    daten = klient.get("/ketten", params={"waehrung": "EUR", "limit": 1}).json()
    assert daten["gesamt"] == 3
    assert len(daten["treffer"]) == 1


def test_aktiv_im_zeitraum_z3(klient):
    """Z3: eröffnet bis `bis`, und offen oder beendet ab `von`.
    10.02.-28.02.: nur C (eröffnet 01-10, beendet 03-01). A und B sind schon
    beendet, D ist noch nicht eröffnet."""
    antwort = klient.get("/ketten", params={"von": "2026-02-10", "bis": "2026-02-28"})
    assert _basiswerte(antwort) == ["CCC"]
    """02.03.-31.03.: nur D (offen, eröffnet 03-05); C endete am 03-01."""
    antwort = klient.get("/ketten", params={"von": "2026-03-02", "bis": "2026-03-31"})
    assert _basiswerte(antwort) == ["DDD"]


def test_aktiv_im_zeitraum_einschliesslich_der_enden(klient):
    """`von` = Schließungstag von C (03-01) zählt noch dazu."""
    antwort = klient.get("/ketten", params={"von": "2026-03-01", "bis": "2026-03-01"})
    assert _basiswerte(antwort) == ["CCC"]


@pytest.mark.parametrize("params", [
    {"geschlossen_ab": "2026-03-01", "geschlossen_bis": "2026-02-01"},
    {"von": "2026-03-01", "bis": "2026-02-01"},
    {"geschlossen_ab": "gestern"},
])
def test_ungueltige_filter_sind_422(klient, params):
    assert klient.get("/ketten", params=params).status_code == 422


# -------------------------------------------------------------- /auswertung


def test_auswertung_ohne_filter(klient):
    daten = klient.get("/auswertung").json()
    assert [(t["datum"], t["netto_eur"], t["kumuliert_eur"], t["drawdown_eur"])
            for t in daten["tage"]] == [
        ("2026-01-03", "56.00", "56.00", "0.00"),
        ("2026-02-05", "-14.00", "42.00", "-14.00"),
        ("2026-03-01", "52.00", "94.00", "0.00"),
    ]
    assert daten["max_drawdown_eur"] == "-14.00"
    assert daten["max_drawdown_datum"] == "2026-02-05"
    assert daten["ergebnis"] == {
        "anzahl_ketten": 4, "anzahl_strukturen": 3, "summe_netto_eur": "94.00",
        "anzahl_kurs_fehlt": 0, "lose_legs_eingeschlossen": True,
    }
    assert [m["monat"] for m in daten["monate"]] == ["2026-01", "2026-02", "2026-03"]


def test_auswertung_nach_waehrung(klient):
    """Die Währung kennt auch ein loses Leg: der Filter schließt es nicht aus
    (hier gibt es keines), die Kennzeichnung bleibt wahr (test_api_filter_lose_legs)."""
    daten = klient.get("/auswertung", params={"waehrung": "USD"}).json()
    assert [(t["datum"], t["netto_eur"]) for t in daten["tage"]] == [("2026-03-01", "52.00")]
    assert daten["ergebnis"] == {
        "anzahl_ketten": 1, "anzahl_strukturen": 1, "summe_netto_eur": "52.00",
        "anzahl_kurs_fehlt": 0, "lose_legs_eingeschlossen": True,
    }
    assert daten["max_drawdown_eur"] == "0.00"


def test_auswertung_nach_strategie(klient):
    """AAA (+56.00, 01-03) und CCC (+52.00, 03-01): kumuliert 56.00 / 108.00."""
    daten = klient.get("/auswertung", params={"strategie": "IC1"}).json()
    assert [(t["datum"], t["kumuliert_eur"]) for t in daten["tage"]] == [
        ("2026-01-03", "56.00"), ("2026-03-01", "108.00")]
    assert daten["ergebnis"]["summe_netto_eur"] == "108.00"
    assert daten["ergebnis"]["anzahl_ketten"] == 2


def test_auswertung_zeitraum_gilt_fuer_den_schliessungstag(klient):
    """Z2/Z4: ab 2026-02-01 zählen B und C; die Kurve beginnt bei 0."""
    daten = klient.get("/auswertung", params={"von": "2026-02-01"}).json()
    # Das laufende Hoch beginnt bei 0 (AP-06e, E4): -14.00 ist sofort Drawdown.
    assert [(t["datum"], t["kumuliert_eur"], t["drawdown_eur"]) for t in daten["tage"]] == [
        ("2026-02-05", "-14.00", "-14.00"),
        ("2026-03-01", "38.00", "0.00"),
    ]
    assert daten["max_drawdown_eur"] == "-14.00"
    assert daten["ergebnis"]["summe_netto_eur"] == "38.00"


def test_auswertung_kettenfilter_und_zeitraum_zusammen(klient):
    daten = klient.get(
        "/auswertung", params={"waehrung": "EUR", "bis": "2026-02-28"}).json()
    assert [(t["datum"], t["netto_eur"]) for t in daten["tage"]] == [
        ("2026-01-03", "56.00"), ("2026-02-05", "-14.00")]
    assert daten["ergebnis"]["anzahl_ketten"] == 3
    assert daten["ergebnis"]["summe_netto_eur"] == "42.00"


def test_auswertung_ohne_treffer(klient):
    daten = klient.get("/auswertung", params={"basiswert": "ZZZ"}).json()
    assert daten["tage"] == [] and daten["monate"] == []
    assert daten["max_drawdown_eur"] == "0.00"
    assert daten["max_drawdown_datum"] is None
    assert daten["ergebnis"]["anzahl_ketten"] == 0
    assert daten["ergebnis"]["summe_netto_eur"] == "0.00"


def test_auswertung_geld_ist_zeichenkette(klient):
    rohtext = klient.get("/auswertung").text.replace(" ", "")
    assert '"summe_netto_eur":"94.00"' in rohtext


@pytest.mark.parametrize("params", [
    {"von": "2026-03-01", "bis": "2026-02-01"},
    {"geschlossen_ab": "2026-03-01", "geschlossen_bis": "2026-02-01"},
    {"bis": "2026-13-01"},
])
def test_auswertung_ungueltige_filter_sind_422(klient, params):
    assert klient.get("/auswertung", params=params).status_code == 422
