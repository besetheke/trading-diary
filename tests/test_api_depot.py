"""Abnahmetests für `GET /depot` (AP-08d): der Bestand laut IB mit letztem
bekanntem Kurs und unrealisiertem Ergebnis. Unveränderlich.

Quelle ist der Bestand der letzten Flex-Auswertung (`flex_open_positions`,
jüngster Stichtag, Ebene SUMMARY): Menge, Einstandskurs, Kurs (`markPrice`),
Marktwert (`positionValue`) und unrealisiertes Ergebnis (`fifoPnlUnrealized`)
je Position, in der Währung der Position; die EUR-Werte entstehen mit IBs
`fxRateToBase` der Zeile. Nichts wird neu bewertet.

Testwelt (frei erfunden; Kurse mit zwei Nachkommastellen, damit die Texte
stabil bleiben):

  Stichtag 2026-10-08 (älter, wird ignoriert): conid 100 mit anderen Werten.
  Stichtag 2026-10-09:
    P1 ABC  Aktie  USD  100 Stück, Einstand 50.00, Kurs 45.00,
         Marktwert 4500.00, unrealisiert -500.00, Kurs 0.90
         → EUR 4500.00 × 0.90 = 4050.00; -500.00 × 0.90 = -450.00
    P2 ABC Put 40 (20.11.2026) Option USD, -2 Kontrakte, Multiplikator 100,
         Einstand 1.50, Kurs 1.00, Marktwert -200.00, unrealisiert 100.00,
         Kurs 0.90 → EUR -180.00 und 90.00
    P3 XYZ  Aktie  EUR  10 Stück, Einstand 18.00, Kurs 20.00,
         Marktwert 200.00, unrealisiert 20.00, Kurs 1.00 → EUR 200.00, 20.00

Summen EUR: Marktwert 4050.00 - 180.00 + 200.00 = 4070.00;
unrealisiert -450.00 + 90.00 + 20.00 = -340.00.
Je Klasse: STK 2 Positionen, Marktwert 4250.00, unrealisiert -430.00;
OPT 1 Position, Marktwert -180.00, unrealisiert 90.00.
Reihenfolge: Aktien zuerst, innerhalb nach Betrag des EUR-Marktwerts absteigend,
danach die übrigen Klassen → conid 100, 300, 200.
"""

import json
from datetime import date
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import flex_open_positions, import_runs  # noqa: E402

_INSTRUMENTE = [
    dict(conid=100, symbol="ABC", underlying="ABC", asset_class="STK", expiry=None,
         strike=None, right=None, multiplikator=Decimal("1"), waehrung="USD"),
    dict(conid=200, symbol="ABC  261120P00040000", underlying="ABC", asset_class="OPT",
         expiry=date(2026, 11, 20), strike=Decimal("40"), right="P",
         multiplikator=Decimal("100"), waehrung="USD"),
    dict(conid=300, symbol="XYZ", underlying="XYZ", asset_class="STK", expiry=None,
         strike=None, right=None, multiplikator=Decimal("1"), waehrung="EUR"),
]


def _zeile(stichtag, conid, symbol, klasse, menge, waehrung, einstand, kurs, wert, pnl, fx,
           *, multiplikator="1"):
    roh = dict(
        conid=str(conid), symbol=symbol, assetCategory=klasse, position=str(menge),
        costBasisPrice=einstand, markPrice=kurs, positionValue=wert, fifoPnlUnrealized=pnl,
        fxRateToBase=fx, multiplier=multiplikator, levelOfDetail="SUMMARY",
        reportDate=stichtag.strftime("%Y%m%d"),
    )
    return dict(stichtag=stichtag, conid=conid, symbol=symbol, asset_class=klasse,
                menge=Decimal(str(menge)), kostenbasis_preis=Decimal(einstand),
                fifo_pnl_unrealisiert=Decimal(pnl), waehrung=waehrung,
                roh_json=json.dumps(roh))


_ZEILEN = [
    _zeile(date(2026, 10, 8), 100, "ABC", "STK", 100, "USD", "49.00", "44.00", "4400.00",
           "-600.00", "0.91"),
    _zeile(date(2026, 10, 9), 100, "ABC", "STK", 100, "USD", "50.00", "45.00", "4500.00",
           "-500.00", "0.90"),
    _zeile(date(2026, 10, 9), 200, "ABC  261120P00040000", "OPT", -2, "USD", "1.50", "1.00",
           "-200.00", "100.00", "0.90", multiplikator="100"),
    _zeile(date(2026, 10, 9), 300, "XYZ", "STK", 10, "EUR", "18.00", "20.00", "200.00",
           "20.00", "1.00"),
]


