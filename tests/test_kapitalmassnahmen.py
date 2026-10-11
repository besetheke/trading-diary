"""Abnahmetests für AP-03vz: Kapitalmaßnahmen aus den Flex-Rohzeilen ableiten
(`flex_corporate_actions` → `corporate_actions`) und im Rebuild anwenden.
Unveränderlich — Vertrag in auftraege/AP-03vz.md.

Teil 1 (reine Funktion `journal.kapitalmassnahmen.kapitalmassnahmen_ableiten`):
Gruppen nach (konto, actionID); je Gruppe genau ein Abgang plus ein Zugang auf
verschiedenen conids = Transfer; Optionsanpassungen, Ausbuchungen und alles
Uneindeutige werden **nicht geraten**, sondern mit Grund gemeldet (Regel 10).

Teil 2 (Rebuild, frei erfundene Welt, von Hand gerechnet): Nach dem Rebuild
liegen die Maßnahmen in `corporate_actions`, und das Matching überträgt die
Lots — Kaufpreis je Stück ÷ Faktor, Eröffnungsausführung bleibt, realisiert
wird nichts (Plan §1, OF-23).
"""

import json
from datetime import date, datetime
from decimal import Decimal as D

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.kapitalmassnahmen import kapitalmassnahmen_ableiten
from journal.rebuild import rebuild
from journal.schema import corporate_actions, flex_corporate_actions, import_runs, legs

# ------------------------------------------------------------ Hilfen (Teil 1)


def _roh(aktion, art, conid, menge, tag, *, kategorie="STK", kosten="", **mehr):
    roh = dict(
        actionID=aktion, type=art, assetCategory=kategorie, conid=str(conid),
        quantity=str(menge), dateTime=f"{tag};202500", costBasis=kosten,
        symbol=f"S{conid}", levelOfDetail="DETAIL",
    )
    roh.update(mehr)
    return roh


def _zeilen(*rohe, konto="U1"):
    return [dict(konto=konto, roh_json=json.dumps(r)) for r in rohe]


def _ohne_roh(massnahme):
    return {k: v for k, v in massnahme.items() if k != "roh_json"}


# ------------------------------------------------------------------- Teil 1


def test_reverse_split_ist_ein_transfer():
    """UNG-förmig: 1000 alte Stück gehen ab, 250 neue kommen zu (1 für 4)."""
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A1", "RS", 200, -1000, "20240123"),
        _roh("A1", "RS", 100, 250, "20240123"),
    ))
    assert [_ohne_roh(m) for m in ergebnis.massnahmen] == [dict(
        aktion_id="A1", konto="U1", typ="RS", stichtag=date(2024, 1, 23),
        alter_conid=200, alte_menge=D("1000"), neuer_conid=100, neue_menge=D("250"),
        kosten_neu=None,
    )]
    assert ergebnis.uebersprungen == ()


def test_roh_json_der_massnahme_traegt_die_quellzeilen():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A1", "RS", 200, -1000, "20240123"),
        _roh("A1", "RS", 100, 250, "20240123"),
    ))
    quellen = json.loads(ergebnis.massnahmen[0]["roh_json"])
    assert sorted(q["conid"] for q in quellen) == ["100", "200"]


def test_forward_split_mit_optionsanpassung_in_derselben_aktion():
    """SMCI-förmig: Aktien 100 → 1000 (Transfer); zwei Optionszeilen derselben
    actionID (Call −9, Put +9, verschiedene Kontrakte) sind keine Paarung —
    sie werden übersprungen, die Aktien trotzdem abgeleitet."""
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A2", "FI", 43, -100, "20240930"),
        _roh("A2", "FI", 731, 1000, "20240930"),
        _roh("A2", "FI", 7001, -9, "20240930", kategorie="OPT", putCall="C"),
        _roh("A2", "FI", 7002, 9, "20240930", kategorie="OPT", putCall="P"),
    ))
    assert [(m["alter_conid"], m["neuer_conid"]) for m in ergebnis.massnahmen] == [(43, 731)]
    assert len(ergebnis.uebersprungen) == 1
    assert ergebnis.uebersprungen[0].aktion_id == "A2"
    assert "Option" in ergebnis.uebersprungen[0].grund


