"""Abnahmetest für AP-04z auf Datenbankebene: Der Rebuild schreibt den
Zuteilungsübergang mit Verknüpfungstyp `zuteilung`, das Paar in
`assignment_links` und zählt ihn nicht als Roll. Fall wie Trade 5213 (frei
erfunden): Short Put 895 und Short Call 807 in einer Order, Put am selben Tag
zugeteilt, Call verfällt 30.09., Aktie am 01.10. verkauft."""

from datetime import date, datetime
from decimal import Decimal

from fixtures_rebuild import befuelle
from sqlalchemy import select

from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import assignment_links, chain_links, chains


def test_rebuild_schreibt_zuteilung_in_die_kette(migrated_db):
    def opt(conid, strike, right):
        return dict(conid=conid, symbol=f"SPY 260930{right}{strike}", underlying="SPY",
                    asset_class="OPT", expiry=date(2026, 9, 30), strike=Decimal(strike),
                    right=right, multiplikator=Decimal("100"), waehrung="USD",
                    abwicklungsart="lieferung")

    instrumente = [
        opt(1, "895", "P"), opt(2, "807", "C"),
        dict(conid=3, symbol="SPY", underlying=None, asset_class="STK", expiry=None,
             strike=None, right=None, multiplikator=Decimal("1"), waehrung="USD"),
    ]
    z = datetime(2026, 8, 28, 16, 20)
    ausf = [
        dict(exec_id="P1", conid=1, side="SELL", preis=Decimal("123.29"), waehrung="USD",
             handelszeit=datetime(2026, 8, 28, 11, 52), exec_batch="9.1"),
        dict(exec_id="C1", conid=2, side="SELL", preis=Decimal("0.78"), waehrung="USD",
             handelszeit=datetime(2026, 8, 28, 11, 52), exec_batch="9.1"),
        dict(exec_id="P2", conid=1, side="BUY", preis=Decimal("0"), waehrung="USD",
             handelszeit=z, ereignistyp="assignment"),
        dict(exec_id="S1", conid=3, side="BUY", menge=Decimal("100"), preis=Decimal("895"),
             waehrung="USD", handelszeit=z, ereignistyp="assignment"),
        dict(exec_id="C2", conid=2, side="BUY", preis=Decimal("0"), waehrung="USD",
             handelszeit=datetime(2026, 9, 30, 16, 20), ereignistyp="expiry"),
        dict(exec_id="S2", conid=3, side="SELL", menge=Decimal("100"), preis=Decimal("766.89"),
             waehrung="USD", handelszeit=datetime(2026, 10, 1, 15, 0)),
    ]
    befuelle(migrated_db, ausfuehrungen=ausf, instrumente_=instrumente)
    rebuild(migrated_db)

    with create_db_engine(migrated_db).connect() as v:
        ketten = v.execute(select(chains).where(chains.c.sicht == "konto")).mappings().all()
        glieder = v.execute(select(chain_links).where(chain_links.c.sicht == "konto")
                            ).mappings().all()
        paare = [(z["option_exec_id"], z["stock_exec_id"], z["erkennung"])
                 for z in v.execute(select(assignment_links)).mappings()]
    assert len(ketten) == 1
    k = ketten[0]
    assert (k["anzahl_rolls"], k["endzustand"]) == (0, "Geschlossen")
    assert k["beendet_am"] == datetime(2026, 10, 1, 15, 0)
    assert sorted(g["verknuepfungstyp"] for g in glieder) == ["open", "zuteilung"]
    assert paare == [("P2", "S1", "auto")]


def test_teilverkaeufe_einer_zuteilung_sind_eigene_strukturen(migrated_db):
    """200 Aktien zugeteilt, in zwei Teilen verkauft: zwei Strukturen mit
    eigenem Naturschlüssel (Eröffnung > Schluss), beide in der Kette — gefunden
    im ersten Lauf über den echten Bestand (52 Ketten, gleicher Schlüssel)."""
    from journal.schema import structures

    instrumente = [
        dict(conid=1, symbol="ABC 260821P50", underlying="ABC", asset_class="OPT",
             expiry=date(2026, 8, 21), strike=Decimal("50"), right="P",
             multiplikator=Decimal("100"), waehrung="EUR", abwicklungsart="lieferung"),
        dict(conid=3, symbol="ABC", underlying=None, asset_class="STK", expiry=None,
             strike=None, right=None, multiplikator=Decimal("1"), waehrung="EUR"),
    ]
    z = datetime(2026, 8, 21, 16, 20)
    ausf = [
        dict(exec_id="P1", conid=1, side="SELL", menge=Decimal("2"), preis=Decimal("1.00"),
             handelszeit=datetime(2026, 8, 1, 10, 0)),
        dict(exec_id="P2", conid=1, side="BUY", menge=Decimal("2"), preis=Decimal("0"),
             handelszeit=z, ereignistyp="assignment"),
        dict(exec_id="S1", conid=3, side="BUY", menge=Decimal("200"), preis=Decimal("50"),
             handelszeit=z, ereignistyp="assignment"),
        dict(exec_id="S2", conid=3, side="SELL", menge=Decimal("100"), preis=Decimal("52"),
             handelszeit=datetime(2026, 9, 10, 15, 0)),
        dict(exec_id="S3", conid=3, side="SELL", menge=Decimal("100"), preis=Decimal("48"),
             handelszeit=datetime(2026, 9, 20, 15, 0)),
    ]
    befuelle(migrated_db, ausfuehrungen=ausf, instrumente_=instrumente)
    rebuild(migrated_db)
    rebuild(migrated_db)  # idempotent

    with create_db_engine(migrated_db).connect() as v:
        schluessel = sorted(
            s for (s,) in v.execute(select(structures.c.natur_schluessel).where(
                structures.c.sicht == "konto"))
        )
        typen = sorted(g for (g,) in v.execute(select(chain_links.c.verknuepfungstyp).where(
            chain_links.c.sicht == "konto")))
    assert schluessel == ["P1", "S1>S2", "S1>S3"]
    assert typen == ["open", "zuteilung", "zuteilung"]
