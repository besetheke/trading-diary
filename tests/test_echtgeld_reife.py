# ruff: noqa: E501
"""Echtgeld-Reife (Nutzer 21.10.2026): Kriterien aus dem Roller-Status, von Hand gerechnet.

Status-Beispiel (heute 22.10.2026):
  Datenquelle live seit 2026-10-15 → 7 Tage (≥ 5)                              → ok
  Statistik: Strategie A 12 geschlossene Ketten mit 6 Rolls, B 20 mit 3 Rolls   → 32 geschlossen (≥ 30) → ok
  Rolls: 6 + 3 = 9 aus Statistik, dazu offene Ketten mit 1 und 0 Rolls          → 10 (≥ 10)            → ok
  Offene Ketten mit Status „pruefen“: 0                                          → ok
  Meldungen „Bestand ohne Kette“: 0                                              → ok
"""
from datetime import date

from api.echtgeld_reife import MANUELL, bewerte

HEUTE = date(2026, 10, 22)


def status(**kw):
    s = {
        "daten": {"art": "live", "seit": "2026-10-15T09:00:00"},
        "statistik": {"A": {"n": 12, "rolls_summe": 6}, "B": {"n": 20, "rolls_summe": 3}},
        "ketten": [{"rolls": 1, "status": "offen"}, {"rolls": 0, "status": "offen"}],
        "meldungen": ["Kette geschlossen"],
    }
    s.update(kw)
    return s


def ok(erg):
    return {k["id"]: k["ok"] for k in erg["kriterien"]}


def test_alles_erfuellt():
    erg = bewerte(status(), HEUTE)
    assert ok(erg) == {"live_daten": True, "rolls": True, "ketten": True, "angehalten": True, "waisen": True}
    assert erg["automatisch_erfuellt"] is True
    assert {k["id"]: k["ist"] for k in erg["kriterien"]}["rolls"] == 10
    assert {k["id"]: k["ist"] for k in erg["kriterien"]}["ketten"] == 32


def test_grenzen_eins_darunter():
    erg = bewerte(status(daten={"art": "live", "seit": "2026-10-18T09:00:00"}), HEUTE)      # 4 Tage
    assert ok(erg)["live_daten"] is False
    erg = bewerte(status(ketten=[{"rolls": 0, "status": "offen"}]), HEUTE)                   # 9 Rolls
    assert ok(erg)["rolls"] is False and erg["automatisch_erfuellt"] is False
    erg = bewerte(status(statistik={"A": {"n": 29, "rolls_summe": 9}}), HEUTE)               # 29 Ketten
    assert ok(erg)["ketten"] is False


def test_verzoegerte_daten_und_probleme():
    erg = bewerte(status(daten={"art": "verzoegert", "seit": "2026-10-01T09:00:00"}), HEUTE)
    assert ok(erg)["live_daten"] is False
    erg = bewerte(status(ketten=[{"rolls": 5, "status": "pruefen"}], meldungen=["2 Optionsposition(en) ... Bestand ohne Kette"]), HEUTE)
    assert ok(erg)["angehalten"] is False and ok(erg)["waisen"] is False


def test_roller_nicht_erreichbar_und_manuelle_liste():
    erg = bewerte(None, HEUTE)
    assert erg["erreichbar"] is False and erg["kriterien"] == [] and erg["automatisch_erfuellt"] is False
    assert [m["id"] for m in erg["manuell"]] == [k for k, _ in MANUELL]


def test_status_mit_strategie_schluessel():
    assert ok(bewerte({"strategie": status()}, HEUTE))["live_daten"] is True


def test_0dte_ketten_zaehlen_nicht(monkeypatch=None):
    """Tagesstrategien (0DTE) zählen weder bei Rolls noch bei geschlossenen Ketten (23.10.2026):
    dieselben 32 Ketten und 10 Rolls wie oben, dazu 100 geschlossene 0DTE-Ketten und eine offene 0DTE-Kette mit 5 Rolls
    ändern nichts; eine angehaltene 0DTE-Kette zählt weiter als Problem."""
    stat = status()
    stat["statistik"]["SPX: BPS D10 W25 0DTE"] = {"n": 100, "rolls_summe": 40}
    stat["ketten"] = stat["ketten"] + [{"strategie": "RUT: BCS D10 W10 0DTE", "rolls": 5, "status": "offen"}]
    erg = bewerte(stat, HEUTE)
    ist = {k["id"]: k["ist"] for k in erg["kriterien"]}
    assert (ist["ketten"], ist["rolls"]) == (32, 10)
    assert ok(erg)["angehalten"] is True
    stat["ketten"] = stat["ketten"] + [{"strategie": "SPX: BPS D10 W25 0DTE", "rolls": 0, "status": "pruefen"}]
    assert ok(bewerte(stat, HEUTE))["angehalten"] is False