def test_reine_optionsaktion_wird_uebersprungen():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A3", "FS", 7010, 1, "20250521", kategorie="OPT", putCall="P"),
        _roh("A3", "FS", 7011, -1, "20250521", kategorie="OPT", putCall="P"),
    ))
    assert ergebnis.massnahmen == ()
    assert len(ergebnis.uebersprungen) == 1


def test_kette_tender_dann_merger_ergibt_zwei_transfers_nach_datum():
    """PARA-förmig: erst Tausch 1:1 (100 → 100), dann Fusion 100 → 39,0741."""
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A6", "TC", 803, -100, "20250806"),
        _roh("A6", "TC", 804, "39.0741", "20250806"),
        _roh("A5", "TO", 393, -100, "20250731"),
        _roh("A5", "TO", 803, 100, "20250731"),
    ))
    assert [
        (m["aktion_id"], m["alter_conid"], m["neuer_conid"], m["alte_menge"], m["neue_menge"])
        for m in ergebnis.massnahmen
    ] == [
        ("A5", 393, 803, D("100"), D("100")),
        ("A6", 803, 804, D("100"), D("39.0741")),
    ]


def test_reiner_zugang_mit_kostenangabe():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A8", "DI", 886, 200, "20260522", kosten="120.50"),
    ))
    assert [_ohne_roh(m) for m in ergebnis.massnahmen] == [dict(
        aktion_id="A8", konto="U1", typ="DI", stichtag=date(2026, 5, 22),
        alter_conid=None, alte_menge=None, neuer_conid=886, neue_menge=D("200"),
        kosten_neu=D("120.50"),
    )]


@pytest.mark.parametrize("kosten", ["", "0", "0.00"])
def test_reiner_zugang_ohne_kosten_wird_nicht_geraten(kosten):
    """Ohne Kostenangabe (leer oder 0) würde ein Zugang ein Lot ohne
    Ausbuchung eröffnen (Rechte verfallen als ED, das die Engine nicht kennt):
    nicht ableiten, mit Grund melden — kein Scheinlot, keine Nullbasis."""
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A8", "DI", 886, 200, "20260522", kosten=kosten),
    ))
    assert ergebnis.massnahmen == ()
    assert len(ergebnis.uebersprungen) == 1
    assert "Kosten" in ergebnis.uebersprungen[0].grund


def test_ausbuchung_mit_mehreren_zeilen_derselben_conid_wird_uebersprungen():
    """ED-förmig: sechs Zeilen auf einer conid, Vorzeichen gemischt."""
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A9", "ED", 886, -199, "20260617"),
        _roh("A9", "ED", 886, -1, "20260617"),
        _roh("A9", "ED", 886, 199, "20260617"),
        _roh("A9", "ED", 886, -198, "20260617"),
        _roh("A9", "ED", 886, 1, "20260617"),
        _roh("A9", "ED", 886, -2, "20260617"),
    ))
    assert ergebnis.massnahmen == ()
    assert len(ergebnis.uebersprungen) == 1


def test_abgang_ohne_zugang_wird_uebersprungen():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A11", "ED", 917, -2, "20260924"),
        _roh("A11", "ED", 917, -198, "20260924"),
    ))
    assert ergebnis.massnahmen == ()
    assert len(ergebnis.uebersprungen) == 1


def test_abgang_und_zugang_auf_derselben_conid_ist_kein_transfer():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A12", "FS", 500, -10, "20250101"),
        _roh("A12", "FS", 500, 20, "20250101"),
    ))
    assert ergebnis.massnahmen == ()
    assert len(ergebnis.uebersprungen) == 1


def test_dieselbe_zeile_aus_zwei_dateien_zaehlt_einmal():
    """Zwei Exporte desselben Zeitraums liefern dieselben Zeilen (conid,
    Menge, Zeit) — sie dürfen weder die Menge verdoppeln noch die Gruppe
    uneindeutig machen."""
    ab = _roh("A1", "RS", 200, -1000, "20240123")
    zu = _roh("A1", "RS", 100, 250, "20240123")
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(ab, zu, ab, zu))
    assert [(m["alte_menge"], m["neue_menge"]) for m in ergebnis.massnahmen] == [
        (D("1000"), D("250"))]


