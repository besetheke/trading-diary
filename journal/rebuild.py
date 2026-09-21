"""Persistenz der Ketten und ``journal rebuild`` (AP-04p).

Umsetzung des Vertrags aus ``auftraege/AP-04v.md`` (Vorbereitungspaket des
starken Modells; Abnahmebasis: ``tests/test_rebuild.py``). Die Engine
(``engine.matching``, ``engine.structures``, ``engine.chains``) rechnet rein im
Speicher — dieses Modul liest die Rohdaten, ruft sie auf und schreibt das
Ergebnis in die abgeleiteten Tabellen. Es steht bewusst nicht unter ``engine/``
(Regel 6) und ändert die Engine nicht.

**Abgleich statt Neuanlage** (AP-04v, Entscheidung 1): ``structures`` und
``chains`` tragen Naturschlüssel. Bekanntes behält seine Nummer, Neues bekommt
eine, Verschwundenes wird entfernt — außer ``chain_overrides`` verweist darauf
(Regel 4). So überleben manuelle Overrides einen vollständigen Rebuild.

**Ohne FX kein Euro-Betrag** (AP-04v, Entscheidung 2): ``netto_pnl_eur`` bleibt
leer; die Umrechnung nach P4 ist AP-06.

Dokumentierte Annahmen (Regel 10) — hier nur im Code festgehalten, weil die
Abnahme Änderungen ausschließlich in ``journal/rebuild.py`` und
``journal/cli.py`` zulässt; für den Review notieren:

- **Verwaist heißt „von der Automatik nicht mehr gefunden"** (Vertrag 20):
  Ein Override, dessen Struktur oder Kette nicht mehr berechnet wird, ist
  verwaist — auch wenn die Zeile selbst wegen des Fremdschlüssels steht.
- **``methode = 'zuteilung'`` bildet auf ``erkennung = 'order_id'`` ab**
  (Vertrag 12): Die Spalte kennt kein ``auto``; die Zuteilung ist wie eine
  Order-Referenz eine Brokertatsache, nicht wie das Zeitfenster erschlossen.
- **Kapitalmaßnahmen ohne Instrumentzeile werden verworfen**, exakt wie am
  Ende der Vorlage ``kapitalmassnahmen_ableiten()``
  (``werkzeuge/abgleich/golden_bestandsabgleich_of23.py``).
- **Eine durch einen Override leer gewordene Kette wird nur gelöscht, wenn
  kein Override auf sie verweist** (Vertrag 19 gegen Regel 4 abgewogen).
"""

import pathlib
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection

from engine.chains import ENDZUSTAND_JE_EREIGNIS, bilde_chains
from engine.chains import Chain as Kette
from engine.matching import bilde_legs
from engine.structures import Structure as Struktur
from engine.structures import bilde_structures
from journal.db import STANDARD_BUSY_TIMEOUT_MS, create_db_engine
from journal.schema import (
    assignment_links,
    chain_links,
    chain_overrides,
    chains,
    corporate_actions,
    executions,
    instruments,
    legs,
    structures,
)

# Vertrag 12: `structures.erkennung` hat ein anderes Vokabular als das Feld
# `Structure.erkennung` der Dataclass. Die Spalte wird aus `methode` abgeleitet.
ERKENNUNG_JE_METHODE = {
    "oa": "order_id",
    "exec_batch": "order_id",
    "zeitfenster": "heuristik",
    # Annahme, siehe Modul-Docstring: Zuteilung ist Brokertatsache.
    "zuteilung": "order_id",
}


@dataclass(frozen=True)
class RebuildErgebnis:
    """Zählwerte eines Rebuild-Laufs (Vertrag 2) — deckungsgleich mit den
    Tabelleninhalten nach dem Lauf (Abnahme AP-04v)."""

    legs: int
    structures: int
    chains: int
    chain_links: int
    nicht_strukturiert: int
    overrides_angewandt: int
    overrides_verwaist: int
    # Rollkandidaten, über die noch nicht entschieden wurde (Plan §6,
    # Block B, Regel 2). Nicht persistiert, bei jedem Lauf neu berechnet.
    kandidaten_offen: int = 0


