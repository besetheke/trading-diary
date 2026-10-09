"""Lese-API über Ketten, Strukturen und Ausführungen (AP-07l), seit AP-08l
mit statischer Auslieferung der gebauten Oberfläche.

Umsetzung des Vertrags 1–17 aus ``auftraege/AP-07lv.md`` (Abnahmebasis:
``tests/test_api_lesen.py``). Die Anwendung ist ausschließlich lesend — im
OpenAPI-Schema kommt keine andere Methode als ``get`` vor (Vertrag 2) — und
reicht durch, was ``journal rebuild`` geschrieben hat. Ausnahmen nur die
genannten: ``struktur_summe_netto`` je Kette (Entscheidung 4) und nichts
anderes gerechnet, keine Umrechnung nach Euro, keine Kennzahlen.

Geld, Mengen, Strikes und Preise gehen als Zeichenketten über die Leitung
(Entscheidung 1): JSON kennt nur Gleitkommazahlen, ein ``Decimal`` als Zahl
wäre der stille Genauigkeitsverlust aus Regel 5. Leere Werte bleiben leer und
werden nie zu ``"0"`` (Vertrag 13). Jede Geldangabe nennt Währung und Sicht;
die Sicht ist hier ausnahmslos ``"konto"`` (Entscheidung 2, OF-36).

Dokumentierte Annahmen (Regel 10, OF-44):

- ``limit`` ist mindestens 1 — der Vertrag nennt Vorgabe und Höchstwert, aber
  keine Untergrenze; ``limit = 0`` wäre eine Anfrage ohne Antwort.
- Bei gleicher ``handelszeit`` entscheidet im Drilldown die ``exec_id``
  aufsteigend, bei gleicher ``eroeffnet_am`` in der Kettenliste die
  aufsteigende ``chain_id`` — der Vertrag verlangt Sortierung und
  Determinierismus, schweigt aber zum Gleichstand.
- Bei gleicher ``sequenz`` zweier Kettenglieder entscheidet die aufsteigende
  ``structure_id``, welches das erste bzw. letzte Glied ist (AP-07p, P8,
  OF-47) — derselbe Gleichstand, dieselbe Antwort.
- Der Standardbauort der Oberfläche ist ``ui/dist`` neben der Datenbankdatei,
  nicht neben diesem Modul — sonst fände jeder Testlauf die einmal gebaute
  Oberfläche des Projektverzeichnisses, und der Normalzustand ohne Build
  (Vertrag 4) wäre nicht mehr prüfbar (OF-45).
"""

import os
import pathlib
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import delete, exists, func, insert, select, update
from sqlalchemy.engine import Connection

from journal.db import create_db_engine
from journal.preise import praemie_als_text
from journal.schema import (
    campaigns,
    chain_links,
    chains,
    entity_tags,
    executions,
    journal_entries,
    legs,
    structures,
    tags,
)

# Entscheidung 2: Die Lese-API liefert ausschließlich die Kontosicht; die
# Kettensicht (OF-36) ist noch nicht gebaut.
SICHT = "konto"


# ---------------------------------------------------------------------------
# Antwortmodelle (Vertrag 8–14)
# ---------------------------------------------------------------------------


class KetteAntwort(BaseModel):
    """Eine Kette (Vertrag 8)."""

    chain_id: int
    natur_schluessel: str
    underlying: str
    asset_class: str
    seite: str | None
    eroeffnet_am: datetime
    beendet_am: datetime | None
    anzahl_rolls: int
    endzustand: str | None
    anzahl_glieder: int
    # AP-07pv, P8: Prämie des ersten bzw. letzten Glieds, Durchreichen.
    eroeffnungspreis: str | None
    schlusspreis: str | None
    struktur_summe_netto: str | None
    waehrung: str | None
    waehrungen: list[str]
    sicht: str
    # AP-13x: OA-Zuordnung der Kette (AP-13wk) — reines Durchreichen der
    # gespeicherten Werte, keine Berechnung, keine Interpretation.
    oa_strategie: str | None
    oa_status: str | None
    oa_erkennung: str | None


class StrukturAntwort(BaseModel):
    """Eine Struktur (Vertrag 10)."""

    structure_id: int
    natur_schluessel: str
    asset_class: str
    typ: str
    underlying: str
    expiry: date | None
    short_strike: str | None
    long_strike: str | None
    breite: str | None
    menge: str
    eroeffnet_am: datetime
    geschlossen_am: datetime | None
    dte_bei_eroeffnung: int | None
    status: str | None
    erkennung: str
    # AP-07pv, P7: Prämien je Kontrakt; offen heißt ohne Schlusspreis.
    eroeffnungspreis: str | None
    schlusspreis: str | None
    brutto_pnl: str | None
    kommission: str | None
    netto_pnl: str | None
    waehrung: str
    sicht: str
    # AP-13x: OA-Zuordnung der Struktur (AP-13wk) — reines Durchreichen.
    oa_strategie: str | None
    oa_status: str | None
    oa_erkennung: str | None


class KettengliedAntwort(BaseModel):
    """Ein Kettenglied mit seiner Struktur (Vertrag 9)."""

    sequenz: int
    verknuepfungstyp: str
    erkennung: str
    struktur: StrukturAntwort


class KetteDetailAntwort(KetteAntwort):
    glieder: list[KettengliedAntwort]


class LegAntwort(BaseModel):
    """Eine Leg (Vertrag 11)."""

    leg_id: int
    conid: int
    open_exec_id: str
    close_exec_id: str | None
    menge: str
    matching_methode: str
    offen_ja_nein: bool
    basis_ungeklaert: bool
    brutto_pnl: str | None
    kommission_gesamt: str | None


class StrukturDetailAntwort(StrukturAntwort):
    legs: list[LegAntwort]


class AusfuehrungAntwort(BaseModel):
    """Eine Ausführung des Drilldowns mit ihrer Rolle (Vertrag 7 und 12)."""

    exec_id: str
    rolle: str
    conid: int
    symbol: str
    side: str
    menge: str
    preis: str
    waehrung: str
    kommission: str | None
    handelszeit: datetime
    ereignistyp: str
    exec_batch: str | None
    oa_trade: str | None


class KettenListeAntwort(BaseModel):
    gesamt: int
    treffer: list[KetteAntwort]


