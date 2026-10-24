# ruff: noqa: E501
"""Restore-Probe (AP-17g, M08): Sicherung wird in temporärer Kopie geprüft, migriert und optional neu aufgebaut."""
import pathlib
import sqlite3

import pytest
from fixtures_rebuild import befuelle

from journal.backup import create_backup
from journal.rebuild import rebuild
from journal.restore_probe import main, restore_probe


@pytest.fixture
def sicherung(migrated_db, tmp_path):
    befuelle(migrated_db)
    rebuild(migrated_db)
    return create_backup(migrated_db, tmp_path / "sicherung.db")


def test_gesunde_sicherung_besteht_und_bleibt_unveraendert(sicherung):
    vorher = pathlib.Path(sicherung).read_bytes()
    b = restore_probe(sicherung)
    assert b["ok"] is True and b["integritaet"] == ["ok"] and b["migration_ok"] is True
    assert b["zeilen_nachher"]["executions"] > 0 and b["zeilen_nachher"]["chains"] > 0
    assert pathlib.Path(sicherung).read_bytes() == vorher               # die Sicherung wird nie verändert


def test_mit_rebuild_wird_der_neuaufbau_mitgeprueft(sicherung):
    b = restore_probe(sicherung, mit_rebuild=True)
    assert b["ok"] is True and "Ketten" in b["rebuild"]


def test_kaputte_datei_ist_ein_befund_kein_absturz(tmp_path):
    kaputt = tmp_path / "kaputt.db"
    kaputt.write_bytes(b"das ist keine sqlite datenbank" * 50)
    b = restore_probe(kaputt)
    assert b["ok"] is False and b["befunde"]


def test_abgeschnittene_sicherung_faellt_auf(sicherung, tmp_path):
    daten = pathlib.Path(sicherung).read_bytes()
    abgeschnitten = tmp_path / "abgeschnitten.db"
    abgeschnitten.write_bytes(daten[: len(daten) // 2])
    b = restore_probe(abgeschnitten)
    assert b["ok"] is False


def test_fehlende_datei_wirft_und_cli_meldet_fehler(tmp_path, capsys):
    with pytest.raises(FileNotFoundError):
        restore_probe(tmp_path / "gibt-es-nicht.db")
    assert main([str(tmp_path / "gibt-es-nicht.db")]) == 1


def test_cli_ausgabe_und_rueckgabewert(sicherung, capsys):
    assert main([str(sicherung)]) == 0
    ausgabe = capsys.readouterr().out
    assert "OK" in ausgabe and "executions:" in ausgabe


def test_alte_sicherung_wird_migriert(tmp_path):
    """Eine Sicherung mit älterem Schema (nur Tabelle alembic_version auf alter Revision fehlt hier bewusst): leere Datenbank ohne
    Schema wird durch die Migration vollständig angelegt, nichts geht verloren."""
    leer = tmp_path / "leer.db"
    sqlite3.connect(leer).close()
    b = restore_probe(leer)
    assert b["migration_ok"] is True and b["ok"] is True
    assert b["zeilen_nachher"]["executions"] == 0
