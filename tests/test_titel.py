"""Abnahmetest für AP-16: Ergebnis je Titel über alle Instrumente.

Geprüft: `analytics/titel.py` und `/titel-auswertung`.

Testwelt (frei erfunden, alle Kurse 1,0 außer wo angegeben, keine Kommission; von Hand gerechnet):

Titel WHL (Wheel, eine Kette mit zwei Strukturen):
  Struktur S1 (Option, geschlossen): Short Put, SELL 1 @ 5,00 (Multiplikator 100) = +500,
    Schließung durch Zuteilung BUY @ 0 = 0                                   → Optionen +500
  Struktur S2 (Aktie, geschlossen): BUY 100 @ 100 = −10.000, SELL 100 @ 110 = +11.000
                                                                             → Aktien +1.000
  Realisiert gesamt 1.500; Optionen 500; Aktien 1.000; nicht aufgeteilt 0.

Titel EKT (nur Aktien, eine Kette): BUY 10 @ 20 = −200, SELL 10 @ 22 = +220    → Aktien +20.

Titel ZZZ (loses Bein ohne Struktur, geschlossen): BUY 5 @ 10 = −50, SELL 5 @ 9 = +45 → Aktien −5.

Titel OFF (offene Aktie): BUY 100 @ 50 (Kurs EUR 0,9);
  IBs Bestand: Marktwert 4.800, fxRateToBase 0,9
  Unrealisiert = (4.800 − 5.000) · 0,9 = −180,00 EUR.  Nicht realisiert.      → Gesamt −180.

Titel KUR (Kursmangel): geschlossene Struktur ohne buchungskurs der Ausführung: zählt nicht,
  steht aber in `kurs_fehlt` (nie still 0).

Summe über alle Titel realisiert: 1.500 + 20 − 5 = 1.515.
"""

from datetime import date, datetime
from decimal import Decimal

from analytics.titel import titel_auswertung

D = Decimal
T0 = datetime(2026, 9, 1, 10, 0)
T1 = datetime(2026, 9, 10, 10, 0)


def _ex(exec_id, conid, side, menge, preis, kurs="1.0", ereignis="trade"):
    return {
        "exec_id": exec_id,
        "conid": conid,
        "side": side,
        "menge": D(menge),
        "preis": D(preis),
        "waehrung": "USD",
        "kommission": None,
        "kommission_waehrung": None,
        "buchungskurs": None if kurs is None else D(kurs),
        "handelszeit": T0 if side == "BUY" else T1,
        "qualitaetsstufe": "A",
        "ereignistyp": ereignis,
        "schlusskurs": None,
    }


def _leg(structure_id, conid, offen, zu, menge):
    return {
        "structure_id": structure_id,
        "conid": conid,
        "open_exec_id": offen,
        "close_exec_id": zu,
        "menge": D(menge),
        "open_faktor": D(1),
        "close_faktor": D(1),
        "brutto_pnl": None,
        "kommission_gesamt": None,
    }


def _instr(conid, klasse, underlying, mult="1"):
    return {
        "conid": conid,
        "multiplikator": D(mult),
        "abwicklungsart": None,
        "underlying": underlying,
        "asset_class": klasse,
        "symbol": underlying,
    }


