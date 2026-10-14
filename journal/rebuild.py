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

**Prämien an der Struktur** (AP-07p): ``_struktur_zeile()`` füllt seit diesem
Paket auch ``eroeffnungspreis`` und ``schlusspreis`` — berechnet einmal in
``journal.preise`` (Vertrag P1–P8 aus ``auftraege/AP-07pv.md``). Offen heißt
ohne Schlusspreis (P2), niemals Null.

**OA-Werte an Kette und Struktur** (AP-13wk): ``_struktur_zeile()`` und
``_kette_zeile()`` setzen ``oa_strategie``/``oa_status``/``oa_erkennung``
bei jedem Lauf zuerst auf ``None``; ``oa_werte_schreiben()``
(``journal.oa_persistenz``) überschreibt sie gezielt. Ohne die Baseline
bliebe eine Zuordnung bestehen, deren OA-Trade nicht mehr importiert ist
(``tests/test_rebuild_oa.py``, „zweiter Lauf entfernt …").

**Offene Campaign-Kandidaten** (AP-05sk): nach jedem Lauf gezählt über
``campaign_kandidaten()`` (``engine.campaigns``) und ``campaign_links``
(``journal.campaigns_sicht``) — reine Anzeige: nichts wird klassifiziert,
geschrieben oder still als ``independent`` einsortiert.

**Overrides in beiden Sichten** (AP-04szk): Ein bestätigter
``chain_overrides`` ist eine Aussage über das reale Geschehen („diese
Struktur setzt jene Kette fort") und wird deshalb einmal gegeben — in der
Kontosicht, wo der Nutzer ihn sieht. Die Kettensicht übernimmt ihn über die
Naturschlüssel: Struktur und Zielkette müssen dort unter demselben Schlüssel
existieren, sonst zählt der Override dort als „ohne Entsprechung" und bleibt
folgenlos — keine Überlappungs-Heuristik.

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
from datetime import datetime

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Connection

from engine.campaigns import campaign_kandidaten
from engine.chains import ENDZUSTAND_JE_EREIGNIS, KettenErgebnis, bilde_chains
from engine.chains import Chain as Kette
from engine.kettensicht import kettensicht_legs
from engine.matching import MatchingErgebnis, bilde_legs
from engine.structures import Structure as Struktur
from engine.structures import StrukturErgebnis, bilde_structures
from journal.campaigns_sicht import offene_kandidaten_zaehlen
from journal.db import STANDARD_BUSY_TIMEOUT_MS, create_db_engine
from journal.kapitalmassnahmen import kapitalmassnahmen_befuellen
from journal.oa_persistenz import oa_werte_schreiben
from journal.preise import nettopraemie
from journal.roller_verknuepfung import METHODE as ROLLER_METHODE
from journal.roller_verknuepfung import verknuepfe_roller
from journal.schema import (
    assignment_links,
    campaign_ablehnungen,
    campaign_links,
    campaigns,
    chain_links,
    chain_overrides,
    chains,
    corporate_actions,
    executions,
    instruments,
    legs,
    roller_link,
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
    # OA-Abgleich (AP-13wk): zugeordnete OA-Trades und solche ohne
    # eindeutige Kette. Ebenfalls nicht persistiert, jeder Lauf neu.
    oa_zugeordnet: int = 0
    oa_fehler: int = 0
    # Campaign-Kandidaten ohne gemeinsame Kampagne (AP-05sk). Wie oben:
    # nicht persistiert, jeder Lauf neu berechnet.
    campaign_kandidaten_offen: int = 0
    # AP-11: Roller-Ketten, die in diesem Lauf neu mit Journal-Ketten verknüpft wurden,
    # und Roller-Ketten ohne Journal-Kette (Ausführung noch nicht im Flex-Export).
    roller_neu: int = 0
    roller_ohne_kette: int = 0
    # AP-04sw: Kettensicht-Zählwerte, parallel zu den obigen (Kontosicht-)
    # Feldern, deren Bedeutung unverändert bleibt.
    structures_kette: int = 0
    chains_kette: int = 0
    legs_kette: int = 0
    chain_links_kette: int = 0
    # AP-04szk: bestätigte Overrides, über die Naturschlüssel auch in der
    # Kettensicht angewandt. „Ohne Entsprechung" heißt: Struktur oder Zielkette
    # existiert dort unter anderem Schlüssel (umgeleitete Ausführungen).
    overrides_kette_angewandt: int = 0
    overrides_kette_ohne_entsprechung: int = 0


@dataclass(frozen=True)
class Bestand:
    """Lesen und Rechnen eines Laufs über die Rohdaten (AP-04d, Vertrag 10).

    Der vordere Teil von ``_rebuild_laufen()`` ohne jedes Schreiben. Die
    Durchsicht der Rollkandidaten (``journal.durchsicht``) ruft dieselbe
    Funktion auf — es gibt nur einen Lesepfad, zwei Kopien liefen früher
    oder später auseinander.
    """

    ausfuehrungen: list[dict]
    exec_je_id: dict[str, dict]
    instrument_je_conid: dict[int, dict]
    kapitalmassnahmen: list[dict]
    matching: MatchingErgebnis
    legs_als_dict: list[dict]
    struktur_ergebnis: StrukturErgebnis
    ketten_ergebnis: KettenErgebnis
    # Einschließlich der synthetischen Zuteilungs-Fortsetzungen, die erst
    # ``bilde_chains()`` anlegt — sie gehören zu ``structures``, sonst hätten
    # ihre chain_links keinen Fremdschlüssel.
    struktur_je_schluessel: dict[str, Struktur]


@dataclass(frozen=True)
class _SichtErgebnis:
    """Rückgabe von ``_sicht_schreiben()`` (AP-04sw) — alles, was der
    Aufrufer braucht, um auf dieser Sicht weiterzuarbeiten: Overrides und
    OA-Abgleich für beide Sichten (AP-04szk/AP-13zk), Campaign-Sichtbarkeit
    nur für ``sicht='konto'``."""

    struktur_id_je_schluessel: dict[str, int]
    ketten_id_je_schluessel: dict[str, int]
    struktur_je_schluessel: dict[str, Struktur]
    kette_je_schluessel: dict[str, Kette]
    glieder_je_kette: dict[str, list[list]]
    ketten_ergebnis: KettenErgebnis


def bestand_berechnen(verbindung: Connection) -> Bestand:
    """Liest die Rohdaten und rechnet Legs, Strukturen und Ketten — rein, ohne
    zu schreiben (AP-04d, Vertrag 10). Schreiben, Abgleich und Overrides sind
    Sache von ``_rebuild_laufen()``."""

    # -- Lesen (Vertrag 4): Rohdaten.
    ausfuehrungen = [dict(z) for z in verbindung.execute(select(executions)).mappings()]
    exec_je_id = {satz["exec_id"]: satz for satz in ausfuehrungen}
    instrument_je_conid = {
        satz["conid"]: satz for satz in verbindung.execute(select(instruments)).mappings()
    }
    # Kapitalmaßnahmen aus corporate_actions; Vorlage ist
    # kapitalmassnahmen_ableiten() (Auftrag AP-04p): Zeilen ohne Instrument
    # werden verworfen, wie dort.
    massnahmen = [dict(z) for z in verbindung.execute(select(corporate_actions)).mappings()]
    kapitalmassnahmen = [
        satz
        for satz in massnahmen
        if satz["neuer_conid"] in instrument_je_conid
        and (satz["alter_conid"] is None or satz["alter_conid"] in instrument_je_conid)
    ]

    # -- Rechnen: die reine Engine, unverändert.
    matching = bilde_legs(ausfuehrungen, instrument_je_conid, kapitalmassnahmen)
    legs_als_dict = [asdict(leg) for leg in matching.legs]
    struktur_ergebnis = bilde_structures(legs_als_dict, ausfuehrungen, instrument_je_conid)
    ketten_ergebnis = bilde_chains(
        struktur_ergebnis, legs_als_dict, ausfuehrungen, instrument_je_conid
    )

    struktur_je_schluessel = _struktur_je_schluessel_mit_synthetischen(
        struktur_ergebnis, ketten_ergebnis
    )

    return Bestand(
        ausfuehrungen=ausfuehrungen,
        exec_je_id=exec_je_id,
        instrument_je_conid=instrument_je_conid,
        kapitalmassnahmen=kapitalmassnahmen,
        matching=matching,
        legs_als_dict=legs_als_dict,
        struktur_ergebnis=struktur_ergebnis,
        ketten_ergebnis=ketten_ergebnis,
        struktur_je_schluessel=struktur_je_schluessel,
    )


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


def offene_rollkandidaten(
    db_pfad: str | pathlib.Path, *, busy_timeout_ms: int = STANDARD_BUSY_TIMEOUT_MS
) -> int:
    """Zählt die offenen Rollkandidaten, ohne etwas zu schreiben (AP-06dk).

    Liefert dieselbe Zahl wie ``RebuildErgebnis.kandidaten_offen``: Rechnen
    über ``bestand_berechnen()`` und ``_offene_kandidaten()`` — der Lesepfad,
    den auch die Durchsicht nutzt (AP-04d, Vertrag 10), kein vollständiger
    Rebuild mit Rücknahme. Die ID-Zuordnungen stammen aus den vorhandenen
    Kontosicht-Zeilen (``structures``/``chains``/``chain_links`` mit
    ``sicht='konto'``): Nach einem ``rebuild`` stehen sie auf dem Stand, den
    ``_rebuild_laufen()`` benutzt hat, angewandte Overrides eingerechnet.
    Die abgeleiteten Tabellen bleiben unangetastet.
    """
    engine = create_db_engine(db_pfad, busy_timeout_ms=busy_timeout_ms)
    try:
        with engine.connect() as verbindung:
            bestand = bestand_berechnen(verbindung)
            overrides = [
                dict(z) for z in verbindung.execute(select(chain_overrides)).mappings()
            ]
            struktur_id_je_schluessel = {
                z["natur_schluessel"]: z["structure_id"]
                for z in verbindung.execute(
                    select(structures.c.natur_schluessel, structures.c.structure_id).where(
                        structures.c.sicht == "konto"
                    )
                ).mappings()
            }
            ketten_id_je_schluessel = {
                z["natur_schluessel"]: z["chain_id"]
                for z in verbindung.execute(
                    select(chains.c.natur_schluessel, chains.c.chain_id).where(
                        chains.c.sicht == "konto"
                    )
                ).mappings()
            }
            # Glieder je Kette wie in _rebuild_laufen(): Naturschlüssel der
            # Struktur plus Erkennung — der Stand NACH angewandten Overrides,
            # so wie ihn _offene_kandidaten() sieht.
            ketten_schluessel_je_id = {cid: k for k, cid in ketten_id_je_schluessel.items()}
            struktur_schluessel_je_id = {
                sid: s for s, sid in struktur_id_je_schluessel.items()
            }
            glieder_je_kette: dict[str, list[list]] = {}
            for zeile in verbindung.execute(
                select(
                    chain_links.c.chain_id, chain_links.c.structure_id, chain_links.c.erkennung
                ).where(chain_links.c.sicht == "konto")
            ).mappings():
                glieder_je_kette.setdefault(
                    ketten_schluessel_je_id[zeile["chain_id"]], []
                ).append([struktur_schluessel_je_id[zeile["structure_id"]], zeile["erkennung"]])
            return _offene_kandidaten(
                bestand.ketten_ergebnis,
                overrides,
                glieder_je_kette,
                struktur_id_je_schluessel,
                ketten_id_je_schluessel,
            )
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------


def _struktur_schluessel(struktur: Struktur) -> str:
    """Naturschlüssel einer Struktur (Vertrag 7): die ``open_exec_id`` ihrer
    Legs, aufsteigend sortiert, mit ``|`` verbunden. AP-04z: Teilverkäufe einer
    Zuteilung tragen dieselbe Eröffnung — ihr Schluss steht dann mit ``>``
    dahinter (``schluessel_zusatz``)."""
    basis = "|".join(sorted(schluessel.open_exec_id for schluessel in struktur.leg_schluessel))
    zusatz = getattr(struktur, "schluessel_zusatz", None)
    return f"{basis}>{zusatz}" if zusatz else basis


def _kette_schluessel(kette: Kette) -> str:
    """Naturschlüssel einer Kette (Vertrag 8): der Naturschlüssel der
    eröffnenden Struktur, mit ``k:`` davor."""
    return "k:" + _struktur_schluessel(kette.glieder[0].structure)


def _struktur_je_schluessel_mit_synthetischen(
    struktur_ergebnis: StrukturErgebnis, ketten_ergebnis: KettenErgebnis
) -> dict[str, Struktur]:
    """Synthetische Zuteilungs-Fortsetzungen (engine.chains) stehen nur als
    Kettenglieder an — sie gehören ebenfalls in structures, sonst hätten
    ihre chain_links keinen Fremdschlüssel. Gemeinsam genutzt von
    ``bestand_berechnen()`` und ``_sicht_schreiben()`` (AP-04sw)."""
    strukturen = list(struktur_ergebnis.structures)
    bekannte_schluessel = {_struktur_schluessel(s) for s in strukturen}
    for kette in ketten_ergebnis.chains:
        for glied in kette.glieder:
            schluessel = _struktur_schluessel(glied.structure)
            if schluessel not in bekannte_schluessel:
                strukturen.append(glied.structure)
                bekannte_schluessel.add(schluessel)
    return {_struktur_schluessel(s): s for s in strukturen}


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
    struktur: Struktur, schluessel: str, bestand: Bestand, leg_je_schluessel, sicht: str
) -> dict:
    """Spaltenwerte einer Structure für ``structures`` (Vertrag 10–12) — seit
    AP-07p samt der Prämien je Kontrakt (AP-07pv, P1/P2)."""
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
    # AP-07pv, P1: je Leg die Leg-Menge × den Preis der zugehörigen
    # Ausführung, je Kontrakt geteilt durch die Strukturmenge. P2: Nur eine
    # geschlossene Struktur bekommt einen Schlusspreis — offen bleibt leer,
    # keine Null, die wie ein Rückkauf zum Nulltarif aus sähe.
    eroeffnungspreis = nettopraemie(
        struktur,
        schliessung=False,
        bestand=bestand,
        leg_je_schluessel=leg_je_schluessel,
    )
    schlusspreis = (
        None
        if struktur.status != "geschlossen"
        else nettopraemie(
            struktur,
            schliessung=True,
            bestand=bestand,
            leg_je_schluessel=leg_je_schluessel,
        )
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
        eroeffnungspreis=eroeffnungspreis,
        schlusspreis=schlusspreis,
        brutto_pnl=struktur.brutto_pnl,
        kommission=struktur.kommission_gesamt,
        netto_pnl=netto_pnl,
        waehrung=_struktur_waehrung(struktur, schluessel, bestand.exec_je_id),
        erkennung=erkennung,
        strategy_id=None,
        # AP-13wk: Baseline None — oa_werte_schreiben() überschreibt gezielt.
        oa_strategie=None,
        oa_status=None,
        oa_erkennung=None,
        sicht=sicht,
    )


def _kette_zeile(kette: Kette, sicht: str) -> dict:
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
        # AP-13wk: Baseline None — oa_werte_schreiben() überschreibt gezielt.
        oa_strategie=None,
        oa_status=None,
        oa_erkennung=None,
        sicht=sicht,
    )


def _anzahl_je_sicht(verbindung: Connection, tabelle, sicht: str) -> int:
    return verbindung.execute(
        select(func.count()).select_from(tabelle).where(tabelle.c.sicht == sicht)
    ).scalar_one()


# ---------------------------------------------------------------------------
# Der Lauf selbst
# ---------------------------------------------------------------------------


def _sicht_schreiben(
    verbindung: Connection,
    sicht: str,
    sicht_legs,
    bestand: Bestand,
    gesicherte_struktur_ids: set[int],
    gesicherte_ketten_ids: set[int],
) -> "_SichtErgebnis":
    """Schreibt Strukturen/Ketten/Legs/Kettenglieder für genau eine Sicht
    (AP-04sw). Baut dafür ``engine.structures``/``engine.chains`` auf dem
    gegebenen Leg-Satz neu auf — für ``sicht='konto'`` liefert das dieselben
    Strukturen/Ketten wie vor AP-04sw (``matching.legs`` unverändert), für
    ``sicht='kette'`` den Satz aus ``engine.kettensicht.kettensicht_legs()``.

    Overrides (``gesicherte_*_ids``) schützen nur die Kontosicht vor
    Löschung — die Kettensicht bekommt die Bestätigungen erst danach, über
    die Naturschlüssel übersetzt durch ``_rebuild_laufen()`` (AP-04szk).
    """
    sicht_legs = tuple(sicht_legs)
    legs_als_dict = [
        dict(
            conid=leg.conid, open_exec_id=leg.open_exec_id, close_exec_id=leg.close_exec_id,
            menge=leg.menge, offen_ja_nein=leg.offen_ja_nein, brutto_pnl=leg.brutto_pnl,
            kommission_gesamt=leg.kommission_gesamt,
        )
        for leg in sicht_legs
    ]
    struktur_ergebnis = bilde_structures(
        legs_als_dict, bestand.ausfuehrungen, bestand.instrument_je_conid
    )
    ketten_ergebnis = bilde_chains(
        struktur_ergebnis, legs_als_dict, bestand.ausfuehrungen, bestand.instrument_je_conid
    )
    struktur_je_schluessel = _struktur_je_schluessel_mit_synthetischen(
        struktur_ergebnis, ketten_ergebnis
    )
    leg_je_schluessel = {
        (leg.open_exec_id, leg.close_exec_id): leg for leg in sicht_legs
    }

    alte_struktur_ids = {
        z["natur_schluessel"]: z["structure_id"]
        for z in verbindung.execute(
            select(structures.c.structure_id, structures.c.natur_schluessel)
            .where(structures.c.sicht == sicht)
        ).mappings()
    }
    alte_ketten_ids = {
        z["natur_schluessel"]: z["chain_id"]
        for z in verbindung.execute(
            select(chains.c.chain_id, chains.c.natur_schluessel).where(chains.c.sicht == sicht)
        ).mappings()
    }

    # structures: Abgleich über den Naturschlüssel (Vertrag 9), je Sicht.
    struktur_id_je_schluessel: dict[str, int] = {}
    for schluessel in sorted(struktur_je_schluessel):
        werte = _struktur_zeile(
            struktur_je_schluessel[schluessel], schluessel, bestand, leg_je_schluessel, sicht
        )
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
    for leg in sicht_legs:
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
                open_faktor=leg.open_faktor,
                close_faktor=leg.close_faktor,
                structure_id=struktur_id_je_leg.get((leg.open_exec_id, leg.close_exec_id)),
                sicht=sicht,
            )
        )

    # chains: Abgleich über den Naturschlüssel (Vertrag 9, 13), je Sicht.
    kette_je_schluessel = {_kette_schluessel(k): k for k in ketten_ergebnis.chains}
    ketten_id_je_schluessel: dict[str, int] = {}
    for schluessel in sorted(kette_je_schluessel):
        werte = _kette_zeile(kette_je_schluessel[schluessel], sicht)
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
        _roller_links_abraeumen(verbindung, entfallene_ketten_ids)
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
                    sicht=sicht,
                )
            )
            # AP-04z: Der Verknüpfungstyp reist mit — Zuteilung und Covered
            # Call bleiben es auch, wenn ein Override die Kette neu ordnet.
            eintraege.append(
                [_struktur_schluessel(glied.structure), glied.erkennung,
                 glied.verknuepfungstyp]
            )
        glieder_je_kette[schluessel] = eintraege

    return _SichtErgebnis(
        struktur_id_je_schluessel=struktur_id_je_schluessel,
        ketten_id_je_schluessel=ketten_id_je_schluessel,
        struktur_je_schluessel=struktur_je_schluessel,
        kette_je_schluessel=kette_je_schluessel,
        glieder_je_kette=glieder_je_kette,
        ketten_ergebnis=ketten_ergebnis,
    )


