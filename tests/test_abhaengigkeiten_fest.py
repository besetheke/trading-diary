# ruff: noqa: E501
"""AP-17g (Review M08): die festgeschriebenen Versionen decken die Abhängigkeiten aus pyproject.toml ab."""
import pathlib
import re

WURZEL = pathlib.Path(__file__).resolve().parents[1]


def _namen(text: str) -> set[str]:
    return {re.split(r"[<>=!~\[ ]", z.strip(), maxsplit=1)[0].lower().replace("_", "-")
            for z in text.splitlines() if z.strip() and not z.strip().startswith("#")}


def test_lock_deckt_pyproject_ab_und_ist_exakt_festgelegt():
    lock = (WURZEL / "requirements-lock.txt").read_text(encoding="utf-8")
    zeilen = [z for z in lock.splitlines() if z.strip() and not z.startswith("#")]
    assert all("==" in z for z in zeilen), "jede Zeile mit exakter Version"
    projekt = (WURZEL / "pyproject.toml").read_text(encoding="utf-8")
    deklariert = {m.lower() for m in re.findall(r'^\s*"([A-Za-z0-9_.\-]+)[<>=]', projekt, re.M)}
    assert deklariert and deklariert <= _namen(lock)


def test_setup_und_deploy_nutzen_den_festen_stand():
    assert "requirements-lock.txt" in (WURZEL / "setup.cmd").read_text(encoding="utf-8")
    assert "requirements-lock.txt" in (WURZEL / "werkzeuge/server/Deploy.ps1").read_text(encoding="utf-8")