def rebuild(
    db_pfad: str | pathlib.Path, *, busy_timeout_ms: int = STANDARD_BUSY_TIMEOUT_MS
) -> RebuildErgebnis:
    """Baut Legs, Strukturen, Ketten und Kettenglieder aus ``executions`` neu.

    Kurze Transaktion über ``create_db_engine()`` (Regel 9 — die Pragmas setzt
    die Engine-Factory, nicht dieses Modul). Schlägt etwas fehl, bleibt die
    Datenbank unverändert; angetastet werden nur ``legs``, ``structures``,
    ``chains``, ``chain_links`` und die nicht-manuellen ``assignment_links``
    (Regel 4).
    """
    engine = create_db_engine(db_pfad, busy_timeout_ms=busy_timeout_ms)
    try:
        with engine.begin() as verbindung:
            return _rebuild_laufen(verbindung)
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


def _struktur_schluessel(struktur: Struktur) -> str:
    """Naturschlüssel einer Struktur (Vertrag 7): die ``open_exec_id`` ihrer
    Legs, aufsteigend sortiert, mit ``|`` verbunden."""
    return "|".join(sorted(schluessel.open_exec_id for schluessel in struktur.leg_schluessel))


def _kette_schluessel(kette: Kette) -> str:
    """Naturschlüssel einer Kette (Vertrag 8): der Naturschlüssel der
    eröffnenden Struktur, mit ``k:`` davor."""
    return "k:" + _struktur_schluessel(kette.glieder[0].structure)


def _struktur_waehrung(
    struktur: Struktur, schluessel: str, exec_je_id: Mapping[str, Mapping]
) -> str:
    """Vertrag 11: Die Währung steht nicht an der Structure, sie kommt aus den
    Ausführungen der Legs. Bei Uneinigkeit Abbruch mit Nennung — nicht die
    häufigste Währung, nicht die erste."""
    waehrungen = {
        satz["waehrung"]
        for leg in struktur.leg_schluessel
        for exec_id in (leg.open_exec_id, leg.close_exec_id)
        if exec_id is not None
        for satz in (exec_je_id.get(exec_id),)
        if satz is not None
    }
    if len(waehrungen) != 1:
        gefundene = ", ".join(sorted(waehrungen)) or "keine"
        raise ValueError(
            f"Struktur {schluessel}: uneinige Währungen in den Ausführungen "
            f"der Legs ({gefundene}) — Abbruch statt Wahl (Vertrag 11)"
        )
    return next(iter(waehrungen))


def _struktur_zeile(
    struktur: Struktur, schluessel: str, exec_je_id: Mapping[str, Mapping]
) -> dict:
    """Spaltenwerte einer Structure für ``structures`` (Vertrag 10–12)."""
    erkennung = ERKENNUNG_JE_METHODE.get(struktur.methode)
    if erkennung is None:
        raise ValueError(
            f"Struktur {schluessel}: unbekannte Methode {struktur.methode!r} — "
            "keine Abbildung auf structures.erkennung (Vertrag 12)"
        )
    # Vertrag 10a: netto = brutto + kommission, ADDIERT. Kommissionen tragen
    # das IB-Vorzeichen — negativ heißt „kostet Geld".
    netto_pnl = (
        None
        if struktur.brutto_pnl is None
        else struktur.brutto_pnl + struktur.kommission_gesamt
    )
    return dict(
        asset_class=struktur.asset_class,
        typ=struktur.typ,
        underlying=struktur.underlying,
        expiry=struktur.expiry,
        short_strike=struktur.short_strike,
        long_strike=struktur.long_strike,
        breite=struktur.breite,
        menge=struktur.menge,
        eroeffnet_am=struktur.eroeffnet_am,
        geschlossen_am=struktur.geschlossen_am,
        dte_bei_eroeffnung=struktur.dte_bei_eroeffnung,
        status=struktur.status,
        brutto_pnl=struktur.brutto_pnl,
        kommission=struktur.kommission_gesamt,
        netto_pnl=netto_pnl,
        waehrung=_struktur_waehrung(struktur, schluessel, exec_je_id),
        erkennung=erkennung,
        strategy_id=None,
    )