# ---------------------------------------------------------------------------
# Journal (AP-07j): Notizen und Tags — Benutzerdaten, überleben jeden Rebuild
# ---------------------------------------------------------------------------


class NotizAntwort(BaseModel):
    """Eine Journal-Notiz (AP-07j, Tabelle)."""

    id: int
    scope_typ: str
    scope_id: str
    text: str
    erstellt_am: datetime
    geaendert_am: datetime | None


class JournalAntwort(BaseModel):
    """Notizen und Tags eines Bereichs (AP-07j, Tabelle)."""

    scope_typ: str
    scope_id: str
    notizen: list[NotizAntwort]
    tags: list[str]


class NotizEingabe(BaseModel):
    """Text einer neuen oder geänderten Notiz — er bleibt unverändert."""

    text: str


class TagsEingabe(BaseModel):
    """Namen der Tags, die die Zuordnung des Bereichs vollständig ersetzen."""

    tags: list[str]


class TagEintrag(BaseModel):
    """Ein Tag mit der Zahl seiner Zuordnungen (AP-07j, ``GET /tags``)."""

    name: str
    anzahl: int


# AP-07j, Entscheidung „Bereiche": ``tag`` ist der Handelstag und braucht kein
# vorhandenes Objekt — das ist das tägliche Journal; chain/structure/campaign
# verlangen die numerische ID und Existenz in der Kontosicht bzw. campaigns.
JOURNAL_BEREICHE = ("campaign", "chain", "structure", "tag")


# ---------------------------------------------------------------------------
# Tagesübersicht und Kalender (AP-07t): was ``journal rebuild`` geschrieben
# hat, je Handelstag aufbereitet — immer lesend, immer aktiv.
# ---------------------------------------------------------------------------


class TagKetteAntwort(BaseModel):
    """Eine Kette in der Tagesliste (AP-07t)."""

    chain_id: int
    natur_schluessel: str
    underlying: str
    asset_class: str
    seite: str | None
    anzahl_rolls: int
    endzustand: str | None
    eroeffnet_am: datetime
    beendet_am: datetime | None


class TagRollAntwort(BaseModel):
    """Ein Roll-Glied, dessen Struktur an dem Tag eröffnet wurde (AP-07t)."""

    chain_id: int
    structure_id: int
    underlying: str
    sequenz: int
    eroeffnet_am: datetime


class TagRealisiertAntwort(BaseModel):
    """Realisiertes Ergebnis einer Währung an einem Tag (AP-07t)."""

    waehrung: str
    sicht: str
    anzahl_strukturen: int
    brutto: str
    kommission: str
    netto: str


class TagAntwort(BaseModel):
    """Die Tagesübersicht — vier Listen, leer, nie 404 (AP-07t)."""

    datum: date
    sicht: str
    eroeffnet: list[TagKetteAntwort]
    beendet: list[TagKetteAntwort]
    rolls: list[TagRollAntwort]
    realisiert: list[TagRealisiertAntwort]


class KalenderRealisiertAntwort(BaseModel):
    """Realisiertes Netto einer Währung an einem Kalendertag (AP-07t)."""

    waehrung: str
    sicht: str
    netto: str


class KalenderTagAntwort(BaseModel):
    """Ein Tag mit Ereignissen im Monatsüberblick (AP-07t)."""

    datum: date
    eroeffnet: int
    beendet: int
    rolls: int
    realisiert: list[KalenderRealisiertAntwort]


class KalenderAntwort(BaseModel):
    """Der Monatsüberblick — nur Tage mit Ereignissen, aufsteigend."""

    monat: str
    sicht: str
    tage: list[KalenderTagAntwort]


# ---------------------------------------------------------------------------
# Umsetzung der Zeilen
# ---------------------------------------------------------------------------


def _als_text(wert: Decimal | None) -> str | None:
    """``Decimal`` als Zeichenkette in Dezimalschreibweise (Entscheidung 1).

    Leer bleibt leer — nie ``"0"``, nie ``None`` als Zahl (Vertrag 13)."""
    return None if wert is None else str(wert)


def _journal_bereich_pruefen(
    verbindung: Connection, scope_typ: str, scope_id: str
) -> None:
    """Prüft den Bereich vor jedem Zugriff (AP-07j): 422 für einen unbekannten
    Bereich, eine nicht numerische ID oder ein ungültiges Datum; 404 für ein
    fehlendes Objekt.

    Ketten und Strukturen müssen in der **Kontosicht** existieren — die
    Sichtspalte liegt auf ``chains`` und ``chain_links``, nicht auf
    ``structures``; eine Struktur zählt deshalb nur, wenn die Kontosicht
    sie verknüpft.
    """
    if scope_typ not in JOURNAL_BEREICHE:
        raise HTTPException(
            status_code=422,
            detail=f"Unbekannter Bereich {scope_typ!r}: "
            "chain, structure, campaign oder tag",
        )
    if scope_typ == "tag":
        try:
            date.fromisoformat(scope_id)
        except ValueError:
            raise HTTPException(
                status_code=422, detail=f"Kein Datum JJJJ-MM-TT: {scope_id!r}"
            ) from None
        return
    try:
        nummer = int(scope_id)
    except ValueError:
        raise HTTPException(
            status_code=422, detail=f"Keine numerische Kennung: {scope_id!r}"
        ) from None
    if scope_typ == "chain":
        vorhanden = verbindung.execute(
            select(chains.c.chain_id).where(
                chains.c.chain_id == nummer, chains.c.sicht == SICHT
            )
        ).scalar_one_or_none()
    elif scope_typ == "structure":
        vorhanden = verbindung.execute(
            select(structures.c.structure_id).where(
                structures.c.structure_id == nummer,
                exists(
                    select(chain_links.c.chain_id).where(
                        chain_links.c.structure_id == structures.c.structure_id,
                        chain_links.c.sicht == SICHT,
                    )
                ),
            )
        ).scalar_one_or_none()
    else:
        vorhanden = verbindung.execute(
            select(campaigns.c.campaign_id).where(campaigns.c.campaign_id == nummer)
        ).scalar_one_or_none()
    if vorhanden is None:
        benennung = {"chain": "Kette", "structure": "Struktur", "campaign": "Kampagne"}
        raise HTTPException(
            status_code=404, detail=f"{benennung[scope_typ]} {nummer} nicht gefunden"
        )


