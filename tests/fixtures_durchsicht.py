"""Frei erfundene Szenarien für die Abnahmetests der Durchsicht (AP-04dv).

Ergänzt ``tests/fixtures_rebuild.py`` um zwei Fälle, die dort nicht
vorkommen. Beide auf ESTX50, ohne ``exec_batch`` — also Fälle, die seit AP-04k
keine Kette mehr bilden, sondern Rollkandidaten:

- **MEHRDEUTIG** — eine Put-Vertikale schließt um 15:00; zwei neue
  Vertikalen öffnen um 15:02 und 15:20. Beide sind Kandidaten derselben
  schließenden Position, Rang 1 und 2.
- **DOPPELT** — zwei Put-Vertikalen schließen um 15:00 und 15:01; *eine*
  neue öffnet um 15:05. Sie ist Kandidat für **beide**. Bestätigt der Nutzer
  beide, beansprucht er dieselbe Struktur für zwei Ketten — ein Widerspruch,
  den das Einlesen abfangen muss (AP-04v, Vertrag 21).

Nachgerechnet gegen die Engine am 22.09.2026 — siehe Auftrag AP-04dv.
"""

from datetime import date, datetime
from decimal import Decimal

from fixtures_rebuild import INSTRUMENTE


def _put(conid, strike, verfall):
    return dict(
        conid=conid, symbol=f"ESTX50 P{strike}", underlying="ESTX50", asset_class="OPT",
        expiry=verfall, strike=Decimal(strike), right="P",
        multiplikator=Decimal("10"), waehrung="EUR",
    )


INSTRUMENTE_ESTX = [s for s in INSTRUMENTE if s["conid"] in (801, 802, 803, 804)] + [
    _put(805, "4700", date(2026, 11, 20)),
    _put(806, "4650", date(2026, 11, 20)),
    _put(807, "4600", date(2026, 9, 18)),
    _put(808, "4550", date(2026, 9, 18)),
]


def _x(exec_id, conid, side, zeit, preis="10.00"):
    return dict(exec_id=exec_id, conid=conid, side=side, preis=Decimal(preis), handelszeit=zeit)


MEHRDEUTIG = [
    _x("Y1", 801, "SELL", datetime(2026, 9, 2, 11, 0)),
    _x("Y2", 802, "BUY", datetime(2026, 9, 2, 11, 0)),
    _x("Y3", 801, "BUY", datetime(2026, 9, 16, 15, 0)),
    _x("Y4", 802, "SELL", datetime(2026, 9, 16, 15, 0)),
    _x("Y5", 803, "SELL", datetime(2026, 9, 16, 15, 2)),
    _x("Y6", 804, "BUY", datetime(2026, 9, 16, 15, 2)),
    _x("Y7", 805, "SELL", datetime(2026, 9, 16, 15, 20)),
    _x("Y8", 806, "BUY", datetime(2026, 9, 16, 15, 20)),
]

DOPPELT = [
    _x("P1", 801, "SELL", datetime(2026, 9, 2, 11, 0)),
    _x("P2", 802, "BUY", datetime(2026, 9, 2, 11, 0)),
    _x("Q1", 807, "SELL", datetime(2026, 9, 3, 11, 0)),
    _x("Q2", 808, "BUY", datetime(2026, 9, 3, 11, 0)),
    _x("P3", 801, "BUY", datetime(2026, 9, 16, 15, 0)),
    _x("P4", 802, "SELL", datetime(2026, 9, 16, 15, 0)),
    _x("Q3", 807, "BUY", datetime(2026, 9, 16, 15, 1)),
    _x("Q4", 808, "SELL", datetime(2026, 9, 16, 15, 1)),
    _x("N1", 803, "SELL", datetime(2026, 9, 16, 15, 5)),
    _x("N2", 804, "BUY", datetime(2026, 9, 16, 15, 5)),
]
