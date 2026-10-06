"""Kettensicht-Zuordnung (AP-04sk, Plan §5 „Zwei Sichten auf dieselben
Ausführungen" und §6, AP-04s).

Grundsatzentscheidung OF-68 (Option A; ersetzt OF-52 „Ausführung zählt
doppelt"): Eine Ausführung, die laut OA ihren **eigenen** Vorgang eröffnen
sollte (``oa_rolle = 'Open Order'``), aber vom kontoweiten FIFO-Abgleich
(AP-03) als Schließung eines **anderen** Vorgangs verbraucht wurde (OF-36),
eröffnet in der Kettensicht nur ihren eigenen Vorgang und schließt nie. Der
alte Vorgang bleibt offen, bis seine eigene Schließung kommt. Damit kommt
jede Ausführung in jeder Sicht genau einmal vor, und realisiertes Brutto wie
Kommission stimmen über beide Sichten überein (Plan §5, Summentreue).

Umsetzung: ein einziger FIFO-Lauf über alle Ausführungen
(``engine.matching.bilde_legs``) mit zwei Zusätzen — die umgeleiteten
Ausführungen eröffnen zwingend, und für Kontrakte, deren Verfall vor der
letzten Handelszeit des Eingabebestands liegt, werden verbliebene
gegenläufige offene Lose am Ende FIFO gegeneinander geschlossen (früheres
Los eröffnet, späteres schließt): Das Konto ist dann flach, es gibt keine
Ausführung mehr, die die Vorgänge trennt. Bekannte Grenze (AP-04sx): Das
innere Ergebnis eines ITM-Verfalls wird nicht auf die beiden Vorgänge
aufgeteilt — die Summe stimmt, die Zuordnung je Kette nicht.

``engine.structures``/``engine.chains`` speisen beide Sichten anschließend
unverändert, nur mit unterschiedlichem Leg-Satz als Eingabe.

Rein im Sinne von CLAUDE.md Regel 6: keine Datenbank, keine Uhrzeit, kein
Zufall — die „letzte Handelszeit" kommt aus den übergebenen Ausführungen,
nicht aus ``datetime.now()``. Der FIFO wird nicht nachgebaut, sondern
``engine.matching.bilde_legs`` mit seinen Zusätzen aufgerufen.
"""

from collections.abc import Iterable, Mapping
from datetime import date, datetime

from engine.matching import Leg, bilde_legs


def _umgeleitet(
    exec_id: str, executions: Mapping[str, Mapping], konto_legs: list[Leg]
) -> bool:
    """Vertrag Schritt 1: ``trade``, ``oa_rolle = 'Open Order'`` mit
    ``oa_trade``, verbraucht als Schließung eines Kontosicht-Legs, dessen
    Eröffner ein anderes (oder kein) ``oa_trade`` trägt."""
    satz = executions[exec_id]
    if satz["ereignistyp"] != "trade" or satz["oa_rolle"] != "Open Order":
        return False
    oa_trade = satz["oa_trade"]
    if not oa_trade:
        return False
    return any(
        leg.close_exec_id == exec_id
        and executions[leg.open_exec_id].get("oa_trade") != oa_trade
        for leg in konto_legs
    )


def _tag(zeit: date) -> date:
    """Datum einer Zeitangabe — datetime liefert seinen Tag, date sich selbst."""
    return zeit.date() if isinstance(zeit, datetime) else zeit


def kettensicht_legs(
    konto_legs: Iterable[Leg],
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
    kapitalmassnahmen: Iterable[Mapping] = (),
) -> tuple[Leg, ...]:
    """Kettensicht-Legs (AP-04sx, OF-68 Option A): ein einziger FIFO-Lauf
    über alle Ausführungen, in dem jede umgeleitete Ausführung zwingend
    eröffnet und verfallene Kontrakte ihre gegenläufigen offenen Lose am
    Ende zusammenführen. Ohne umgeleitete Ausführung werden die
    Kontosicht-Legs unverändert zurückgegeben.
    """
    konto_liste = list(konto_legs)

    umgeleitet = frozenset(
        exec_id for exec_id in sorted(executions) if _umgeleitet(exec_id, executions, konto_liste)
    )
    if not umgeleitet:
        return tuple(konto_liste)

    # Regel 4 (AP-04sx): Ein Kontrakt ist verfallen, wenn sein Verfall vor
    # der letzten Handelszeit des Eingabebestands liegt — rein, die letzte
    # Handelszeit kommt aus den übergebenen Ausführungen. Instrumente ohne
    # Verfallsdatum (etwa Aktien) verfallen nicht; fehlt eine Instrumenten-
    # zeile ganz, meldet bilde_legs sie mit Nennung der Ausführung.
    letzte_zeit = max(_tag(satz["handelszeit"]) for satz in executions.values())
    verfallene: set[int] = set()
    for conid in {satz["conid"] for satz in executions.values()}:
        instrument = instruments.get(conid)
        verfall = instrument.get("expiry") if instrument is not None else None
        if verfall is not None and _tag(verfall) < letzte_zeit:
            verfallene.add(conid)

    ergebnis = bilde_legs(
        executions.values(),
        instruments,
        kapitalmassnahmen,
        erzwungene_eroeffnungen=umgeleitet,
        verfallene_conids=verfallene,
    )
    return ergebnis.legs
