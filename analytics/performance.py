"""Wertentwicklung des Kontos (AP-08p): zeitgewichteter Index, Drawdown in Prozent
vom Höchststand, Wochen- und Monatswerte.

Ein Drawdown auf den Kontowert selbst wäre durch Einzahlungen verfälscht. Daher
ein zeitgewichteter Index wie IBs TWR:

- Tagesrendite ``r_t = (K_t − E_t) / K_{t−1}`` mit Kontowert ``K`` und den
  Einzahlungen ``E_t`` seit dem Vortag (Differenz der kumulierten
  Einzahlungen; Annahme wie AP-06h: eine Einzahlung zählt am Buchungstag schon
  in den Kontowert). Ist ``K_{t−1}`` nicht positiv, bleibt der Index stehen.
- ``Index_t = Π (1 + r)``; Basis 1 am Tag vor dem Zeitraum (sonst am ersten
  Tag). Drawdown = Index / bisheriges Hoch − 1 (Hoch einschließlich Basis).
- Gewinn laut IB je Tag = ``K_t − K_{t−1} − E_t``; je Woche (ISO, Mo–So) und
  Monat summiert; die Rendite je Periode ist Π (1 + r) − 1 über ihre Tage.
- Realisiert (Journal) je Periode = Summe der Equity-Tage (Tag der Schließung).

Rein (``performance_auswertung``) und Hülle (``performance_bericht``); alle
Werte ``Decimal``, Quoten ungerundet.
"""

import pathlib
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from analytics.equity import equity_bericht
from analytics.nav import nav_bericht

_NULL = Decimal("0")
_EINS = Decimal("1")


@dataclass(frozen=True)
class PerformanceTag:
    datum: date
    kontowert: Decimal
    gewinn_ib: Decimal          # Veränderung ohne Einzahlungen an diesem Tag
    index: Decimal
    drawdown_quote: Decimal     # ≤ 0


@dataclass(frozen=True)
class Periode:
    schluessel: str             # 'JJJJ-Www' oder 'JJJJ-MM'
    beginn: date
    ende: date
    gewinn_ib: Decimal
    realisiert: Decimal
    rendite_quote: Decimal


@dataclass(frozen=True)
class PerformanceErgebnis:
    tage: tuple[PerformanceTag, ...]
    max_drawdown_quote: Decimal
    max_drawdown_datum: date | None
    wochen: tuple[Periode, ...]
    monate: tuple[Periode, ...]
    # Realisiertes Ergebnis kumuliert je Tag mit Schließung (Equity), damit das
    # Dashboard keine zweite Abfrage braucht; im Zeitraum ab 0 (AP-08f2, Z4).
    realisiert_kumuliert: tuple[tuple[date, Decimal], ...] = ()


def _woche(tag: date) -> tuple[str, date, date]:
    jahr, woche, _ = tag.isocalendar()
    montag = tag - timedelta(days=tag.weekday())
    return f"{jahr}-W{woche:02d}", montag, montag + timedelta(days=6)


def _monat(tag: date) -> tuple[str, date, date]:
    erster = tag.replace(day=1)
    naechster = (erster + timedelta(days=32)).replace(day=1)
    return f"{tag.year:04d}-{tag.month:02d}", erster, naechster - timedelta(days=1)


def performance_auswertung(
    nav_tage: list[dict],
    equity_tage: list[dict],
    *,
    von: date | None = None,
    bis: date | None = None,
) -> PerformanceErgebnis:
    """Rein. ``nav_tage``: ``datum``, ``gesamt``, ``einzahlungen_kumuliert``
    (aufsteigend oder nicht); ``equity_tage``: ``datum``, ``netto_eur``."""
    tage_sortiert = sorted(nav_tage, key=lambda t: t["datum"])

    def im_zeitraum(tag: date) -> bool:
        return (von is None or tag >= von) and (bis is None or tag <= bis)

    tage: list[PerformanceTag] = []
    renditen: dict[date, Decimal] = {}
    gewinne: dict[date, Decimal] = {}
    index = _EINS
    hoch = _EINS
    max_dd = _NULL
    max_dd_datum: date | None = None
    vorher: dict | None = None
    for tag in tage_sortiert:
        if vorher is None:
            rendite = _EINS
            gewinn = _NULL
        else:
            einzahlung = tag["einzahlungen_kumuliert"] - vorher["einzahlungen_kumuliert"]
            gewinn = tag["gesamt"] - vorher["gesamt"] - einzahlung
            rendite = (
                (tag["gesamt"] - einzahlung) / vorher["gesamt"] if vorher["gesamt"] > 0 else _EINS
            )
        vorher = tag
        if not im_zeitraum(tag["datum"]):
            continue
        index *= rendite
        hoch = max(hoch, index)
        drawdown = index / hoch - _EINS
        if drawdown < max_dd:
            max_dd = drawdown
            max_dd_datum = tag["datum"]
        renditen[tag["datum"]] = rendite
        gewinne[tag["datum"]] = gewinn
        tage.append(PerformanceTag(
            datum=tag["datum"], kontowert=tag["gesamt"], gewinn_ib=gewinn,
            index=index, drawdown_quote=drawdown,
        ))

    realisiert: dict[date, Decimal] = {}
    for e in equity_tage:
        if im_zeitraum(e["datum"]):
            realisiert[e["datum"]] = realisiert.get(e["datum"], _NULL) + e["netto_eur"]

    def perioden(schluessel_von) -> tuple[Periode, ...]:
        sammlung: dict[str, dict] = {}
        for tag in sorted(set(renditen) | set(realisiert)):
            schluessel, beginn, ende = schluessel_von(tag)
            p = sammlung.setdefault(schluessel, dict(
                beginn=beginn, ende=ende, gewinn=_NULL, realisiert=_NULL, faktor=_EINS))
            if tag in renditen:
                p["gewinn"] += gewinne[tag]
                p["faktor"] *= renditen[tag]
            if tag in realisiert:
                p["realisiert"] += realisiert[tag]
        return tuple(
            Periode(
                schluessel=s, beginn=p["beginn"], ende=p["ende"], gewinn_ib=p["gewinn"],
                realisiert=p["realisiert"], rendite_quote=p["faktor"] - _EINS,
            )
            for s, p in sorted(sammlung.items())
        )

    return PerformanceErgebnis(
        tage=tuple(tage),
        max_drawdown_quote=max_dd,
        max_drawdown_datum=max_dd_datum,
        wochen=perioden(_woche),
        monate=perioden(_monat),
    )


def performance_bericht(
    db_pfad: str | pathlib.Path, *, von: date | None = None, bis: date | None = None
) -> PerformanceErgebnis:
    """Liest Kontowert (``nav_bericht``, ganze Historie — der Vortag des Zeitraums
    ist die Basis) und Equity; nur lesend."""
    nav = nav_bericht(db_pfad)
    nav_tage = [
        dict(datum=t.datum, gesamt=t.gesamt, einzahlungen_kumuliert=t.einzahlungen_kumuliert)
        for t in nav.tage
    ]
    equity = equity_bericht(db_pfad, von=von, bis=bis)
    equity_tage = [dict(datum=t.datum, netto_eur=t.netto_eur) for t in equity.tage]
    ergebnis = performance_auswertung(nav_tage, equity_tage, von=von, bis=bis)
    return replace(
        ergebnis, realisiert_kumuliert=tuple((t.datum, t.kumuliert_eur) for t in equity.tage)
    )
