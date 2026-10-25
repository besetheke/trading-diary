# ruff: noqa: E501
"""Datenqualität als Arbeitsliste (AP-17g, M04): Betriebsstatus und Punkte, von Hand gerechnet.

Heute = 25.10.2026.
  Abruf-Alter:  letzter erfolgreicher Abruf 22.10. → 3 Tage (≥ 2): Warnung; 24.10. → 1 Tag: keine Warnung
  Rebuild:      Import ok 25.10. 05:30, Rebuild ok 25.10. 04:00 → Neuaufbau älter als der Import: Warnung; Rebuild ok 25.10. 05:40: keine
  Fehlschlag:   Rebuild fehler 05:35 nach Rebuild ok 04:00 → Fehler; ein späterer Erfolg 05:50 löst den Punkt auf
  Teilerfolg:   Rebuild teilweise (verwaiste Overrides) → Warnung
"""
from datetime import date, datetime

import pytest
from fixtures_rebuild import befuelle

from journal import cli
from journal.betrieb import protokolliere
from journal.datenqualitaet import arbeitsliste
from journal.rebuild import rebuild

HEUTE = date(2026, 10, 25)


def punkte(db, **kw):
    return {p["id"]: p for p in arbeitsliste(db, HEUTE, mit_abgleich=False, **kw)["punkte"]}


def test_leere_datenbank_hat_nur_hinweise(migrated_db):
    erg = arbeitsliste(migrated_db, HEUTE, mit_abgleich=False)
    assert erg["status"] == "ok" and {p["schwere"] for p in erg["punkte"]} <= {"hinweis"}


def test_fehlschlag_wird_sichtbar_und_durch_spaeteren_erfolg_aufgeloest(migrated_db):
    protokolliere(migrated_db, "rebuild", "ok", "100 Ketten", datetime(2026, 10, 25, 4, 0))
    protokolliere(migrated_db, "rebuild", "fehler", "Widerspruch in den Overrides", datetime(2026, 10, 25, 5, 35))
    erg = arbeitsliste(migrated_db, HEUTE, mit_abgleich=False)
    p = {x["id"]: x for x in erg["punkte"]}["lauf-rebuild"]
    assert erg["status"] == "fehler" and p["schwere"] == "fehler" and "Widerspruch in den Overrides" in p["titel"]
    assert "journal rebuild" in p["loesung"]
    protokolliere(migrated_db, "rebuild", "ok", "100 Ketten", datetime(2026, 10, 25, 5, 50))
    assert "lauf-rebuild" not in punkte(migrated_db)


def test_teilerfolg_ist_eine_warnung(migrated_db):
    protokolliere(migrated_db, "rebuild", "teilweise", "1 verwaiste Overrides", datetime(2026, 10, 25, 5, 40))
    assert punkte(migrated_db)["lauf-rebuild"]["schwere"] == "warnung"


def test_abruf_alter(migrated_db):
    protokolliere(migrated_db, "abruf", "ok", "x.xml", datetime(2026, 10, 22, 5, 30))
    p = punkte(migrated_db)["abruf-alt"]
    assert p["schwere"] == "warnung" and "3 Tagen" in p["titel"]
    protokolliere(migrated_db, "abruf", "ok", "y.xml", datetime(2026, 10, 24, 5, 30))
    assert "abruf-alt" not in punkte(migrated_db)


def test_neuaufbau_aelter_als_der_import(migrated_db):
    protokolliere(migrated_db, "abruf", "ok", "x.xml", datetime(2026, 10, 25, 5, 30))
    protokolliere(migrated_db, "import", "ok", "x.xml", datetime(2026, 10, 25, 5, 30))
    assert punkte(migrated_db)["rebuild-nie"]["schwere"] == "hinweis"
    protokolliere(migrated_db, "rebuild", "ok", "100 Ketten", datetime(2026, 10, 25, 4, 0))
    assert punkte(migrated_db)["rebuild-alt"]["schwere"] == "warnung"
    protokolliere(migrated_db, "rebuild", "ok", "100 Ketten", datetime(2026, 10, 25, 5, 40))
    assert "rebuild-alt" not in punkte(migrated_db) and "rebuild-nie" not in punkte(migrated_db)


def test_fehlender_wechselkurs_mit_zeitraum(migrated_db):
    befuelle(migrated_db)
    from sqlalchemy import text

    from journal.db import create_db_engine
    with create_db_engine(migrated_db).begin() as v:
        v.execute(text("UPDATE executions SET buchungskurs = NULL WHERE waehrung != 'EUR'"))
        erwartet = v.execute(text("SELECT COUNT(*), MIN(substr(handelszeit,1,10)), MAX(substr(handelszeit,1,10)) FROM executions WHERE buchungskurs IS NULL AND waehrung != 'EUR'")).one()
    if erwartet[0] == 0:
        pytest.skip("Testwelt hat keine Fremdwährung")
    p = punkte(migrated_db)["kurs-fehlt"]
    assert (p["anzahl"], p["von"], p["bis"]) == tuple(erwartet) and p["schwere"] == "fehler"


def test_nicht_strukturierte_legs_und_rollkandidaten_bleiben_getrennt_vom_betrieb(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    erg = arbeitsliste(migrated_db, HEUTE, mit_abgleich=True)
    ids = {p["id"] for p in erg["punkte"]}
    assert not any(i.startswith("lauf-") for i in ids)            # kein Betriebsfehler ohne protokollierten Fehlschlag
    for p in erg["punkte"]:
        assert p["loesung"] or p["schwere"] == "hinweis", p["id"]


def test_ohne_tabelle_wird_die_offene_migration_gemeldet(migrated_db):
    from sqlalchemy import text

    from journal.db import create_db_engine
    with create_db_engine(migrated_db).begin() as v:
        v.execute(text("DROP TABLE betriebslaeufe"))
    p = punkte(migrated_db)
    assert p["schema-veraltet"]["schwere"] == "warnung" and "alembic upgrade head" in p["schema-veraltet"]["loesung"]
    assert protokolliere(migrated_db, "abruf", "ok") is False     # Protokollieren scheitert still


def test_cli_protokolliert_rebuild_und_fehlgeschlagenen_import(migrated_db, tmp_path, capsys):
    befuelle(migrated_db)
    assert cli.main(["rebuild", "--db", str(migrated_db)]) == 0
    assert cli.main(["import", str(tmp_path / "gibt-es-nicht.xml"), "--db", str(migrated_db)]) == 1
    laeufe = arbeitsliste(migrated_db, HEUTE, mit_abgleich=False)["laeufe"]
    assert laeufe["rebuild"]["zuletzt_ok"] is not None and laeufe["rebuild"]["zuletzt"]["ergebnis"] == "ok"
    assert laeufe["import"]["zuletzt"]["ergebnis"] == "fehler" and "gibt-es-nicht.xml" in laeufe["import"]["zuletzt"]["meldung"]
    assert "import-fehler" not in punkte(migrated_db) and punkte(migrated_db)["lauf-import"]["schwere"] == "fehler"


def test_api_liefert_die_arbeitsliste(migrated_db):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app
    protokolliere(migrated_db, "rebuild", "fehler", "kaputt", datetime.now())
    c = TestClient(erzeuge_app(migrated_db, mit_journal=True))
    d = c.get("/datenqualitaet-liste", params={"kurz": "true"}).json()
    assert d["status"] == "fehler" and any(p["id"] == "lauf-rebuild" for p in d["punkte"])
    assert set(d["laeufe"]) == {"abruf", "import", "rebuild"}