def _kette_zeile(kette: Kette) -> dict:
    """Spaltenwerte einer Chain für ``chains`` (Vertrag 13; Entscheidung 2:
    kein Euro-Betrag ohne FX-Umrechnung)."""
    return dict(
        underlying=kette.underlying,
        asset_class=kette.asset_class,
        seite=kette.seite,
        eroeffnet_am=kette.eroeffnet_am,
        beendet_am=kette.beendet_am,
        anzahl_rolls=kette.anzahl_rolls,
        endzustand=kette.endzustand,
        netto_pnl_eur=None,
    )


def _anzahl(verbindung: Connection, tabelle) -> int:
    return verbindung.execute(select(func.count()).select_from(tabelle)).scalar_one()


# ---------------------------------------------------------------------------
# Der Lauf selbst
# ---------------------------------------------------------------------------


def _rebuild_laufen(verbindung: Connection) -> RebuildErgebnis:
    # -- Lesen (Vertrag 4): Rohdaten, Overrides, aktueller Stand der
    #    abgeleiteten Tabellen für den Abgleich.
    ausfuehrungen = [dict(z) for z in verbindung.execute(select(executions)).mappings()]
    exec_je_id = {satz["exec_id"]: satz for satz in ausfuehrungen}
    instrumente = {
        satz["conid"]: satz for satz in verbindung.execute(select(instruments)).mappings()
    }
    # Kapitalmaßnahmen aus corporate_actions; Vorlage ist
    # kapitalmassnahmen_ableiten() (Auftrag AP-04p): Zeilen ohne Instrument
    # werden verworfen, wie dort.
    massnahmen = [dict(z) for z in verbindung.execute(select(corporate_actions)).mappings()]
    kapitalmassnahmen = [
        satz
        for satz in massnahmen
        if satz["neuer_conid"] in instrumente
        and (satz["alter_conid"] is None or satz["alter_conid"] in instrumente)
    ]

    overrides = [dict(z) for z in verbindung.execute(select(chain_overrides)).mappings()]
    # Plan §6, Block B, Regel 2: Bestätigung und Ablehnung sind beide
    # Benutzerdaten. Angewandt wird nur die Bestätigung; die Ablehnung hält
    # einen Kandidaten dauerhaft von der Liste fern. Gesichert gegen Löschung
    # (Regel 4) sind die Zeilen beider Urteile.
    bestaetigungen = [o for o in overrides if o["urteil"] == "bestaetigt"]
    gesicherte_struktur_ids = {o["structure_id"] for o in overrides}
    gesicherte_ketten_ids = {o["chain_id"] for o in overrides}

    alte_struktur_ids = {
        z["natur_schluessel"]: z["structure_id"]
        for z in verbindung.execute(
            select(structures.c.structure_id, structures.c.natur_schluessel)
        ).mappings()
    }
    alte_ketten_ids = {
        z["natur_schluessel"]: z["chain_id"]
        for z in verbindung.execute(
            select(chains.c.chain_id, chains.c.natur_schluessel)
        ).mappings()
    }

    # -- Rechnen: die reine Engine, unverändert.
    matching = bilde_legs(ausfuehrungen, instrumente, kapitalmassnahmen)
    legs_als_dict = [asdict(leg) for leg in matching.legs]
    struktur_ergebnis = bilde_structures(legs_als_dict, ausfuehrungen, instrumente)
    ketten_ergebnis = bilde_chains(struktur_ergebnis, legs_als_dict, ausfuehrungen, instrumente)

    # Synthetische Zuteilungs-Fortsetzungen (engine.chains) stehen nur als
    # Kettenglieder an — sie gehören ebenfalls in structures, sonst hätten
    # ihre chain_links keinen Fremdschlüssel.
    strukturen = list(struktur_ergebnis.structures)
    bekannte_schluessel = {_struktur_schluessel(s) for s in strukturen}
    for kette in ketten_ergebnis.chains:
        for glied in kette.glieder:
            schluessel = _struktur_schluessel(glied.structure)
            if schluessel not in bekannte_schluessel:
                strukturen.append(glied.structure)
                bekannte_schluessel.add(schluessel)
    struktur_je_schluessel = {_struktur_schluessel(s): s for s in strukturen}

    # -- Schreiben (Vertrag 6). legs und chain_links sind vollständiger
    #    Austausch (Vertrag 14/15) und gehen zuerst weg — sie halten die
    #    Fremdschlüssel auf structures/chains.
    verbindung.execute(delete(legs))
    verbindung.execute(delete(chain_links))

    # structures: Abgleich über den Naturschlüssel (Vertrag 9).
    struktur_id_je_schluessel: dict[str, int] = {}
    for schluessel in sorted(struktur_je_schluessel):
        werte = _struktur_zeile(struktur_je_schluessel[schluessel], schluessel, exec_je_id)
        structure_id = alte_struktur_ids.get(schluessel)
        if structure_id is None:
            structure_id = verbindung.execute(
                insert(structures).values(**werte, natur_schluessel=schluessel)
            ).inserted_primary_key[0]
        else:
            verbindung.execute(
                update(structures)
                .where(structures.c.structure_id == structure_id)
                .values(**werte)
            )
        struktur_id_je_schluessel[schluessel] = structure_id

    entfallene_struktur_ids = [
        structure_id
        for schluessel, structure_id in alte_struktur_ids.items()
        if schluessel not in struktur_id_je_schluessel
        and structure_id not in gesicherte_struktur_ids
    ]
    if entfallene_struktur_ids:
        verbindung.execute(
            delete(structures).where(structures.c.structure_id.in_(entfallene_struktur_ids))
        )

    # legs: frisch schreiben; structure_id zeigt auf die Struktur, in der die
    # Leg gelandet ist, sonst leer (Vertrag 15).
    struktur_id_je_leg = {
        (leg.open_exec_id, leg.close_exec_id): struktur_id_je_schluessel[schluessel]
        for schluessel, struktur in struktur_je_schluessel.items()
        for leg in struktur.leg_schluessel
    }
    for leg in matching.legs:
        verbindung.execute(
            insert(legs).values(
                conid=leg.conid,
                open_exec_id=leg.open_exec_id,
                close_exec_id=leg.close_exec_id,
                menge=leg.menge,
                matching_methode=leg.matching_methode,
                brutto_pnl=leg.brutto_pnl,
                kommission_gesamt=leg.kommission_gesamt,
                offen_ja_nein=leg.offen_ja_nein,
                basis_ungeklaert=leg.basis_ungeklaert,
                structure_id=struktur_id_je_leg.get((leg.open_exec_id, leg.close_exec_id)),
            )
        )

    # chains: Abgleich über den Naturschlüssel (Vertrag 9, 13).
    kette_je_schluessel = {_kette_schluessel(k): k for k in ketten_ergebnis.chains}
    ketten_id_je_schluessel: dict[str, int] = {}
    for schluessel in sorted(kette_je_schluessel):
        werte = _kette_zeile(kette_je_schluessel[schluessel])
        chain_id = alte_ketten_ids.get(schluessel)
        if chain_id is None:
            chain_id = verbindung.execute(
                insert(chains).values(**werte, natur_schluessel=schluessel)
            ).inserted_primary_key[0]
        else:
            verbindung.execute(
                update(chains).where(chains.c.chain_id == chain_id).values(**werte)
            )
        ketten_id_je_schluessel[schluessel] = chain_id

    entfallene_ketten_ids = [
        chain_id
        for schluessel, chain_id in alte_ketten_ids.items()
        if schluessel not in ketten_id_je_schluessel and chain_id not in gesicherte_ketten_ids
    ]
    if entfallene_ketten_ids:
        verbindung.execute(delete(chains).where(chains.c.chain_id.in_(entfallene_ketten_ids)))

    # chain_links: unverändert aus ChainGlied (Vertrag 14) — dessen Feld
    # erkennung unterscheidet dort bereits auto/heuristik/manuell.
    glieder_je_kette: dict[str, list[list]] = {}
    for schluessel, kette in kette_je_schluessel.items():
        eintraege = []
        for glied in kette.glieder:
            verbindung.execute(
                insert(chain_links).values(
                    chain_id=ketten_id_je_schluessel[schluessel],
                    structure_id=struktur_id_je_schluessel[
                        _struktur_schluessel(glied.structure)
                    ],
                    sequenz=glied.sequenz,
                    verknuepfungstyp=glied.verknuepfungstyp,
                    erkennung=glied.erkennung,
                )
            )
            eintraege.append([_struktur_schluessel(glied.structure), glied.erkennung])
        glieder_je_kette[schluessel] = eintraege

    # -- Overrides anwenden (Vertrag 16–21); chain_overrides selbst wird nie
    #    geschrieben oder gelöscht (Regel 4).
    angewandt, verwaiste = _overrides_anwenden(
        verbindung,
        bestaetigungen,
        glieder_je_kette,
        struktur_id_je_schluessel,
        ketten_id_je_schluessel,
        struktur_je_schluessel,
        gesicherte_ketten_ids,
    )

    # -- assignment_links (Vertrag 22): nicht-manuelle Zeilen neu schreiben.
    _assignment_links_neu_schreiben(verbindung, ketten_ergebnis, exec_je_id)

    offene_kandidaten = _offene_kandidaten(
        ketten_ergebnis,
        overrides,
        glieder_je_kette,
        struktur_id_je_schluessel,
        ketten_id_je_schluessel,
    )

    return RebuildErgebnis(
        legs=_anzahl(verbindung, legs),
        structures=_anzahl(verbindung, structures),
        chains=_anzahl(verbindung, chains),
        chain_links=_anzahl(verbindung, chain_links),
        nicht_strukturiert=len(struktur_ergebnis.nicht_strukturiert),
        overrides_angewandt=angewandt,
        overrides_verwaist=len(verwaiste),
        kandidaten_offen=offene_kandidaten,
    )