def test_gleiche_aktionsnummer_in_zwei_konten_sind_zwei_gruppen():
    gemischt = (
        _zeilen(_roh("A1", "RS", 200, -1000, "20240123"),
                _roh("A1", "RS", 100, 250, "20240123"), konto="U1")
        + _zeilen(_roh("A1", "RS", 200, -40, "20240123"),
                  _roh("A1", "RS", 100, 10, "20240123"), konto="U2")
    )
    ergebnis = kapitalmassnahmen_ableiten(gemischt)
    assert sorted((m["konto"], m["alte_menge"]) for m in ergebnis.massnahmen) == [
        ("U1", D("1000")), ("U2", D("40"))]


def test_zeile_ohne_aktionsnummer_wird_nicht_geraten():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("", "RS", 200, -1000, "20240123"),
        _roh("", "RS", 100, 250, "20240123"),
    ))
    assert ergebnis.massnahmen == ()
    assert len(ergebnis.uebersprungen) >= 1


def test_ergebnis_ist_unabhaengig_von_der_eingabereihenfolge():
    rohe = [
        _roh("A6", "TC", 803, -100, "20250806"), _roh("A6", "TC", 804, "39.0741", "20250806"),
        _roh("A5", "TO", 393, -100, "20250731"), _roh("A5", "TO", 803, 100, "20250731"),
        _roh("A1", "RS", 200, -1000, "20240123"), _roh("A1", "RS", 100, 250, "20240123"),
    ]
    vorwaerts = kapitalmassnahmen_ableiten(_zeilen(*rohe))
    rueckwaerts = kapitalmassnahmen_ableiten(_zeilen(*reversed(rohe)))
    assert vorwaerts == rueckwaerts
    assert [m["aktion_id"] for m in vorwaerts.massnahmen] == ["A1", "A5", "A6"]


def test_mengen_sind_decimal_nie_float():
    ergebnis = kapitalmassnahmen_ableiten(_zeilen(
        _roh("A6", "TC", 803, -100, "20250806"),
        _roh("A6", "TC", 804, "39.0741", "20250806"),
    ))
    massnahme = ergebnis.massnahmen[0]
    assert isinstance(massnahme["alte_menge"], D) and isinstance(massnahme["neue_menge"], D)


# ------------------------------------------------------- Hilfen (Teil 2)

_INSTRUMENTE = [
    dict(conid=c, symbol=s, underlying=s, asset_class="STK", expiry=None, strike=None,
         right=None, multiplikator=D("1"), waehrung="EUR")
    for c, s in ((100, "NEU"), (200, "ALT"), (300, "MITTE"), (400, "ENDE"))
]


def _ausf(exec_id, conid, side, menge, preis, zeit):
    return dict(exec_id=exec_id, conid=conid, side=side, menge=D(menge), preis=D(preis),
                handelszeit=zeit, buchungskurs=D("1"))


def _massnahme_zeilen(db_pfad, *rohe):
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


def _legs(db_pfad):
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return [dict(z) for z in verbindung.execute(
            select(legs).where(legs.c.sicht == "konto").order_by(legs.c.leg_id)
        ).mappings()]


# ------------------------------------------------------------------- Teil 2


def test_rebuild_uebertraegt_die_lots_bei_einem_reverse_split(migrated_db):
    """400 Stück ALT zu 10.00 am 02.01.; 1 für 4 am 02.02. (ALT −400, NEU +100);
    100 Stück NEU zu 50.00 am 02.03. verkauft.
    Kaufpreis je neuem Stück 10.00 × 4 = 40.00 → Brutto (50.00 − 40.00) × 100
    = 1000.00; ein einziges, geschlossenes Leg auf NEU, eröffnet durch E1."""
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=[
        _ausf("E1", 200, "BUY", "400", "10.00", datetime(2026, 1, 2, 10, 0)),
        _ausf("E2", 100, "SELL", "100", "50.00", datetime(2026, 3, 2, 10, 0)),
    ])
    _massnahme_zeilen(
        migrated_db,
        _roh("R1", "RS", 200, -400, "20260202"),
        _roh("R1", "RS", 100, 100, "20260202"),
    )
    rebuild(migrated_db)

    gefunden = _legs(migrated_db)
    assert len(gefunden) == 1
    leg = gefunden[0]
    assert (leg["conid"], leg["open_exec_id"], leg["close_exec_id"]) == (100, "E1", "E2")
    assert D(str(leg["menge"])) == D("100")
    assert D(str(leg["brutto_pnl"])) == D("1000.00")
    assert not leg["basis_ungeklaert"]

    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        zeilen = verbindung.execute(select(corporate_actions)).mappings().all()
    assert len(zeilen) == 1
    assert (zeilen[0]["aktion_id"], zeilen[0]["alter_conid"], zeilen[0]["neuer_conid"]) == (
        "R1", 200, 100)
    assert zeilen[0]["stichtag"] == date(2026, 2, 2)


