# ruff: noqa: E501
"""Kostenbasis einer Kette (AP-19, Entscheidung des Nutzers 30.10.2026).

Eine Formel für alle Strategien:

    Kostenbasis = Einstand der deckenden Aktien − (realisiertes Ergebnis aller abgeschlossenen Glieder
                  + Zufluss der offenen Optionsglieder)

alles netto nach Kommission, in der Währung der Kette. Die Glieder kommen aus dem Journal; beim Wheel gehören die
Put-Prämie vor der Zuteilung, die zugeteilten Aktien und die Covered Calls zur selben Kette (AP-04z), die Put-Prämie
zählt also mit (Nutzer, Punkt 1). Ändert sich die Stückzahl (Teilverkauf), steht das Ergebnis der verkauften Lots im
realisierten Teil; geteilt wird durch die noch gehaltenen Stück — die Basis verteilt sich anteilig (Punkt 2).

- **Mit Aktien:** Kostenbasis je Aktie = Kostenbasis ÷ gehaltene Stück = Breakeven der Aktie.
- **Nur Optionen (Spread, naked, Kalender):** Netto der Kette = realisiert + offener Zufluss (Credit positiv).
  Je Einheit (÷ Kontrakte × Multiplikator) ergibt das den Breakeven am Verfall: Put Short − Netto, Call Short + Netto;
  bei einem Spread ist der höchste Verlust (Breite − Netto) × Kontrakte × Multiplikator.

Rein: keine Datenbank, nur Decimal (Regel 5). Fehlt ein Betrag, bleibt das Ergebnis leer statt still 0.
"""

from dataclasses import dataclass
from decimal import Decimal

_NULL = Decimal("0")


@dataclass(frozen=True)
class Glied:
    sequenz: int
    art: str                 # open / roll / close / zuteilung / covered_call …
    typ: str                 # BPS / BCS / Single / Stock …
    offen: bool
    # abgeschlossen: Ergebnis netto; offen: Zufluss netto (Credit positiv, Aktienkauf negativ)
    betrag: Decimal | None
    stueck: Decimal = _NULL  # offene Aktien dieses Glieds (nur typ Stock)


@dataclass(frozen=True)
class Kostenbasis:
    realisiert: Decimal | None
    praemien_offen: Decimal | None
    aktien_einstand: Decimal | None   # positiv = bezahlt
    aktien_stueck: Decimal
    netto: Decimal | None             # realisiert + offene Prämien (Credit positiv)
    kostenbasis: Decimal | None       # nur mit Aktien: Einstand − netto
    je_aktie: Decimal | None
    je_einheit: Decimal | None        # nur ohne Aktien: netto ÷ (Kontrakte × Multiplikator)
    breakeven: Decimal | None
    max_verlust: Decimal | None       # nur Spread


def _summe(werte: list[Decimal | None]) -> Decimal | None:
    if any(w is None for w in werte):
        return None
    return sum(werte, _NULL)


def kostenbasis(glieder: list[Glied], *, recht: str | None = None, short: Decimal | None = None,
                long: Decimal | None = None, kontrakte: Decimal | None = None,
                multiplikator: Decimal | None = None) -> Kostenbasis:
    """``recht``/``short``/``long``/``kontrakte``/``multiplikator`` beschreiben die offene Short-Position (für Breakeven
    und höchsten Verlust ohne Aktien)."""
    abgeschlossen = [g.betrag for g in glieder if not g.offen]
    optionen_offen = [g.betrag for g in glieder if g.offen and g.typ != "Stock"]
    aktien = [g for g in glieder if g.offen and g.typ == "Stock"]
    realisiert = _summe(abgeschlossen)
    praemien = _summe(optionen_offen)
    netto = None if realisiert is None or praemien is None else realisiert + praemien
    if aktien:
        einstand_roh = _summe([g.betrag for g in aktien])
        einstand = None if einstand_roh is None else -einstand_roh
        stueck = sum((g.stueck for g in aktien), _NULL)
        basis = None if einstand is None or netto is None else einstand - netto
        je_aktie = basis / stueck if basis is not None and stueck else None
        return Kostenbasis(realisiert, praemien, einstand, stueck, netto, basis, je_aktie, None, je_aktie, None)
    je_einheit = breakeven = max_verlust = None
    if netto is not None and kontrakte and multiplikator:
        je_einheit = netto / (kontrakte * multiplikator)
        if short is not None and recht in ("P", "C"):
            breakeven = short - je_einheit if recht == "P" else short + je_einheit
        if short is not None and long is not None and long != short:
            max_verlust = (abs(short - long) - je_einheit) * kontrakte * multiplikator
    return Kostenbasis(realisiert, praemien, None, _NULL, netto, None, None, je_einheit, breakeven, max_verlust)