def _journal_laden(
    verbindung: Connection, scope_typ: str, scope_id: str
) -> JournalAntwort:
    """Notizen und Tags eines Bereichs (AP-07j): Notizen neueste zuerst, bei
    Gleichstand die größere ``id``; Tags alphabetisch ohne Beachtung der
    Schreibweise, in der Schreibweise der Tabelle."""
    notiz_zeilen = verbindung.execute(
        select(journal_entries)
        .where(
            journal_entries.c.scope_typ == scope_typ,
            journal_entries.c.scope_id == scope_id,
        )
        .order_by(journal_entries.c.erstellt_am.desc(), journal_entries.c.id.desc())
    ).mappings().all()
    tag_namen = verbindung.execute(
        select(tags.c.name)
        .join(entity_tags, entity_tags.c.tag_id == tags.c.id)
        .where(
            entity_tags.c.scope_typ == scope_typ,
            entity_tags.c.scope_id == scope_id,
        )
        .order_by(func.lower(tags.c.name), tags.c.name)
    ).scalars().all()
    return JournalAntwort(
        scope_typ=scope_typ,
        scope_id=scope_id,
        notizen=[
            NotizAntwort(
                id=z["id"],
                scope_typ=z["scope_typ"],
                scope_id=z["scope_id"],
                text=z["text"],
                erstellt_am=z["erstellt_am"],
                geaendert_am=z["geaendert_am"],
            )
            for z in notiz_zeilen
        ],
        tags=list(tag_namen),
    )


def _text_pruefen(text: str) -> None:
    """Mindestens ein Zeichen außer Leerraum, sonst 422 (AP-07j).

    Der Text selbst bleibt unverändert — Leerzeichen und Zeilenumbrüche
    werden weder beim Anlegen noch beim Ändern angetastet."""
    if not text.strip():
        raise HTTPException(
            status_code=422, detail="Der Text braucht mindestens ein Zeichen außer Leerraum"
        )


def _tag_kette_als_dict(k) -> dict:
    """Spaltenwerte einer Kettenzeile für die Tagesliste (AP-07t)."""
    return dict(
        chain_id=k["chain_id"],
        natur_schluessel=k["natur_schluessel"],
        underlying=k["underlying"],
        asset_class=k["asset_class"],
        seite=k["seite"],
        anzahl_rolls=k["anzahl_rolls"],
        endzustand=k["endzustand"],
        eroeffnet_am=k["eroeffnet_am"],
        beendet_am=k["beendet_am"],
    )


def _null(wert: Decimal | None) -> Decimal:
    """Leere Geldfelder zählen beim Summieren als 0 (AP-07t) — geschlossene
    Strukturen tragen immer Werte, die Ausnahme ist rein defensiv."""
    return Decimal(0) if wert is None else wert


def _realisiert_je_waehrung(
    verbindung: Connection, anfang: datetime, ende: datetime
) -> dict[str, dict]:
    """Summen der im halboffenen Fenster ``[anfang, ende)`` geschlossenen
    Strukturen der Kontosicht, je Währung (AP-07t).

    Die Sichtspalte liegt auf ``chain_links``, nicht auf ``structures``;
    der ``exists``-Zusatz hält Strukturen der Kettensicht heraus — dieselbe
    Technik wie bei der Bereichsprüfung des Journals.
    """
    zeilen = verbindung.execute(
        select(
            structures.c.waehrung,
            structures.c.brutto_pnl,
            structures.c.kommission,
            structures.c.netto_pnl,
        ).where(
            structures.c.geschlossen_am >= anfang,
            structures.c.geschlossen_am < ende,
            exists(
                select(chain_links.c.chain_id).where(
                    chain_links.c.structure_id == structures.c.structure_id,
                    chain_links.c.sicht == SICHT,
                )
            ),
        )
    ).all()
    summen: dict[str, dict] = {}
    for waehrung, brutto, kommission, netto in zeilen:
        eintrag = summen.setdefault(
            waehrung,
            dict(
                anzahl=0,
                brutto=Decimal(0),
                kommission=Decimal(0),
                netto=Decimal(0),
            ),
        )
        eintrag["anzahl"] += 1
        eintrag["brutto"] += _null(brutto)
        eintrag["kommission"] += _null(kommission)
        eintrag["netto"] += _null(netto)
    return summen


def _struktur_als_dict(s) -> dict:
    """Spaltenwerte einer Strukturzeile für das Antwortmodell (Vertrag 10)."""
    return dict(
        structure_id=s["structure_id"],
        natur_schluessel=s["natur_schluessel"],
        asset_class=s["asset_class"],
        typ=s["typ"],
        underlying=s["underlying"],
        expiry=s["expiry"],
        short_strike=_als_text(s["short_strike"]),
        long_strike=_als_text(s["long_strike"]),
        breite=_als_text(s["breite"]),
        menge=_als_text(s["menge"]),
        eroeffnet_am=s["eroeffnet_am"],
        geschlossen_am=s["geschlossen_am"],
        dte_bei_eroeffnung=s["dte_bei_eroeffnung"],
        status=s["status"],
        erkennung=s["erkennung"],
        # P7 (AP-07pv): Zeichenkette nach P3; offen heißt ohne Schlusspreis.
        eroeffnungspreis=praemie_als_text(s["eroeffnungspreis"]),
        schlusspreis=praemie_als_text(s["schlusspreis"]),
        brutto_pnl=_als_text(s["brutto_pnl"]),
        kommission=_als_text(s["kommission"]),
        netto_pnl=_als_text(s["netto_pnl"]),
        waehrung=s["waehrung"],
        sicht=SICHT,
        # AP-13x: direkt aus der Strukturzeile durchreichen — keine Berechnung.
        oa_strategie=s["oa_strategie"],
        oa_status=s["oa_status"],
        oa_erkennung=s["oa_erkennung"],
    )


