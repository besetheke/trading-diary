"""Kapitalentwicklung, realisiert (AP-06g).

Vertrag ist ``auftraege/AP-06g.md``; die Abnahmetests in
``tests/test_kapital.py`` sind unveränderlich. Alle Beträge ``Decimal``.

Kapital = Ein-/Auszahlungen + realisiertes Ergebnis + Cash-Posten
(Dividenden, Quellensteuer, Zinsen, Gebühren, Kommissionsanpassungen,
Sonstiges). Das realisierte Ergebnis kommt aus der Equity-Kurve (AP-06e);
Kommissionen und Barausgleich stecken darin und zählen nicht ein zweites
Mal (AP-06f, C3). Kategorien der Cash-Buchungen wie in AP-06f
(``TYP_KATEGORIE``).

**Realisiert, nicht NAV:** Unrealisierte Gewinne und Verluste offener
Positionen fehlen — die Datenbank kennt keinen täglichen Kontowert. Die
Kurve zeigt, was durch Einzahlungen, abgeschlossene Geschäfte und
Cash-Posten tatsächlich geflossen ist.

Zeitraum: Kapital ist ein Bestand. Die Tagesreihe trägt die absoluten,
seit Beginn kumulierten Werte, gezeigt werden die Tage im Zeitraum (beide
Enden einschließlich). ``anfangskapital`` ist der Stand am Ende des letzten
Ereignistags vor dem Zeitraum, ``endkapital`` der Stand am letzten
Ereignistag im Zeitraum (ohne Ereignis: wie der Anfang). Die Veränderung im
Zeitraum ist nach Einzahlungen, Ergebnis und Cash aufgeteilt.
"""

import pathlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from analytics.cashflows import TYP_KATEGORIE, cash_zeilen_lesen
from analytics.equity import EquityTag, equity_bericht
from journal.db import create_db_engine

_NULL = Decimal("0")


@dataclass(frozen=True)
class KapitalTag:
    datum: date
    einzahlungen_kumuliert: Decimal
    ergebnis_kumuliert: Decimal
    cash_kumuliert: Decimal
    kapital: Decimal


@dataclass(frozen=True)
class KapitalErgebnis:
    tage: tuple[KapitalTag, ...]
    anfangskapital: Decimal
    endkapital: Decimal
    einzahlungen_im_zeitraum: Decimal
    ergebnis_im_zeitraum: Decimal
    cash_im_zeitraum: Decimal
    anzahl_kurs_fehlt: int           # Cash-Buchungen im Zeitraum ohne Kurs


def kapital_auswertung(
    equity_tage: Iterable[EquityTag],
    cash_zeilen: list[dict],
    *,
    von: date | None = None,
    bis: date | None = None,
) -> KapitalErgebnis:
    """Rein (P2). ``equity_tage`` müssen die **gesamte** Historie abdecken
    (Equity ohne Zeitraum) — sonst fehlte der Bestand vor dem Zeitraum."""
    if von is not None and bis is not None and von > bis:
        raise ValueError(f"Zeitraum ungültig: von {von} liegt nach bis {bis}")

    def im_zeitraum(tag: date) -> bool:
        return (von is None or tag >= von) and (bis is None or tag <= bis)

    einzahlung_je_tag: dict[date, Decimal] = {}
    ergebnis_je_tag: dict[date, Decimal] = {}
    cash_je_tag: dict[date, Decimal] = {}
    kurs_fehlt = 0

    for t in equity_tage:
        ergebnis_je_tag[t.datum] = ergebnis_je_tag.get(t.datum, _NULL) + t.netto_eur

    for c in cash_zeilen:
        tag = c["datum"].date() if hasattr(c["datum"], "date") else c["datum"]
        if c.get("kurs") is None:
            if im_zeitraum(tag):
                kurs_fehlt += 1
            continue
        betrag = c["betrag"] * c["kurs"]
        if TYP_KATEGORIE.get(c["typ"]) == "ein_auszahlungen":
            einzahlung_je_tag[tag] = einzahlung_je_tag.get(tag, _NULL) + betrag
        else:
            cash_je_tag[tag] = cash_je_tag.get(tag, _NULL) + betrag

    einz = erg = cash = _NULL
    # Stand am Ende des letzten Tages vor dem Zeitraum (je Bestandteil).
    vor_einz = vor_erg = vor_cash = _NULL
    tage: list[KapitalTag] = []
    for tag in sorted(set(einzahlung_je_tag) | set(ergebnis_je_tag) | set(cash_je_tag)):
        if bis is not None and tag > bis:
            break
        einz += einzahlung_je_tag.get(tag, _NULL)
        erg += ergebnis_je_tag.get(tag, _NULL)
        cash += cash_je_tag.get(tag, _NULL)
        if not im_zeitraum(tag):  # hierher kommen nur Tage vor dem Zeitraum
            vor_einz, vor_erg, vor_cash = einz, erg, cash
            continue
        tage.append(
            KapitalTag(
                datum=tag,
                einzahlungen_kumuliert=einz,
                ergebnis_kumuliert=erg,
                cash_kumuliert=cash,
                kapital=einz + erg + cash,
            )
        )

    return KapitalErgebnis(
        tage=tuple(tage),
        anfangskapital=vor_einz + vor_erg + vor_cash,
        endkapital=einz + erg + cash,
        einzahlungen_im_zeitraum=einz - vor_einz,
        ergebnis_im_zeitraum=erg - vor_erg,
        cash_im_zeitraum=cash - vor_cash,
        anzahl_kurs_fehlt=kurs_fehlt,
    )


def kapital_bericht(
    db_pfad: str | pathlib.Path,
    *,
    von: date | None = None,
    bis: date | None = None,
) -> KapitalErgebnis:
    """Liest (P3), schreibt nichts. Die Equity läuft über die ganze Historie
    (siehe ``kapital_auswertung``)."""
    equity = equity_bericht(db_pfad)
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        cash_zeilen = cash_zeilen_lesen(verbindung)
    return kapital_auswertung(equity.tage, cash_zeilen, von=von, bis=bis)