def _d(text):
    """EUR-Beträge sind gerechnete Produkte (Wert × Kurs, nicht gerundet): der
    Text trägt so viele Nachkommastellen, wie die Faktoren ergeben — verglichen
    wird der Wert, nicht die Schreibweise."""
    assert isinstance(text, str), text
    return Decimal(text)


def _bestand_schreiben(db_pfad, zeilen):
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(select(import_runs.c.id)).scalars().first()
        for nr, z in enumerate(zeilen, 1):
            verbindung.execute(insert(flex_open_positions).values(
                import_run_id=lauf, konto="U1234567",
                quell_schluessel=f"op:{z['stichtag']}|{z['conid']}|{nr}", **z))


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, ausfuehrungen=[], instrumente_=_INSTRUMENTE)
    _bestand_schreiben(migrated_db, _ZEILEN)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


@pytest.fixture
def leerer_klient(migrated_db):
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


def test_nur_der_juengste_stichtag_zaehlt(klient):
    daten = klient.get("/depot").json()
    assert daten["stichtag"] == "2026-10-09"
    assert [p["conid"] for p in daten["positionen"]] == [100, 300, 200]


def test_position_aktie_in_dollar(klient):
    p = {p["conid"]: p for p in klient.get("/depot").json()["positionen"]}[100]
    assert (p["symbol"], p["basiswert"], p["anlageklasse"], p["waehrung"]) == (
        "ABC", "ABC", "STK", "USD")
    assert p["menge"] == "100"
    assert (p["einstandskurs"], p["kurs"]) == ("50.00", "45.00")
    assert (p["marktwert"], p["unrealisiert"]) == ("4500.00", "-500.00")
    assert (_d(p["marktwert_eur"]), _d(p["unrealisiert_eur"])) == (
        Decimal("4050.00"), Decimal("-450.00"))


def test_position_option_mit_stammdaten(klient):
    p = {p["conid"]: p for p in klient.get("/depot").json()["positionen"]}[200]
    assert (p["anlageklasse"], p["basiswert"], p["seite"]) == ("OPT", "ABC", "Put")
    assert (p["verfall"], p["strike"], p["multiplikator"]) == ("2026-11-20", "40", "100")
    assert p["menge"] == "-2"
    assert (_d(p["marktwert_eur"]), _d(p["unrealisiert_eur"])) == (
        Decimal("-180.00"), Decimal("90.00"))


def test_aktie_in_euro_wird_nicht_umgerechnet_verfaelscht(klient):
    p = {p["conid"]: p for p in klient.get("/depot").json()["positionen"]}[300]
    assert (_d(p["marktwert_eur"]), _d(p["unrealisiert_eur"])) == (
        Decimal("200.00"), Decimal("20.00"))


def test_summen_und_summen_je_klasse(klient):
    summen = klient.get("/depot").json()["summen"]
    assert _d(summen["marktwert_eur"]) == Decimal("4070.00")
    assert _d(summen["unrealisiert_eur"]) == Decimal("-340.00")
    je_klasse = [(k["anlageklasse"], k["anzahl"], _d(k["marktwert_eur"]),
                  _d(k["unrealisiert_eur"])) for k in summen["je_klasse"]]
    assert je_klasse == [
        ("STK", 2, Decimal("4250.00"), Decimal("-430.00")),
        ("OPT", 1, Decimal("-180.00"), Decimal("90.00")),
    ]


def test_geld_ist_zeichenkette_nie_zahl(klient):
    rohtext = klient.get("/depot").text.replace(" ", "")
    assert '"marktwert":"4500.00"' in rohtext      # Rohwert, unverändert durchgereicht
    assert '"marktwert_eur":"' in rohtext          # Text, nie eine Zahl
    assert '"marktwert_eur":4' not in rohtext


def test_leerer_bestand(leerer_klient):
    daten = leerer_klient.get("/depot").json()
    assert daten["stichtag"] is None
    assert daten["positionen"] == []
    assert _d(daten["summen"]["marktwert_eur"]) == 0
    assert _d(daten["summen"]["unrealisiert_eur"]) == 0
    assert daten["summen"]["je_klasse"] == []
