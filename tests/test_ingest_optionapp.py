"""Abnahmetests für AP-13, Teil 1: den Parser des OptionApp-Trade-Exports.

Geschrieben nach §11.2 des Plans durch das starke Modell (AP-13p) — für das
günstige Modell unveränderlich. Maßgeblich für das Format ist
`auftraege/AP-13-anhang-oa-format.md`, für den Vertrag `auftraege/AP-13p.md`.

Das Modul springt still ab, solange `ingest/optionapp.py` nicht existiert;
sobald es existiert, laufen alle Tests scharf — dieselbe Regel wie bei
`tests/test_matching.py`.

Die Fixtures unter `fixtures/optionapp/` sind frei erfunden und werden von
`fixtures/optionapp/erzeugen.py` erzeugt. `fixtures/golden/` wird hier nicht
gelesen.

**Jeder Erwartungswert ist von Hand nachgerechnet** (Regel 8): Die
Leg-Zerlegung folgt der Grammatik aus dem Anhang, `Profit` der deutschen
Schreibweise mit Währungszeichen.
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select

pytest.importorskip("ingest.optionapp")

from ingest.optionapp import import_optionapp_file  # noqa: E402
from journal.db import create_db_engine  # noqa: E402
from journal.schema import (  # noqa: E402
    import_runs,
    optionapp_legs,
    optionapp_trades,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "optionapp"


def _importiere(db_pfad, dateiname):
    return import_optionapp_file(db_pfad, FIXTURES / dateiname)


def _trades(db_pfad) -> dict:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        zeilen = verbindung.execute(select(optionapp_trades)).mappings().all()
    return {zeile["oa_trade"]: dict(zeile) for zeile in zeilen}


def _legs(db_pfad, trade_id) -> list:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return [
            dict(zeile)
            for zeile in verbindung.execute(
                select(optionapp_legs)
                .where(optionapp_legs.c.optionapp_trade_id == trade_id)
                .order_by(optionapp_legs.c.position)
            )
            .mappings()
            .all()
        ]


# ---------------------------------------------------------------------------
# Regelfall
# ---------------------------------------------------------------------------


def test_standardfall_legt_alle_trades_und_legs_an(migrated_db):
    """Vertrag 1: vier Trades mit 4 + 2 + 3 + 2 = 11 Legs."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert sorted(trades) == ["1001", "1002", "1003", "1004"]
    gesamt = sum(len(_legs(migrated_db, t["id"])) for t in trades.values())
    assert gesamt == 11


def test_profit_wird_aus_deutschem_format_gelesen(migrated_db):
    """Vertrag 2: `-1.234,56 $` → Decimal('-1234.56') plus Währungszeichen.
    Tausenderpunkt entfernen, Komma zu Punkt — kein float."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1001"]["profit"] == Decimal("-1234.56")
    assert trades["1001"]["profit_waehrung"] == "$"
    assert trades["1002"]["profit"] == Decimal("610.00")
    assert trades["1003"]["profit"] == Decimal("-375.50")


def test_preise_sind_decimal_ohne_float_umweg(migrated_db):
    """Vertrag 2, Regel 5: `Open` und `Close` stehen als Zahl in der Zelle und
    werden zu Decimal — 11.49 bleibt 11.49, nicht 11.489999999999999."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1001"]["offen_preis"] == Decimal("11.49")
    assert trades["1001"]["schluss_preis"] == Decimal("4.2")


def test_stops_unterscheidet_kein_stop_von_null(migrated_db):
    """Vertrag 3: `-` heißt „kein Stop" (Zahlwert leer), `0` ist ein gesetzter
    Stop. Der Rohwert bleibt in beiden Fällen erhalten."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1001"]["stop_roh"] == "-"
    assert trades["1001"]["stop_wert"] is None
    assert trades["1002"]["stop_roh"] == "0"
    assert trades["1002"]["stop_wert"] == Decimal("0")
    assert trades["1003"]["stop_wert"] == Decimal("-14.4")


def test_quantity_wird_als_verhaeltnis_gespeichert(migrated_db):
    """Vertrag 4: `n/m` getrennt halten, Gleichheit nicht voraussetzen."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1002"]["menge_zaehler"] == Decimal("2")
    assert trades["1002"]["menge_nenner"] == Decimal("2")


