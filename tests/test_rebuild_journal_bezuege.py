# ruff: noqa: E501
"""AP-17d (Review R02): Notizen, Tags und Anhänge überleben einen nachgelieferten Teilfill.

Der Naturschlüssel einer Struktur besteht aus den eröffnenden Ausführungen. Kommt zur Eröffnung ``E1`` die
Ausführung ``E2`` derselben Order hinzu, heißt die Struktur ``E1|E2`` und die Kette ``k:E1|E2``; die alte Kette entfällt.
Erwartung: Journalbezüge wandern auf die fortgeführte Position; ohne eindeutige Fortsetzung bleiben sie stehen und
werden gezählt (nie still verloren).
"""
from datetime import datetime

import pytest
from fixtures_rebuild import _VORGABEN, AUSFUEHRUNGEN, INSTRUMENTE, befuelle
from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.rebuild import _journal_bezuege_fortfuehren, rebuild
from journal.schema import attachments, chains, entity_tags, executions, journal_entries, tags


def _bezuege_anlegen(v, scope_typ, scope_id):
    v.execute(insert(journal_entries).values(
        scope_typ=scope_typ, scope_id=scope_id, text="schlecht getimt", erstellt_am=datetime(2026, 9, 2)))
    tag_id = v.execute(insert(tags).values(name=f"t-{scope_typ}-{scope_id}")).inserted_primary_key[0]
    v.execute(insert(entity_tags).values(tag_id=tag_id, scope_typ=scope_typ, scope_id=scope_id))
    v.execute(insert(attachments).values(
        scope_typ=scope_typ, scope_id=scope_id, dateipfad="x.png", erstellt_am=datetime(2026, 9, 2)))
    return tag_id


def _bezuege(v, scope_typ, scope_id):
    return {
        "notizen": len(v.execute(select(journal_entries).where(
            journal_entries.c.scope_typ == scope_typ, journal_entries.c.scope_id == scope_id)).all()),
        "tags": len(v.execute(select(entity_tags).where(
            entity_tags.c.scope_typ == scope_typ, entity_tags.c.scope_id == scope_id)).all()),
        "anhaenge": len(v.execute(select(attachments).where(
            attachments.c.scope_typ == scope_typ, attachments.c.scope_id == scope_id)).all()),
    }


def test_nachgelieferter_teilfill_haengt_notiz_tag_und_anhang_um(migrated_db):
    dax = [e for e in AUSFUEHRUNGEN if e["exec_id"] in ("E1", "E2")]
    befuelle(migrated_db, ausfuehrungen=dax[:1], instrumente_=[i for i in INSTRUMENTE if i["conid"] in (601, 602)])
    rebuild(migrated_db)
    engine = create_db_engine(migrated_db)
    with engine.begin() as v:
        alt = v.execute(select(chains.c.chain_id).where(
            chains.c.natur_schluessel == "k:E1", chains.c.sicht == "konto")).scalar_one()
        _bezuege_anlegen(v, "chain", str(alt))
        lauf = v.execute(select(executions.c.import_run_id)).scalars().first()
        werte = dict(_VORGABEN) | dax[1] | {"import_run_id": lauf, "symbol": "DAX  260918P18900"}
        v.execute(insert(executions).values(**werte))                      # E2 kommt nach
    ergebnis = rebuild(migrated_db)
    with engine.connect() as v:
        neu = v.execute(select(chains.c.chain_id).where(
            chains.c.natur_schluessel == "k:E1|E2", chains.c.sicht == "konto")).scalar_one()
        assert neu != alt
        assert _bezuege(v, "chain", str(alt)) == {"notizen": 0, "tags": 0, "anhaenge": 0}
        assert _bezuege(v, "chain", str(neu)) == {"notizen": 1, "tags": 1, "anhaenge": 1}
    assert ergebnis.journal_bezuege_umgehaengt >= 1 and ergebnis.journal_bezuege_verwaist == 0


# --- die Zuordnung selbst, ohne Rebuild -------------------------------------------------------------------------
def _ausfuehren(db, scope_typ, entfallen, frische, vorher):
    with create_db_engine(db).begin() as v:
        for sid in vorher:
            _bezuege_anlegen(v, scope_typ, str(sid))
        return _journal_bezuege_fortfuehren(v, scope_typ, entfallen, frische)


def test_eindeutige_fortsetzung_wird_umgehaengt_andere_ketten_bleiben(migrated_db):
    r = _ausfuehren(migrated_db, "chain", {7: "k:E1", 8: "k:Z1"}, {"k:E1|E2": 9}, vorher=[7, 8])
    assert r == (1, 0, 1)                                   # E1 → E1|E2 umgehängt; Z1 hat keinen Nachfolger: verwaist
    with create_db_engine(migrated_db).connect() as v:
        assert _bezuege(v, "chain", "9")["notizen"] == 1
        assert _bezuege(v, "chain", "8")["notizen"] == 1    # verwaist: unverändert, nicht gelöscht
        assert _bezuege(v, "chain", "7")["notizen"] == 0


def test_mehrere_moegliche_fortsetzungen_bleiben_unveraendert_und_werden_gezaehlt(migrated_db):
    r = _ausfuehren(migrated_db, "chain", {7: "k:E1"}, {"k:E1|E2": 9, "k:E1|E3": 10}, vorher=[7])
    assert r == (0, 1, 0)
    with create_db_engine(migrated_db).connect() as v:
        assert _bezuege(v, "chain", "7")["notizen"] == 1


def test_keine_obermenge_keine_fortsetzung(migrated_db):
    assert _ausfuehren(migrated_db, "chain", {7: "k:E1|E2"}, {"k:E1": 9, "k:E3|E4": 10}, vorher=[7]) == (0, 0, 1)


def test_tag_der_schon_an_der_fortsetzung_haengt_wird_nicht_doppelt(migrated_db):
    with create_db_engine(migrated_db).begin() as v:
        tag_id = _bezuege_anlegen(v, "chain", "7")
        v.execute(insert(entity_tags).values(tag_id=tag_id, scope_typ="chain", scope_id="9"))
        assert _journal_bezuege_fortfuehren(v, "chain", {7: "k:E1"}, {"k:E1|E2": 9}) == (1, 0, 0)
        zeilen = v.execute(select(entity_tags).where(entity_tags.c.tag_id == tag_id)).all()
        assert [(z.scope_typ, z.scope_id) for z in zeilen] == [("chain", "9")]


def test_strukturen_werden_wie_ketten_behandelt(migrated_db):
    assert _ausfuehren(migrated_db, "structure", {3: "E1"}, {"E1|E2": 5}, vorher=[3]) == (1, 0, 0)


def test_ohne_bezuege_passiert_nichts(migrated_db):
    with create_db_engine(migrated_db).begin() as v:
        assert _journal_bezuege_fortfuehren(v, "chain", {7: "k:E1"}, {"k:E1|E2": 9}) == (0, 0, 0)


@pytest.mark.parametrize("schluessel", ["k:E1", "E1"])
def test_schluessel_teile(schluessel):
    from journal.rebuild import _schluessel_teile
    assert _schluessel_teile(schluessel) == frozenset({"E1"})
    assert _schluessel_teile("k:E1|E2") == frozenset({"E1", "E2"})
