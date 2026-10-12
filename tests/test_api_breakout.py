"""Abnahmetest für AP-14c: `GET /breakout-stand` — die Station zeigt den Stand der BO
Research Suite, nur lesend.

Die BO Research Suite ist ein Forschungsprojekt mit eigener Governance (versiegelte
Validation-/Holdout-Stichproben, eine Discovery-Läufe je Hypothese). Die Station
liest nur: `PROJECT_STATE.md` (Ziel, Stand), das Hypothesenregister (Blatt
„Experiment Backlog" der Excel-Datei) und die Zusammenfassung der Discovery-
Ergebnisse (`data/results/hyp*_discovery_v1.json`: Status, Sitzungen, Kosten 0,5,
Bootstrap, Gates). Nie Validation oder Holdout, nie einen Lauf anstoßen.

Erfundener Ordner (tmp_path):
  PROJECT_STATE.md  „Updated 2026-09-20." und Abschnitt Objective „Ziel A."
  Backlog           HYP-001 (Discovery failed - retired, Entscheidung „zu"),
                    HYP-003 (Blocked), zwei leere Zeilen darunter ignoriert
  Ergebnis HYP-001  retired, 504 Sitzungen, Kosten 0.5: gesamt 133.47, Mittel
                    0.2648; Bootstrap p05 −0.3247; Gate primary nicht bestanden,
                    halves bestanden
  Ergebnis HYP-002  älteres Format: all_gates_pass false, gate_outcomes {a: true,
                    b: false}, keine Kosten → Status „Gates nicht bestanden", Werte leer
Erwartung: gefunden true, stand 2026-09-20, ziel „Ziel A.", 2 Hypothesen in
Reihenfolge, 2 Ergebnisse (nach ID: HYP-001 mit den Werten oben und gates
{primary: false, halves: true}, dann HYP-002 im älteren Format).
Ohne Ordner: gefunden false, leere Listen.
"""

import json

import pytest
from openpyxl import Workbook

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api.app import erzeuge_app  # noqa: E402


def _bo(pfad):
    (pfad / "data" / "results").mkdir(parents=True)
    (pfad / "PROJECT_STATE.md").write_text(
        "# Breakout Research Project State\n\n> Single source. Updated 2026-09-20.\n\n"
        "## Objective\n\nZiel A.\n\n## Evidence\n\nanderes\n", encoding="utf-8")
    wb = Workbook()
    ws = wb.active
    ws.title = "Experiment Backlog"
    ws.append(["EXPERIMENT BACKLOG"])
    ws.append([])
    ws.append(["ID", "Question / hypothesis", "Universe", "Stage", "Priority", "Status",
               "Evidence / result", "Decision"])
    ws.append(["HYP-001", "Frage 1", "SPX", "Event study", "High",
               "Discovery failed - retired", "e", "zu"])
    ws.append(["HYP-003", "Frage 3", "ES", "Event study", "Later", "Blocked", None, None])
    ws.append([None] * 8)
    ws.append([None] * 8)
    wb.save(pfad / "breakout_research_project_command_center_MVP_v2.xlsx")
    (pfad / "data" / "results" / "hyp001_discovery_v1.json").write_text(json.dumps({
        "hypothesis_id": "HYP-001_spx_orb_low_normalized_range_v1",
        "sample_role": "discovery", "session_count": 504, "promotion_status": "retired",
        "cost_reports": {"0.5": {"total_points": 133.47, "mean_points": 0.2648}},
        "bootstrap": {"primary_p05": -0.3247},
        "acceptance_gates": {"primary": {"passed": False}, "halves": {"passed": True},
                             "tails": {"252": {"primary_positive": True}}},
        "records": [{"x": 1}] * 3,
    }), encoding="utf-8")
    (pfad / "data" / "results" / "hyp002_discovery_v1.json").write_text(json.dumps({
        "hypothesis_id": "HYP-002_x", "sample_role": "discovery", "all_gates_pass": False,
        "gate_outcomes": {"a": True, "b": False}}), encoding="utf-8")
    # Validation-Artefakte werden nie gelesen — auch wenn eine Datei so heißt.
    (pfad / "data" / "results" / "hyp001_validation_v1.json").write_text(
        json.dumps({"hypothesis_id": "GEHEIM", "sample_role": "validation"}), encoding="utf-8")


def test_stand(tmp_path, migrated_db):
    _bo(tmp_path)
    d = TestClient(erzeuge_app(migrated_db, bo_ordner=tmp_path)).get("/breakout-stand").json()
    assert (d["gefunden"], d["stand"], d["ziel"]) == (True, "2026-09-20", "Ziel A.")
    assert [(h["id"], h["status"], h["entscheidung"]) for h in d["hypothesen"]] == [
        ("HYP-001", "Discovery failed - retired", "zu"), ("HYP-003", "Blocked", None)]
    e, alt = d["ergebnisse"]
    assert (alt["id"], alt["status"], alt["gates"], alt["gesamt_punkte_05"]) == (
        "HYP-002_x", "Gates nicht bestanden", {"a": True, "b": False}, None)
    assert (e["id"], e["status"], e["sitzungen"]) == (
        "HYP-001_spx_orb_low_normalized_range_v1", "retired", 504)
    assert (e["gesamt_punkte_05"], e["mittel_punkte_05"], e["bootstrap_p05"]) == (
        133.47, 0.2648, -0.3247)
    assert e["gates"] == {"primary": False, "halves": True}


def test_validation_wird_nie_gelesen(tmp_path, migrated_db):
    _bo(tmp_path)
    d = TestClient(erzeuge_app(migrated_db, bo_ordner=tmp_path)).get("/breakout-stand").json()
    assert "GEHEIM" not in json.dumps(d)


def test_ohne_ordner(tmp_path, migrated_db):
    d = TestClient(erzeuge_app(migrated_db, bo_ordner=tmp_path / "gibt-es-nicht")
                   ).get("/breakout-stand").json()
    assert d["gefunden"] is False and d["hypothesen"] == [] and d["ergebnisse"] == []


def test_ohne_konfiguration(migrated_db):
    d = TestClient(erzeuge_app(migrated_db)).get("/breakout-stand").json()
    assert d["gefunden"] is False
