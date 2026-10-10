"""Kontowert-Kurve (AP-06h): Depotwert je Tag laut IB und der Gewinn laut IB.

Vertrag ist ``auftraege/AP-06h.md``; die Abnahmetests in ``tests/test_nav.py``
sind unveränderlich. Alle Beträge ``Decimal``.

- Der Kontowert je Tag kommt unverändert aus ``flex_nav_tage`` (AP-02n) —
  realisiert und unrealisiert, Währungen zum Tageskurs, so wie IB ihn
  ausweist. Hier wird er nicht nachgerechnet.
- **Gewinn laut IB** = Kontowert − kumulierte Ein-/Auszahlungen bis
  einschließlich des Tages. Die Einzahlungen kommen aus den Cash-Buchungen
  (Kategorie ``ein_auszahlungen``, AP-06f) × fxRateToBase. Das ist die Größe,
  die sich mit dem realisierten Ergebnis des Journals vergleichen lässt (OF-78).
- Zeitraum wie die Kapitalentwicklung (AP-06g, K3): absolute Werte, gezeigt
  werden die Tage im Zeitraum; ``anfangswert`` ist der Kontowert am letzten
  Tag davor (``None``, wenn es keinen gibt).

Annahme (Regel 10): Eine Einzahlung zählt am Tag ihrer Buchung schon in den
Kontowert dieses Tages. Weicht IB davon ab, verschiebt sich der Gewinn an
diesem einen Tag, nicht in der Summe.
"""

import pathlib
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from analytics.cashflows import TYP_KATEGORIE, cash_zeilen_lesen
from journal.db import create_db_engine
from journal.schema import flex_nav_tage

_NULL = Decimal("0")


@dataclass(frozen=True)
class NavTag:
    datum: date
    gesamt: Decimal
    cash: Decimal | None
    aktien: Decimal | None
    optionen: Decimal | None
    rohstoffe: Decimal | None
    einzahlungen_kumuliert: Decimal
    gewinn: Decimal                 # gesamt − einzahlungen_kumuliert


@dataclass(frozen=True)
class NavErgebnis:
    tage: tuple[NavTag, ...]
    anfangswert: Decimal | None     # Kontowert am letzten Tag vor dem Zeitraum
    endwert: Decimal | None         # Kontowert am letzten Tag im Zeitraum
    anzahl_kurs_fehlt: int          # Ein-/Auszahlungen ohne Kurs (nicht gezählt)


def nav_auswertung(
    nav_zeilen: Iterable[dict],
    cash_zeilen: list[dict],
    *,
    von: date | None = None,
    bis: date | None = None,
) -> NavErgebnis:
    """Rein (P2). ``nav_zeilen`` tragen ``datum``, ``gesamt``, ``cash``,
    ``aktien``, ``optionen``, ``rohstoffe``."""
    if von is not None and bis is not None and von > bis:
        raise ValueError(f"Zeitraum ungültig: von {von} liegt nach bis {bis}")

    einzahlungen: list[tuple[date, Decimal]] = []
    kurs_fehlt = 0
    for c in cash_zeilen:
        if TYP_KATEGORIE.get(c["typ"]) != "ein_auszahlungen":
            continue
        if c.get("kurs") is None:
            kurs_fehlt += 1
            continue
        tag = c["datum"].date() if hasattr(c["datum"], "date") else c["datum"]
        einzahlungen.append((tag, c["betrag"] * c["kurs"]))
    einzahlungen.sort(key=lambda e: e[0])

    tage: list[NavTag] = []
    anfang: Decimal | None = None
    kumuliert = _NULL
    naechste = 0
    for z in sorted(nav_zeilen, key=lambda z: z["datum"]):
        tag = z["datum"]
        while naechste < len(einzahlungen) and einzahlungen[naechste][0] <= tag:
            kumuliert += einzahlungen[naechste][1]
            naechste += 1
        if bis is not None and tag > bis:
            break
        if von is not None and tag < von:
            anfang = z["gesamt"]
            continue
        tage.append(
            NavTag(
                datum=tag,
                gesamt=z["gesamt"],
                cash=z["cash"],
                aktien=z["aktien"],
                optionen=z["optionen"],
                rohstoffe=z["rohstoffe"],
                einzahlungen_kumuliert=kumuliert,
                gewinn=z["gesamt"] - kumuliert,
            )
        )
    return NavErgebnis(
        tage=tuple(tage),
        anfangswert=anfang,
        endwert=tage[-1].gesamt if tage else anfang,
        anzahl_kurs_fehlt=kurs_fehlt,
    )


def nav_bericht(
    db_pfad: str | pathlib.Path,
    *,
    von: date | None = None,
    bis: date | None = None,
) -> NavErgebnis:
    """Liest (P3), schreibt nichts."""
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        nav_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    flex_nav_tage.c.datum,
                    flex_nav_tage.c.gesamt,
                    flex_nav_tage.c.cash,
                    flex_nav_tage.c.aktien,
                    flex_nav_tage.c.optionen,
                    flex_nav_tage.c.rohstoffe,
                )
            ).mappings()
        ]
        cash_zeilen = cash_zeilen_lesen(verbindung)
    return nav_auswertung(nav_zeilen, cash_zeilen, von=von, bis=bis)
