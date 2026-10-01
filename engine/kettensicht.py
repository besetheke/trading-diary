"""Kettensicht-Zuordnung (AP-04sk, Plan §5 „Zwei Sichten auf dieselben
Ausführungen" und §6, AP-04s).

Grundsatzentscheidung OF-52: Eine Ausführung, die laut OA ihren **eigenen**
Vorgang eröffnen sollte (``oa_rolle = 'Open Order'``), aber vom
kontoweiten FIFO-Abgleich (AP-03) als Schließung eines **anderen** Vorgangs
verbraucht wurde (OF-36), **zählt doppelt** — sie schließt den alten Vorgang
(Kontosicht, unverändert) **und** eröffnet den eigenen (Kettensicht, hier).

Die Kettensicht-Legs sind eine Obermenge der Kontosicht-Legs mit gezielten
Ergänzungen/Entfernungen; ``engine.structures``/``engine.chains`` speisen
beide anschließend unverändert, nur mit unterschiedlichem Leg-Satz als
Eingabe.

**Nur freie Ausführungen werden umgewidmet** (Vertrag, „Die Stelle, an der
erfahrungsgemäß geraten wird"): Findet der eingeschränkte FIFO eine
Schließung ``F``, muss ``F`` in der Kontosicht eine offene (nie
geschlossene) Eröffnung gewesen sein — und ihr altes, offenes Leg entfällt
aus der Kettensicht. Sonst wäre ``F`` zweimal **innerhalb derselben**
Sicht verwendet; „doppelt" im Sinne von OF-52 gilt nur für die umgeleitete
Ausführung selbst und nur **über zwei Sichten**. Gibt es keinen freien
Schließer, bleibt die neue Struktur offen — keine Kaskade über eine
dritte, unbeteiligte Ausführung (Vertragsgrenze; in der echten Historie
nicht beobachtet, OF-36).

Rein im Sinne von CLAUDE.md Regel 6: keine Datenbank, keine Uhrzeit, kein
Zufall. FIFO wird nicht nachgebaut, sondern ``engine.matching.bilde_legs``
auf einem je umgeleiteter Ausführung eingeschränkten Pool aufgerufen.
"""

from collections.abc import Iterable, Mapping

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


def kettensicht_legs(
    konto_legs: Iterable[Leg],
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
    kapitalmassnahmen: Iterable[Mapping] = (),
) -> tuple[Leg, ...]:
    """Kettensicht-Legs aus Kontosicht-Legs (Vertrag ``auftraege/AP-04s.md``,
    Ablauf 1–6): alle unveränderten Kontosicht-Legs, abzüglich der
    umgewidmeten freien Eröffnungen, plus je umgeleiteter Ausführung eine
    eigene, neue Struktur-Eröffnung.
    """
    konto_liste = list(konto_legs)

    # Schritt 2: frei ist, wer in der Kontosicht eine offene (nie
    # geschlossene) Eröffnung ist — nur solche dürfen umgewidmet werden.
    freie = {leg.open_exec_id for leg in konto_liste if leg.close_exec_id is None}

    neue_legs: list[Leg] = []
    verbrauchte: set[str] = set()
    for exec_id in sorted(executions):
        if not _umgeleitet(exec_id, executions, konto_liste):
            continue
        satz = executions[exec_id]

        # Schritt 3: eingeschränkter Pool — derselbe oa_trade und conid wie
        # die umgeleitete Ausführung, nur freie (oder sie selbst); FIFO
        # wiederverwendet, nicht nachgebaut.
        pool = [
            anderer
            for anderen_id, anderer in executions.items()
            if anderer["conid"] == satz["conid"]
            and anderer["oa_trade"] == satz["oa_trade"]
            and (anderen_id in freie or anderen_id == exec_id)
        ]
        ergebnis = bilde_legs(pool, instruments, kapitalmassnahmen)
        eigenes = next(
            (leg for leg in ergebnis.legs if leg.open_exec_id == exec_id), None
        )
        if eigenes is None:
            # Der FIFO hat die umgeleitete Ausführung im Pool selbst als
            # Schließung einer früheren freien Eröffnung verbraucht — dann
            # gibt es hier keine eigene Eröffnung zu übernehmen.
            continue
        neue_legs.append(eigenes)

        # Schritt 4: die gefundene Schließung war frei — ihr altes, offenes
        # Kontosicht-Leg entfällt, sonst wäre sie zweimal in dieser Sicht.
        # Schritt 5: ohne Schließung bleibt das neue Leg offen (keine
        # Kaskade), genau wie bilde_legs es liefert.
        if eigenes.close_exec_id is not None:
            verbrauchte.add(eigenes.close_exec_id)

    # Schritt 6: unveränderte Kontosicht-Legs in ihrer Reihenfolge, ohne die
    # umgewidmeten offenen Eröffnungen, plus die neuen Legs dahinter.
    uebrig = [
        leg
        for leg in konto_liste
        if not (leg.close_exec_id is None and leg.open_exec_id in verbrauchte)
    ]
    return tuple(uebrig + neue_legs)
