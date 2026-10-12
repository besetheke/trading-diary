"""Abnahmetest für AP-12c: `journal backtest-bericht <datei> [--von] [--bis]`
schreibt alle Paare Backtest ↔ Bot (ohne abgelehnte Zuordnungen) als CSV —
Semikolon, UTF-8 mit BOM, Beträge mit zwei Nachkommastellen, wie die anderen
Berichte. Welt: tests/test_api_backtests.py.

Kopf: backtest;bot;art;eroeffnung_backtest;eroeffnung_bot;oa_trade;versatz_min;
kontrakte_backtest;kontrakte_bot;pl_backtest;pl_bot;differenz;ursache;
kontrakt_effekt (je Kontrakt in USD).
Strategie IC (SPX: IC +Vo/n), Zeitraum 2.–3.3.2026:
  paar;7001: Versatz +1, 1/1 Kontrakte, 224.00 / 210.00, Differenz −14.00,
             Ursache strikeauswahl
  paar;7002: Versatz 0, 1/2 Kontrakte, −500.00 / −550.00, −50.00, kontrakte,
             Kontrakt-Effekt −550.00
Mit `--von 2026-03-03` bleibt nur 7002 aus dieser Strategie.
"""

from test_api_backtests import IC, klient  # noqa: F401 (Fixture)

from journal.cli import main


def _zeilen(pfad):
    text = pfad.read_bytes().decode("utf-8-sig")
    kopf, *rest = text.strip("\n").split("\n")
    return kopf.split(";"), [z.split(";") for z in rest]


def test_csv(klient, migrated_db, tmp_path):  # noqa: F811
    ziel = tmp_path / "bt.csv"
    assert main(["backtest-bericht", str(ziel), "--db", str(migrated_db)]) == 0
    assert ziel.read_bytes().startswith(b"\xef\xbb\xbf")
    kopf, zeilen = _zeilen(ziel)
    assert kopf == ["backtest", "bot", "art", "eroeffnung_backtest", "eroeffnung_bot",
                    "oa_trade", "versatz_min", "kontrakte_backtest", "kontrakte_bot",
                    "pl_backtest", "pl_bot", "differenz", "ursache", "kontrakt_effekt"]
    je = {(z[0], z[5]): dict(zip(kopf, z, strict=True)) for z in zeilen}
    a = je[(IC, "7001")]
    assert (a["art"], a["versatz_min"], a["pl_backtest"], a["pl_bot"], a["differenz"],
            a["ursache"]) == ("paar", "1", "224.00", "210.00", "-14.00", "strikeauswahl")
    b = je[(IC, "7002")]
    assert (b["kontrakte_backtest"], b["kontrakte_bot"], b["differenz"], b["ursache"],
            b["kontrakt_effekt"]) == ("1", "2", "-50.00", "kontrakte", "-550.00")


def test_zeitraum(klient, migrated_db, tmp_path):  # noqa: F811
    ziel = tmp_path / "bt.csv"
    assert main(["backtest-bericht", str(ziel), "--db", str(migrated_db),
                 "--von", "2026-03-03"]) == 0
    kopf, zeilen = _zeilen(ziel)
    ic = [dict(zip(kopf, z, strict=True)) for z in zeilen if z[0] == IC and z[2] == "paar"]
    assert [z["oa_trade"] for z in ic] == ["7002"]
