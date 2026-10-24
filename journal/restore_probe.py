# ruff: noqa: E501
"""Restore-Probe (AP-17g, Review M08): Eine Sicherung wird in einer **temporären** Kopie wiederhergestellt und geprüft.

Geprüft werden Integrität (``PRAGMA integrity_check``, ``PRAGMA foreign_key_check``), die Migration auf den neuesten Stand
(``alembic upgrade head``, wie beim Deploy) und die Zahl der Zeilen in den wichtigsten Tabellen; mit ``mit_rebuild`` zusätzlich
ein vollständiger Neuaufbau der abgeleiteten Tabellen. Die Sicherung selbst und ``journal.db`` werden nie verändert.

Aufruf: ``python -m journal restore-probe <sicherung.db> [--rebuild]``; Rückgabewert 0 nur, wenn alles in Ordnung ist.
"""
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

WICHTIGE_TABELLEN = ("executions", "instruments", "legs", "structures", "chains", "import_runs", "flex_nav_tage")


def _zaehlen(verbindung: sqlite3.Connection) -> dict:
    vorhanden = {z[0] for z in verbindung.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    return {t: verbindung.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in WICHTIGE_TABELLEN if t in vorhanden}


def restore_probe(sicherung: str | pathlib.Path, *, mit_rebuild: bool = False,
                  projekt: str | pathlib.Path | None = None) -> dict:
    """Stellt ``sicherung`` in einer temporären Datei her und prüft sie. Rückgabe: Bericht mit ``ok`` und den Einzelbefunden."""
    quelle = pathlib.Path(sicherung)
    if not quelle.is_file():
        raise FileNotFoundError(f"Sicherung nicht gefunden: {quelle}")
    projekt = pathlib.Path(projekt) if projekt else pathlib.Path(__file__).resolve().parents[1]
    bericht: dict = {"datei": quelle.name, "groesse_mb": round(quelle.stat().st_size / 1e6, 1), "befunde": []}

    with tempfile.TemporaryDirectory(prefix="restore-probe-") as ordner:
        kopie = pathlib.Path(ordner) / "probe.db"
        shutil.copy2(quelle, kopie)

        try:
            verbindung = sqlite3.connect(kopie)
            try:
                integritaet = [z[0] for z in verbindung.execute("PRAGMA integrity_check")]
                fremdschluessel = verbindung.execute("PRAGMA foreign_key_check").fetchall()
                bericht["zeilen_vorher"] = _zaehlen(verbindung)
            finally:
                verbindung.close()
        except sqlite3.DatabaseError as fehler:
            bericht.update(ok=False)
            bericht["befunde"].append(f"Datei nicht lesbar als SQLite-Datenbank: {fehler}")
            return bericht
        bericht["integritaet"] = integritaet
        if integritaet != ["ok"]:
            bericht["befunde"].append(f"integrity_check: {integritaet[:3]}")
        if fremdschluessel:
            bericht["befunde"].append(f"foreign_key_check: {len(fremdschluessel)} Verstöße")

        lauf = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=projekt, capture_output=True,
                              text=True, env={**os.environ, "JOURNAL_DB": str(kopie)})
        bericht["migration_ok"] = lauf.returncode == 0
        if lauf.returncode != 0:
            bericht["befunde"].append(f"alembic upgrade head fehlgeschlagen: {(lauf.stderr or lauf.stdout)[-300:]}")

        if mit_rebuild and lauf.returncode == 0 and integritaet == ["ok"]:
            from journal.rebuild import rebuild
            try:
                ergebnis = rebuild(kopie)
                bericht["rebuild"] = f"{ergebnis.chains} Ketten, {ergebnis.legs} Legs, {ergebnis.structures} Strukturen"
            except Exception as fehler:  # noqa: BLE001 — jeder Fehler ist ein Befund der Probe
                bericht["befunde"].append(f"Rebuild fehlgeschlagen: {type(fehler).__name__}: {fehler}")

        if lauf.returncode == 0:
            verbindung = sqlite3.connect(kopie)
            try:
                bericht["zeilen_nachher"] = _zaehlen(verbindung)
            finally:
                verbindung.close()
            vorher, nachher = bericht["zeilen_vorher"], bericht["zeilen_nachher"]
            for tabelle, n in vorher.items():
                if nachher.get(tabelle, 0) < n:
                    bericht["befunde"].append(f"{tabelle}: nach der Migration weniger Zeilen ({n} -> {nachher.get(tabelle, 0)})")

    bericht["ok"] = not bericht["befunde"]
    return bericht


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Restore-Probe: Sicherung in temporärer Kopie prüfen")
    parser.add_argument("sicherung", type=pathlib.Path)
    parser.add_argument("--rebuild", action="store_true", help="zusätzlich vollständiger Neuaufbau (dauert länger)")
    a = parser.parse_args(argv)
    try:
        bericht = restore_probe(a.sicherung, mit_rebuild=a.rebuild)
    except FileNotFoundError as fehler:
        print(f"Restore-Probe: {fehler}", file=sys.stderr)
        return 1
    print(f"Restore-Probe {bericht['datei']} ({bericht['groesse_mb']} MB): {'OK' if bericht['ok'] else 'FEHLER'}")
    print(f"  Integrität: {bericht.get('integritaet')}, Migration: {'ok' if bericht.get('migration_ok') else 'FEHLER'}")
    for tabelle, n in (bericht.get("zeilen_nachher") or bericht.get("zeilen_vorher") or {}).items():
        print(f"  {tabelle}: {n}")
    if bericht.get("rebuild"):
        print(f"  Rebuild: {bericht['rebuild']}")
    for befund in bericht["befunde"]:
        print(f"  BEFUND: {befund}", file=sys.stderr)
    return 0 if bericht["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