def _roller_links_abraeumen(verbindung: Connection, chain_ids: list[int]) -> None:
    """AP-11: Wegfallende Ketten reißen keine ``roller_link``-Zeile mit. Nur die aus der
    ``orderReference`` abgeleiteten Zeilen werden entfernt — sie entstehen nach dem Rebuild
    wieder; Zeilen anderer Herkunft blockieren das Löschen (Regel 4, kein Überschreiben)."""
    verbindung.execute(delete(roller_link).where(
        roller_link.c.journal_chain_id.in_(chain_ids), roller_link.c.methode == ROLLER_METHODE))


def _rebuild_laufen(verbindung: Connection) -> RebuildErgebnis:
    # -- Kapitalmaßnahmen (AP-03vz): aus den Flex-Rohzeilen ableiten und in
    #    corporate_actions ergänzen, bevor gerechnet wird. Ergänzt nur, was
    #    fehlt (Regel 4); bestand_berechnen() und damit die Durchsicht der
    #    Rollkandidaten lesen dieselbe Tabelle und bleiben lesend.
    kapitalmassnahmen_befuellen(verbindung)

    # -- Lesen und Rechnen über die gemeinsame Funktion (AP-04d, Vertrag 10):
    #    kein zweiter Lesepfad neben der Durchsicht der Rollkandidaten.
    bestand = bestand_berechnen(verbindung)
    exec_je_id = bestand.exec_je_id
    matching = bestand.matching

    # -- Lesen (Vertrag 4): Overrides, aktueller Stand der abgeleiteten
    #    Tabellen für den Abgleich. Gelten nur für die Kontosicht (Grenze).
    overrides = [dict(z) for z in verbindung.execute(select(chain_overrides)).mappings()]
    # Plan §6, Block B, Regel 2: Bestätigung und Ablehnung sind beide
    # Benutzerdaten. Angewandt wird nur die Bestätigung; die Ablehnung hält
    # einen Kandidaten dauerhaft von der Liste fern. Gesichert gegen Löschung
    # (Regel 4) sind die Zeilen beider Urteile.
    bestaetigungen = [o for o in overrides if o["urteil"] == "bestaetigt"]
    gesicherte_struktur_ids = {o["structure_id"] for o in overrides}
    gesicherte_ketten_ids = {o["chain_id"] for o in overrides}
    # AP-05d (Regel 4): Die Kampagnen-Klassifikation sind ebenso Benutzerdaten
    # mit Fremdschlüsseln auf chains — die Ketten aus campaign_links und
    # campaign_ablehnungen zählen wie die der Overrides zu den gesicherten,
    # sonst bräche der Rebuild ab, sobald eine klassifizierte Kette
    # verschwindet. Hier einmal gelesen; die Kandidaten-Zählung unten nutzt
    # dieselben Zeilen wieder.
    kampagnen_links = [
        dict(z) for z in verbindung.execute(select(campaign_links)).mappings()
    ]
    ablehnungen = [
        dict(z) for z in verbindung.execute(select(campaign_ablehnungen)).mappings()
    ]
    gesicherte_ketten_ids |= {z["chain_id"] for z in kampagnen_links}
    gesicherte_ketten_ids |= {z["chain_id_a"] for z in ablehnungen}
    gesicherte_ketten_ids |= {z["chain_id_b"] for z in ablehnungen}

    # -- Schreiben (Vertrag 6). legs und chain_links sind vollständiger
    #    Austausch (Vertrag 14/15) und gehen zuerst weg — sie halten die
    #    Fremdschlüssel auf structures/chains. Beide Sichten zusammen, da
    #    keine der beiden Tabellen eine Sicht-übergreifende Identität trägt.
    verbindung.execute(delete(legs))
    verbindung.execute(delete(chain_links))

    konto = _sicht_schreiben(
        verbindung, "konto", matching.legs, bestand, gesicherte_struktur_ids,
        gesicherte_ketten_ids,
    )
    struktur_id_je_schluessel = konto.struktur_id_je_schluessel
    ketten_id_je_schluessel = konto.ketten_id_je_schluessel
    struktur_je_schluessel = konto.struktur_je_schluessel
    kette_je_schluessel = konto.kette_je_schluessel
    glieder_je_kette = konto.glieder_je_kette
    ketten_ergebnis = konto.ketten_ergebnis

    # AP-04sw: die Kettensicht — eigene Zuordnung derselben Ausführungen
    # (Plan §5), ohne Override-Schutz (Grenze von AP-04s).
    kette_legs = kettensicht_legs(
        matching.legs, exec_je_id, bestand.instrument_je_conid
    )
    kette_sicht = _sicht_schreiben(verbindung, "kette", kette_legs, bestand, set(), set())

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

    # -- AP-04szk (OF-61): dieselben Bestätigungen auch in der Kettensicht.
    #    Der Nutzer entscheidet in der Kontosicht; übersetzt wird über die
    #    Naturschlüssel — Struktur und Zielkette müssen dort unter demselben
    #    Schlüssel existieren. Fehlt einer von beiden (die Kettensicht hat
    #    andere Strukturen, wo Ausführungen umgeleitet sind), zählt der
    #    Override als „ohne Entsprechung" — gezählt, nicht angewandt, nie
    #    ein Fehler. Keine Überlappungs-Heuristik.
    konto_schluessel_je_struktur_id = {
        sid: s for s, sid in struktur_id_je_schluessel.items()
    }
    konto_schluessel_je_ketten_id = {cid: k for k, cid in ketten_id_je_schluessel.items()}
    uebersetzte: list[dict] = []
    ohne_entsprechung = 0
    for override in bestaetigungen:
        struktur_id = kette_sicht.struktur_id_je_schluessel.get(
            konto_schluessel_je_struktur_id.get(override["structure_id"])
        )
        chain_id = kette_sicht.ketten_id_je_schluessel.get(
            konto_schluessel_je_ketten_id.get(override["chain_id"])
        )
        if struktur_id is None or chain_id is None:
            ohne_entsprechung += 1
            continue
        uebersetzte.append(dict(structure_id=struktur_id, chain_id=chain_id))

    overrides_kette_angewandt, _ = _overrides_anwenden(
        verbindung,
        uebersetzte,
        kette_sicht.glieder_je_kette,
        kette_sicht.struktur_id_je_schluessel,
        kette_sicht.ketten_id_je_schluessel,
        kette_sicht.struktur_je_schluessel,
        {o["chain_id"] for o in uebersetzte},
        sicht="kette",
    )

    # -- assignment_links (Vertrag 22): nicht-manuelle Zeilen neu schreiben.
    _assignment_links_neu_schreiben(verbindung, ketten_ergebnis, exec_je_id)

    # -- OA-Abgleich (AP-13wk): Baseline steht seit _struktur_zeile()/
    #    _kette_zeile() auf None, hier gezielt überschreiben. Nach den
    #    Overrides, damit Ketten, die diese löschen (Vertrag 19), nicht mehr
    #    beschrieben werden.
    oa_zugeordnet, oa_fehler = oa_werte_schreiben(
        verbindung,
        kette_je_schluessel,
        struktur_je_schluessel,
        struktur_id_je_schluessel,
        ketten_id_je_schluessel,
        exec_je_id,
        bestand.instrument_je_conid,
    )

    # -- OA-Abgleich auch für die Kettensicht (AP-13zk): dieselbe Funktion,
    #    mit Ketten/Strukturen und ID-Zuordnungen der Kettensicht — der
    #    Fingerabdruck prüft je Sicht gegen deren eigene Strukturen. Die
    #    Zählwerte entfallen, RebuildErgebnis bleibt auf die Kontosicht
    #    bezogen (Abnahmebasis AP-13z). Wie dort laufen die Overrides der
    #    Kettensicht (AP-04szk) vorher, damit Ketten, die sie löschen
    #    (Vertrag 19), nicht mehr beschrieben werden.
    oa_werte_schreiben(
        verbindung,
        kette_sicht.kette_je_schluessel,
        kette_sicht.struktur_je_schluessel,
        kette_sicht.struktur_id_je_schluessel,
        kette_sicht.ketten_id_je_schluessel,
        exec_je_id,
        bestand.instrument_je_conid,
    )

    offene_kandidaten = _offene_kandidaten(
        ketten_ergebnis,
        overrides,
        glieder_je_kette,
        struktur_id_je_schluessel,
        ketten_id_je_schluessel,
    )

    # -- Kampagnen-Zeiten nachziehen (AP-05d): underlying, eroeffnet_am und
    #    beendet_am jeder Kampagne sind aus ihren Ketten abgeleitet — bei
    #    jedem Lauf neu bestimmt, aus den Kontosicht-Zeilen. netto_pnl_eur
    #    bleibt unberührt (kein Euro-Betrag ohne FX-Umrechnung, AP-04v,
    #    Entscheidung 2).
    _kampagnen_zeiten_nachziehen(verbindung)

    # -- Campaign-Kandidaten (AP-05sk): wie viele noch keine gemeinsame
    #    Kampagne haben — reine Anzeige, kein Schreiben. Ein Kandidat gilt
    #    als entschieden, wenn beide Ketten bereits derselben campaign_id
    #    zugeordnet sind (unabhängig vom beziehungstyp) — oder, seit AP-05d,
    #    wenn das Paar in campaign_ablehnungen steht.
    kampagnen_je_chain_id: dict[int, set[int]] = {}
    for zeile in kampagnen_links:
        kampagnen_je_chain_id.setdefault(zeile["chain_id"], set()).add(
            zeile["campaign_id"]
        )
    chain_id_je_objekt = {
        id(kette): ketten_id_je_schluessel[schluessel]
        for schluessel, kette in kette_je_schluessel.items()
    }
    campaign_kandidaten_offen = offene_kandidaten_zaehlen(
        campaign_kandidaten(kette_je_schluessel.values()),
        kampagnen_je_chain_id,
        chain_id_je_objekt,
        abgelehnt={(z["chain_id_a"], z["chain_id_b"], z["typ"]) for z in ablehnungen},
    )

    roller = verknuepfe_roller(verbindung, datetime.now())

    return RebuildErgebnis(
        roller_neu=roller.neu,
        roller_ohne_kette=len(roller.ohne_kette),
        legs=_anzahl_je_sicht(verbindung, legs, "konto"),
        structures=_anzahl_je_sicht(verbindung, structures, "konto"),
        chains=_anzahl_je_sicht(verbindung, chains, "konto"),
        chain_links=_anzahl_je_sicht(verbindung, chain_links, "konto"),
        nicht_strukturiert=len(bestand.struktur_ergebnis.nicht_strukturiert),
        overrides_angewandt=angewandt,
        overrides_verwaist=len(verwaiste),
        kandidaten_offen=offene_kandidaten,
        oa_zugeordnet=oa_zugeordnet,
        oa_fehler=oa_fehler,
        campaign_kandidaten_offen=campaign_kandidaten_offen,
        legs_kette=_anzahl_je_sicht(verbindung, legs, "kette"),
        structures_kette=_anzahl_je_sicht(verbindung, structures, "kette"),
        chains_kette=_anzahl_je_sicht(verbindung, chains, "kette"),
        chain_links_kette=_anzahl_je_sicht(verbindung, chain_links, "kette"),
        overrides_kette_angewandt=overrides_kette_angewandt,
        overrides_kette_ohne_entsprechung=ohne_entsprechung,
    )


