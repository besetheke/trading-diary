"""Leg-Matching: Ausführungen → Legs mit realisiertem Brutto-P&L (AP-03).

FIFO je ``conid`` über alle Ereignisarten, die die Position verändern —
``trade``, ``expiry``, ``exercise``, ``assignment`` (§1.4); ein Verfall
schließt zum Preis seiner Ereigniszeile, in der Regel 0. Zeilen mit einem
anderen ``ereignistyp`` (derzeit ``unbekannt``, OF-16) nehmen nicht teil und
werden unter ``nicht_gematcht`` mit Grund gemeldet — nichts wird still
verworfen.

Grundsätze:

- **Rein (P2).** Keine Datenbank, kein Netz, keine Uhr, kein Zufall. Zeit
  kommt als Parameter herein; gleiche Eingabe liefert bitgleiche Ausgabe,
  auch bei anderer Eingabereihenfolge — maßgeblich ist die Handelszeit, bei
  gleicher Zeit die ``exec_id``.
- **Kein Standardwert.** Fehlt die Instrumentenzeile oder der
  ``multiplikator``, endet der Lauf mit ``ValueError`` unter Nennung des
  ``conid``. Der ``tickwert`` ist Berichtsgröße und geht nicht in den P&L
  ein, auch nicht, wo er gesetzt ist (OF-14).
- **Zentgenau (Regel 5).** Alle Beträge und Mengen sind ``Decimal``,
  niemals float. Der Brutto-P&L wird auf den Cent gerundet
  (``ROUND_HALF_UP``); die Kommission einer Ausführung wird nach Menge auf
  ihre Teilmengen verteilt, und die letzte Teilmenge erhält den Rundungsrest
  — die Summe über alle Legs eines ``conid`` ist damit exakt die Summe der
  gebuchten Kommissionen.
- **Kapitalmaßnahmen vor dem Matching.** Ausführungen vor dem Stichtag
  werden angepasst: Menge × Faktor, Preis ÷ Faktor. Eine Ausführung am
  Stichtag selbst gilt bereits zu neuen Konditionen (OF-15). Die Kommission
  bleibt, wie gebucht — sie hängt nicht an der Stückzahl des Splits.

Das Persistieren nach ``legs`` ist nicht Teil dieses Moduls. Der verbindliche
Vertrag steht in ``auftraege/AP-03.md`` unter „Vertrag an die Umsetzung".
"""

from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

# Ereignisarten, die Positionen verändern und am Matching teilnehmen (§1.4).
# 'unbekannt' (Ereigniscode P, OF-07) gehört nicht dazu (OF-16).
MATCHENDE_EREIGNISTYPEN = frozenset({"trade", "expiry", "exercise", "assignment"})

# Richtung kommt aus side; das Vorzeichen von menge wird nicht ausgewertet,
# die Quelle führt es uneinheitlich (OF-13).
RICHTUNGEN = {"BUY": 1, "SELL": -1}

CENT = Decimal("0.01")

# ---------------------------------------------------------------------------
# Ergebnis — genau die Spalten von legs (§5) ohne leg_id
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Leg:
    """Teilmenge einer Eröffnung, geschlossen oder offen; vergleichbar über ==.

    Offene Legs tragen keine Schließung und kein realisiertes Ergebnis:
    ``close_exec_id`` und ``brutto_pnl`` sind ``None``, ``offen_ja_nein`` ist
    wahr. Die eingefrorene Datenklasse lässt zwei Läufe gegeneinander prüfen.
    """

    conid: int
    open_exec_id: str
    close_exec_id: str | None
    menge: Decimal
    matching_methode: str
    brutto_pnl: Decimal | None
    kommission_gesamt: Decimal
    offen_ja_nein: bool


@dataclass(frozen=True)
class NichtGematcht:
    """Ausführung, die nicht am Matching teilnahm — benannt, nicht verworfen."""

    exec_id: str
    grund: str


@dataclass(frozen=True)
class MatchingErgebnis:
    """Gesamtergebnis eines Matching-Laufs über alle conids."""

    legs: tuple[Leg, ...]
    nicht_gematcht: tuple[NichtGematcht, ...]


# ---------------------------------------------------------------------------
# Buchführung während des Matching (modulintern, veränderlich)
# ---------------------------------------------------------------------------


@dataclass
class _Buchung:
    """Eine teilnehmende Ausführung, angepasst um Kapitalmaßnahmen.

    ``teilmengen`` sammelt die Portionen, in die die Menge während des
    Matching zerlegt wird, in Verbrauchsreihenfolge — die letzte Teilmenge
    trägt den Rundungsrest der Kommission.
    """

    exec_id: str
    conid: int
    handelszeit: date
    richtung: int
    menge: Decimal
    preis: Decimal
    kommission: Decimal
    teilmengen: list[Decimal] = field(default_factory=list)