def _offene_kandidaten(
    ketten_ergebnis,
    overrides: list[dict],
    glieder_je_kette: dict[str, list[list]],
    struktur_id_je_schluessel: dict[str, int],
    ketten_id_je_schluessel: dict[str, int],
) -> int:
    """Rollkandidaten abzüglich der bereits entschiedenen (Vertrag 13).

    Ein Kandidat gilt als entschieden, wenn eine Zeile in
    ``chain_overrides`` dieselbe Kombination aus Kette der schließenden
    Seite und vorgeschlagener Struktur trägt — gleich ob bestätigt oder
    abgelehnt. Die Engine kennt diese Urteile nicht (Regel 6); gefiltert
    wird deshalb hier.
    """
    kette_je_struktur_schluessel = {
        eintrag[0]: ketten_schluessel
        for ketten_schluessel, eintraege in glieder_je_kette.items()
        for eintrag in eintraege
    }
    entschieden = {(o["chain_id"], o["structure_id"]) for o in overrides}

    offen = 0
    for kandidat in ketten_ergebnis.kandidaten:
        schliessende = _struktur_schluessel(kandidat.schliessende)
        eroeffnende = _struktur_schluessel(kandidat.eroeffnende)
        ketten_schluessel = kette_je_struktur_schluessel.get(schliessende)
        chain_id = ketten_id_je_schluessel.get(ketten_schluessel)
        structure_id = struktur_id_je_schluessel.get(eroeffnende)
        if (chain_id, structure_id) not in entschieden:
            offen += 1
    return offen