def test_rebuild_verkettet_aufeinanderfolgende_transfers(migrated_db):
    """100 Stück ALT zu 20.00 (02.01.); Tausch 1:1 auf MITTE (02.02.); Fusion
    100 → 40 auf ENDE (02.03.); 40 Stück ENDE zu 60.00 am 01.04. verkauft.
    Kaufpreis je ENDE-Stück 20.00 × 100 ÷ 40 = 50.00 → Brutto
    (60.00 − 50.00) × 40 = 400.00; Eröffnung bleibt E1."""
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=[
        _ausf("E1", 200, "BUY", "100", "20.00", datetime(2026, 1, 2, 10, 0)),
        _ausf("E2", 400, "SELL", "40", "60.00", datetime(2026, 4, 1, 10, 0)),
    ])
    _massnahme_zeilen(
        migrated_db,
        _roh("R2", "TO", 200, -100, "20260202"), _roh("R2", "TO", 300, 100, "20260202"),
        _roh("R3", "TC", 300, -100, "20260302"), _roh("R3", "TC", 400, 40, "20260302"),
    )
    rebuild(migrated_db)

    gefunden = _legs(migrated_db)
    assert len(gefunden) == 1
    leg = gefunden[0]
    assert (leg["conid"], leg["open_exec_id"], leg["close_exec_id"]) == (400, "E1", "E2")
    assert D(str(leg["menge"])) == D("40")
    assert D(str(leg["brutto_pnl"])) == D("400.00")


def test_zweiter_rebuild_verdoppelt_nichts_und_laesst_die_rohzeilen_unberuehrt(migrated_db):
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=[
        _ausf("E1", 200, "BUY", "400", "10.00", datetime(2026, 1, 2, 10, 0)),
    ])
    _massnahme_zeilen(
        migrated_db,
        _roh("R1", "RS", 200, -400, "20260202"),
        _roh("R1", "RS", 100, 100, "20260202"),
    )
    rebuild(migrated_db)
    rebuild(migrated_db)

    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        assert len(verbindung.execute(select(corporate_actions)).all()) == 1
        assert len(verbindung.execute(select(flex_corporate_actions)).all()) == 2
    # Offen bleibt das Lot — auf der neuen conid, 100 Stück zu 40.00.
    offen = [leg for leg in _legs(migrated_db) if leg["close_exec_id"] is None]
    assert [(leg["conid"], D(str(leg["menge"]))) for leg in offen] == [(100, D("100"))]


def test_ohne_kapitalmassnahmen_bleibt_alles_wie_vorher(migrated_db):
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=[
        _ausf("E1", 200, "BUY", "10", "10.00", datetime(2026, 1, 2, 10, 0)),
        _ausf("E2", 200, "SELL", "10", "12.00", datetime(2026, 1, 9, 10, 0)),
    ])
    rebuild(migrated_db)
    gefunden = _legs(migrated_db)
    assert len(gefunden) == 1
    assert D(str(gefunden[0]["brutto_pnl"])) == D("20.00")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        assert verbindung.execute(select(corporate_actions)).all() == []


def test_uebersprungene_gruppen_veraendern_das_matching_nicht(migrated_db):
    """Eine Ausbuchung (ED) ohne Zugang wird übersprungen: Die offene Position
    bleibt, wie sie ist — nichts wird still bewegt."""
    befuelle(migrated_db, instrumente_=_INSTRUMENTE, ausfuehrungen=[
        _ausf("E1", 200, "BUY", "10", "10.00", datetime(2026, 1, 2, 10, 0)),
    ])
    _massnahme_zeilen(
        migrated_db,
        _roh("R9", "ED", 200, -2, "20260302"),
        _roh("R9", "ED", 200, -8, "20260302"),
    )
    rebuild(migrated_db)
    offen = [leg for leg in _legs(migrated_db) if leg["close_exec_id"] is None]
    assert [(leg["conid"], D(str(leg["menge"]))) for leg in offen] == [(200, D("10"))]
