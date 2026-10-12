"""Abnahmetests für AP-06sd: Scorecard mit Roll-Schritten (`analytics/strategien.py`).
Nutzerwunsch 12.10.2026 (Fall DAX: BPS noExit): eine gerollte offene Kette zeigt
ihre Verluste erst beim Schließen — die Scorecard soll sie sofort zeigen, und
die Rollschritte sollen einzeln gezählt werden können, wie OA es tut.

Ketten (Strategie S, Beträge EUR netto, Kontosicht):
  Kette 1, geschlossen 08.01.: drei Glieder, geschlossen 03.01. −10.00,
    05.01. −20.00, 08.01. +50.00 (Roll, Roll, Ende)
  Kette 2, offen: Glied 4 geschlossen 06.01. −5.00, Glied 5 noch offen
Kettenansicht (`strategie_auswertung`, unverändert): 1 Position +20.00.
  Neu je Strategie: `bisher_offene_eur` = realisierte Teile offener Ketten
  = −5.00; `max_drawdown_schritte_eur`: alle Schritte nach Schließung
  −10 (03.01.), −20 (05.01.), −5 (06.01.), +50 (08.01.): Kurve −10, −30, −35,
  15 → Hoch bleibt 0 → Drawdown −35.00.
Schrittansicht (`schritte_als_positionen`): Jedes geschlossene Glied ist eine
  Position (−10, −20, +50, −5), das offene Glied 5 zählt als offen:
  Anzahl 4, offen 1, Gewinner 1, Verlierer 3, Trefferquote 1/4 = 0.2500,
  Summe 15.00, Drawdown (Reihenfolge der Schließung) −35.00, Zuteilung:
  Glieder der Kette 1 mit Zuteilung (alle drei).
"""

from datetime import datetime
from decimal import Decimal as D

from analytics.strategien import schritte_als_positionen, strategie_auswertung

KETTEN = [
    dict(chain_id=1, oa_strategie="S", eroeffnet_am=datetime(2026, 1, 2),
         beendet_am=datetime(2026, 1, 8)),
    dict(chain_id=2, oa_strategie="S", eroeffnet_am=datetime(2026, 1, 4), beendet_am=None),
]
STRUKTUREN = [
    dict(structure_id=1, eroeffnet_am=datetime(2026, 1, 2), geschlossen_am=datetime(2026, 1, 3)),
    dict(structure_id=2, eroeffnet_am=datetime(2026, 1, 3), geschlossen_am=datetime(2026, 1, 5)),
    dict(structure_id=3, eroeffnet_am=datetime(2026, 1, 5), geschlossen_am=datetime(2026, 1, 8)),
    dict(structure_id=4, eroeffnet_am=datetime(2026, 1, 4), geschlossen_am=datetime(2026, 1, 6)),
    dict(structure_id=5, eroeffnet_am=datetime(2026, 1, 6), geschlossen_am=None),
]
GLIEDER = [dict(chain_id=c, structure_id=s) for c, s in
           [(1, 1), (1, 2), (1, 3), (2, 4), (2, 5)]]
NETTO = {1: D("-10.00"), 2: D("-20.00"), 3: D("50.00"), 4: D("-5.00"), 5: None}


def _positionen():
    return schritte_als_positionen(KETTEN, STRUKTUREN, GLIEDER, NETTO, mit_zuteilung={1})


def test_schritte_als_positionen():
    p = _positionen()
    assert [(x["chain_id"], x["netto_eur"], x["beendet_am"] is None) for x in p] == [
        (1, D("-10.00"), False), (1, D("-20.00"), False), (1, D("50.00"), False),
        (2, D("-5.00"), False), (2, None, True)]
    assert [x["zuteilung"] for x in p] == [True, True, True, False, False]


def test_schrittansicht():
    s = strategie_auswertung(_positionen())[0]
    assert (s.anzahl, s.offen, s.gewinner, s.verlierer) == (4, 1, 1, 3)
    assert s.trefferquote == D("0.2500")
    assert s.summe_eur == D("15.00")
    assert s.max_drawdown_eur == D("-35.00")


def test_kettenansicht_zeigt_bisher_und_schritt_drawdown():
    ketten = [
        dict(chain_id=1, strategie="S", eroeffnet_am=datetime(2026, 1, 2),
             beendet_am=datetime(2026, 1, 8), netto_eur=D("20.00"), zuteilung=False,
             schritte=[(datetime(2026, 1, 3), D("-10.00")), (datetime(2026, 1, 5), D("-20.00")),
                       (datetime(2026, 1, 8), D("50.00"))]),
        dict(chain_id=2, strategie="S", eroeffnet_am=datetime(2026, 1, 4), beendet_am=None,
             netto_eur=None, zuteilung=False, schritte=[(datetime(2026, 1, 6), D("-5.00"))]),
    ]
    s = strategie_auswertung(ketten)[0]
    assert (s.anzahl, s.offen, s.summe_eur, s.max_drawdown_eur) == (1, 1, D("20.00"), D("0"))
    assert s.bisher_offene_eur == D("-5.00")
    assert s.max_drawdown_schritte_eur == D("-35.00")
