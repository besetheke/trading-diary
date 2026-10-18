# ruff: noqa: E501
"""Die Oberfläche sendet bei Schreibaufrufen den Header der Station (AP-17c).

Nach der Absicherung der Trading-Befehle antwortet die API ohne ``X-Trading-Station: 1`` mit 403 — auch dann, wenn die
Oberfläche nach der Änderung nicht neu gebaut wurde (18.10.2026: „HTTP 403 — Befehl nur aus der Station“ beim Start von
Momentum Lab, weil ``ui/dist`` noch der alte Stand war). Deshalb prüft ein Test Quelle UND gebauten Stand.
"""
import pathlib

WURZEL = pathlib.Path(__file__).resolve().parents[1]


def test_quelle_setzt_den_header():
    assert "X-Trading-Station" in (WURZEL / "ui/src/api.ts").read_text(encoding="utf-8")


def test_gebauter_stand_enthaelt_den_header():
    assets = WURZEL / "ui" / "dist" / "assets"
    skripte = sorted(assets.glob("index-*.js")) if assets.is_dir() else []
    if not skripte:
        return  # nicht gebaut (z. B. reine Testumgebung): der Build ist Sache von Deploy.ps1
    assert any("X-Trading-Station" in s.read_text(encoding="utf-8", errors="ignore") for s in skripte), (
        "ui/dist ist veraltet: `npm run build` in ui/ ausführen"
    )