def test_leg_grammatik_wird_vollstaendig_zerlegt(migrated_db):
    """Vertrag 5: `-1xC751 (260831) / 1xC761 (260831) / -1xP717 (260918) /
    1xP707 (260918)` — Richtung aus dem führenden Minus, Menge, Typ, Strike,
    Verfall aus `JJMMTT`, Reihenfolge als position."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    legs = _legs(migrated_db, trades["1001"]["id"])
    assert [leg["richtung"] for leg in legs] == [-1, 1, -1, 1]
    assert [leg["right"] for leg in legs] == ["C", "C", "P", "P"]
    assert [leg["strike"] for leg in legs] == [
        Decimal("751"),
        Decimal("761"),
        Decimal("717"),
        Decimal("707"),
    ]
    assert [leg["expiry"] for leg in legs] == [
        date(2026, 8, 31),
        date(2026, 8, 31),
        date(2026, 9, 18),
        date(2026, 9, 18),
    ]
    assert [leg["menge"] for leg in legs] == [Decimal("1")] * 4


def test_leg_mit_dezimalstrike_wird_gelesen(migrated_db):
    """Vertrag 5: Der Strike darf einen Dezimalteil tragen, auch wenn in den
    Referenzexporten keiner vorkam — halbe Punkte sind üblich."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    legs = _legs(migrated_db, trades["1004"]["id"])
    assert [leg["strike"] for leg in legs] == [Decimal("612.5"), Decimal("602.5")]


def test_klammernummer_ist_die_letzte_gruppe(migrated_db):
    """Vertrag 6: Der freie Text kann selbst Klammern enthalten —
    „mit (Klammer) im Text [1002]" schlüsselt auf 1002, nicht auf „Klammer"."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert "1002" in trades
    assert trades["1002"]["name_roh"] == "mit (Klammer) im Text [1002]"


def test_zeitstempel_werden_naiv_gelesen(migrated_db):
    """Vertrag 7: Format `JJJJ/MM/TT hh:mm:ss`, gespeichert wie geliefert."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1001"]["entry_zeit"] == datetime(2026, 8, 17, 9, 57, 19)
    assert trades["1001"]["schluss_zeit"] == datetime(2026, 8, 28, 16, 5, 0)


