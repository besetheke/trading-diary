"""Abnahmetests für AP-13ab, Teil Import: inhaltlich gleiche Trades übernehmen
auf Wunsch (`anreichern=True`) das vollständigere Zeilenbild des neuen Exports
(Gewinn in Originalwährung, Währung) — ohne den Inhalt zu ändern; der alte
Rohstand bleibt unter „_vorher". Vertrag: auftraege/AP-13ab.md.

7001 erst im alten Format (Zeilenbild als Liste), dann im neuen (AP-13r3) mit
`anreichern=True`: 1 angereichert, 2 neu; `roh_json` ist danach ein Objekt mit
„Profit (orig.)" = „144.24" und „Currency" = „USD", „_vorher" ist die alte
Liste; `name_roh` bleibt „IF7  [7001]". Ein zweiter Lauf reichert nichts mehr
an. Ohne `anreichern` bleibt die Liste.
"""

import json
from pathlib import Path

from sqlalchemy import select

from ingest.optionapp import import_optionapp_file
from journal.db import create_db_engine
from journal.schema import optionapp_trades

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optionapp"


def _zeile(db, nr):
    with create_db_engine(db).connect() as v:
        return dict(v.execute(select(optionapp_trades).where(
            optionapp_trades.c.oa_trade == nr)).mappings().one())


def test_anreichern(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_v3_alt_7001.xlsx")
    e = import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx", anreichern=True)
    assert (e.zeilen_neu, e.zeilen_angereichert) == (2, 1)
    z = _zeile(migrated_db, "7001")
    roh = json.loads(z["roh_json"])
    assert (roh["Profit (orig.)"], roh["Currency"]) == ("144.24", "USD")
    assert isinstance(roh["_vorher"], list)
    assert z["name_roh"] == "IF7  [7001]"
    zweiter = import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx", anreichern=True)
    assert (zweiter.zeilen_neu, zweiter.zeilen_angereichert) == (0, 0)


def test_ohne_anreichern_bleibt_die_liste(migrated_db):
    import_optionapp_file(migrated_db, FIXTURES / "oa_v3_alt_7001.xlsx")
    import_optionapp_file(migrated_db, FIXTURES / "oa_v3.xlsx")
    assert isinstance(json.loads(_zeile(migrated_db, "7001")["roh_json"]), list)
