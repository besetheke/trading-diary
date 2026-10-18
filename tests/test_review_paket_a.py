# ruff: noqa: E501
"""AP-17 Teilpaket A (Review R08–R12), von Hand gerechnet.

R08  Roller-Kette: 100 USD und 50 EUR dürfen nicht zu 150 zusammenlaufen; USD bleibt USD.
R09  Die Hülle der Roll-Degradation reicht die Faktoren der Kapitalmaßnahmen an die Rechnung weiter.
R10  Ein Problem nur 2026 blockiert nur 2026; ein Problem ohne bekanntes Jahr blockiert jedes Jahr.
R11  Jeder API-Weg, den die Oberfläche aufruft, steht im Vite-Proxy.
"""
import pathlib
import re
from datetime import date
from decimal import Decimal as D

import pytest
from fixtures_rebuild import befuelle

pytest.importorskip("fastapi")

from analytics import degradation  # noqa: E402
from api.app import _fasse_ketten_zusammen  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402

WURZEL = pathlib.Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------------------------ R08
def _info(chain_id, bisher, waehrung):
    return {"chain_id": chain_id, "anzahl_rolls": 1, "strategie": "S", "eroeffnet_am": "2026-01-01T10:00:00",
            "realisiert_bisher": bisher, "waehrung": waehrung, "praemie_offen_eur": None,
            "praemie_aktuell_eur": None, "unrealisiert_eur": None}


def test_r08_gleiche_waehrung_wird_summiert_und_benannt():
    z = _fasse_ketten_zusammen([_info(1, "100", "USD"), _info(2, "50", "USD")])
    assert D(z["realisiert_bisher"]) == D("150") and z["waehrung"] == "USD"


def test_r08_verschiedene_waehrungen_werden_nicht_addiert():
    z = _fasse_ketten_zusammen([_info(1, "100", "USD"), _info(2, "50", "EUR")])
    assert z["realisiert_bisher"] is None and z["waehrung"] is None


# ------------------------------------------------------------------------------------------------ R09
def test_r09_degradations_huelle_liest_die_faktoren(migrated_db, monkeypatch):
    befuelle(migrated_db)
    rebuild(migrated_db)
    gesehen = {}

    def spaeher(ketten, strukturen, glieder, legs, *args, **kw):
        gesehen["legs"] = list(legs)
        raise RuntimeError("Abbruch nach dem Lesen")

    monkeypatch.setattr(degradation, "degradations_auswertung", spaeher)
    with pytest.raises(RuntimeError):
        degradation.degradations_bericht(migrated_db)
    assert gesehen["legs"], "die Testwelt muss Legs der Kettensicht haben"
    assert all("open_faktor" in leg and "close_faktor" in leg for leg in gesehen["legs"])


# ------------------------------------------------------------------------------------------------ R10
from test_steuer_zufluss import PUT100, cash, ex, inst, lauf, leg  # noqa: E402


def _etf_2026():
    etf = inst(14, "STK", symbol="SPY", underlying="SPY")
    etf["unterkategorie"] = "ETF"
    return ([leg(1, 14, "A", "B", "10")],
            [ex("A", 14, "BUY", 10, "100", "1", date(2026, 1, 5), waehrung="EUR"),
             ex("B", 14, "SELL", 10, "110", "1", date(2026, 2, 5), waehrung="EUR")], [etf])


def test_r10_etf_fall_2026_blockiert_2025_nicht():
    legs, execs, instr = _etf_2026()
    dividende = cash("Dividends", "10", "1", date(2025, 3, 3),
                     beschr="WDC(US1) CASH DIVIDEND USD 0.10 PER SHARE (Ordinary Dividend)")
    dividende26 = cash("Dividends", "10", "1", date(2026, 3, 3),
                       beschr="WDC(US1) CASH DIVIDEND USD 0.10 PER SHARE (Ordinary Dividend)")
    j = lauf(legs, execs, instr, [dividende, dividende26]).jahre()
    assert j[2025]["deklarationsstatus"]["status"] == "deklarierbar_mit_erlaeuterung"
    assert j[2025]["deklarationsstatus"]["gruende"] == []
    assert j[2026]["deklarationsstatus"]["status"] == "nicht_deklarationsfaehig"


def test_r10_datenluecke_nur_2026_blockiert_nur_2026():
    kurzer = ex("O", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR")
    e1 = ex("O2", 1, "SELL", 1, "3.00", "1", date(2026, 3, 3), waehrung="EUR")
    e2 = ex("C2", 1, "BUY", 1, "1.00", None, date(2026, 4, 3), waehrung="EUR")   # Kurs fehlt, 2026
    j = lauf([leg(1, 1, "O", None, "-1"), leg(2, 1, "O2", "C2", "-1")], [kurzer, e1, e2], [PUT100]).jahre()
    assert j[2025]["deklarationsstatus"]["gruende"] == []
    assert any("Datenlücken" in g for g in j[2026]["deklarationsstatus"]["gruende"])


def test_r10_luecke_ohne_bekanntes_jahr_blockiert_jedes_jahr():
    e = ex("O", 1, "SELL", 1, "3.00", "1", date(2025, 3, 3), waehrung="EUR")
    erg = lauf([leg(1, 1, "O", "FEHLT", "-1")], [e], [PUT100])      # Schließung fehlt: Jahr unbekannt
    assert erg.datenluecken[0].jahr is None
    assert any("Datenlücken" in g for g in erg.jahre()[2025]["deklarationsstatus"]["gruende"])


# ------------------------------------------------------------------------------------------------ R11
def test_r11_jeder_api_weg_der_oberflaeche_steht_im_vite_proxy():
    api = (WURZEL / "ui/src/api.ts").read_text(encoding="utf-8")
    wege = set(re.findall(r"""(?:hole|schicke)\(\s*(?:'(?:GET|POST|PUT|DELETE)',\s*)?[`'"](/[a-z\-]+)""", api))
    wege |= set(re.findall(r"""fetch\(\s*[`'"](/[a-z\-]+)""", api))
    steuer = (WURZEL / "ui/src/Steuer.tsx").read_text(encoding="utf-8")
    wege |= set(re.findall(r"""href=\{?[`'"](/steuer-csv)""", steuer))        # Download-Link
    proxy = set(re.findall(r"""'(/[a-z\-\.]+)':""", (WURZEL / "ui/vite.config.ts").read_text(encoding="utf-8")))
    assert wege, "es müssen API-Wege gefunden werden"
    assert sorted(w for w in wege if w not in proxy) == []
