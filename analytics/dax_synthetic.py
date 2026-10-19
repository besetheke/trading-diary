# ruff: noqa: E501
"""DAX Synthetic erkennen und auswerten (Nutzernotiz 19.10.2026).

Die Strategie besteht aus drei Bausteinen auf dem DAX (alles EUR):
  1. Long-Future (FDAX), vor Verfall auf den nächsten Kontrakt gerollt           → Baustein ``future``
  2. Long-Put mit langer Laufzeit (rund 1,5 Jahre) als Absicherung               → Baustein ``schutz_put``
  3. Short-Call auf eine Woche, leicht im Geld, immer wieder gerollt             → Baustein ``short_call``
Future + Long-Put ist synthetisch ein Long-Call, der Short-Call darauf ergibt eine Art Covered Call.

**Erkennung ist ein Vorschlag, keine Tatsache** (Regel 7): sie arbeitet auf Legs der Kontosicht und ordnet nach festen
Merkmalen zu (Annahmen, OF-103): Schutz-Put = gekaufter Put mit mindestens ``SCHUTZ_PUT_MIN_DTE`` Tagen Restlaufzeit bei
Eröffnung; Short-Call = **nackter** (Struktur ``Single``) verkaufter Call mit höchstens ``SHORT_CALL_MAX_DTE`` Tagen
Restlaufzeit — Short-Beine von Spreads und Condors anderer Strategien (BCS, Custom, Vertical) gehören nicht dazu.
Alles andere auf dem DAX bleibt ``sonstige`` und fließt nicht ein. Rein: keine Datenbank, keine Uhr (der Stichtag kommt als Parameter).
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

SCHUTZ_PUT_MIN_DTE = 180
SHORT_CALL_MAX_DTE = 14

BAUSTEINE = ("future", "schutz_put", "short_call")


@dataclass(frozen=True)
class Baustein:
    art: str
    anzahl: int = 0
    offen: int = 0
    kontrakte: Decimal = Decimal(0)     # Summe der Mengen aller Legs
    brutto: Decimal = Decimal(0)
    kommission: Decimal = Decimal(0)

    @property
    def netto(self) -> Decimal:
        return self.brutto + self.kommission


@dataclass(frozen=True)
class SyntheticEinheit:
    """Ein Schutz-Put und alles, was in seiner Haltezeit realisiert wurde."""
    put_leg_id: int
    strike: Decimal
    verfall: date
    eroeffnet: datetime
    beendet: datetime | None
    ergebnis: dict = field(default_factory=dict)       # Baustein -> Netto im Zeitraum (Schließung im Zeitraum)


@dataclass(frozen=True)
class SyntheticErgebnis:
    bausteine: tuple[Baustein, ...]
    einheiten: tuple[SyntheticEinheit, ...]
    aktiv_von: datetime | None        # erster Zeitpunkt mit Long-Future UND Schutz-Put gleichzeitig
    aktiv_bis: datetime | None        # None = bis heute
    sonstige: int
    trades: tuple[dict, ...] = ()     # jedes zugeordnete Leg einzeln, nach Eröffnung sortiert (Feld ``baustein``)


def klassifiziere(leg: dict) -> str | None:
    """Baustein eines Legs (Zeilen mit asset_class, right, side, eroeffnet, expiry) oder None."""
    dte = (leg["expiry"] - leg["eroeffnet"].date()).days if leg.get("expiry") else None
    if leg["asset_class"] == "FUT":
        return "future" if leg["side"] == "BUY" else None
    if leg["asset_class"] != "OPT" or dte is None:
        return None
    if leg["right"] == "P" and leg["side"] == "BUY" and dte >= SCHUTZ_PUT_MIN_DTE:
        return "schutz_put"
    if (leg["right"] == "C" and leg["side"] == "SELL" and dte <= SHORT_CALL_MAX_DTE
            and leg.get("struktur_typ") == "Single"):
        return "short_call"
    return None


def _ende(leg: dict, stichtag: datetime) -> datetime:
    return leg["beendet"] or stichtag


def dax_synthetic_auswertung(legs: list[dict], stichtag: datetime) -> SyntheticErgebnis:
    """``legs``: DAX-Legs der Kontosicht mit leg_id, asset_class, right, side (Eröffnung), eroeffnet, beendet (None =
    offen), expiry, strike, brutto, kommission (None bei offenen Legs zählt als 0)."""
    je_art: dict[str, list[dict]] = {a: [] for a in BAUSTEINE}
    sonstige = 0
    for leg in legs:
        art = klassifiziere(leg)
        if art is None:
            sonstige += 1
        else:
            je_art[art].append(leg)

    bausteine = tuple(
        Baustein(
            art=a, anzahl=len(ls), offen=sum(1 for x in ls if x["beendet"] is None),
            kontrakte=sum((x.get("menge") or Decimal(0) for x in ls), Decimal(0)),
            brutto=sum((x["brutto"] or Decimal(0) for x in ls), Decimal(0)),
            kommission=sum((x["kommission"] or Decimal(0) for x in ls), Decimal(0)),
        )
        for a, ls in je_art.items()
    )

    einheiten = []
    for put in sorted(je_art["schutz_put"], key=lambda x: (x["eroeffnet"], x["leg_id"])):
        von, bis = put["eroeffnet"], _ende(put, stichtag)
        ergebnis = {}
        for a in BAUSTEINE:
            ergebnis[a] = sum(
                ((x["brutto"] or Decimal(0)) + (x["kommission"] or Decimal(0))
                 for x in je_art[a] if x["beendet"] is not None and von <= x["beendet"] <= bis),
                Decimal(0),
            )
        einheiten.append(SyntheticEinheit(put["leg_id"], put["strike"], put["expiry"], von, put["beendet"], ergebnis))

    # Aktiv: Zeiträume, in denen mindestens ein Long-Future und ein Schutz-Put zugleich gehalten werden.
    aktiv: list[tuple[datetime, datetime]] = []
    for f in je_art["future"]:
        for p in je_art["schutz_put"]:
            von, bis = max(f["eroeffnet"], p["eroeffnet"]), min(_ende(f, stichtag), _ende(p, stichtag))
            if von < bis:
                aktiv.append((von, bis))
    aktiv_von = min((a for a, _ in aktiv), default=None)
    offen = any(f["beendet"] is None for f in je_art["future"]) and any(p["beendet"] is None for p in je_art["schutz_put"])
    aktiv_bis = None if offen else max((b for _, b in aktiv), default=None)
    trades = tuple(
        {**x, "baustein": a} for a in BAUSTEINE for x in je_art[a]
    )
    trades = tuple(sorted(trades, key=lambda x: (x["eroeffnet"], x["leg_id"])))
    return SyntheticErgebnis(bausteine, tuple(einheiten), aktiv_von, aktiv_bis, sonstige, trades)


def dax_synthetic_bericht(db_pfad, stichtag: datetime) -> SyntheticErgebnis:
    """Liest die DAX-Legs der Kontosicht (nur lesend) und wertet sie aus; ``stichtag`` ersetzt „jetzt“."""
    from sqlalchemy import select
    from sqlalchemy.orm import aliased

    from journal.db import create_db_engine
    from journal.schema import executions, instruments, legs, structures

    eo, ec = aliased(executions), aliased(executions)
    engine = create_db_engine(db_pfad)
    with engine.connect() as v:
        zeilen = v.execute(
            select(
                legs.c.leg_id, legs.c.menge, structures.c.typ.label("struktur_typ"),
                instruments.c.asset_class, instruments.c.right, instruments.c.expiry,
                instruments.c.strike, eo.c.side, eo.c.handelszeit.label("eroeffnet"),
                ec.c.handelszeit.label("beendet"), legs.c.brutto_pnl.label("brutto"),
                legs.c.kommission_gesamt.label("kommission"),
            )
            .join(eo, eo.c.exec_id == legs.c.open_exec_id)
            .join(instruments, instruments.c.conid == legs.c.conid)
            .outerjoin(ec, ec.c.exec_id == legs.c.close_exec_id)
            .outerjoin(structures, structures.c.structure_id == legs.c.structure_id)
            .where(legs.c.sicht == "konto", instruments.c.underlying == "DAX")
        ).mappings().all()
    return dax_synthetic_auswertung([dict(z) for z in zeilen], stichtag)
