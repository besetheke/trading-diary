# ruff: noqa: E501
"""Kettenkarten der Station (Nutzerwunsch 25.10.2026): die Bausteine stehen im Quelltext, hängen an den Rollparametern des Roller-Status
und sind in die Strategie-Karte der Station eingebunden. Rechenlogik gibt es dort nicht; die Werte kommen vom Roller."""
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "ui" / "src"


def test_vier_bilder_und_einbindung():
    karte = (SRC / "Kettenkarte.tsx").read_text(encoding="utf-8")
    for baustein in ("StrikeLeiter", "RollRegel", "Kostenbremse", "Kettenverlauf"):
        assert f"export function {baustein}" in karte, baustein
    station = (SRC / "Station.tsx").read_text(encoding="utf-8")
    assert "<Kettenkarten strategie={s} />" in station


def test_rollparameter_kommen_aus_dem_status():
    api = (SRC / "api.ts").read_text(encoding="utf-8")
    for feld in ("staffel: [number, number][]", "gap_aufschlag", "max_kettenverlust_anteil", "ziel_delta", "max_verschiebung"):
        assert feld in api, feld
    assert "regeln?: RollerRegeln" in api


def test_kostenbremse_grenze_ist_anteil_mal_breite():
    # Grenze der Kostenbremse = Anteil x Breite (Punkte), wie im Roller (max_kettenverlust_anteil)
    karte = (SRC / "Kettenkarte.tsx").read_text(encoding="utf-8")
    assert "regeln.max_kettenverlust_anteil * regeln.breite" in karte
