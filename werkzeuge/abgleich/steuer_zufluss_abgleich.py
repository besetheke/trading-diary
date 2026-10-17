"""Abgleich der Steuer nach Zufluss (AP-10c) gegen das Altverfahren (AP-10), je Zuflussjahr.

Liest nur die Journal-Datenbank (nicht ``fixtures/golden/``), schreibt nichts und gibt ausschließlich Summen und
Zählwerte je Jahr aus: Altverfahren (Ergebnis im Schließungsjahr, EUR über den Buchungskurs der Schließung),
Neuverfahren (Zufluss je Zahlungsstrom), die Differenz und woraus sie sich im Wesentlichen zusammensetzt
(offene Stillhalterpositionen, Barausgleich, ausgesonderte ETFs, Datenlücken). Nachweis der Abnahme von AP-10c.

Aufruf: ``python -m werkzeuge.abgleich.steuer_zufluss_abgleich [journal.db]``.
"""

import sys
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from analytics.steuer_zufluss import TOPF_AKTIEN, TOPF_STILLHALTER, TOPF_TERMIN
from journal.db import create_db_engine
from journal.schema import legs
from journal.steuer import steuer_bericht
from journal.steuer_zufluss import steuer_zufluss_bericht

_NULL = Decimal("0")


def main(db: str = "journal.db") -> int:
    alt = steuer_bericht(db)
    neu = steuer_zufluss_bericht(db)
    with create_db_engine(db).connect() as v:
        offene_legs = {
            z[0] for z in v.execute(select(legs.c.leg_id).where(legs.c.sicht == "konto", legs.c.offen_ja_nein.is_(True)))
        }
    alt_je_jahr: dict[int, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: _NULL))
    for t in alt.toepfe:
        alt_je_jahr[t.jahr][t.topf] += t.netto_eur_ib
    neu_je_jahr = neu.jahre()
    offene_praemie: dict[int, Decimal] = defaultdict(lambda: _NULL)
    barausgleich: dict[int, Decimal] = defaultdict(lambda: _NULL)
    for s in neu.stroeme:
        if s.vorgang == "stillhalterpraemie" and s.leg_id in offene_legs:
            offene_praemie[s.jahr] += s.betrag_eur
        if s.vorgang == "barausgleich":
            barausgleich[s.jahr] += s.betrag_eur
    print("Jahr | alt Aktien | neu Aktien | alt Termin | neu Stillhalter+Termin | Differenz Stillhalter+Termin | "
          "davon offene Prämien | Barausgleich (in neu Termin) | betroffen")
    for jahr in sorted(set(alt_je_jahr) | set(neu_je_jahr)):
        a = alt_je_jahr.get(jahr, {})
        n = neu_je_jahr.get(jahr, {"toepfe": {}, "betroffen": 0})["toepfe"]

        def saldo(topf: str, n: dict = n) -> Decimal:
            return n.get(topf, {}).get("saldo", _NULL)

        neu_so = saldo(TOPF_STILLHALTER) + saldo(TOPF_TERMIN)
        alt_termin = a.get(TOPF_TERMIN, _NULL)
        print(
            f"{jahr} | {a.get(TOPF_AKTIEN, _NULL):.0f} | {saldo(TOPF_AKTIEN):.0f} | {alt_termin:.0f} | {neu_so:.0f} | "
            f"{neu_so - alt_termin:.0f} | {offene_praemie.get(jahr, _NULL):.0f} | {barausgleich.get(jahr, _NULL):.0f} | "
            f"{neu_je_jahr.get(jahr, {}).get('betroffen', 0)}"
        )
    print(f"Ströme {len(neu.stroeme)}; Datenlücken {len(neu.datenluecken)}; offene Regeln:")
    for r in neu.regeln_offen:
        print(f"  {r.art}: {r.anzahl} Fälle, {r.betrag_eur:.0f} EUR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:2]))