@dataclass
class _Lot:
    """Noch offene Restmenge einer Ausführung im FIFO-Bestand."""

    buchung: _Buchung
    restmenge: Decimal


@dataclass
class _Schluss:
    """Ein geschlossenes Leg, bevor die Kommission verteilt ist."""

    offen: _Buchung
    schluss: _Buchung
    menge: Decimal
    # Position der Teilmenge in den teilmengen-Listen der beiden Ausführungen.
    index_offen: int
    index_schluss: int


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------


def bilde_legs(
    executions: Iterable[Mapping],
    instruments: Mapping[int, Mapping],
    kapitalmassnahmen: Iterable[Mapping] = (),
) -> MatchingErgebnis:
    """Bilde aus Ausführungen geschlossene und offene Legs, FIFO je conid.

    ``executions`` trägt die Spalten aus §5 (``exec_id``, ``conid``, ``side``,
    ``menge``, ``preis``, ``kommission``, ``handelszeit``, ``ereignistyp``),
    ``instruments`` ist nach ``conid`` verschlüsselt, ``kapitalmassnahmen``
    trägt ``conid``, ``typ``, ``stichtag``, ``faktor``.
    """
    nicht_gematcht: list[NichtGematcht] = []
    zeiten: dict[str, date] = {}
    je_conid: dict[int, list[_Buchung]] = {}

    for satz in executions:
        ereignistyp = satz["ereignistyp"]
        if ereignistyp not in MATCHENDE_EREIGNISTYPEN:
            nicht_gematcht.append(NichtGematcht(satz["exec_id"], _grund(ereignistyp)))
            continue
        buchung = _buchung(satz)
        _instrument_pruefen(buchung, instruments)
        zeiten[buchung.exec_id] = buchung.handelszeit
        je_conid.setdefault(buchung.conid, []).append(buchung)

    massnahmen = _massnahmen_je_conid(kapitalmassnahmen)

    legs: list[Leg] = []
    for conid in sorted(je_conid):
        buchungen = sorted(je_conid[conid], key=lambda b: (b.handelszeit, b.exec_id))
        _kapitalmassnahmen_anwenden(conid, buchungen, massnahmen.get(conid, ()))
        legs.extend(_fifo(conid, buchungen, instruments[conid]["multiplikator"]))

    def sortierschluessel(leg: Leg) -> tuple:
        # Reihenfolge nach conid, Eröffnungszeit, open_exec_id, Schließzeit,
        # close_exec_id — offene Legs tragen als Schließzeit ihre
        # Eröffnungszeit.
        offen_zeit = zeiten[leg.open_exec_id]
        schluss_zeit = zeiten[leg.close_exec_id] if leg.close_exec_id else offen_zeit
        return (
            leg.conid,
            offen_zeit,
            leg.open_exec_id,
            schluss_zeit,
            leg.close_exec_id or "",
        )

    legs.sort(key=sortierschluessel)
    return MatchingErgebnis(
        legs=tuple(legs),
        nicht_gematcht=tuple(sorted(nicht_gematcht, key=lambda e: e.exec_id)),
    )


# ---------------------------------------------------------------------------
# Vorprüfung und Wertumwandlung — jeder Fehler nennt die Zeile
# ---------------------------------------------------------------------------


def _grund(ereignistyp: str) -> str:
    if ereignistyp == "unbekannt":
        return (
            "ereignistyp 'unbekannt' ist fachlich nicht klassifiziert (OF-07); "
            "nimmt nicht am Matching teil, die Position bleibt offen"
        )
    return (
        f"ereignistyp {ereignistyp!r} ist keine matchende Ereignisart "
        f"({', '.join(sorted(MATCHENDE_EREIGNISTYPEN))})"
    )


def _dezimal(wert: object, *, feld: str, exec_id: str) -> Decimal:
    """Decimal erzwingen — float wäre stiller Präzisionsverlust (Regel 5)."""
    if isinstance(wert, bool) or not isinstance(wert, (Decimal, int)):
        raise TypeError(
            f"{exec_id}: Feld '{feld}' muss Decimal sein, "
            f"erhalten: {type(wert).__name__} ({wert!r})"
        )
    return wert if isinstance(wert, Decimal) else Decimal(wert)


def _datum(zeit: date) -> date:
    """Datum einer Zeitangabe — datetime liefert seinen Tag, date sich selbst."""
    return zeit.date() if isinstance(zeit, datetime) else zeit