def _kette_als_dict(
    k,
    glieder: int,
    waehrungen: list[str],
    summe: Decimal | None,
    eroeffnungspreis: Decimal | None,
    schlusspreis: Decimal | None,
) -> dict:
    """Spaltenwerte einer Kettenzeile für das Antwortmodell (Vertrag 8)."""
    return dict(
        chain_id=k["chain_id"],
        natur_schluessel=k["natur_schluessel"],
        underlying=k["underlying"],
        asset_class=k["asset_class"],
        # Vertrag 8: der Wert aus der Spalte, nie neu abgeleitet — eine Kette
        # ohne Optionen hat keine Seite, das ist kein "n.a.".
        seite=k["seite"],
        eroeffnet_am=k["eroeffnet_am"],
        beendet_am=k["beendet_am"],
        anzahl_rolls=k["anzahl_rolls"],
        endzustand=k["endzustand"],
        anzahl_glieder=glieder,
        # P8 (AP-07pv): Prämien aus erstem und letztem Glied — nur
        # Durchreichen, kein Rechnen.
        eroeffnungspreis=praemie_als_text(eroeffnungspreis),
        schlusspreis=praemie_als_text(schlusspreis),
        struktur_summe_netto=_als_text(summe),
        waehrung=waehrungen[0] if len(waehrungen) == 1 else None,
        waehrungen=waehrungen,
        sicht=SICHT,
        # AP-13x: die Kette trägt diese Spalten bereits (AP-13w-Migration) —
        # direkt aus der Kettenzeile, nicht über _ketten_zuschuesse()
        # hergeleitet.
        oa_strategie=k["oa_strategie"],
        oa_status=k["oa_status"],
        oa_erkennung=k["oa_erkennung"],
    )


def _ketten_zuschuesse(
    verbindung: Connection, chain_ids: list[int]
) -> dict[
    int, tuple[int, list[str], Decimal | None, Decimal | None, Decimal | None]
]:
    """Gliederzahl, Währungen, Struktursumme und die Prämien aus erstem und
    letztem Glied je Kette (Vertrag 8; AP-07pv, P8).

    Die Summe bleibt leer, wenn die Kette mehrere Währungen enthält
    (Entscheidung 3) oder eines ihrer Glieder noch kein Ergebnis trägt
    (Entscheidung 4) — eine offene Struktur ist kein Nullergebnis.

    Erstes und letztes Glied nach ``sequenz``; bei gleicher Sequenz
    entscheidet die aufsteigende ``structure_id`` (OF-47) — derselbe
    Determinismus wie bei OF-44.
    """
    je_kette: dict[int, dict] = {}
    if chain_ids:
        zeilen = verbindung.execute(
            select(
                chain_links.c.chain_id,
                chain_links.c.sequenz,
                chain_links.c.structure_id,
                structures.c.waehrung,
                structures.c.netto_pnl,
                structures.c.eroeffnungspreis,
                structures.c.schlusspreis,
            )
            .join(structures, structures.c.structure_id == chain_links.c.structure_id)
            .where(chain_links.c.chain_id.in_(chain_ids))
        ).all()
        for (
            chain_id,
            sequenz,
            structure_id,
            waehrung,
            netto_pnl,
            eroeffnungspreis,
            schlusspreis,
        ) in zeilen:
            eintrag = je_kette.setdefault(
                chain_id,
                dict(
                    glieder=0,
                    waehrungen=set(),
                    netto_pnls=[],
                    erste=None,
                    letzte=None,
                    eroeffnungspreis=None,
                    schlusspreis=None,
                ),
            )
            eintrag["glieder"] += 1
            eintrag["waehrungen"].add(waehrung)
            eintrag["netto_pnls"].append(netto_pnl)
            # P8: Prämie aus dem ersten bzw. letzten Glied — nur
            # Durchreichen, kein Rechnen.
            stelle = (sequenz, structure_id)
            if eintrag["erste"] is None or stelle < eintrag["erste"]:
                eintrag["erste"] = stelle
                eintrag["eroeffnungspreis"] = eroeffnungspreis
            if eintrag["letzte"] is None or stelle > eintrag["letzte"]:
                eintrag["letzte"] = stelle
                eintrag["schlusspreis"] = schlusspreis
    zuschuesse: dict[
        int, tuple[int, list[str], Decimal | None, Decimal | None, Decimal | None]
    ] = {}
    for chain_id, eintrag in je_kette.items():
        waehrungen = sorted(eintrag["waehrungen"])
        # Einheitlich und vollständig: nur dann ist die Summe eine Aussage.
        summe = (
            sum(eintrag["netto_pnls"])
            if len(waehrungen) == 1 and all(n is not None for n in eintrag["netto_pnls"])
            else None
        )
        zuschuesse[chain_id] = (
            eintrag["glieder"],
            waehrungen,
            summe,
            eintrag["eroeffnungspreis"],
            eintrag["schlusspreis"],
        )
    return zuschuesse


# ---------------------------------------------------------------------------
# Anwendung
# ---------------------------------------------------------------------------


