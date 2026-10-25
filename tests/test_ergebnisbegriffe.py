# ruff: noqa: E501
"""M06 (erste Stufe): einheitliche Ergebnisbegriffe und ausdrücklicher Bewertungsstichtag in allen Ergebnisansichten."""
import pathlib

SRC = pathlib.Path(__file__).resolve().parents[1] / "ui" / "src"


def test_baustein_steht_in_allen_ergebnisansichten():
    for seite in ("Dashboard", "Positionen", "Titel", "Strategien"):
        text = (SRC / f"{seite}.tsx").read_text(encoding="utf-8")
        assert "<ErgebnisBegriffe />" in text, seite


def test_baustein_definiert_die_begriffe_und_zeigt_den_fehlenden_historischen_wert():
    text = (SRC / "ErgebnisBegriffe.tsx").read_text(encoding="utf-8")
    for begriff in ("Realisiert:", "Teilrealisiert:", "Unrealisiert:", "Gesamt:", "Bewertungsstichtag"):
        assert begriff in text, begriff
    # Liegt der gewählte Endtag vor dem Stichtag, steht das ausdrücklich da (kein stilles Weglassen)
    assert "keine historische Bewertung" in text and "zeitraum.bis < stichtag" in text


def test_dist_enthaelt_den_baustein():
    dist = SRC.parent / "dist" / "assets"
    if not dist.is_dir():
        return
    assert any("Bewertungsstichtag" in p.read_text(encoding="utf-8", errors="ignore") for p in dist.glob("*.js"))
