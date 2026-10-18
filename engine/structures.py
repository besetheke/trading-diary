"""Legs → Structures: Zusammenfassung gemeinsam eröffneter Legs (AP-04, Teil 1).

Block A der Erkennungsreihenfolge aus §6, Abschnitt AP-04 — „Legs →
Struktur". Block B, „Strukturen → Kette" (Rolls, Zuteilungsübergang,
Override-Mechanismus, `journal rebuild`), ist eigens zu bauen
(``engine.chains``) und nicht Teil dieses Moduls. Die beiden Blöcke sind
bewusst getrennt: „gleiche Expiry" gilt **nur** für die Strukturbildung hier
— beim Verketten (Block B) wäre die Bedingung sinnwidrig, ein Roll wechselt
gerade die Expiry (Plan, 19.09.2026, nach Rückfrage präzisiert).

Block A, wie im Plan nummeriert:

- **0, Vorfilter (P7).** Nur Legs, deren eröffnende Ausführung
  ``ereignistyp == 'trade'`` trägt, nehmen an der Strukturbildung teil. Ohne
  diesen Schritt verklebt das Zeitfenster (Schritt 2) Tagesabschlussbuchungen
  über mehrere Basiswerte zu Phantomstrukturen. Legs mit anderer
  Eröffnungsart (etwa eine durch Zuteilung entstandene Aktienposition)
  werden benannt zurückgegeben, nicht stillschweigend einsortiert — ihre
  Einordnung ist Sache der Kettenbildung (Zuteilungsübergang, ``engine.chains``).
- **0a, OptionApp-Referenz.** Trägt die eröffnende Ausführung eine
  strukturierte ``orderReference`` (``oa_trade`` **und** ``oa_order``
  gesetzt — bereits von ``ingest/flex.py`` geparst, §6.1), bestimmt das Paar
  (OA-Trade, OA-Order) die Structure. Die Order-Nummer allein ist nicht
  global eindeutig; erst das Paar ist es.
- **1, ``ibExecID``-Präfix.** Ohne OA-Referenz gruppiert ``exec_batch`` (die
  ersten zwei Segmente von ``ibExecID``, bereits von ``ingest/flex.py``
  berechnet) Legs derselben Combo-Ausführung.
- **1a, Teilfills.** Mehrere Legs mit gleichem ``conid`` und gleicher
  Richtung innerhalb einer Gruppe (mehrere Fills desselben Orderbeins) werden
  zu einer Leg-Position verdichtet — die Menge wird summiert, nicht als
  eigene Position gezählt.
- **2, Zeitfenster, nur ersatzweise.** Fehlt sowohl OA-Referenz als auch
  ``exec_batch``, gilt ein Fenster von 3 Minuten bei gleichem Underlying,
  gleicher Expiry, **gegenläufigen Richtungen** und vergleichbarer Menge
  (höchstens 20 % Abweichung) — zwei getrennt ausgeführte Beine einer
  Struktur finden so zueinander. Gleicher Basiswert und gleiche Expiry sind
  Pflichtbedingung, nicht Feinschliff (§6, Beleg: acht sekundengleiche Legs
  aus zwei getrennten Orders auf SPY und XSP dürfen nicht verschmelzen).
- **3, keine Zwei-Bein-Annahme.** Structures sind nicht auf zwei Legs
  beschränkt; zwei, drei und vier kommen regulär vor (Iron Condors u. Ä.).

Frühere Fassung dieses Moduls nahm „gleiche Seite" für Schritt 2 an
(dieselbe Richtung je Cluster) — das war eine dokumentierte, an den
Golden-Daten nicht prüfbare Annahme (OF-34). Der Plan stellt seitdem klar:
Schritt 2 verlangt **gegenläufige** Richtungen, weil er zwei Beine EINER
Struktur zusammenführt, nicht mehrere unabhängige Eröffnungen. OF-34 ist
damit aufgelöst.
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
    # Schließung — nur gesetzt, wenn ALLE Legs der Structure geschlossen sind;
    # eine teilgeschlossene Structure gilt als offen (kein irreführendes
    # Teilergebnis). ``schluss_ereignistyp`` ist die Ereignisart der letzten
    # Schließung — Grundlage für den Kettenendzustand (Verfall/Zuteilung/
    # Ausübung/gewöhnlich geschlossen), den die Kettenbildung daraus ableitet.
    status: str = "offen"  # offen / geschlossen
    geschlossen_am: datetime | None = None
    schluss_ereignistyp: str | None = None
    brutto_pnl: Decimal | None = None
    kommission_gesamt: Decimal = Decimal(0)
    # Optionsrechte, die unter den Legs vorkommen ('C'/'P') — Grundlage für
    # die Seite (Call/Put) einer Kette; leer bei Aktien/Futures.
    rechte: frozenset[str] = frozenset()
    # (oa_trade, oa_order) der eröffnenden Ausführung, falls per OA-Referenz
    # gebildet — Grundlage der Kettenidentität bei OptionApp-Positionen
    # (mehrere oa_order-Werte unter demselben oa_trade sind Rolls derselben
    # Kette, AP-04 Teil 2).
    oa_trade: str | None = None
    # exec_batch der eröffnenden bzw. schließenden Ausführungen — Grundlage
    # des Kettenschritts B1 „Roll in einer Order" (engine.chains): schließt
    # eine Combo-Ausführung Legs einer Structure und eröffnet zugleich Legs
    # einer anderen, teilen sich beide denselben exec_batch. ``None``, wenn
    # nicht per exec_batch gebildet bzw. wenn die Schließung uneinheitliche
    # exec_batch-Werte trägt (keine gemeinsame Roll-Order).
    oeffnungs_exec_batch: str | None = None
    schluss_exec_batch: str | None = None
    # AP-04z: Unterscheidet Zuteilungs-Structures derselben Lieferung (je
    # Teilverkauf eine) im Naturschlüssel — sonst trügen sie dieselbe
    # open_exec_id. Nur dort gesetzt; sonst ``None`` (Schlüssel unverändert).
    schluessel_zusatz: str | None = None


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


def _leg_sortierschluessel(al: _ArbeitsLeg) -> tuple:
    """Total ordnender Schlüssel: Zeit, Basiswert, Verfall, Recht, Strike, Richtung, Menge, IDs."""
    return (
        al.handelszeit, al.underlying or "", al.expiry or date.min, al.right or "",
        al.strike if al.strike is not None else Decimal(0), al.richtung, al.menge,
        al.schluessel.open_exec_id, al.schluessel.close_exec_id or "",
    )


def _struktur_endschluessel(s) -> tuple:
    return tuple(sorted((k.open_exec_id, k.close_exec_id or "") for k in s.leg_schluessel))


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

    # Vollständiger Sortierschlüssel (AP-17f, R06): das Ergebnis darf nicht von der Reihenfolge der
    # Eingabe abhängen, auch nicht bei gleichen Zeitstempeln.
    arbeits_legs.sort(key=_leg_sortierschluessel)

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
        _structure_bilden(cluster, methode_je_gruppe[schluessel], exec_je_id)
        for schluessel, cluster in gruppen.items()
    ]
    structures.sort(key=lambda s: (s.eroeffnet_am, s.underlying, _struktur_endschluessel(s)))

    return StrukturErgebnis(
        structures=tuple(structures), nicht_strukturiert=tuple(nicht_strukturiert)
    )


def _zeitfenster_clustern(legs: list[_ArbeitsLeg]) -> list[list[_ArbeitsLeg]]:
    """Struktur-Schritt 2 (Ersatzweg A): 3-Minuten-Fenster, gleicher
    Basiswert, gleiche Expiry, **gegenläufige Richtungen**, Menge höchstens
    20 % abweichend vom Cluster-Anfang.

    Gleicher Basiswert und gleiche Expiry sind Pflichtbedingung (§6) — die
    Vorsortierung danach verhindert von vornherein jede Vermischung über
    Underlyings oder Verfallstermine hinweg. Gegenläufige Richtungen, weil
    dieser Weg zwei getrennt ausgeführte Beine EINER Struktur zusammenführt
    (z. B. ein Long-Bein aus der einen Order, das Short-Bein einer
    unmittelbar danach platzierten zweiten Order) — nicht, um mehrere
    unabhängige, gleichgerichtete Eröffnungen zu verschmelzen. Innerhalb
    einer (Underlying, Expiry)-Gruppe entscheidet die Zeit- und Mengennähe
    zum jeweils ersten Leg eines Clusters (kein Kettendrift über mehrere
    Schritte).
    """
    je_underlying_expiry: dict[tuple, list[_ArbeitsLeg]] = {}
    for al in legs:
        je_underlying_expiry.setdefault((al.underlying, al.expiry), []).append(al)

    alle_cluster: list[list[_ArbeitsLeg]] = []
    for gruppe in je_underlying_expiry.values():
        gruppe.sort(key=_leg_sortierschluessel)
        offene_cluster: list[list[_ArbeitsLeg]] = []
        for al in gruppe:
            # Mehrdeutigkeit (AP-17f, R06): passen mehrere Cluster, bekommt das Bein den Cluster
            # mit den wenigsten Beinen seiner eigenen Richtung (zwei Short + zwei Long ergeben so
            # zwei Paare statt 3 + 1); bei Gleichstand der frühere. Der Ersatzweg bleibt
            # ohnehin ein Vorschlag (erkennung = heuristik).
            ziel = None
            beste_zahl = None
            for cluster in offene_cluster:
                anker = cluster[0]
                if (
                    al.richtung != anker.richtung
                    and al.handelszeit - anker.handelszeit <= ZEITFENSTER
                    and mengen_vergleichbar(al.menge, anker.menge)
                ):
                    gleiche = sum(1 for x in cluster if x.richtung == al.richtung)
                    if beste_zahl is None or gleiche < beste_zahl:
                        ziel, beste_zahl = cluster, gleiche
            if ziel is None:
                offene_cluster.append([al])
            else:
                ziel.append(al)
        alle_cluster.extend(offene_cluster)
    return alle_cluster


def mengen_vergleichbar(a: Decimal, b: Decimal) -> bool:
    if a == 0 or b == 0:
        return a == b
    return abs(a - b) / max(a, b) <= MENGENTOLERANZ


def schliessung_bestimmen(
    cluster: list[_ArbeitsLeg], exec_je_id: Mapping[str, Mapping]
) -> tuple[str, datetime | None, str | None, Decimal | None, str | None]:
    """Schließung einer Structure — nur vollständig, wenn jedes Leg zu ist.

    Priorität der Ereignisart bei gemischten Schlüssen innerhalb einer
    Structure (etwa ein Spread, dessen kurzes Bein zugeteilt wird, während
    das lange verfällt): Zuteilung vor Ausübung vor Verfall vor gewöhnlicher
    Schließung — die folgenreichste Art gewinnt, nicht die häufigste.

    Der fünfte Rückgabewert ist der ``exec_batch`` der schließenden
    Ausführungen, wenn alle denselben tragen — Grundlage für Kettenschritt
    B1 „Roll in einer Order" (``engine.chains``): schließt dieselbe
    Combo-Ausführung zugleich eine andere Structure, teilen sich beide den
    exec_batch. ``None`` bei uneinheitlichen Werten oder wenn keiner gesetzt
    ist.
    """
    geschlossene = [al for al in cluster if al.leg.get("offen_ja_nein") is False]
    if len(geschlossene) != len(cluster):
        return "offen", None, None, None, None

    geschlossen_am = max(
        exec_je_id[al.leg["close_exec_id"]]["handelszeit"] for al in geschlossene
    )
    schluss_execs = [exec_je_id[al.leg["close_exec_id"]] for al in geschlossene]
    ereignisarten = {satz["ereignistyp"] for satz in schluss_execs}
    for vorrang in ("assignment", "exercise", "expiry", "trade"):
        if vorrang in ereignisarten:
            schluss_ereignistyp = vorrang
            break
    else:
        schluss_ereignistyp = next(iter(ereignisarten))

    schluss_batches = {satz.get("exec_batch") for satz in schluss_execs}
    schluss_exec_batch = next(iter(schluss_batches)) if len(schluss_batches) == 1 else None

    brutto_pnl = sum(
        (al.leg["brutto_pnl"] for al in geschlossene if al.leg.get("brutto_pnl") is not None),
        Decimal(0),
    )
    return "geschlossen", geschlossen_am, schluss_ereignistyp, brutto_pnl, schluss_exec_batch


def _structure_bilden(
    cluster: list[_ArbeitsLeg], methode: str, exec_je_id: Mapping[str, Mapping]
) -> Structure:
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

    status, geschlossen_am, schluss_ereignistyp, brutto_pnl, schluss_exec_batch = (
        schliessung_bestimmen(cluster, exec_je_id)
    )
    kommission_gesamt = sum(
        (al.leg["kommission_gesamt"] for al in cluster), Decimal(0)
    )
    rechte = frozenset(al.right for al in cluster if al.right)
    oa_trade = erste.oa_trade if methode == "oa" else None
    oeffnungs_exec_batch = erste.exec_batch if methode == "exec_batch" else None

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
        status=status,
        geschlossen_am=geschlossen_am,
        schluss_ereignistyp=schluss_ereignistyp,
        brutto_pnl=brutto_pnl,
        kommission_gesamt=kommission_gesamt,
        rechte=rechte,
        oa_trade=oa_trade,
        oeffnungs_exec_batch=oeffnungs_exec_batch,
        schluss_exec_batch=schluss_exec_batch,
    )


def _typ_klassifizieren(
    cluster: list[_ArbeitsLeg],
) -> tuple[str, Decimal | None, Decimal | None, Decimal | None, date | None]:
    """Ordnet eine Structure ihrem Typ zu — BCS (Call-Credit) und BPS (Put-Credit) nur für den
    genauen Zwei-Bein-Fall, sonst Vertical/Custom/Single/Stock/Future.

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
            # Credit-Spreads: Put-Credit (BPS) hat den Short am höheren, Call-Credit (BCS) den Short
            # am niedrigeren Strike; Debit-Spreads beider Arten bleiben Vertical (AP-17b, R05).
            if recht == "C" and long_al.strike > short_al.strike:
                typ = "BCS"
            elif recht == "P" and long_al.strike < short_al.strike:
                typ = "BPS"
            else:
                typ = "Vertical"
            return typ, short_al.strike, long_al.strike, breite, expiry
        return "Vertical", None, None, None, expiry

    return "Custom", None, None, None, expiry