def erzeuge_app(
    db_pfad: str | pathlib.Path,
    *,
    ui_verzeichnis: str | pathlib.Path | None = None,
    mit_journal: bool = False,
) -> FastAPI:
    """Baut die Lese-Anwendung auf einer Datenbankdatei (Vertrag 1).

    ``ui_verzeichnis`` benennt das Bauverzeichnis der Oberfläche (AP-08l,
    Vertrag 1): Ist es vorhanden, liefert die Anwendung ``index.html`` unter
    ``/`` aus, die Dateien darunter und für unbekannte Wege den Rückfall.
    Ohne Angabe wird ``ui/dist`` neben der Datenbankdatei gesucht (OF-45) —
    fehlt es dort, bleibt die Anwendung reine API, und die Wurzel sagt, was
    fehlt (Vertrag 4).

    ``mit_journal`` schaltet die Journal-Routen dazu (AP-07j): Ohne den
    Schalter bleibt das OpenAPI-Schema ausschließlich lesend. Das Modulobjekt
    ``app`` startet mit Journal — die Oberfläche braucht es.
    """
    engine = create_db_engine(db_pfad)  # Vertrag 3: die Pragmas setzt die Factory.

    if ui_verzeichnis is not None:
        ui_wurzel = pathlib.Path(ui_verzeichnis)
    else:
        # OF-45: Der Standardbauort hängt an der Datenbank, nicht an diesem
        # Modul und nicht am Arbeitsverzeichnis — sonst fände jeder Testlauf
        # die einmal gebaute Oberfläche des Projektverzeichnisses, und der
        # Normalzustand „frisch geklont, ohne Build“ wäre nicht mehr prüfbar.
        ui_wurzel = pathlib.Path(db_pfad).resolve().parent / "ui" / "dist"
    hat_oberflaeche = ui_wurzel.is_dir()

    applikation = FastAPI(title="Trading-Journal — Lese-API (Kontosicht)")

    @applikation.get("/ketten", response_model=KettenListeAntwort)
    def ketten(
        basiswert: str | None = None,
        anlageklasse: str | None = None,
        seite: str | None = None,
        endzustand: str | None = None,
        min_rolls: Annotated[int | None, Query(ge=0)] = None,
        max_rolls: Annotated[int | None, Query(ge=0)] = None,
        eroeffnet_ab: date | None = None,
        eroeffnet_bis: date | None = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> KettenListeAntwort:
        """Liste der Ketten — `gesamt` zählt vor der Begrenzung (Vertrag 4)."""
        # AP-04sw, Plan §5: „Keine Abfrage liefert Zeilen aus beiden Sichten
        # in einer Summe." Die Lese-API zeigt ausschließlich die Kontosicht
        # — die Kettensicht hat noch keine eigene Oberfläche/Route.
        bedingungen = [chains.c.sicht == "konto"]
        if basiswert:
            bedingungen.append(chains.c.underlying == basiswert)
        if anlageklasse:
            bedingungen.append(chains.c.asset_class == anlageklasse)
        if seite:
            bedingungen.append(chains.c.seite == seite)
        if endzustand:
            bedingungen.append(chains.c.endzustand == endzustand)
        if min_rolls is not None:
            bedingungen.append(chains.c.anzahl_rolls >= min_rolls)
        if max_rolls is not None:
            bedingungen.append(chains.c.anzahl_rolls <= max_rolls)
        if eroeffnet_ab is not None:
            bedingungen.append(chains.c.eroeffnet_am >= eroeffnet_ab)
        if eroeffnet_bis is not None:
            bedingungen.append(chains.c.eroeffnet_am <= eroeffnet_bis)
        with engine.connect() as verbindung:
            gesamt = verbindung.execute(
                select(func.count()).select_from(chains).where(*bedingungen)
            ).scalar_one()
            zeilen = verbindung.execute(
                select(chains)
                .where(*bedingungen)
                # Vertrag 4: das Neueste zuerst, bei Gleichstand nach
                # chain_id aufsteigend (OF-44) — deterministisch.
                .order_by(chains.c.eroeffnet_am.desc(), chains.c.chain_id)
                .limit(limit)
                .offset(offset)
            ).mappings().all()
            zuschuesse = _ketten_zuschuesse(verbindung, [z["chain_id"] for z in zeilen])
        leer = (0, [], None, None, None)
        return KettenListeAntwort(
            gesamt=gesamt,
            treffer=[
                KetteAntwort(**_kette_als_dict(z, *zuschuesse.get(z["chain_id"], leer)))
                for z in zeilen
            ],
        )

    @applikation.get("/ketten/{chain_id}", response_model=KetteDetailAntwort)
    def kette_einzeln(chain_id: int) -> KetteDetailAntwort:
        """Eine Kette samt Gliedern, nach Sequenz aufsteigend (Vertrag 5)."""
        with engine.connect() as verbindung:
            zeile = verbindung.execute(
                select(chains).where(chains.c.chain_id == chain_id)
            ).mappings().one_or_none()
            if zeile is None:
                raise HTTPException(status_code=404, detail="Kette nicht gefunden")
            zuschuesse = _ketten_zuschuesse(verbindung, [chain_id])
            glied_zeilen = verbindung.execute(
                select(chain_links)
                .where(chain_links.c.chain_id == chain_id)
                .order_by(chain_links.c.sequenz)
            ).mappings().all()
            strukturen = {
                s["structure_id"]: s
                for s in verbindung.execute(
                    select(structures).where(
                        structures.c.structure_id.in_([g["structure_id"] for g in glied_zeilen])
                    )
                ).mappings().all()
            }
        return KetteDetailAntwort(
            **_kette_als_dict(zeile, *zuschuesse.get(chain_id, (0, [], None, None, None))),
            glieder=[
                KettengliedAntwort(
                    sequenz=g["sequenz"],
                    verknuepfungstyp=g["verknuepfungstyp"],
                    erkennung=g["erkennung"],
                    struktur=StrukturAntwort(
                        **_struktur_als_dict(strukturen[g["structure_id"]])
                    ),
                )
                for g in glied_zeilen
            ],
        )

    @applikation.get("/strukturen/{structure_id}", response_model=StrukturDetailAntwort)
    def struktur_einzeln(structure_id: int) -> StrukturDetailAntwort:
        """Eine Struktur samt Legs (Vertrag 6)."""
        with engine.connect() as verbindung:
            zeile = verbindung.execute(
                select(structures).where(structures.c.structure_id == structure_id)
            ).mappings().one_or_none()
            if zeile is None:
                raise HTTPException(status_code=404, detail="Struktur nicht gefunden")
            leg_zeilen = verbindung.execute(
                select(legs)
                .where(legs.c.structure_id == structure_id)
                .order_by(legs.c.leg_id)
            ).mappings().all()
        return StrukturDetailAntwort(
            **_struktur_als_dict(zeile),
            legs=[
                LegAntwort(
                    leg_id=leg["leg_id"],
                    conid=leg["conid"],
                    open_exec_id=leg["open_exec_id"],
                    close_exec_id=leg["close_exec_id"],
                    menge=_als_text(leg["menge"]),
                    matching_methode=leg["matching_methode"],
                    offen_ja_nein=leg["offen_ja_nein"],
                    basis_ungeklaert=leg["basis_ungeklaert"],
                    brutto_pnl=_als_text(leg["brutto_pnl"]),
                    kommission_gesamt=_als_text(leg["kommission_gesamt"]),
                )
                for leg in leg_zeilen
            ],
        )

    @applikation.get(
        "/strukturen/{structure_id}/ausfuehrungen",
        response_model=list[AusfuehrungAntwort],
    )
    def ausfuehrungen(structure_id: int) -> list[AusfuehrungAntwort]:
        """Drilldown: jede Ausführung, die ein Leg dieser Struktur eröffnet
        oder schließt, zeitlich geordnet, je mit der Rolle (Vertrag 7)."""
        with engine.connect() as verbindung:
            vorhanden = verbindung.execute(
                select(structures.c.structure_id).where(
                    structures.c.structure_id == structure_id
                )
            ).scalar_one_or_none()
            if vorhanden is None:
                raise HTTPException(status_code=404, detail="Struktur nicht gefunden")
            rollen: dict[str, str] = {}
            for open_exec_id, close_exec_id in verbindung.execute(
                select(legs.c.open_exec_id, legs.c.close_exec_id).where(
                    legs.c.structure_id == structure_id
                )
            ).all():
                rollen[open_exec_id] = "eroeffnung"
                if close_exec_id is not None:
                    rollen[close_exec_id] = "schliessung"
            zeilen = verbindung.execute(
                select(executions)
                .where(executions.c.exec_id.in_(rollen))
                # Vertrag 7: aufsteigend nach handelszeit; Gleichstand
                # entscheidet die exec_id aufsteigend (OF-44).
                .order_by(executions.c.handelszeit, executions.c.exec_id)
            ).mappings().all()
        return [
            AusfuehrungAntwort(
                exec_id=z["exec_id"],
                rolle=rollen[z["exec_id"]],
                conid=z["conid"],
                symbol=z["symbol"],
                side=z["side"],
                menge=_als_text(z["menge"]),
                preis=_als_text(z["preis"]),
                waehrung=z["waehrung"],
                kommission=_als_text(z["kommission"]),
                handelszeit=z["handelszeit"],
                ereignistyp=z["ereignistyp"],
                exec_batch=z["exec_batch"],
                oa_trade=z["oa_trade"],
            )
            for z in zeilen
        ]

    # -----------------------------------------------------------------------
    # Tagesübersicht und Kalender (AP-07t): rein lesend, ohne Schalter immer
    # aktiv — das Schema der Standard-API bleibt ausschließlich ``get``. Auch
    # diese Routen stehen vor der Rückfall-Route der Oberfläche.
    # -----------------------------------------------------------------------

    @applikation.get("/tage/{datum}", response_model=TagAntwort)
    def tag_lesen(datum: date) -> TagAntwort:
        """Was an einem Handelstag passiert ist (AP-07t): eröffnete und
        beendete Ketten, Rolls und das realisierte Ergebnis je Währung.

        Ein Tag ist das Kalenderdatum der Zeitstempel, die Tagesgrenze das
        halboffene Intervall ``[00:00, nächster Tag 00:00)``.
        """
        anfang = datetime(datum.year, datum.month, datum.day)
        ende = anfang + timedelta(days=1)
        with engine.connect() as verbindung:
            eroeffnet = verbindung.execute(
                select(chains)
                .where(
                    chains.c.sicht == SICHT,
                    chains.c.eroeffnet_am >= anfang,
                    chains.c.eroeffnet_am < ende,
                )
                .order_by(chains.c.eroeffnet_am, chains.c.chain_id)
            ).mappings().all()
            beendet = verbindung.execute(
                select(chains)
                .where(
                    chains.c.sicht == SICHT,
                    chains.c.beendet_am >= anfang,
                    chains.c.beendet_am < ende,
                )
                .order_by(chains.c.beendet_am, chains.c.chain_id)
            ).mappings().all()
            roll_zeilen = verbindung.execute(
                select(
                    chain_links.c.chain_id,
                    chain_links.c.structure_id,
                    chain_links.c.sequenz,
                    structures.c.underlying,
                    structures.c.eroeffnet_am,
                )
                .join(structures, structures.c.structure_id == chain_links.c.structure_id)
                .where(
                    chain_links.c.sicht == SICHT,
                    chain_links.c.verknuepfungstyp == "roll",
                    structures.c.eroeffnet_am >= anfang,
                    structures.c.eroeffnet_am < ende,
                )
                .order_by(structures.c.eroeffnet_am, chain_links.c.chain_id)
            ).mappings().all()
            summen = _realisiert_je_waehrung(verbindung, anfang, ende)
        return TagAntwort(
            datum=datum,
            sicht=SICHT,
            eroeffnet=[TagKetteAntwort(**_tag_kette_als_dict(k)) for k in eroeffnet],
            beendet=[TagKetteAntwort(**_tag_kette_als_dict(k)) for k in beendet],
            rolls=[
                TagRollAntwort(
                    chain_id=z["chain_id"],
                    structure_id=z["structure_id"],
                    underlying=z["underlying"],
                    sequenz=z["sequenz"],
                    eroeffnet_am=z["eroeffnet_am"],
                )
                for z in roll_zeilen
            ],
            realisiert=[
                TagRealisiertAntwort(
                    waehrung=waehrung,
                    sicht=SICHT,
                    anzahl_strukturen=eintrag["anzahl"],
                    brutto=format(eintrag["brutto"], "f"),
                    kommission=format(eintrag["kommission"], "f"),
                    netto=format(eintrag["netto"], "f"),
                )
                for waehrung, eintrag in sorted(summen.items())
            ],
        )

    @applikation.get("/kalender", response_model=KalenderAntwort)
    def kalender(monat: Annotated[str, Query()]) -> KalenderAntwort:
        """Monatsüberblick (AP-07t): nur Tage mit Ereignissen, aufsteigend —
        Anzahlen der Eröffnungen, Beendigungen und Rolls, realisiertes Netto
        je Währung. ``monat`` ist ``JJJJ-MM``, alles andere ist 422."""
        teile = monat.split("-")
        if (
            len(teile) != 2
            or len(teile[0]) != 4
            or len(teile[1]) != 2
            or not teile[0].isdigit()
            or not teile[1].isdigit()
        ):
            raise HTTPException(status_code=422, detail=f"Kein Monat JJJJ-MM: {monat!r}")
        jahr, monat_nummer = int(teile[0]), int(teile[1])
        if not 1 <= monat_nummer <= 12:
            raise HTTPException(status_code=422, detail=f"Kein Monat JJJJ-MM: {monat!r}")
        anfang = datetime(jahr, monat_nummer, 1)
        ende = (
            datetime(jahr + 1, 1, 1)
            if monat_nummer == 12
            else datetime(jahr, monat_nummer + 1, 1)
        )
        ereignisse: dict[date, dict] = {}

        def eintrag_fuer(tag_datum: date) -> dict:
            return ereignisse.setdefault(
                tag_datum, dict(eroeffnet=0, beendet=0, rolls=0, realisiert={})
            )

        with engine.connect() as verbindung:
            for zeitpunkt in verbindung.execute(
                select(chains.c.eroeffnet_am).where(
                    chains.c.sicht == SICHT,
                    chains.c.eroeffnet_am >= anfang,
                    chains.c.eroeffnet_am < ende,
                )
            ).scalars():
                eintrag_fuer(zeitpunkt.date())["eroeffnet"] += 1
            for zeitpunkt in verbindung.execute(
                select(chains.c.beendet_am).where(
                    chains.c.sicht == SICHT,
                    chains.c.beendet_am >= anfang,
                    chains.c.beendet_am < ende,
                )
            ).scalars():
                eintrag_fuer(zeitpunkt.date())["beendet"] += 1
            for zeitpunkt in verbindung.execute(
                select(structures.c.eroeffnet_am)
                .join(chain_links, chain_links.c.structure_id == structures.c.structure_id)
                .where(
                    chain_links.c.sicht == SICHT,
                    chain_links.c.verknuepfungstyp == "roll",
                    structures.c.eroeffnet_am >= anfang,
                    structures.c.eroeffnet_am < ende,
                )
            ).scalars():
                eintrag_fuer(zeitpunkt.date())["rolls"] += 1
            for geschlossen_am, waehrung, netto in verbindung.execute(
                select(
                    structures.c.geschlossen_am,
                    structures.c.waehrung,
                    structures.c.netto_pnl,
                ).where(
                    structures.c.geschlossen_am >= anfang,
                    structures.c.geschlossen_am < ende,
                    exists(
                        select(chain_links.c.chain_id).where(
                            chain_links.c.structure_id == structures.c.structure_id,
                            chain_links.c.sicht == SICHT,
                        )
                    ),
                )
            ).all():
                realisiert = eintrag_fuer(geschlossen_am.date())["realisiert"]
                realisiert[waehrung] = realisiert.get(waehrung, Decimal(0)) + _null(netto)
        return KalenderAntwort(
            monat=monat,
            sicht=SICHT,
            tage=[
                KalenderTagAntwort(
                    datum=tag_datum,
                    eroeffnet=eintrag["eroeffnet"],
                    beendet=eintrag["beendet"],
                    rolls=eintrag["rolls"],
                    realisiert=[
                        KalenderRealisiertAntwort(
                            waehrung=waehrung,
                            sicht=SICHT,
                            netto=format(netto, "f"),
                        )
                        for waehrung, netto in sorted(eintrag["realisiert"].items())
                    ],
                )
                for tag_datum, eintrag in sorted(ereignisse.items())
            ],
        )

    # -----------------------------------------------------------------------
    # Journal (AP-07j): Notizen und Tags — nur auf Wunsch aktiv
    # (``mit_journal``), sonst bliebe das OpenAPI-Schema nicht ausschließlich
    # lesend (Vertrag 2). Die Routen stehen vor der Rückfall-Route der
    # Oberfläche, sonst finge diese sie ab. Jeder Aufruf schreibt in einer
    # kurzen Transaktion (Regel 9) und nur in ``journal_entries``, ``tags``,
    # ``entity_tags``; die Zeitstempel kommen vom Server (AP-07j).
    # -----------------------------------------------------------------------

    if mit_journal:

        @applikation.get("/journal/{scope_typ}/{scope_id}", response_model=JournalAntwort)
        def journal_lesen(scope_typ: str, scope_id: str) -> JournalAntwort:
            """Notizen und Tags eines Bereichs — neueste Notiz zuerst."""
            with engine.connect() as verbindung:
                _journal_bereich_pruefen(verbindung, scope_typ, scope_id)
                return _journal_laden(verbindung, scope_typ, scope_id)

        @applikation.post(
            "/journal/{scope_typ}/{scope_id}/notizen",
            response_model=NotizAntwort,
            status_code=201,
        )
        def notiz_anlegen(
            scope_typ: str, scope_id: str, eingabe: NotizEingabe
        ) -> NotizAntwort:
            """Neue Notiz — der Text bleibt unverändert, Zeilen inklusive."""
            _text_pruefen(eingabe.text)
            jetzt = datetime.now()
            with engine.begin() as verbindung:
                _journal_bereich_pruefen(verbindung, scope_typ, scope_id)
                notiz_id = verbindung.execute(
                    insert(journal_entries).values(
                        scope_typ=scope_typ,
                        scope_id=scope_id,
                        text=eingabe.text,
                        erstellt_am=jetzt,
                    )
                ).inserted_primary_key[0]
            return NotizAntwort(
                id=notiz_id,
                scope_typ=scope_typ,
                scope_id=scope_id,
                text=eingabe.text,
                erstellt_am=jetzt,
                geaendert_am=None,
            )

        @applikation.put("/journal/notizen/{notiz_id}", response_model=NotizAntwort)
        def notiz_aendern(notiz_id: int, eingabe: NotizEingabe) -> NotizAntwort:
            """Text einer Notiz ersetzen; ``erstellt_am`` bleibt,
            ``geaendert_am`` wird gesetzt."""
            _text_pruefen(eingabe.text)
            jetzt = datetime.now()
            with engine.begin() as verbindung:
                zeile = verbindung.execute(
                    select(journal_entries).where(journal_entries.c.id == notiz_id)
                ).mappings().one_or_none()
                if zeile is None:
                    raise HTTPException(status_code=404, detail="Notiz nicht gefunden")
                verbindung.execute(
                    update(journal_entries)
                    .where(journal_entries.c.id == notiz_id)
                    .values(text=eingabe.text, geaendert_am=jetzt)
                )
            return NotizAntwort(
                id=notiz_id,
                scope_typ=zeile["scope_typ"],
                scope_id=zeile["scope_id"],
                text=eingabe.text,
                erstellt_am=zeile["erstellt_am"],
                geaendert_am=jetzt,
            )

        @applikation.delete("/journal/notizen/{notiz_id}", status_code=204)
        def notiz_loeschen(notiz_id: int) -> None:
            """Notiz auf ausdrücklichen Wunsch entfernen (AP-07j: Nutzer-Handlung
            an eigenen Daten, Regel 4)."""
            with engine.begin() as verbindung:
                ergebnis = verbindung.execute(
                    delete(journal_entries).where(journal_entries.c.id == notiz_id)
                )
                if ergebnis.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Notiz nicht gefunden")

        @applikation.put(
            "/journal/{scope_typ}/{scope_id}/tags", response_model=JournalAntwort
        )
        def tags_ersetzen(
            scope_typ: str, scope_id: str, eingabe: TagsEingabe
        ) -> JournalAntwort:
            """Tag-Zuordnung des Bereichs vollständig ersetzen (AP-07j).

            Namen werden getrimmt; gleiche Namen ohne Beachtung der
            Schreibweise zählen einmal (erste Schreibweise der Anfrage), ein
            bereits vorhandener Tag behält **seine** Schreibweise. Tags werden
            nie gelöscht — nur Zuordnungen.
            """
            namen: list[str] = []
            gesehene: set[str] = set()
            for rohname in eingabe.tags:
                name = rohname.strip()
                if not name:
                    raise HTTPException(status_code=422, detail="Tag-Name ohne Inhalt")
                if name.lower() not in gesehene:
                    gesehene.add(name.lower())
                    namen.append(name)
            with engine.begin() as verbindung:
                _journal_bereich_pruefen(verbindung, scope_typ, scope_id)
                tag_ids: list[int] = []
                for name in namen:
                    tag_id = verbindung.execute(
                        select(tags.c.id).where(func.lower(tags.c.name) == name.lower())
                    ).scalar_one_or_none()
                    if tag_id is None:
                        tag_id = verbindung.execute(
                            insert(tags).values(name=name)
                        ).inserted_primary_key[0]
                    tag_ids.append(tag_id)
                verbindung.execute(
                    delete(entity_tags).where(
                        entity_tags.c.scope_typ == scope_typ,
                        entity_tags.c.scope_id == scope_id,
                    )
                )
                if tag_ids:
                    verbindung.execute(
                        insert(entity_tags),
                        [
                            {
                                "tag_id": tag_id,
                                "scope_typ": scope_typ,
                                "scope_id": scope_id,
                            }
                            for tag_id in tag_ids
                        ],
                    )
                antwort = _journal_laden(verbindung, scope_typ, scope_id)
            return antwort

        @applikation.get("/tags", response_model=list[TagEintrag])
        def tags_alle() -> list[TagEintrag]:
            """Alle Tags mit der Zahl ihrer Zuordnungen — alphabetisch ohne
            Beachtung der Schreibweise; ein unbenutzter Tag bleibt mit 0."""
            with engine.connect() as verbindung:
                zeilen = verbindung.execute(
                    select(tags.c.name, func.count(entity_tags.c.tag_id).label("anzahl"))
                    .select_from(
                        tags.outerjoin(entity_tags, entity_tags.c.tag_id == tags.c.id)
                    )
                    .group_by(tags.c.id, tags.c.name)
                    .order_by(func.lower(tags.c.name), tags.c.name)
                ).all()
            return [TagEintrag(name=name, anzahl=anzahl) for name, anzahl in zeilen]

    # -----------------------------------------------------------------------
    # Statische Auslieferung der Oberfläche (AP-08l, Vertrag 1–5)
    #
    # Diese Route steht absichtlich ganz am Ende: Erst die API-Routen, dann
    # die Dateien, dann der Rückfall auf ``index.html`` (Vertrag 3). Auch
    # FastAPIs eigene Wege — ``/openapi.json``, ``/docs`` — sind bei der
    # Erzeugung registriert und gehen damit ebenfalls vor. Ein Aufruf wie
    # ``/ketten/abc`` passt weiterhin auf die API-Route und bleibt 422; ein
    # unbekannter Bezeichner bleibt die 404 aus dem API-Handler.
    # -----------------------------------------------------------------------

    @applikation.get("/{voller_pfad:path}", include_in_schema=False)
    def oberflaeche(voller_pfad: str) -> FileResponse:
        """Liefert die gebaute Oberfläche — Datei oder Rückfall (AP-08l)."""
        if not hat_oberflaeche:
            # Vertrag 4: Ohne Build bleibt die API nutzbar, und die Wurzel
            # sagt, was fehlt — der Normalzustand auf einem frisch geklonten
            # Rechner.
            raise HTTPException(
                status_code=404,
                detail=(
                    "Keine Oberfläche ausgeliefert: Das Bauverzeichnis fehlt. "
                    "Im Verzeichnis ui bauen (npm install, npm run build) oder "
                    "erzeuge_app(..., ui_verzeichnis=...) übergeben."
                ),
            )
        wurzel = ui_wurzel.resolve()
        # Vertrag 5: Kein Ausbruch aus dem Bauverzeichnis. Erst auflösen,
        # dann gegen die Wurzel prüfen — ein Pfad mit „..“ oder absoluten
        # Stücken landet außerhalb und bekommt 404, niemals eine Projektdatei.
        kandidat = (wurzel / voller_pfad).resolve()
        try:
            kandidat.relative_to(wurzel)
        except ValueError:
            raise HTTPException(
                status_code=404, detail="Pfad außerhalb der Oberfläche"
            ) from None
        if not kandidat.is_file():
            # Vertrag 2: Eine Einzelseitenanwendung führt ihre Wege selbst —
            # tiefe Verweise wie /positionen/17 bleiben so nach dem Neuladen
            # brauchbar.
            kandidat = wurzel / "index.html"
        if not kandidat.is_file():
            raise HTTPException(
                status_code=404, detail="index.html fehlt im Bauverzeichnis"
            )
        return FileResponse(kandidat)

    return applikation


# Vertrag 1: Modulobjekt mit dem Pfad wie die CLI — Umgebungsvariable
# JOURNAL_DB, sonst journal.db (OF-06). Mit Journal (AP-07j): Die Oberfläche
# des täglichen Journals braucht die schreibenden Routen.
app = erzeuge_app(os.environ.get("JOURNAL_DB", "journal.db"), mit_journal=True)