def _overrides_anwenden(
    verbindung: Connection,
    overrides: list[dict],
    glieder_je_kette: dict[str, list[list]],
    struktur_id_je_schluessel: dict[str, int],
    ketten_id_je_schluessel: dict[str, int],
    struktur_je_schluessel: dict[str, Struktur],
    gesicherte_ketten_ids: set[int],
) -> tuple[int, list[tuple[object, object]]]:
    """Wendet chain_overrides an: Struktur in die Zielkette hängen, erkennung
    'manuell', betroffene Ketten neu nummerieren und Kennzahlen nachziehen
    (Vertrag 17/18). Liefert (Anzahl angewandt, Liste verwaister)."""
    schluessel_je_struktur_id = {sid: s for s, sid in struktur_id_je_schluessel.items()}
    schluessel_je_ketten_id = {cid: k for k, cid in ketten_id_je_schluessel.items()}

    # Vertrag 21: dieselbe Struktur in zwei Ketten ist ein Widerspruch in den
    # Benutzerdaten — Abbruch mit Nennung beider Ketten.
    ketten_ids_je_struktur: dict[int, set[int]] = {}
    for override in overrides:
        ketten_ids_je_struktur.setdefault(override["structure_id"], set()).add(
            override["chain_id"]
        )
    for structure_id, chain_ids in ketten_ids_je_struktur.items():
        if len(chain_ids) > 1:
            namen = ", ".join(
                sorted(str(schluessel_je_ketten_id.get(cid, cid)) for cid in chain_ids)
            )
            raise ValueError(
                f"Struktur {schluessel_je_struktur_id.get(structure_id, structure_id)} "
                f"wird von zwei Ketten beansprucht: {namen} (Vertrag 21)"
            )

    verwaiste: list[tuple[object, object]] = []
    betroffene_ketten: set[str] = set()
    for override in overrides:
        struktur_schluessel = schluessel_je_struktur_id.get(override["structure_id"])
        kette_schluessel = schluessel_je_ketten_id.get(override["chain_id"])
        if struktur_schluessel is None or kette_schluessel is None:
            # Vertrag 20: benannt, gezählt, nicht gelöscht, nicht übergangen.
            verwaiste.append(
                (
                    struktur_schluessel or override["structure_id"],
                    kette_schluessel or override["chain_id"],
                )
            )
            continue

        herkunft = next(
            (
                schluessel
                for schluessel, eintraege in glieder_je_kette.items()
                if any(eintrag[0] == struktur_schluessel for eintrag in eintraege)
            ),
            None,
        )
        if herkunft is not None:
            glieder_je_kette[herkunft] = [
                eintrag
                for eintrag in glieder_je_kette[herkunft]
                if eintrag[0] != struktur_schluessel
            ]
            betroffene_ketten.add(herkunft)
        glieder_je_kette[kette_schluessel].append([struktur_schluessel, "manuell"])
        betroffene_ketten.add(kette_schluessel)

    for kette_schluessel in betroffene_ketten:
        chain_id = ketten_id_je_schluessel[kette_schluessel]
        verbindung.execute(delete(chain_links).where(chain_links.c.chain_id == chain_id))
        eintraege = glieder_je_kette[kette_schluessel]
        if not eintraege:
            # Vertrag 19: eine durch den Override leer gewordene Kette wird
            # gelöscht — außer ein Override verweist auf sie (Regel 4).
            if chain_id not in gesicherte_ketten_ids:
                verbindung.execute(delete(chains).where(chains.c.chain_id == chain_id))
            continue

        eintraege.sort(key=lambda eintrag: struktur_je_schluessel[eintrag[0]].eroeffnet_am)
        for position, (struktur_schluessel, erkennung) in enumerate(eintraege, start=1):
            verbindung.execute(
                insert(chain_links).values(
                    chain_id=chain_id,
                    structure_id=struktur_id_je_schluessel[struktur_schluessel],
                    sequenz=position,
                    verknuepfungstyp="open" if position == 1 else "roll",
                    erkennung=erkennung,
                )
            )

        # Vertrag 18: Kennzahlen der betroffenen Kette nachziehen. Der
        # Endzustand kommt aus ENDZUSTAND_JE_EREIGNIS (importiert, nicht
        # nachgebaut), ausgewertet über das letzte Glied.
        betroffene = [struktur_je_schluessel[eintrag[0]] for eintrag in eintraege]
        geschlossen = all(s.status == "geschlossen" for s in betroffene)
        letzte = betroffene[-1]
        verbindung.execute(
            update(chains)
            .where(chains.c.chain_id == chain_id)
            .values(
                eroeffnet_am=min(s.eroeffnet_am for s in betroffene),
                anzahl_rolls=len(betroffene) - 1,
                beendet_am=letzte.geschlossen_am if geschlossen else None,
                endzustand=(
                    ENDZUSTAND_JE_EREIGNIS.get(letzte.schluss_ereignistyp, "Geschlossen")
                    if geschlossen
                    else "Offen"
                ),
            )
        )

    for struktur_name, kette_name in verwaiste:
        print(
            f"Verwaister Override: Struktur {struktur_name} an Kette {kette_name} "
            "— von der Automatik nicht mehr gefunden; Zeile bleibt stehen",
            file=sys.stderr,
        )
    return len(overrides) - len(verwaiste), verwaiste