def _buchung(satz: Mapping) -> _Buchung:
    """Ausführungszeile in die interne Buchung überführen.

    Eine NULL-Kommission heißt „keine gebucht" und wirkt wie 0 (OF-17);
    der Import legt NULL an, wo die Quelle ``ibCommission`` leer liefert.
    """
    exec_id = satz["exec_id"]
    side = satz["side"]
    if side not in RICHTUNGEN:
        raise ValueError(
            f"{exec_id}: unbekannte side {side!r} — Richtung nicht bestimmbar"
        )
    handelszeit = satz["handelszeit"]
    if not isinstance(handelszeit, date):
        raise TypeError(f"{exec_id}: handelszeit ist kein Datum: {handelszeit!r}")
    kommission = satz.get("kommission")
    return _Buchung(
        exec_id=exec_id,
        conid=satz["conid"],
        handelszeit=handelszeit,
        richtung=RICHTUNGEN[side],
        menge=abs(_dezimal(satz["menge"], feld="menge", exec_id=exec_id)),
        preis=_dezimal(satz["preis"], feld="preis", exec_id=exec_id),
        kommission=(
            _dezimal(kommission, feld="kommission", exec_id=exec_id)
            if kommission is not None
            else Decimal("0")
        ),
    )


def _instrument_pruefen(buchung: _Buchung, instruments: Mapping[int, Mapping]) -> None:
    """Preisfaktor sicherstellen: Stammdatenzeile und multiplikator müssen da sein.

    Der Preisfaktor ist bei allen Anlageklassen der ``multiplikator`` — bei
    Futures der Punktwert. Ein gesetzter ``tickwert`` springt nicht ein; er
    ist Berichtsgröße (OF-14).
    """
    satz = instruments.get(buchung.conid)
    if satz is None:
        raise ValueError(
            f"{buchung.exec_id}: keine Instrumentenzeile zu conid {buchung.conid} — "
            "kein Standardmultiplikator"
        )
    multiplikator = satz.get("multiplikator")
    if multiplikator is not None and not isinstance(multiplikator, Decimal):
        raise TypeError(
            f"{buchung.exec_id}: multiplikator zu conid {buchung.conid} muss Decimal "
            f"sein, erhalten: {type(multiplikator).__name__} ({multiplikator!r})"
        )
    if multiplikator is None or multiplikator <= 0:
        raise ValueError(
            f"{buchung.exec_id}: conid {buchung.conid} trägt keinen brauchbaren "
            "multiplikator — Preisfaktor unbekannt, tickwert geht nicht in den "
            "P&L ein (OF-14)"
        )


# ---------------------------------------------------------------------------
# Kapitalmaßnahmen vor dem Matching (OF-15)
# ---------------------------------------------------------------------------


def _massnahmen_je_conid(kapitalmassnahmen: Iterable[Mapping]) -> dict[int, list]:
    """Kapitalmaßnahmen je conid sammeln, in deterministischer Reihenfolge.

    Mehrere Maßnahmen je conid wirken zusammengesetzt (Menge × f₁ × f₂,
    Preis ÷ f₁ ÷ f₂) und sind damit in ihrer Wirkung reihenfolgengleich; die
    feste Sortierung hält den Lauf dennoch in jeder Hinsicht deterministisch.
    """
    je_conid: dict[int, list] = {}
    for satz in kapitalmassnahmen:
        je_conid.setdefault(satz["conid"], []).append(satz)
    for liste in je_conid.values():
        liste.sort(key=lambda satz: (satz["stichtag"], satz["typ"], str(satz["faktor"])))
    return je_conid


def _kapitalmassnahmen_anwenden(
    conid: int, buchungen: list[_Buchung], massnahmen: Iterable[Mapping]
) -> None:
    """Ausführungen vor dem Stichtag anpassen: Menge × Faktor, Preis ÷ Faktor.

    Der Faktor ist die Zahl neuer Stücke je altem Stück (Split 2:1 → 2,
    Reverse 1:10 → 0.1). Eine Ausführung am Stichtag selbst gilt bereits zu
    neuen Konditionen — ihre Kurse sind schon bereinigt (OF-15).
    """
    for satz in massnahmen:
        faktor = satz["faktor"]
        if not isinstance(faktor, Decimal):
            raise TypeError(
                f"conid {conid}: faktor einer Kapitalmaßnahme muss Decimal sein, "
                f"erhalten: {type(faktor).__name__} ({faktor!r})"
            )
        if faktor <= 0:
            raise ValueError(f"conid {conid}: unbrauchbarer Splitfaktor {faktor}")
        stichtag = _datum(satz["stichtag"])
        for buchung in buchungen:
            if _datum(buchung.handelszeit) < stichtag:
                buchung.menge *= faktor
                buchung.preis /= faktor