def _welt(von=None, bis=None):
    ausf = [
        _ex("P1", 1, "SELL", 1, "5.00"),
        _ex("P2", 1, "BUY", 1, "0"),  # Put WHL
        _ex("S1", 2, "BUY", 100, "100"),
        _ex("S2", 2, "SELL", 100, "110"),  # Aktie WHL
        _ex("E1", 3, "BUY", 10, "20"),
        _ex("E2", 3, "SELL", 10, "22"),  # EKT
        _ex("Z1", 4, "BUY", 5, "10"),
        _ex("Z2", 4, "SELL", 5, "9"),  # ZZZ lose
        _ex("O1", 5, "BUY", 100, "50", kurs="0.9"),  # OFF offen
        _ex("K1", 6, "BUY", 1, "10", kurs=None),
        _ex("K2", 6, "SELL", 1, "12", kurs=None),  # KUR
    ]
    instrumente = [
        _instr(1, "OPT", "WHL", "100"),
        _instr(2, "STK", "WHL"),
        _instr(3, "STK", "EKT"),
        _instr(4, "STK", "ZZZ"),
        _instr(5, "STK", "OFF"),
        _instr(6, "STK", "KUR"),
    ]
    ketten = [
        {
            "chain_id": 1,
            "underlying": "WHL",
            "asset_class": "OPT",
            "anzahl_rolls": 0,
            "beendet_am": T1,
        },
        {
            "chain_id": 2,
            "underlying": "EKT",
            "asset_class": "STK",
            "anzahl_rolls": 0,
            "beendet_am": T1,
        },
        {
            "chain_id": 3,
            "underlying": "OFF",
            "asset_class": "STK",
            "anzahl_rolls": 0,
            "beendet_am": None,
        },
        {
            "chain_id": 4,
            "underlying": "KUR",
            "asset_class": "STK",
            "anzahl_rolls": 0,
            "beendet_am": T1,
        },
    ]

    def struktur(sid, typ, geschlossen, netto):
        # ``netto_pnl`` (Instrumentenwährung) schreibt der Rebuild; ohne ihn keine Strukturzahl.
        return {
            "structure_id": sid,
            "typ": typ,
            "waehrung": "USD",
            "brutto_pnl": None,
            "kommission": None,
            "netto_pnl": netto,
            "geschlossen_am": geschlossen,
        }

    strukturen = [
        struktur(1, "Single", T1, D("500")),
        struktur(2, "Stock", T1, D("1000")),
        struktur(3, "Stock", T1, D("20")),
        struktur(4, "Stock", None, None),
        struktur(5, "Stock", T1, D("2")),
    ]
    glieder = [
        {
            "chain_id": c,
            "structure_id": s,
            "sequenz": 0,
            "verknuepfungstyp": "open",
            "erkennung": "auto",
        }
        for c, s in ((1, 1), (1, 2), (2, 3), (3, 4), (4, 5))
    ]
    beine = [
        _leg(1, 1, "P1", "P2", "-1"),
        _leg(2, 2, "S1", "S2", "100"),
        _leg(3, 3, "E1", "E2", "10"),
        _leg(None, 4, "Z1", "Z2", "5"),
        _leg(4, 5, "O1", None, "100"),
        _leg(5, 6, "K1", "K2", "1"),
    ]
    bestand = {5: {"menge": D(100), "wert": D("4800"), "kurs": D("0.9")}}
    return titel_auswertung(
        ketten, strukturen, glieder, beine, ausf, instrumente, bestand, date(2026, 10, 12), von, bis
    )


def _je_titel():
    return {z.basiswert: z for z in _welt()}


def test_wheel_wird_nach_klasse_aufgeteilt_summe_stimmt():
    z = _je_titel()["WHL"]
    assert z.realisiert_eur == D("1500")
    assert z.realisiert_je_klasse == {"OPT": D("500"), "STK": D("1000")}
    assert z.nicht_aufgeteilt_eur == 0
    assert (z.ketten, z.ketten_offen, z.strukturen_geschlossen) == (1, 0, 2)
    assert z.unrealisiert_eur == 0 and z.gesamt_eur == D("1500")


def test_reine_aktie_zaehlt_ohne_optionen():
    z = _je_titel()["EKT"]
    assert z.realisiert_eur == D("20")
    assert z.realisiert_je_klasse == {"STK": D("20")}


def test_loses_bein_zaehlt_mit_geld():
    z = _je_titel()["ZZZ"]
    assert z.realisiert_eur == D("-5.00")
    assert z.realisiert_je_klasse == {"STK": D("-5.00")}
    assert z.ketten == 0