def _kampagnen_zeiten_nachziehen(verbindung: Connection) -> None:
    """AP-05d: ``underlying``/``eroeffnet_am``/``beendet_am`` jeder Kampagne
    aus ihren Ketten (Kontosicht) neu bestimmen — früheste Eröffnung,
    ``beendet_am`` leer, solange eine Kette offen ist, sonst die späteste
    Schließung.

    Ein campaign_links auf eine Kette ohne Kontosicht-Zeile bliebe folgenlos;
    eine Kampagne ohne jede Kontosicht-Kette wird nicht angefasst (keine
    still erfundenen Zeiten). ``netto_pnl_eur`` bleibt unberührt. Bei
    unterschiedlichen Underlyings der Ketten — über ``independent``
    möglich — gewinnt das alphabetisch erste: deterministisch, ohne die
    Daten zu mischen (Annahme, Regel 10).
    """
    ketten_zeile_je_id = {
        z["chain_id"]: z
        for z in verbindung.execute(
            select(chains).where(chains.c.sicht == "konto")
        ).mappings()
    }
    ketten_je_kampagne: dict[int, list[dict]] = {}
    for zeile in verbindung.execute(select(campaign_links)).mappings():
        kette = ketten_zeile_je_id.get(zeile["chain_id"])
        if kette is not None:
            ketten_je_kampagne.setdefault(zeile["campaign_id"], []).append(kette)
    for campaign_id, ketten in ketten_je_kampagne.items():
        verbindung.execute(
            update(campaigns)
            .where(campaigns.c.campaign_id == campaign_id)
            .values(
                underlying=min(k["underlying"] for k in ketten),
                eroeffnet_am=min(k["eroeffnet_am"] for k in ketten),
                beendet_am=(
                    None
                    if any(k["beendet_am"] is None for k in ketten)
                    else max(k["beendet_am"] for k in ketten)
                ),
            )
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
    sicht: str = "konto",
) -> tuple[int, list[tuple[object, object]]]:
    """Wendet chain_overrides an: Struktur in die Zielkette hängen, erkennung
    'manuell', betroffene Ketten neu nummerieren und Kennzahlen nachziehen
    (Vertrag 17/18). ``sicht`` landet in den neu geschriebenen chain_links —
    die Kettensicht ruft mit übersetzten Overrides (AP-04szk). Liefert
    (Anzahl angewandt, Liste verwaister)."""
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
                _roller_links_abraeumen(verbindung, [chain_id])
                verbindung.execute(delete(chains).where(chains.c.chain_id == chain_id))
            continue

        eintraege.sort(key=lambda eintrag: struktur_je_schluessel[eintrag[0]].eroeffnet_am)
        anzahl_rolls = 0
        for position, eintrag in enumerate(eintraege, start=1):
            struktur_schluessel, erkennung = eintrag[0], eintrag[1]
            bisher = eintrag[2] if len(eintrag) > 2 else None
            if bisher in ("zuteilung", "covered_call"):
                typ = bisher
            else:
                typ = "open" if position == 1 else "roll"
            anzahl_rolls += typ == "roll"
            verbindung.execute(
                insert(chain_links).values(
                    chain_id=chain_id,
                    structure_id=struktur_id_je_schluessel[struktur_schluessel],
                    sequenz=position,
                    verknuepfungstyp=typ,
                    erkennung=erkennung,
                    sicht=sicht,
                )
            )

        # Vertrag 18: Kennzahlen der betroffenen Kette nachziehen. Der
        # Endzustand kommt aus ENDZUSTAND_JE_EREIGNIS (importiert, nicht
        # nachgebaut), ausgewertet über das letzte Glied.
        betroffene = [struktur_je_schluessel[eintrag[0]] for eintrag in eintraege]
        geschlossen = all(s.status == "geschlossen" for s in betroffene)
        # AP-04z: wie in engine.chains — die späteste Schließung beendet die Kette.
        letzte = max(
            enumerate(betroffene),
            key=lambda e: (e[1].geschlossen_am or datetime.max, e[0]),
        )[1]
        verbindung.execute(
            update(chains)
            .where(chains.c.chain_id == chain_id)
            .values(
                eroeffnet_am=min(s.eroeffnet_am for s in betroffene),
                anzahl_rolls=anzahl_rolls,
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
    # AP-04z: Die Paare liefert die Kettenbildung selbst (Zuteilung am Leg,
    # Zuordnung über Zeit, Basiswert und Strike). Manuelle Paare bleiben.
    manuell = {
        (z[0], z[1])
        for z in verbindung.execute(
            select(assignment_links.c.option_exec_id, assignment_links.c.stock_exec_id)
        )
    }
    paare: set[tuple[str, str]] = {
        paar for paar in ketten_ergebnis.zuteilungs_paare if paar not in manuell
    }

    # AP-04pk: `assignment_links` ist eine Menge von Paaren, keine Liste.
    # Schließt **eine** Zuteilungsausführung mehrere Legs derselben Struktur,
    # liefert die Kombinatorik oben dasselbe Paar mehrfach — am echten
    # Bestand 10 von 320. Verdichtet wird die erzeugte Menge; ein
    # `INSERT OR IGNORE` wäre etwas anderes, es verschluckte auch echte
    # Widersprüche.
    for option_exec_id, stock_exec_id in sorted(paare):
        verbindung.execute(
            insert(assignment_links).values(
                option_exec_id=option_exec_id,
                stock_exec_id=stock_exec_id,
                erkennung="auto",
                bestaetigt_am=None,
            )
        )
