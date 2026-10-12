"""Abnahmetest für AP-12a, Teil Zuordnung: ``engine.oo_zuordnung`` (rein).

Kriterien (Auftrag, Vertrag 3): gleicher Tag, gleiche Familie, gleiche
Signatur, relative Spannweite höchstens max(1 ‰, 30 %) verschieden, höchstens
20 Minuten auseinander; der zeitlich nächste Kandidat gewinnt.

Von Hand:
- SPX-IC 6800/6900 mit Flügeln 30 (Spannweite 160/6850 = 23,4 ‰) gegen
  XSP-IC 680/690 mit Flügeln 3 (16/685 = 23,4 ‰): gleiche Familie, gleiche
  Signatur, gleiche Spannweite → passt.
- SPX-IC mit Flügeln 100 (300/6850 = 43,8 ‰): Abstand 20,4 > 0,3 · 23,4 = 7,0
  → passt nicht.
- PBF 4/2/2 (Strikes 6825 B, 6855 S, 6885 B) hat die Signatur von 1/2/1 —
  nicht die einer Vertikalen 1/1.
- Vorschläge: OO-Strategie „A" mit 5 Trades, 4 gepaart mit OA „X", 1 mit „Y":
  X 4 Treffer, Anteil 0,8000, eindeutig; Y 1 Treffer, Anteil 0,2000 → nicht
  gezeigt (weder ≥ 2 Treffer noch Anteil ≥ 0,5).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from engine.oo_zuordnung import (
    Eroeffnung,
    Leg,
    kontrakte,
    paaren,
    signatur,
    spannweite,
    vorschlaege,
)

T = date(2026, 3, 2)


def _ic(kurz_p, kurz_c, fluegel, menge=1):
    return (
        Leg(menge, "S", "P", Decimal(kurz_p), T),
        Leg(menge, "S", "C", Decimal(kurz_c), T),
        Leg(menge, "B", "P", Decimal(kurz_p - fluegel), T),
        Leg(menge, "B", "C", Decimal(kurz_c + fluegel), T),
    )


def _e(schluessel, strategie, zeit, basiswert, legs):
    return Eroeffnung(schluessel=schluessel, strategie=strategie, zeit=zeit,
                      basiswert=basiswert, legs=legs)


def test_spannweite_und_kontrakte():
    assert spannweite(_ic(6800, 6900, 30)) == Decimal("23.4")
    assert spannweite(_ic(6800, 6900, 100)) == Decimal("43.8")
    assert kontrakte(_ic(6800, 6900, 30, menge=2)) == 2


def test_signatur_pbf_ungleich_vertikale():
    pbf = (Leg(4, "S", "P", Decimal("6855"), T), Leg(2, "B", "P", Decimal("6825"), T),
           Leg(2, "B", "P", Decimal("6885"), T))
    pbf_live = (Leg(1, "S", "P", Decimal("6850"), T), Leg(1, "S", "P", Decimal("6850"), T),
                Leg(1, "B", "P", Decimal("6820"), T), Leg(1, "B", "P", Decimal("6880"), T))
    vertikale = (Leg(1, "S", "P", Decimal("6855"), T), Leg(1, "B", "P", Decimal("6825"), T))
    assert signatur(pbf, T) == signatur(pbf_live, T)
    assert signatur(pbf, T) != signatur(vertikale, T)


def test_paaren():
    oo = [_e("o1", "A", datetime(2026, 3, 2, 9, 32), "SPX", _ic(6800, 6900, 30))]
    live = [
        _e("passt", "X", datetime(2026, 3, 2, 9, 40), "XSP", _ic(680, 690, 3)),
        _e("naeher", "Y", datetime(2026, 3, 2, 9, 33), "SPX", _ic(6805, 6905, 30)),
        _e("zu_breit", "Z", datetime(2026, 3, 2, 9, 32), "SPX", _ic(6800, 6900, 100)),
        _e("zu_spaet", "Z", datetime(2026, 3, 2, 9, 53), "SPX", _ic(6800, 6900, 30)),
        _e("anderer_tag", "Z", datetime(2026, 3, 3, 9, 32), "SPX", _ic(6800, 6900, 30)),
        _e("andere_familie", "Z", datetime(2026, 3, 2, 9, 32), "RUT", _ic(6800, 6900, 30)),
    ]
    assert paaren(oo, live) == {"o1": "naeher"}
    assert paaren(oo, live[:1]) == {"o1": "passt"}
    assert paaren(oo, live[2:]) == {}
    assert paaren(oo, live[3:4], toleranz=timedelta(minutes=21)) == {"o1": "zu_spaet"}


def test_vorschlaege():
    oo = [_e(f"o{i}", "A", datetime(2026, 3, 2 + i, 9, 32), "SPX", _ic(6800, 6900, 30))
          for i in range(5)]
    live = [_e(f"l{i}", "X" if i < 4 else "Y", datetime(2026, 3, 2 + i, 9, 33), "SPX",
               _ic(6800, 6900, 30)) for i in range(5)]
    p = paaren(oo, live)
    v = vorschlaege(oo, live, p)
    assert [(x.oo_strategie, x.oa_strategie, x.treffer, x.anteil, x.eindeutig, x.erster,
             x.letzter) for x in v] == [
        ("A", "X", 4, Decimal("0.8000"), True, date(2026, 3, 2), date(2026, 3, 5)),
    ]
