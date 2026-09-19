"""Legs → Structures: Zusammenfassung gemeinsam eröffneter Legs (AP-04, Teil 1).

Erste Hälfte der Erkennungsreihenfolge aus §6, Abschnitt AP-04 — „Legs →
Positionen". Die zweite Hälfte, „Positionen → Ketten" (Zuteilungsübergang,
Futures-Rolls, Override-Mechanismus, `journal rebuild`), ist eigens zu
bauen und nicht Teil dieses Moduls.

Erkennungsreihenfolge, wie im Plan nummeriert:

- **0, Vorfilter (P7).** Nur Legs, deren eröffnende Ausführung
  ``ereignistyp == 'trade'`` trägt, nehmen an der Strukturbildung teil. Ohne
  diesen Schritt verklebt das Zeitfenster (Schritt 2) Tagesabschlussbuchungen
  über mehrere Basiswerte zu Phantomstrukturen. Legs mit anderer
  Eröffnungsart (etwa eine durch Zuteilung entstandene Aktienposition)
  werden benannt zurückgegeben, nicht stillschweigend einsortiert — ihre
  Einordnung ist Sache der Kettenbildung (Zuteilungsübergang, AP-04 Teil 2).
- **0a, höchste Priorität: OptionApp-Referenz.** Trägt die eröffnende
  Ausführung eine strukturierte ``orderReference`` (``oa_trade`` **und**
  ``oa_order`` gesetzt — bereits von ``ingest/flex.py`` geparst, §6.1),
  bestimmt das Paar (OA-Trade, OA-Order) die Structure. Die Order-Nummer
  allein ist nicht global eindeutig; erst das Paar ist es.
- **1, primär: Ausführungsidentität.** Ohne OA-Referenz gruppiert
  ``exec_batch`` (die ersten zwei Segmente von ``ibExecID``, bereits von
  ``ingest/flex.py`` berechnet) Legs derselben Combo-Ausführung.
- **1a, Teilfills.** Mehrere Legs mit gleichem ``conid`` und gleicher
  Richtung innerhalb einer Gruppe (mehrere Fills desselben Orderbeins) werden
  zu einer Leg-Position verdichtet — die Menge wird summiert, nicht als
  eigene Position gezählt.
- **2, sekundär: Zeitfenster.** Fehlt sowohl OA-Referenz als auch
  ``exec_batch``, gilt ein Fenster von 3 Minuten bei gleichem Underlying,
  gleicher Expiry und vergleichbarer Menge (höchstens 20 % Abweichung).
  Gleicher Basiswert und gleiche Expiry sind Pflichtbedingung, nicht
  Feinschliff (§6, Beleg: acht sekundengleiche Legs aus zwei getrennten
  Orders auf SPY und XSP dürfen nicht verschmelzen).

**Offene Annahme (Regel 10, siehe OFFENE_FRAGEN.md OF-34):** Das Plan-Wort
„gleicher Seite" für Schritt 2 ist nicht eindeutig — eine Structure aus
gegenläufigen Legs (z. B. ein Vertical) hat per Definition keine einheitliche
``side``. Angenommen: „gleiche Seite" gilt je Leg-Paar, das über das
Zeitfenster gruppiert wird, nicht über die ganze entstehende Structure —
zwei Legs mit identischem ``side`` können einander im Zeitfenster finden,
ein drittes mit anderer Seite bildet einen eigenen Cluster, sofern nicht
über ``exec_batch``/OA bereits verbunden. Diese Annahme ist an den
Golden-Daten nicht prüfbar: Keine einzige Ausführung dort braucht das
Zeitfenster (alle 24.902 Handelszeilen tragen entweder eine OA-Referenz oder
``exec_batch``).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

RICHTUNGEN = {"BUY": 1, "SELL": -1}

# Konfigurierbare Werte des Zeitfenster-Verfahrens (§6, Schritt 2) — als
# benannte Konstanten im Modul, nicht in der DB, damit ein Lauf gegen
# Fixtures deterministisch bleibt (AP-04-Vorgabe).
ZEITFENSTER = timedelta(minutes=3)
MENGENTOLERANZ = Decimal("0.20")

# ---------------------------------------------------------------------------
# Ergebnis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegSchluessel:
    """Identifiziert ein Leg ohne DB-Bezug — dieselben Felder wie
    ``engine.matching.Leg`` trägt, nur die zur Identität nötigen."""

    open_exec_id: str
    close_exec_id: str | None


@dataclass(frozen=True)
class Structure:
    """Eine Gruppe gemeinsam eröffneter Legs — eine Combo-Order oder ein
    per Zeitfenster erkannter gemeinsamer Einstieg.

    ``leg_schluessel`` referenziert die eingehenden Legs über
    ``open_exec_id``/``close_exec_id`` (wie ``engine.matching.Leg``), nicht
    über einen DB-``leg_id`` — die Zuordnung zur Datenbank ist Sache der
    Persistenz, nicht dieses reinen Moduls.
    """

    leg_schluessel: tuple[LegSchluessel, ...]
    asset_class: str
    typ: str  # BCS / BPS / Vertical / Single / Stock / Future / Custom
    underlying: str
    expiry: date | None
    short_strike: Decimal | None
    long_strike: Decimal | None
    breite: Decimal | None
    menge: Decimal
    eroeffnet_am: datetime
    dte_bei_eroeffnung: int | None
    methode: str  # oa / exec_batch / zeitfenster
    erkennung: str  # auto / heuristik (CLAUDE.md Regel 7)


@dataclass(frozen=True)
class NichtStrukturiert:
    """Ein Leg, das nicht an der Strukturbildung teilnimmt — benannt, nicht
    verworfen. Seine Einordnung (etwa ein Zuteilungsübergang) ist Sache der
    Kettenbildung."""

    leg_schluessel: LegSchluessel
    grund: str


@dataclass(frozen=True)
class StrukturErgebnis:
    structures: tuple[Structure, ...]
    nicht_strukturiert: tuple[NichtStrukturiert, ...]


# ---------------------------------------------------------------------------
# Internes Arbeitsobjekt: ein Leg mit den zur Gruppierung nötigen Angaben
# aus seiner eröffnenden Ausführung
# ---------------------------------------------------------------------------


@dataclass
class _ArbeitsLeg:
    leg: Mapping
    schluessel: LegSchluessel
    conid: int
    menge: Decimal
    richtung: int
    handelszeit: datetime
    asset_class: str
    underlying: str
    expiry: date | None
    strike: Decimal | None
    right: str | None
    oa_trade: str | None
    oa_order: str | None
    exec_batch: str | None


def _datum(zeit) -> date:
    return zeit.date() if isinstance(zeit, datetime) else zeit


def bilde_structures(
    legs: Iterable[Mapping],
    executions: Iterable[Mapping],
    instruments: Mapping[int, Mapping],
) -> StrukturErgebnis:
    """Bildet Structures aus Legs nach der Erkennungsreihenfolge (§6, AP-04).

    ``legs`` trägt die Spalten von ``engine.matching.Leg`` (oder gleichwertig:
    ``conid``, ``open_exec_id``, ``close_exec_id``, ``menge``), ``executions``
    die Spalten aus §5 (insbesondere ``ereignistyp``, ``side``, ``handelszeit``,
    ``exec_batch``, ``oa_trade``, ``oa_order``), ``instruments`` ist nach
    ``conid`` verschlüsselt.
    """
    exec_je_id = {satz["exec_id"]: satz for satz in executions}

    arbeits_legs: list[_ArbeitsLeg] = []
    nicht_strukturiert: list[NichtStrukturiert] = []

    for leg in legs:
        schluessel = LegSchluessel(
            open_exec_id=leg["open_exec_id"], close_exec_id=leg.get("close_exec_id")
        )
        oeffnung = exec_je_id.get(leg["open_exec_id"])
        if oeffnung is None:
            nicht_strukturiert.append(
                NichtStrukturiert(
                    schluessel,
                    f"eröffnende Ausführung {leg['open_exec_id']} nicht gefunden",
                )
            )
            continue
        if oeffnung["ereignistyp"] != "trade":
            nicht_strukturiert.append(
                NichtStrukturiert(
                    schluessel,
                    f"eröffnet durch ereignistyp {oeffnung['ereignistyp']!r}, "
                    "nicht 'trade' (P7) — Einordnung ist Sache der Kettenbildung",
                )
            )
            continue
        instrument = instruments.get(leg["conid"])
        if instrument is None:
            nicht_strukturiert.append(
                NichtStrukturiert(
                    schluessel, f"keine Instrumentenzeile zu conid {leg['conid']}"
                )
            )
            continue
        side = oeffnung["side"]
        if side not in RICHTUNGEN:
            nicht_strukturiert.append(
                NichtStrukturiert(schluessel, f"unbekannte side {side!r} an der Eröffnung")
            )
            continue
        arbeits_legs.append(
            _ArbeitsLeg(
                leg=leg,
                schluessel=schluessel,
                conid=leg["conid"],
                menge=leg["menge"],
                richtung=RICHTUNGEN[side],
                handelszeit=oeffnung["handelszeit"],
                asset_class=instrument.get("asset_class"),
                underlying=instrument.get("underlying") or instrument.get("symbol"),
                expiry=instrument.get("expiry"),
                strike=instrument.get("strike"),
                right=instrument.get("right"),
                oa_trade=oeffnung.get("oa_trade"),
                oa_order=oeffnung.get("oa_order"),
                exec_batch=oeffnung.get("exec_batch"),
            )
        )

    gruppen: dict[tuple, list[_ArbeitsLeg]] = {}
    methode_je_gruppe: dict[tuple, str] = {}
    ohne_schluessel: list[_ArbeitsLeg] = []

    for al in arbeits_legs:
        if al.oa_trade and al.oa_order:
            schluessel = ("oa", al.oa_trade, al.oa_order)
            methode = "oa"
        elif al.exec_batch:
            schluessel = ("batch", al.exec_batch)
            methode = "exec_batch"
        else:
            ohne_schluessel.append(al)
            continue
        gruppen.setdefault(schluessel, []).append(al)
        methode_je_gruppe[schluessel] = methode

    zeitfenster_gruppen = _zeitfenster_clustern(ohne_schluessel)
    for index, cluster in enumerate(zeitfenster_gruppen):
        schluessel = ("zeitfenster", index)
        gruppen[schluessel] = cluster
        methode_je_gruppe[schluessel] = "zeitfenster"

    structures = [
        _structure_bilden(cluster, methode_je_gruppe[schluessel])
        for schluessel, cluster in gruppen.items()
    ]
    structures.sort(key=lambda s: (s.eroeffnet_am, s.underlying))

    return StrukturErgebnis(
        structures=tuple(structures), nicht_strukturiert=tuple(nicht_strukturiert)
    )


def _zeitfenster_clustern(legs: list[_ArbeitsLeg]) -> list[list[_ArbeitsLeg]]:
    """Schritt 2: 3-Minuten-Fenster, gleicher Basiswert, gleiche Expiry,
    gleiche Seite je Paar, Menge höchstens 20 % abweichend vom Cluster-Anfang.

    Gleicher Basiswert und gleiche Expiry sind Pflichtbedingung (§6) — die
    Vorsortierung danach verhindert von vornherein jede Vermischung über
    Underlyings oder Verfallstermine hinweg. Innerhalb einer
    (Underlying, Expiry)-Gruppe entscheidet die Zeit- und Mengennähe zum
    jeweils ersten Leg eines Clusters (kein Kettendrift über mehrere Schritte).
    """
    je_underlying_expiry: dict[tuple, list[_ArbeitsLeg]] = {}
    for al in legs:
        je_underlying_expiry.setdefault((al.underlying, al.expiry), []).append(al)

    alle_cluster: list[list[_ArbeitsLeg]] = []
    for gruppe in je_underlying_expiry.values():
        gruppe.sort(key=lambda al: al.handelszeit)
        offene_cluster: list[list[_ArbeitsLeg]] = []
        for al in gruppe:
            ziel = None
            for cluster in offene_cluster:
                anker = cluster[0]
                if (
                    al.richtung == anker.richtung
                    and al.handelszeit - anker.handelszeit <= ZEITFENSTER
                    and _mengen_vergleichbar(al.menge, anker.menge)
                ):
                    ziel = cluster
                    break
            if ziel is None:
                offene_cluster.append([al])
            else:
                ziel.append(al)
        alle_cluster.extend(offene_cluster)
    return alle_cluster


def _mengen_vergleichbar(a: Decimal, b: Decimal) -> bool:
    if a == 0 or b == 0:
        return a == b
    return abs(a - b) / max(a, b) <= MENGENTOLERANZ


def _structure_bilden(cluster: list[_ArbeitsLeg], methode: str) -> Structure:
    """Schritt 1a: mehrere Legs mit gleichem conid und gleicher Richtung
    (mehrere Fills desselben Orderbeins) verdichten sich über die Summe der
    Menge — sie werden hier nicht zu getrennten Beinen der Structure."""
    verdichtet: dict[tuple[int, int], Decimal] = {}
    for al in cluster:
        schluessel = (al.conid, al.richtung)
        verdichtet[schluessel] = verdichtet.get(schluessel, Decimal(0)) + al.menge

    erste = cluster[0]
    asset_classes = {al.asset_class for al in cluster}
    asset_class = erste.asset_class if len(asset_classes) == 1 else "Custom"
    underlying = erste.underlying
    eroeffnet_am = min(al.handelszeit for al in cluster)

    typ, short_strike, long_strike, breite, expiry = _typ_klassifizieren(cluster)

    # Größe der Structure: die kleinste verdichtete Beinmenge (Regel 10 — bei
    # einem Ratio-Spread mit ungleichen Beinmengen ist „die" Structure-Größe
    # nicht eindeutig definiert; das Minimum ist die konservative Annahme,
    # nicht als allgemeingültige Regel hergeleitet).
    menge = min(verdichtet.values(), default=Decimal(0))
    dte = None
    if expiry is not None:
        dte = (expiry - _datum(eroeffnet_am)).days

    leg_schluessel = tuple(
        sorted(
            (al.schluessel for al in cluster),
            key=lambda s: (s.open_exec_id, s.close_exec_id or ""),
        )
    )

    return Structure(
        leg_schluessel=leg_schluessel,
        asset_class=asset_class,
        typ=typ,
        underlying=underlying,
        expiry=expiry,
        short_strike=short_strike,
        long_strike=long_strike,
        breite=breite,
        menge=menge,
        eroeffnet_am=eroeffnet_am,
        dte_bei_eroeffnung=dte,
        methode=methode,
        erkennung="auto",
    )


def _typ_klassifizieren(
    cluster: list[_ArbeitsLeg],
) -> tuple[str, Decimal | None, Decimal | None, Decimal | None, date | None]:
    """Ordnet eine Structure ihrem Typ zu — BCS/BPS nur für den genauen
    Zwei-Bein-Fall, sonst Vertical/Custom/Single/Stock/Future.

    Kein Rateversuch bei mehr als zwei distinkten Instrumenten: Iron Condors
    und andere Mehrbein-Gebilde sind ``Custom``, nicht auf zwei Legs
    zurechtgestutzt (§6, Pflichttest).
    """
    asset_classes = {al.asset_class for al in cluster}
    if asset_classes == {"STK"}:
        return "Stock", None, None, None, None
    if asset_classes == {"FUT"}:
        return "Future", None, None, None, None

    distinkte_instrumente = {(al.strike, al.right, al.expiry) for al in cluster}
    expiries = {al.expiry for al in cluster}
    expiry = next(iter(expiries)) if len(expiries) == 1 else None

    if len(distinkte_instrumente) == 1:
        al = cluster[0]
        return "Single", None, None, None, al.expiry

    if len(distinkte_instrumente) == 2 and len(expiries) == 1:
        rechte = {al.right for al in cluster}
        richtungen = {al.richtung for al in cluster}
        if len(rechte) == 1 and richtungen == {1, -1}:
            long_al = next(al for al in cluster if al.richtung == 1)
            short_al = next(al for al in cluster if al.richtung == -1)
            breite = abs(short_al.strike - long_al.strike)
            recht = next(iter(rechte))
            if recht == "C" and long_al.strike < short_al.strike:
                typ = "BCS"
            elif recht == "P" and long_al.strike < short_al.strike:
                typ = "BPS"
            else:
                typ = "Vertical"
            return typ, short_al.strike, long_al.strike, breite, expiry
        return "Vertical", None, None, None, expiry

    return "Custom", None, None, None, expiry