# ---------------------------------------------------------------------------
# FIFO-Matching
# ---------------------------------------------------------------------------


def _fifo(conid: int, buchungen: list[_Buchung], multiplikator: Decimal) -> list[Leg]:
    """FIFO je conid: eine Gegenbewegung schließt das älteste Los zuerst.

    Was über den Bestand hinausgeht, kehrt die Position um und eröffnet neu —
    es wird nicht verworfen. Der Bestand bleibt richtungsrein: eine
    entgegengerichtete Ausführung verzehrt ihn vollständig, ehe sie eröffnet.
    """
    bestand: deque[_Lot] = deque()
    schluesse: list[_Schluss] = []

    for buchung in buchungen:
        rest = buchung.menge
        while rest > 0 and bestand and bestand[0].buchung.richtung != buchung.richtung:
            lot = bestand[0]
            teil = min(rest, lot.restmenge)
            schluesse.append(
                _Schluss(
                    offen=lot.buchung,
                    schluss=buchung,
                    menge=teil,
                    index_offen=len(lot.buchung.teilmengen),
                    index_schluss=len(buchung.teilmengen),
                )
            )
            lot.buchung.teilmengen.append(teil)
            buchung.teilmengen.append(teil)
            lot.restmenge -= teil
            rest -= teil
            if lot.restmenge == 0:
                bestand.popleft()
        if rest > 0:
            bestand.append(_Lot(buchung=buchung, restmenge=rest))

    # Der offene Rest einer Eröffnung ist deren letzte Teilmenge — der
    # Rundungsrest ihrer Kommission fällt damit auf den offenen Bestand.
    for lot in bestand:
        lot.buchung.teilmengen.append(lot.restmenge)

    anteile = {buchung.exec_id: _kommission_verteilen(buchung) for buchung in buchungen}

    legs = [
        Leg(
            conid=conid,
            open_exec_id=schluss.offen.exec_id,
            close_exec_id=schluss.schluss.exec_id,
            menge=schluss.menge,
            matching_methode="fifo",
            brutto_pnl=_brutto_pnl(schluss, multiplikator),
            kommission_gesamt=(
                anteile[schluss.offen.exec_id][schluss.index_offen]
                + anteile[schluss.schluss.exec_id][schluss.index_schluss]
            ),
            offen_ja_nein=False,
        )
        for schluss in schluesse
    ]
    for lot in bestand:
        buchung = lot.buchung
        legs.append(
            Leg(
                conid=conid,
                open_exec_id=buchung.exec_id,
                close_exec_id=None,
                menge=lot.restmenge,
                matching_methode="fifo",
                brutto_pnl=None,
                kommission_gesamt=anteile[buchung.exec_id][-1],
                offen_ja_nein=True,
            )
        )
    return legs


def _brutto_pnl(schluss: _Schluss, multiplikator: Decimal) -> Decimal:
    """(Schließpreis − Eröffnungspreis) × Menge × Preisfaktor × Richtung.

    Richtung ist die der Eröffnung: +1 für long, −1 für short eröffnet.
    Auf den Cent gerundet, ``ROUND_HALF_UP``.
    """
    delta = schluss.schluss.preis - schluss.offen.preis
    ergebnis = delta * schluss.menge * multiplikator * schluss.offen.richtung
    return ergebnis.quantize(CENT, rounding=ROUND_HALF_UP)


def _kommission_verteilen(buchung: _Buchung) -> list[Decimal]:
    """Kommission nach Menge auf die Teilmengen, zentgenau ROUND_HALF_UP.

    Die letzte Teilmenge erhält den Rundungsrest, damit die Summe exakt der
    gebuchten Kommission entspricht — keine stillen Rundungen (Regel 5).
    """
    if not buchung.teilmengen:
        if buchung.kommission == 0:
            return []
        raise ValueError(
            f"{buchung.exec_id}: Kommission {buchung.kommission} ohne Menge — "
            "auf keine Teilmenge zuteilbar"
        )
    anteile: list[Decimal] = []
    verteilt = Decimal("0")
    for teil in buchung.teilmengen[:-1]:
        anteil = (
            buchung.kommission * teil / buchung.menge
        ).quantize(CENT, rounding=ROUND_HALF_UP)
        anteile.append(anteil)
        verteilt += anteil
    anteile.append(
        (buchung.kommission - verteilt).quantize(CENT, rounding=ROUND_HALF_UP)
    )
    return anteile
