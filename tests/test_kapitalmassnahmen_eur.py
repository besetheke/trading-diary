"""Abnahmetests für AP-03vz2: Kapitalmaßnahmen und die EUR-Analytik.
Unveränderlich — Vertrag in auftraege/AP-03vz2.md.

Befund (11.10.2026): Nach einer Kapitalmaßnahme trägt ein Leg die Menge in
**neuen** Stücken, die Ausführung aber noch Menge und Preis der **alten**.
Alles, was Preis × Leg-Menge aus der Ausführung neu rechnet (EUR-Kennzahlen,
Equity, Kommissionsanteile, die Prämien „Preis auf/zu"), lieferte dann
falsche Werte — im Echtbestand kippte die Equity von +102.335 € auf −282.232 €.

Vertrag: Das Matching merkt sich je Leg den Faktor der Maßnahmen, den die
Eröffnungs- und die Schließungsausführung durchlaufen haben
(``open_faktor``, ``close_faktor``; Faktor = neue ÷ alte Menge, mehrere
Maßnahmen multiplizieren sich; ohne Maßnahme 1). Die Analytik rechnet je
Seite mit Preis ÷ Faktor und der Ausführungsmenge × Faktor.

Welt wie tests/test_kapitalmassnahmen.py (frei erfunden, EUR, Kurs 1,
Multiplikator 1, Kommission −2.00 je Ausführung):

  BUY 400 ALT zu 10.00 (02.01.), Reverse Split 1:4 am 02.02. (ALT −400,
  NEU +100: Faktor 0.25), SELL 100 NEU zu 50.00 (02.03.).

Von Hand:
  Faktor der Eröffnung 0.25 → Kaufpreis je neuem Stück 10.00 ÷ 0.25 = 40.00.
  Eröffnung: −1 × 40.00 × 100 = −4000.00; Kommission −2.00 × (100 ÷ (400 × 0.25))
  = −2.00. Schließung: +1 × 50.00 × 100 = +5000.00, Kommission −2.00.
  Netto = (−4000 − 2) + (5000 − 2) = 996.00 EUR.
  (Ohne Faktor: −1000.00 − 0.50 + 4998.00 = 3997.50 — falsch.)
  „Preis auf" je Stück −40.00, „Preis zu" 50.00.
"""

import json
from datetime import datetime
from decimal import Decimal as D

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

pytest.importorskip("fastapi")
pytest.importorskip("api.app")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402
from engine.matching import bilde_legs  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import flex_corporate_actions, import_runs, legs  # noqa: E402

_INSTRUMENTE = [
    dict(conid=c, symbol=s, underlying=s, asset_class="STK", expiry=None, strike=None,
         right=None, multiplikator=D("1"), waehrung="EUR")
    for c, s in ((100, "NEU"), (200, "ALT"), (300, "MITTE"), (400, "ENDE"))
]


def _ausf(exec_id, conid, side, menge, preis, zeit):
    return dict(exec_id=exec_id, conid=conid, side=side, menge=D(menge), preis=D(preis),
                handelszeit=zeit, buchungskurs=D("1"))


def _roh(aktion, art, conid, menge, tag):
    return dict(actionID=aktion, type=art, assetCategory="STK", conid=str(conid),
                quantity=str(menge), dateTime=f"{tag};202500", costBasis="",
                symbol=f"S{conid}", levelOfDetail="DETAIL")


def _massnahmen_eintragen(db_pfad, *rohe):
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        lauf = verbindung.execute(select(import_runs.c.id)).scalars().first()
        for nr, roh in enumerate(rohe, 1):
            tag = roh["dateTime"][:8]
            verbindung.execute(insert(flex_corporate_actions).values(
                import_run_id=lauf, konto="U1234567", quell_schluessel=f"tx:{nr}|{roh['type']}",
                conid=int(roh["conid"]), typ=roh["type"],
                datum=datetime(int(tag[:4]), int(tag[4:6]), int(tag[6:8]), 20, 25),
                beschreibung="x", roh_json=json.dumps(roh)))


_AUSFUEHRUNGEN = [
    _ausf("E1", 200, "BUY", "400", "10.00", datetime(2026, 1, 2, 10, 0)),
    _ausf("E2", 100, "SELL", "100", "50.00", datetime(2026, 3, 2, 10, 0)),
]

_MASSNAHME = [_roh("R1", "RS", 200, -400, "20260202"), _roh("R1", "RS", 100, 100, "20260202")]


@pytest.fixture
def klient(migrated_db):
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=_AUSFUEHRUNGEN)
    _massnahmen_eintragen(migrated_db, *_MASSNAHME)
    rebuild(migrated_db)
    with TestClient(erzeuge_app(migrated_db)) as klient:
        yield klient


# ------------------------------------------------------------ Engine (rein)