def test_offene_aktie_ist_unrealisiert_und_nicht_realisiert():
    z = _je_titel()["OFF"]
    assert z.realisiert_eur == 0
    assert z.unrealisiert_eur == D("-180.00")  # (4800 - 5000) x 0,9
    assert z.unrealisiert_je_klasse == {"STK": D("-180.00")}
    assert z.gesamt_eur == D("-180.00")
    assert (z.ketten, z.ketten_offen) == (1, 1)


def test_kursmangel_zaehlt_nicht_und_steht_in_kurs_fehlt():
    z = _je_titel()["KUR"]
    assert z.realisiert_eur == 0
    assert z.kurs_fehlt == 1


def test_summe_ueber_alle_titel():
    zeilen = _welt()
    assert sum(z.realisiert_eur for z in zeilen) == D("1515")  # 1.500 + 20 - 5
    assert sum(z.nicht_aufgeteilt_eur for z in zeilen) == 0
    assert [z.basiswert for z in zeilen] == [
        "EKT",
        "KUR",
        "OFF",
        "WHL",
        "ZZZ",
    ]  # nach Basiswert sortiert


def test_api_leere_datenbank(migrated_db):
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    d = TestClient(erzeuge_app(migrated_db)).get("/titel-auswertung").json()
    assert d["stichtag"] is None and d["titel"] == []
    assert d["summen"]["basiswert"] == "Summe"
    assert d["summen"]["realisiert_eur"] in ("0", "0.00")


# Zeitraum (von/bis, beide Enden einschließlich): Realisiert zählt am Schließungstag, das
# Unrealisierte gilt zum Stichtag (2026-10-12) und entfällt, wenn ``bis`` davor liegt.
# Alle Schließungen der Testwelt: 2026-09-10.


def _welt_mit_zeitraum(von, bis):
    return {z.basiswert: z for z in _welt(von, bis)}


def test_zeitraum_beide_enden_einschliesslich():
    z = _welt_mit_zeitraum(date(2026, 9, 10), date(2026, 9, 10))  # genau der Schließungstag
    assert z["WHL"].realisiert_eur == D("1500")
    assert z["EKT"].realisiert_eur == D("20")
    assert z["ZZZ"].realisiert_eur == D("-5.00")
    assert z["WHL"].strukturen_geschlossen == 2 and z["ZZZ"].lose_beine == 1


def test_zeitraum_nach_der_schliessung_zaehlt_nichts_realisiert_aber_unrealisiert_bleibt():
    z = _welt_mit_zeitraum(date(2026, 9, 11), None)
    assert z["WHL"].realisiert_eur == 0 and z["EKT"].realisiert_eur == 0
    assert "ZZZ" not in z       # nur ein loses Bein, außerhalb des Zeitraums: keine Zeile
    assert z["WHL"].strukturen_geschlossen == 0
    assert z["OFF"].unrealisiert_eur == D("-180.00")  # bis offen: Stichtag gilt


def test_bis_vor_dem_stichtag_entfaellt_das_unrealisierte():
    z = _welt_mit_zeitraum(None, date(2026, 10, 11))  # Stichtag ist 2026-10-12
    assert z["OFF"].unrealisiert_eur == 0
    assert z["OFF"].offene_ohne_kurs == 0  # nicht "ohne Kurs", sondern gar nicht gerechnet
    assert z["WHL"].realisiert_eur == D("1500")  # Schließung 09-10 liegt im Zeitraum
    z = _welt_mit_zeitraum(None, date(2026, 10, 12))  # bis = Stichtag: gilt noch
    assert z["OFF"].unrealisiert_eur == D("-180.00")


def test_api_zeitraum_wird_durchgereicht_und_geprueft(migrated_db):
    import pytest

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from api.app import erzeuge_app

    klient = TestClient(erzeuge_app(migrated_db))
    assert klient.get("/titel-auswertung?von=2026-01-01&bis=2026-01-31").status_code == 200
    assert klient.get("/titel-auswertung?von=2026-02-01&bis=2026-01-31").status_code == 422
