# ruff: noqa: E501
"""Paper-Journal: eigene Datenbank, eigener Port, keine Zugangsdaten im Repo (24.10.2026)."""
import pathlib
import re

ORDNER = pathlib.Path(__file__).resolve().parents[1] / "werkzeuge" / "paper"


def lies(name: str) -> str:
    return (ORDNER / name).read_text(encoding="utf-8")


def code(name: str) -> str:
    """Nur ausführbare Zeilen (ohne # und rem): Kommentare dürfen das echte Journal nennen."""
    return chr(10).join(z for z in lies(name).splitlines() if not z.lstrip().startswith(("#", "rem ")))


def test_alle_skripte_nutzen_die_paper_datenbank_und_nie_journal_db():
    for name in ("Einrichten-Paper.ps1", "Schnellstart-Paper.ps1", "nachtlauf-paper.cmd"):
        text = code(name)
        assert "journal-paper.db" in text, name
        assert not re.search(r"(?<![\w-])journal\.db", text.replace("journal-paper.db", "")), name


def test_paper_server_laeuft_auf_8001_und_nicht_auf_8000():
    text = code("Schnellstart-Paper.ps1")
    assert "$port = 8001" in text and "8000" not in text.replace("8600", "")


def test_nachtlauf_nutzt_eigene_zugangsdaten_und_gibt_sie_nicht_aus():
    text = lies("nachtlauf-paper.cmd")
    assert "flex-paper.cmd" in text and "FLEX_TOKEN" not in text and "echo %FLEX" not in text
    assert "JOURNAL_DB=%STAMM%\\journal-paper.db" in text


def test_vorlage_enthaelt_keine_zugangsdaten():
    text = lies("Einrichten-Paper.ps1")
    assert 'set "FLEX_TOKEN="' in text and 'set "FLEX_QUERY_ID="' in text      # leer
    assert not re.search(r'FLEX_(TOKEN|QUERY_ID)="[^"' + chr(10) + r']', text)       # nach dem Anführungszeichen folgt nichts


def test_readme_nennt_die_einzelkonto_grenze_und_dass_der_nutzer_das_flex_konto_anlegt():
    text = lies("README-Paper.md")
    assert "eigenen Datenbank" in text and "Einzelkonto-Grenze" in text and "Das kann nur der Nutzer tun" in text


def test_projektverzeichnis_ist_die_repo_wurzel_drei_ebenen_ueber_dem_skript():
    """Die Skripte liegen in werkzeuge\paper: bis zur Wurzel sind es drei Ebenen (Fehler beim ersten Lauf am 24.10.2026)."""
    for name in ("Einrichten-Paper.ps1", "Schnellstart-Paper.ps1"):
        assert "Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))" in code(name), name
    assert (ORDNER.parents[1] / ".venv").exists() or (ORDNER.parents[1] / "pyproject.toml").exists()


def test_paper_server_bekommt_die_oberflaeche_aus_dem_projekt():
    """Der Bauordner der Oberflaeche haengt an der Datenbank (OF-45); die Paper-Datenbank liegt ausserhalb des Projekts."""
    assert "$env:JOURNAL_UI" in code("Schnellstart-Paper.ps1")
    app_text = (ORDNER.parents[1] / "api" / "app.py").read_text(encoding="utf-8")
    assert 'ui_verzeichnis=os.environ.get("JOURNAL_UI") or None' in app_text