def _assignment_links_neu_schreiben(
    verbindung: Connection, ketten_ergebnis, exec_je_id: Mapping[str, Mapping]
) -> None:
    """Vertrag 22: Zeilen mit erkennung 'auto'/'heuristik' neu schreiben,
    Zeilen mit 'manuell' bleiben unangetastet.

    Die Paare (Optionsausführung, Aktienausführung) ergeben sich aus dem
    Zuteilungsübergang der Automatik: Jede Zuteilungs-Fortsetzung in einer
    Kette gehört zur vorangehenden Struktur, die per ``assignment`` geschlossen
    wurde; deren Legs liefern die Options-, die Fortsetzung die Aktien-Id."""
    verbindung.execute(
        delete(assignment_links).where(assignment_links.c.erkennung != "manuell")
    )
    for kette in ketten_ergebnis.chains:
        glieder = list(kette.glieder)
        for position, glied in enumerate(glieder):
            fortsetzung = glied.structure
            if fortsetzung.methode != "zuteilung":
                continue
            option = next(
                (
                    glieder[stelle].structure
                    for stelle in range(position - 1, -1, -1)
                    if glieder[stelle].structure.schluss_ereignistyp == "assignment"
                ),
                None,
            )
            if option is None:
                raise ValueError(
                    f"Zuteilungsstruktur {_struktur_schluessel(fortsetzung)}: keine per "
                    "Zuteilung geschlossene Optionsstruktur in derselben Kette — "
                    "kein assignment_links-Paar ableitbar"
                )
            for leg in option.leg_schluessel:
                schliessung = exec_je_id.get(leg.close_exec_id or "")
                if schliessung is None or schliessung["ereignistyp"] != "assignment":
                    continue
                for fortschreibung in fortsetzung.leg_schluessel:
                    verbindung.execute(
                        insert(assignment_links).values(
                            option_exec_id=leg.close_exec_id,
                            stock_exec_id=fortschreibung.open_exec_id,
                            erkennung="auto",
                            bestaetigt_am=None,
                        )
                    )