def test_offener_trade_bleibt_ohne_schliessung(migrated_db):
    """Vertrag 8: Leeres `Close` und `Close Time` sind erlaubt; der Trade wird
    trotzdem gebucht."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1004"]["schluss_preis"] is None
    assert trades["1004"]["schluss_zeit"] is None
    assert trades["1004"]["status"] == "UNMANAGED"


def test_strich_in_close_und_close_time_heisst_offen(migrated_db):
    """Vertrag 8, erweitert durch AP-13pl (OF-37): Bei noch nicht
    geschlossenen Trades tragen `Close` und `Close Time` den Strich — nie
    nur eine der beiden Spalten. Er bedeutet dasselbe wie eine leere Zelle
    und dasselbe wie `-` in `Stops`: „gibt es nicht", nicht „unlesbar".

    Gemessen an den realen Exporten trifft das 187 von 268 Zeilen der
    Januar- und 24 von 178 Zeilen der Augustdatei; ohne diese Behandlung
    ist keine von beiden einlesbar.
    """
    _importiere(migrated_db, "oa_laufend.xlsx")
    trades = _trades(migrated_db)
    assert sorted(trades) == ["3001", "3002", "3003"]
    for nummer in ("3001", "3002", "3003"):
        assert trades[nummer]["schluss_preis"] is None
        assert trades[nummer]["schluss_zeit"] is None
    assert trades["3001"]["status"] == "CANCELED"
    assert trades["3002"]["status"] == "RUNNING"
    assert trades["3003"]["status"] == "PARTIALLY STOPPED"


def test_strich_laesst_uebrige_felder_unberuehrt(migrated_db):
    """Der Strich in `Close` gilt nur für `Close` — er reißt die übrigen
    Spalten nicht mit. `[3003]` trägt einen gesetzten Stop, einen
    Eröffnungspreis, ein Ergebnis und drei Legs.

    Von Hand nachgerechnet (Regel 8): `Stops` `14.4` ist ein gesetzter Stop
    (Vertrag 3), `-125,00 $` ist deutsch geschrieben und wird zu
    `Decimal("-125.00")` mit Währung `$` (Vertrag 2), und die
    `Strikes`-Zelle zerfällt an ` / ` in drei Legs (Vertrag 5).
    """
    _importiere(migrated_db, "oa_laufend.xlsx")
    trades = _trades(migrated_db)
    dreitausenddrei = trades["3003"]
    assert dreitausenddrei["stop_roh"] == "14.4"
    assert dreitausenddrei["stop_wert"] == Decimal("14.4")
    assert dreitausenddrei["offen_preis"] == Decimal("3.6")
    assert dreitausenddrei["profit"] == Decimal("-125.00")
    assert dreitausenddrei["profit_waehrung"] == "$"
    assert dreitausenddrei["entry_zeit"] == datetime(2026, 8, 4, 9, 45, 0)
    assert len(_legs(migrated_db, dreitausenddrei["id"])) == 3


def test_status_bleibt_rohwert(migrated_db):
    """Vertrag 9: Der Endzustand wird roh gespeichert, nicht abgebildet."""
    _importiere(migrated_db, "oa_standard.xlsx")
    trades = _trades(migrated_db)
    assert trades["1003"]["status"] == "PARTIALLY STOPPED"


# ---------------------------------------------------------------------------
# Fehlerfälle — jeder bricht ab, keiner entscheidet still
# ---------------------------------------------------------------------------


def test_defekte_leg_grammatik_bricht_ab(migrated_db):
    """Vertrag 5: Die Grammatik ist über 856 Legs ausnahmslos stabil; eine
    Abweichung ist ein Defekt der Quelle und kein Fall zum Raten."""
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "oa_grammatik_defekt.xlsx")
    assert "1101" in str(fehler.value) or "Z751" in str(fehler.value)


def test_fehlende_klammernummer_bricht_ab(migrated_db):
    """Vertrag 6: Ohne Schlüssel ist der Trade nicht verknüpfbar."""
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "oa_ohne_klammernummer.xlsx")
    assert "ohne Nummer" in str(fehler.value) or "Name" in str(fehler.value)


def test_doppelte_nummer_mit_abweichendem_inhalt_bricht_ab(migrated_db):
    """Vertrag 10: Dieselbe Nummer mit anderem Inhalt ist ein Fehlerfall mit
    Nennung der Nummer — kein Überschreiben."""
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "oa_doppelte_nummer.xlsx")
    assert "2001" in str(fehler.value)


# ---------------------------------------------------------------------------
# Importlauf
# ---------------------------------------------------------------------------


def test_importlauf_traegt_quelle_und_kennzeichen(migrated_db):
    """Vertrag 11: `quelle = 'optionapp'`, Qualitätsstufe B, und
    `realized_pnl_verfuegbar = false` — ein OA-Lauf trägt keine IB-Ergebnisse,
    und kein Vergleich darf dort welche suchen (OF-21)."""
    _importiere(migrated_db, "oa_standard.xlsx")
    engine = create_db_engine(migrated_db)
    with engine.connect() as verbindung:
        lauf = verbindung.execute(select(import_runs)).mappings().one()
    assert lauf["quelle"] == "optionapp"
    assert lauf["qualitaetsstufe"] == "B"
    assert bool(lauf["realized_pnl_verfuegbar"]) is False


def test_doppelter_import_derselben_datei_legt_nichts_neu_an(migrated_db):
    """Vertrag 10: Gleiche Nummer mit identischem Inhalt ist derselbe Trade."""
    _importiere(migrated_db, "oa_standard.xlsx")
    _importiere(migrated_db, "oa_standard.xlsx")
    assert len(_trades(migrated_db)) == 4


# ---------------------------------------------------------------------------
# Nicht ausgeführte Trades und die zweite Exportvariante (AP-13pm, OF-40)
# ---------------------------------------------------------------------------


def test_abgebrochener_trade_wird_ohne_legs_gebucht(migrated_db):
    """Vertrag 14: `CANCELED` heißt „nie eröffnet". `Strikes` trägt dann
    einen Abbruchgrund statt einer Leg-Spezifikation und wird nicht zerlegt;
    `Open` darf den Strich tragen.

    Gemessen: alle 179 `CANCELED`-Trades der Januardatei tragen `-` in
    `Open`, `Close` und `Close Time` und in `Strikes` einen Grund oder
    nichts.
    """
    _importiere(migrated_db, "oa_nicht_ausgefuehrt.xlsx")
    trades = _trades(migrated_db)
    abgebrochen = trades["4001"]
    assert abgebrochen["status"] == "CANCELED"
    assert abgebrochen["strikes_roh"] == "Entry condition not met"
    assert abgebrochen["offen_preis"] is None
    assert abgebrochen["schluss_preis"] is None
    assert abgebrochen["schluss_zeit"] is None
    assert _legs(migrated_db, abgebrochen["id"]) == []


def test_abgebrochener_trade_mit_leerem_strikes(migrated_db):
    """Vertrag 14: Ein leeres `Strikes` bei `CANCELED` wird als leerer
    Rohwert gebucht — die Spalte ist Pflicht, ihr Inhalt hier nicht."""
    _importiere(migrated_db, "oa_nicht_ausgefuehrt.xlsx")
    trades = _trades(migrated_db)
    assert trades["4002"]["strikes_roh"] == ""
    assert _legs(migrated_db, trades["4002"]["id"]) == []


def test_laufender_trade_mit_geplanten_legs(migrated_db):
    """Vertrag 15: `RUNNING` mit Legs in Restlaufzeitform (`-7DTE`) — geplant,
    nicht ausgeführt, ohne Verfallsdatum. Keine Legs, Rohwert erhalten; der
    Eröffnungspreis ist gelesen."""
    _importiere(migrated_db, "oa_nicht_ausgefuehrt.xlsx")
    trades = _trades(migrated_db)
    laufend = trades["4003"]
    assert laufend["strikes_roh"] == "-1xP5000-7DTE / 1xP4950-7DTE"
    assert laufend["offen_preis"] == Decimal("2.1")
    assert _legs(migrated_db, laufend["id"]) == []


def test_profit_als_zahl_ohne_waehrung(migrated_db):
    """Vertrag 16: In der Januarvariante steht `Profit` als Zahl in der
    Zelle. Gelesen über `Decimal(str(wert))`; eine Währung steht nicht da
    und wird nicht unterstellt.

    Von Hand: 7.72 → `Decimal("7.72")`, `profit_waehrung` leer. Beim
    abgebrochenen Trade steht die Zahl 0 → `Decimal("0")`.
    """
    _importiere(migrated_db, "oa_nicht_ausgefuehrt.xlsx")
    trades = _trades(migrated_db)
    assert trades["4004"]["profit"] == Decimal("7.72")
    assert trades["4004"]["profit_waehrung"] is None
    assert trades["4001"]["profit"] == Decimal("0")
    assert len(_legs(migrated_db, trades["4004"]["id"])) == 2


def test_leeres_stops_ist_keine_angabe(migrated_db):
    """Vertrag 17: Ein leeres `Stops` ist weder `-` noch `0` — es ist keine
    Angabe. Rohwert leer, kein Stopwert."""
    _importiere(migrated_db, "oa_nicht_ausgefuehrt.xlsx")
    trades = _trades(migrated_db)
    assert trades["4004"]["stop_roh"] == ""
    assert trades["4004"]["stop_wert"] is None


def test_mehrere_stops_in_einer_zelle(migrated_db):
    """Vertrag 18: Zwei Stops, zeilengetrennt — gemessen nur bei Trades mit
    drei oder vier Legs. Der Rohwert bleibt vollständig erhalten; einen
    einzelnen Stopwert gibt es nicht, also bleibt `stop_wert` leer."""
    _importiere(migrated_db, "oa_nicht_ausgefuehrt.xlsx")
    trades = _trades(migrated_db)
    zwei = trades["4005"]
    assert zwei["stop_roh"] == "-14.4\n-12.1"
    assert zwei["stop_wert"] is None
    assert len(_legs(migrated_db, zwei["id"])) == 4


def test_freitext_bei_ausgefuehrtem_trade_bricht_weiter_ab(migrated_db):
    """Vertrag 14, Gegenprobe: Die Lockerung gilt nur für nie eröffnete
    Trades. Bei einem geschlossenen Trade bleibt Freitext in `Strikes` ein
    Defekt der Quelle — über 1.114 Legs ausgeführter Trades hält die
    Grammatik ausnahmslos."""
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "oa_freitext_ausgefuehrt.xlsx")
    assert "4101" in str(fehler.value)


def test_mehrere_stops_mit_unlesbarer_zeile_brechen_ab(migrated_db):
    """Vertrag 18, Gegenprobe: Jede Zeile muss für sich Vertrag 3 genügen."""
    with pytest.raises(ValueError) as fehler:
        _importiere(migrated_db, "oa_mehrstop_defekt.xlsx")
    assert "4201" in str(fehler.value)