def _engine_welt():
    ausfuehrungen = [
        dict(exec_id="E1", conid=200, side="BUY", menge=D("400"), preis=D("10.00"),
             kommission=D("-2.00"), handelszeit=datetime(2026, 1, 2, 10, 0),
             ereignistyp="trade"),
        dict(exec_id="E2", conid=100, side="SELL", menge=D("100"), preis=D("50.00"),
             kommission=D("-2.00"), handelszeit=datetime(2026, 3, 2, 10, 0),
             ereignistyp="trade"),
    ]
    instrumente = {c: dict(conid=c, multiplikator=D("1"), asset_class="STK")
                   for c in (100, 200)}
    massnahmen = [dict(aktion_id="R1", konto="U1", typ="RS", stichtag=datetime(2026, 2, 2),
                       alter_conid=200, alte_menge=D("400"), neuer_conid=100,
                       neue_menge=D("100"), kosten_neu=None)]
    return ausfuehrungen, instrumente, massnahmen


def test_leg_traegt_die_faktoren_der_massnahmen():
    ausfuehrungen, instrumente, massnahmen = _engine_welt()
    (leg,) = bilde_legs(ausfuehrungen, instrumente, massnahmen).legs
    assert leg.open_faktor == D("0.25")     # 100 ÷ 400
    assert leg.close_faktor == D("1")       # am 02.03. schon zu neuen Konditionen
    assert leg.menge == D("100")
    assert leg.brutto_pnl == D("1000.00")   # (50.00 − 40.00) × 100


def test_ohne_massnahme_ist_der_faktor_eins():
    ausfuehrungen, instrumente, _ = _engine_welt()
    for a in ausfuehrungen:
        a["conid"] = 200
    (leg,) = bilde_legs(ausfuehrungen[:1] + [dict(ausfuehrungen[1], menge=D("400"))],
                        instrumente).legs
    assert (leg.open_faktor, leg.close_faktor) == (D("1"), D("1"))


def test_faktoren_aufeinanderfolgender_massnahmen_multiplizieren_sich():
    """1:1 (Tausch) dann 100 → 40 (Fusion): 1 × 0.4 = 0.4."""
    ausfuehrungen = [
        dict(exec_id="E1", conid=200, side="BUY", menge=D("100"), preis=D("20.00"),
             kommission=D("-2.00"), handelszeit=datetime(2026, 1, 2, 10, 0),
             ereignistyp="trade"),
        dict(exec_id="E2", conid=400, side="SELL", menge=D("40"), preis=D("60.00"),
             kommission=D("-2.00"), handelszeit=datetime(2026, 4, 1, 10, 0),
             ereignistyp="trade"),
    ]
    instrumente = {c: dict(conid=c, multiplikator=D("1"), asset_class="STK")
                   for c in (200, 300, 400)}
    massnahmen = [
        dict(aktion_id="R2", konto="U1", typ="TO", stichtag=datetime(2026, 2, 2),
             alter_conid=200, alte_menge=D("100"), neuer_conid=300, neue_menge=D("100"),
             kosten_neu=None),
        dict(aktion_id="R3", konto="U1", typ="TC", stichtag=datetime(2026, 3, 2),
             alter_conid=300, alte_menge=D("100"), neuer_conid=400, neue_menge=D("40"),
             kosten_neu=None),
    ]
    (leg,) = bilde_legs(ausfuehrungen, instrumente, massnahmen).legs
    assert leg.open_faktor == D("0.4")
    assert leg.brutto_pnl == D("400.00")    # (60.00 − 50.00) × 40


# ----------------------------------------------------------- Rebuild/Tabelle


def test_legs_tabelle_speichert_die_faktoren(klient, migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        zeilen = [dict(z) for z in verbindung.execute(
            select(legs).where(legs.c.sicht == "konto")).mappings()]
    assert len(zeilen) == 1
    assert D(str(zeilen[0]["open_faktor"])) == D("0.25")
    assert D(str(zeilen[0]["close_faktor"])) == D("1")


def test_legs_ohne_massnahme_haben_faktor_eins(migrated_db):
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=[
        _ausf("E1", 200, "BUY", "10", "10.00", datetime(2026, 1, 2, 10, 0)),
        _ausf("E2", 200, "SELL", "10", "12.00", datetime(2026, 1, 9, 10, 0)),
    ])
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        zeilen = [dict(z) for z in verbindung.execute(select(legs)).mappings()]
    assert zeilen
    assert all(D(str(z["open_faktor"])) == 1 and D(str(z["close_faktor"])) == 1
               for z in zeilen)


# --------------------------------------------------------------------- API


def test_equity_rechnet_mit_dem_faktor(klient):
    """Netto 996.00 EUR am Verkaufstag (Herleitung im Kopf der Datei)."""
    daten = klient.get("/equity").json()
    assert [(t["datum"], t["netto_eur"]) for t in daten["tage"]] == [("2026-03-02", "996.00")]


def test_praemien_je_stueck_sind_umgerechnet(klient):
    """„Preis auf" −40.00 (10.00 ÷ 0.25, gekauft), „Preis zu" 50.00 (verkauft)."""
    treffer = klient.get("/ketten").json()["treffer"]
    kette = next(k for k in treffer if k["underlying"] == "NEU")
    assert kette["eroeffnungspreis"] == "-40.00"
    assert kette["schlusspreis"] == "50.00"
    assert kette["menge"] == "100"


def test_kennzahlen_und_equity_stimmen_ueberein(klient):
    kapital = klient.get("/kapital").json()
    assert kapital["ergebnis_im_zeitraum"] == "996.00"
