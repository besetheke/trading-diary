"""Lese-API über Ketten, Strukturen und Ausführungen (AP-07l), seit AP-08l
mit statischer Auslieferung der gebauten Oberfläche, seit AP-08-kampagnen mit
den bestätigten Kampagnen (``campaigns``/``campaign_links``) und seit AP-06e
mit der Equity-Kurve (``/equity``) — der erste echte Kennzahlen-Endpunkt
(Plan §6, AP-07 „Rest"): er reicht nicht nur durch, sondern reicht, was
``analytics.equity.equity_bericht`` rechnet.

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

import json
import os
import pathlib
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, delete, exists, func, insert, or_, select, update
from sqlalchemy.engine import Connection

from analytics.cashflows import cashflow_bericht
from analytics.equity import EquityErgebnis, LoseLegFilter, equity_bericht
from analytics.ib_abgleich import ib_abgleich_bericht
from analytics.kapital import kapital_bericht
from analytics.nav import nav_bericht
from analytics.performance import performance_bericht
from analytics.unrealisiert import unrealisiert_auswertung
from journal.db import create_db_engine
from journal.preise import praemie_als_text
from journal.schema import (
    campaign_links,
    campaigns,
    chain_links,
    chains,
    entity_tags,
    executions,
    flex_ib_realized,
    flex_open_positions,
    instruments,
    journal_entries,
    legs,
    structures,
    tags,
)

# Entscheidung 2: Die Lese-API liefert ausschließlich die Kontosicht; die
# Kettensicht (OF-36) ist noch nicht gebaut.
SICHT = "konto"

# AP-07s: Sortierbare Spalten der Kettenliste — nur echte Spalten der Tabelle
# ``chains``. Abgeleitete Werte (``struktur_summe_netto``, Preise) sind nicht
# sortierbar: Sie werden je Seite zusammengestellt, eine Sortierung über die
# aktuelle Seite wäre irreführend. Die ``Literal``-Typen tragen die Aufzählung
# ins OpenAPI-Schema und lehnen alles andere mit 422 ab (Regel „nichts
# zurechtbiegen"); Groß-/Kleinschreibung bleibt bedeutungstragend.
Sortierspalte = Literal[
    "eroeffnet_am",
    "beendet_am",
    "underlying",
    "asset_class",
    "seite",
    "anzahl_rolls",
    "endzustand",
    "oa_strategie",
]
Richtung = Literal["asc", "desc"]


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
    # Kontrakte bzw. Stück der Eröffnung: ``menge`` des ersten Glieds,
    # Durchreichen (Spalte „Anzahl").
    menge: str | None
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


# AP-08-kampagnen: bestätigte Kampagnen — reines Durchreichen der Tabellen,
# keine Neuberechnung der Kandidaten (die bleiben bei der CLI-Dateirundreise).
class KampagneAntwort(BaseModel):
    """Eine bestätigte Kampagne (campaigns-Zeile mit Kettenzahl)."""

    campaign_id: int
    underlying: str
    eroeffnet_am: datetime
    beendet_am: datetime | None
    # Regel 5/13: Geld als Zeichenkette wie bei /ketten; eine laufende
    # Kampagne ohne Ergebnis bleibt leer, kein "0".
    netto_pnl_eur: str | None
    anzahl_ketten: int


class KampagnenKetteAntwort(BaseModel):
    """Eine verknüpfte Kette einer Kampagne (campaign_links-Zeile)."""

    chain_id: int
    natur_schluessel: str
    beziehungstyp: str
    erkennung: str
    bestaetigt_am: datetime | None


class KampagneDetailAntwort(KampagneAntwort):
    ketten: list[KampagnenKetteAntwort]


class KampagnenListeAntwort(BaseModel):
    gesamt: int
    treffer: list[KampagneAntwort]


# AP-06e: Equity-Kurve und Drawdown, immer Kontosicht (analytics.equity, E1).
# AP-06i (I7): lose Legs — ihre Beträge laufen in netto_eur/summe_netto_eur
# mit, die Anzahlen stehen getrennt dahinter.
class EquityTagAntwort(BaseModel):
    datum: date
    netto_eur: str
    kumuliert_eur: str
    drawdown_eur: str
    anzahl_strukturen: int
    anzahl_strukturen_kurs_fehlt: int
    anzahl_lose_legs: int
    anzahl_lose_legs_kurs_fehlt: int


class EquityMonatAntwort(BaseModel):
    monat: str
    anzahl_strukturen: int
    summe_netto_eur: str
    durchschnitt_netto_eur: str | None
    trefferquote: str | None
    anzahl_strukturen_kurs_fehlt: int
    lose_legs_eur: str
    anzahl_lose_legs: int
    anzahl_lose_legs_kurs_fehlt: int


class EquityAntwort(BaseModel):
    tage: list[EquityTagAntwort]
    monate: list[EquityMonatAntwort]
    max_drawdown_eur: str
    max_drawdown_datum: date | None


# AP-07f: Verlauf und Ergebnis der gefilterten Ketten — ``tage``, ``monate``
# und ``max_drawdown_*`` sind die Equity-Modelle (denselben Bericht, dieselbe
# Kurve), dazu der Kopf mit der Summe der gefilterten Auswahl.
class AuswertungErgebnisAntwort(BaseModel):
    anzahl_ketten: int
    anzahl_strukturen: int
    summe_netto_eur: str
    anzahl_kurs_fehlt: int
    lose_legs_eingeschlossen: bool


class WaehrungsbetragAntwort(BaseModel):
    waehrung: str
    summe: str


class VerlaufPunktAntwort(BaseModel):
    datum: date
    kumuliert_eur: str


class AuswertungWocheAntwort(BaseModel):
    schluessel: str
    beginn: date
    ende: date
    summe_netto_eur: str


class AuswertungUnrealisiertAntwort(BaseModel):
    stichtag: date | None
    eur: str
    anzahl_legs: int
    ohne_kurs: int
    # AP-07fv: realisiert der Auswahl + unrealisiert — Endpunkt der gestrichelten
    # Verlängerung im Diagramm (das Frontend rechnet kein Geld, Vertrag 8).
    mit_realisiert_eur: str = "0.00"


class AuswertungAntwort(BaseModel):
    tage: list[EquityTagAntwort]
    monate: list[EquityMonatAntwort]
    max_drawdown_eur: str
    max_drawdown_datum: date | None
    ergebnis: AuswertungErgebnisAntwort
    # AP-07fu: Wochen (ISO) und das unrealisierte Ergebnis offener Positionen.
    wochen: list[AuswertungWocheAntwort] = []
    unrealisiert: AuswertungUnrealisiertAntwort | None = None
    # AP-07fv: aufsummiert realisiert für jeden Kalendertag vom ersten bis zum
    # letzten Schließungstag (Tage ohne Schließung tragen den Vortageswert).
    verlauf: list[VerlaufPunktAntwort] = []
    # AP-07fv: realisiert netto je Positionswährung (nativ), nach Währung sortiert.
    netto_je_waehrung: list[WaehrungsbetragAntwort] = []


# AP-07fw: wählbare Werte der Positionsfilter — nur Listen, keine Zählwerte.
class FilterwerteAntwort(BaseModel):
    basiswerte: list[str]
    anlageklassen: list[str]
    waehrungen: list[str]
    strategien: list[str]
    seiten: list[str]
    endzustaende: list[str]


# AP-08d: Bestand laut IB mit letztem bekanntem Kurs und unrealisiertem
# Ergebnis (flex_open_positions, jüngster Stichtag) — Werte der Quelle, nichts
# neu bewertet; EUR mit IBs fxRateToBase der Zeile.
class DepotPositionAntwort(BaseModel):
    conid: int
    symbol: str
    basiswert: str
    anlageklasse: str
    seite: str | None
    verfall: date | None
    strike: str | None
    multiplikator: str | None
    menge: str
    waehrung: str
    einstandskurs: str | None
    kurs: str | None
    marktwert: str | None
    unrealisiert: str | None
    marktwert_eur: str | None
    unrealisiert_eur: str | None


class DepotKlasseAntwort(BaseModel):
    anlageklasse: str
    anzahl: int
    marktwert_eur: str
    unrealisiert_eur: str


class DepotSummenAntwort(BaseModel):
    marktwert_eur: str
    unrealisiert_eur: str
    je_klasse: list[DepotKlasseAntwort]


class DepotAntwort(BaseModel):
    stichtag: date | None
    positionen: list[DepotPositionAntwort]
    summen: DepotSummenAntwort


# AP-08u: Überleitung vom Ergebnis zum Kontostand. Jede Zahl hat eine Quelle
# (Kontowert/Einzahlungen: /nav, IB realisiert: flex_ib_realized, unrealisiert:
# /depot, sonstige Buchungen und Journal-Ergebnis: /kapital); der Rest ist die
# Differenz — nichts wird frei erfunden.
class UeberleitungIbAntwort(BaseModel):
    realisiert: str
    unrealisiert: str
    sonstige_buchungen: str
    rest: str


class UeberleitungJournalAntwort(BaseModel):
    realisiert: str
    differenz_realisiert: str


class UeberleitungAbdeckungAntwort(BaseModel):
    ausfuehrungen: int
    mit_ib_wert: int


# AP-08u2: die Journal-Spalte neben IB und die Zerlegung des Unterschieds.
class UeberleitungSpalteAntwort(BaseModel):
    einzahlungen: str
    realisiert: str
    unrealisiert: str
    sonstige_buchungen: str
    rest: str


class UeberleitungEinzelrestAntwort(BaseModel):
    gruppe: str
    waehrung: str
    nativ: str
    eur: str


class UeberleitungAbgleichAntwort(BaseModel):
    praemien_im_einstand: str
    waehrungsmethode: str
    zeitpunkt_offene_strukturen: str
    # Beitrag zum Unterschied mit Vorzeichen (= −Zeitpunkt): die Teile summieren sich.
    zeitpunkt_beitrag: str
    nicht_zugeordnet: str
    anzahl_legs_offene_strukturen: int
    zeilen_gleich: int
    zeilen_abweichend: int
    # AP-08u3: der Rest im Einzelnen — Kurseffekt auf verschobene Prämien und
    # Einzelreste je Basiswert-Gruppe in Positionswährung.
    kurseffekt_praemien: str = "0"
    einzelreste: list[UeberleitungEinzelrestAntwort] = []


class UeberleitungAntwort(BaseModel):
    stichtag: date | None
    bestand_stichtag: date | None
    kontowert: str | None
    einzahlungen: str | None
    gewinn_ib: str | None
    ib: UeberleitungIbAntwort | None
    journal: UeberleitungJournalAntwort | None
    abdeckung: UeberleitungAbdeckungAntwort
    anzahl_kurs_fehlt: int
    journal_spalte: UeberleitungSpalteAntwort | None = None
    # Journal minus IB je Zeile (die Anzeige rechnet nichts, Vertrag 8).
    unterschied_spalte: UeberleitungSpalteAntwort | None = None
    abgleich_realisiert: UeberleitungAbgleichAntwort | None = None


# AP-08p: Wertentwicklung — zeitgewichteter Index, Drawdown in % vom Höchststand,
# Wochen und Monate (analytics.performance).
class PunktAntwort(BaseModel):
    datum: date
    wert: str


class PerformanceTagAntwort(BaseModel):
    datum: date
    kontowert: str
    gewinn_ib: str
    index: str
    drawdown_quote: str
    drawdown_prozent: str


class PeriodeAntwort(BaseModel):
    schluessel: str
    beginn: date
    ende: date
    gewinn_ib: str
    realisiert: str
    rendite_quote: str


class PerformanceAntwort(BaseModel):
    tage: list[PerformanceTagAntwort]
    max_drawdown_quote: str
    max_drawdown_prozent: str
    max_drawdown_datum: date | None
    kontowert_ende: str | None
    gewinn_ib_zeitraum: str
    rendite_zeitraum_quote: str
    realisiert_zeitraum: str
    wochen: list[PeriodeAntwort]
    monate: list[PeriodeAntwort]
    # Realisiertes Ergebnis kumuliert (Equity), je Tag mit Schließung.
    realisiert_kumuliert: list[PunktAntwort] = []


# AP-06f: Kosten & Erträge (analytics.cashflows), in EUR.
class CashflowKategorieAntwort(BaseModel):
    kategorie: str
    anzahl: int
    summe_eur: str
    anzahl_kurs_fehlt: int
    im_ergebnis_enthalten: bool


class CashflowMonatAntwort(BaseModel):
    monat: str
    kategorie: str
    anzahl: int
    summe_eur: str
    anzahl_kurs_fehlt: int


class CashflowAntwort(BaseModel):
    kategorien: list[CashflowKategorieAntwort]
    monate: list[CashflowMonatAntwort]


# AP-06g: Kapitalentwicklung, realisiert (analytics.kapital), in EUR.
class KapitalTagAntwort(BaseModel):
    datum: date
    einzahlungen_kumuliert: str
    ergebnis_kumuliert: str
    cash_kumuliert: str
    kapital: str


class NavTagAntwort(BaseModel):
    datum: date
    gesamt: str
    cash: str | None
    aktien: str | None
    optionen: str | None
    rohstoffe: str | None
    einzahlungen_kumuliert: str
    gewinn: str


# AP-06h: Kontowert laut IB (realisiert + unrealisiert) und Gewinn laut IB.
class NavAntwort(BaseModel):
    tage: list[NavTagAntwort]
    anfangswert: str | None
    endwert: str | None
    anzahl_kurs_fehlt: int


class KapitalAntwort(BaseModel):
    tage: list[KapitalTagAntwort]
    anfangskapital: str
    endkapital: str
    einzahlungen_im_zeitraum: str
    ergebnis_im_zeitraum: str
    cash_im_zeitraum: str
    anzahl_kurs_fehlt: int


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
    menge: Decimal | None = None,
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
        menge=_als_text(menge),
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


def _kampagne_als_dict(zeile, anzahl_ketten: int) -> dict:
    """Spaltenwerte einer Kampagnenzeile für das Antwortmodell (AP-08-kampagnen).

    Reines Durchreichen: ``netto_pnl_eur`` wird wie jedes Geld zur Zeichenkette
    (Regel 5/13), ein leerer Wert bleibt leer — eine laufende Kampagne ohne
    Ergebnis ist kein Nullergebnis.
    """
    return dict(
        campaign_id=zeile["campaign_id"],
        underlying=zeile["underlying"],
        eroeffnet_am=zeile["eroeffnet_am"],
        beendet_am=zeile["beendet_am"],
        netto_pnl_eur=_als_text(zeile["netto_pnl_eur"]),
        anzahl_ketten=anzahl_ketten,
    )


def _ketten_zuschuesse(
    verbindung: Connection, chain_ids: list[int]
) -> dict[
    int,
    tuple[
        int, list[str], Decimal | None, Decimal | None, Decimal | None, Decimal | None
    ],
]:
    """Gliederzahl, Währungen, Struktursumme, die Prämien aus erstem und
    letztem Glied und die Menge des ersten Glieds je Kette (Vertrag 8;
    AP-07pv, P8).

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
                structures.c.menge,
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
            menge,
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
                    menge=None,
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
                eintrag["menge"] = menge
            if eintrag["letzte"] is None or stelle > eintrag["letzte"]:
                eintrag["letzte"] = stelle
                eintrag["schlusspreis"] = schlusspreis
    zuschuesse: dict[
        int,
        tuple[
            int, list[str], Decimal | None, Decimal | None, Decimal | None, Decimal | None
        ],
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
            eintrag["menge"],
        )
    return zuschuesse


def _mitternacht(tag: date) -> datetime:
    """AP-07f: Tagesgrenze gegen ``DateTime``-Spalten — halboffene
    Intervalle ``[Mitternacht(ab), Mitternacht(bis + 1 Tag))`` fassen den Tag
    an beiden Enden einschließlich."""
    return datetime(tag.year, tag.month, tag.day)


def _datumspaar_pruefen(
    ab: date | None, bis: date | None, ab_name: str, bis_name: str
) -> None:
    """AP-07f: Ein auf dem Kopf stehendes Datumspaar ist 422 — nicht
    stillschweigend zurechtbiegen (wie ``von`` nach ``bis`` bei ``/equity``,
    Vertrag 16/17). Ungültige Einzelwerte wirft bereits FastAPI beim
    ``date``-Parsing (422)."""
    if ab is not None and bis is not None and ab > bis:
        raise HTTPException(status_code=422, detail=f"{ab_name} liegt nach {bis_name}")


def _ketten_bedingungen(
    *,
    basiswert: str | None = None,
    anlageklasse: str | None = None,
    seite: str | None = None,
    endzustand: str | None = None,
    min_rolls: int | None = None,
    max_rolls: int | None = None,
    eroeffnet_ab: date | None = None,
    eroeffnet_bis: date | None = None,
    geschlossen_ab: date | None = None,
    geschlossen_bis: date | None = None,
    waehrung: str | None = None,
    strategie: str | None = None,
    von: date | None = None,
    bis: date | None = None,
) -> list[ColumnElement[bool]]:
    """Die gemeinsamen Kettenfilter für ``/ketten`` und ``/auswertung``
    (AP-07f) — immer mit der Kontosicht (AP-04sw, Plan §5).

    Die ersten acht Parameter sind unverändert aus ``/ketten`` übernommen
    (stellenidentisch; ``eroeffnet_ab``/``eroeffnet_bis`` unangetastet).

    Neu (AP-07f): ``geschlossen_ab``/``geschlossen_bis`` am Ende der Kette
    (``beendet_am``, beide Enden einschließlich des Tages; offene Ketten
    fallen heraus, sobald einer gesetzt ist — der NULL-Vergleich ist nie
    wahr), ``waehrung`` (mindestens ein Glied über ``chain_links`` in dieser
    Währung), ``strategie`` (``chains.oa_strategie``) sowie ``von``/``bis``
    als Z3 (AP-08f): aktiv im Zeitraum — eröffnet bis ``bis`` (Tag
    einschließlich) und offen oder beendet ab ``von`` (Tag einschließlich).
    ``/auswertung`` ruft sie ohne ``von``/``bis``: Dort gilt der Zeitraum am
    Schließungstag (Z2/Z4 wie ``/equity``), nicht auf der Kette.
    """
    bedingungen: list[ColumnElement[bool]] = [chains.c.sicht == SICHT]
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
    if geschlossen_ab is not None:
        bedingungen.append(chains.c.beendet_am >= _mitternacht(geschlossen_ab))
    if geschlossen_bis is not None:
        bedingungen.append(
            chains.c.beendet_am < _mitternacht(geschlossen_bis) + timedelta(days=1)
        )
    if waehrung:
        bedingungen.append(
            exists().where(
                chain_links.c.sicht == SICHT,
                chain_links.c.chain_id == chains.c.chain_id,
                structures.c.structure_id == chain_links.c.structure_id,
                structures.c.waehrung == waehrung,
            )
        )
    if strategie:
        bedingungen.append(chains.c.oa_strategie == strategie)
    if von is not None:
        bedingungen.append(
            or_(
                chains.c.beendet_am.is_(None),
                chains.c.beendet_am >= _mitternacht(von),
            )
        )
    if bis is not None:
        bedingungen.append(
            chains.c.eroeffnet_am < _mitternacht(bis) + timedelta(days=1)
        )
    return bedingungen


def _equity_als_antwort(ergebnis: EquityErgebnis) -> EquityAntwort:
    """AP-07f: dieselbe Umwandlung eines Equity-Berichts für ``/equity`` und
    ``/auswertung`` — kein kopierter Block. Geld als Zeichenkette
    (Entscheidung 1), leere Werte bleiben leer (Vertrag 13)."""
    return EquityAntwort(
        tage=[
            EquityTagAntwort(
                datum=t.datum,
                netto_eur=_als_text(t.netto_eur),
                kumuliert_eur=_als_text(t.kumuliert_eur),
                drawdown_eur=_als_text(t.drawdown_eur),
                anzahl_strukturen=t.anzahl_strukturen,
                anzahl_strukturen_kurs_fehlt=t.anzahl_strukturen_kurs_fehlt,
                anzahl_lose_legs=t.anzahl_lose_legs,
                anzahl_lose_legs_kurs_fehlt=t.anzahl_lose_legs_kurs_fehlt,
            )
            for t in ergebnis.tage
        ],
        monate=[
            EquityMonatAntwort(
                monat=m.monat,
                anzahl_strukturen=m.anzahl_strukturen,
                summe_netto_eur=_als_text(m.summe_netto_eur),
                durchschnitt_netto_eur=_als_text(m.durchschnitt_netto_eur),
                trefferquote=_als_text(m.trefferquote),
                anzahl_strukturen_kurs_fehlt=m.anzahl_strukturen_kurs_fehlt,
                lose_legs_eur=_als_text(m.lose_legs_eur),
                anzahl_lose_legs=m.anzahl_lose_legs,
                anzahl_lose_legs_kurs_fehlt=m.anzahl_lose_legs_kurs_fehlt,
            )
            for m in ergebnis.monate
        ],
        max_drawdown_eur=_als_text(ergebnis.max_drawdown_eur),
        max_drawdown_datum=ergebnis.max_drawdown_datum,
    )


def _ueberleitung_aufbauen(engine, db_pfad: str | pathlib.Path) -> UeberleitungAntwort:
    """Vom Gewinn laut IB zu seinen Bestandteilen (AP-08u), nur lesend."""
    nav = nav_bericht(db_pfad)
    with engine.connect() as verbindung:
        ausfuehrungen = verbindung.execute(
            select(func.count()).select_from(executions).where(
                executions.c.ereignistyp.in_(["trade", "expiry", "exercise", "assignment"])
            )
        ).scalar_one()
        mit_ib_wert = verbindung.execute(
            select(func.count()).select_from(executions).where(
                executions.c.ereignistyp.in_(["trade", "expiry", "exercise", "assignment"]),
                executions.c.exec_id.in_(select(flex_ib_realized.c.exec_id)),
            )
        ).scalar_one()
        abdeckung = UeberleitungAbdeckungAntwort(
            ausfuehrungen=ausfuehrungen, mit_ib_wert=mit_ib_wert
        )
        if not nav.tage:
            return UeberleitungAntwort(
                stichtag=None, bestand_stichtag=None, kontowert=None, einzahlungen=None,
                gewinn_ib=None, ib=None, journal=None, abdeckung=abdeckung, anzahl_kurs_fehlt=0,
            )
        letzter = nav.tage[-1]
        realisiert = Decimal("0.00")
        kurs_fehlt = 0
        for pnl, kurs in verbindung.execute(
            select(flex_ib_realized.c.fifo_pnl_realized, flex_ib_realized.c.fx_rate_to_base).where(
                flex_ib_realized.c.handelstag <= letzter.datum
            )
        ):
            if kurs is None:
                kurs_fehlt += 1
            else:
                realisiert += pnl * kurs
        depot = _depot_aufbauen(verbindung)
    unrealisiert = Decimal(depot.summen.unrealisiert_eur)
    kapital = kapital_bericht(db_pfad)
    sonstige = kapital.cash_im_zeitraum
    gewinn = letzter.gewinn
    rest = gewinn - (realisiert + unrealisiert + sonstige)
    journal = kapital.ergebnis_im_zeitraum
    # AP-08u2: Journal-Spalte und Zerlegung (analytics.ib_abgleich). Das
    # unrealisierte Ergebnis des Journals ist IBs Wert, bewertet gegen den
    # Journal-Einstand: Die Prämien, die IB im Einstand gehaltener Positionen
    # führt, stehen im Journal schon im realisierten Ergebnis.
    abgleich = ib_abgleich_bericht(db_pfad)
    j_unrealisiert = unrealisiert - abgleich.praemien_im_einstand_heute
    j_rest = letzter.gesamt - (
        letzter.einzahlungen_kumuliert + journal + j_unrealisiert + sonstige
    )
    nicht_zugeordnet = (journal - realisiert) - (
        abgleich.praemien_im_einstand
        + abgleich.waehrungsmethode
        - abgleich.zeitpunkt_offene_strukturen
    )
    return UeberleitungAntwort(
        stichtag=letzter.datum,
        bestand_stichtag=depot.stichtag,
        kontowert=_als_text(letzter.gesamt),
        einzahlungen=_als_text(letzter.einzahlungen_kumuliert),
        gewinn_ib=_als_text(gewinn),
        ib=UeberleitungIbAntwort(
            realisiert=_als_text(realisiert),
            unrealisiert=_als_text(unrealisiert),
            sonstige_buchungen=_als_text(sonstige),
            rest=_als_text(rest),
        ),
        journal=UeberleitungJournalAntwort(
            realisiert=_als_text(journal),
            differenz_realisiert=_als_text(journal - realisiert),
        ),
        abdeckung=abdeckung,
        anzahl_kurs_fehlt=kurs_fehlt,
        journal_spalte=UeberleitungSpalteAntwort(
            einzahlungen=_als_text(letzter.einzahlungen_kumuliert),
            realisiert=_als_text(journal),
            unrealisiert=_als_text(j_unrealisiert),
            sonstige_buchungen=_als_text(sonstige),
            rest=_als_text(j_rest),
        ),
        unterschied_spalte=UeberleitungSpalteAntwort(
            einzahlungen=_als_text(Decimal("0.00")),
            realisiert=_als_text(journal - realisiert),
            unrealisiert=_als_text(j_unrealisiert - unrealisiert),
            sonstige_buchungen=_als_text(Decimal("0.00")),
            rest=_als_text(j_rest - rest),
        ),
        abgleich_realisiert=UeberleitungAbgleichAntwort(
            praemien_im_einstand=_als_text(abgleich.praemien_im_einstand),
            waehrungsmethode=_als_text(abgleich.waehrungsmethode),
            zeitpunkt_offene_strukturen=_als_text(abgleich.zeitpunkt_offene_strukturen),
            zeitpunkt_beitrag=_als_text(-abgleich.zeitpunkt_offene_strukturen),
            nicht_zugeordnet=_als_text(nicht_zugeordnet),
            anzahl_legs_offene_strukturen=abgleich.anzahl_legs_offene_strukturen,
            zeilen_gleich=abgleich.zeilen_gleich,
            zeilen_abweichend=abgleich.zeilen_abweichend,
            kurseffekt_praemien=_als_text(abgleich.kurseffekt_praemien),
            einzelreste=[
                UeberleitungEinzelrestAntwort(
                    gruppe=r.gruppe, waehrung=r.waehrung,
                    nativ=_als_text(r.nativ), eur=_als_text(r.eur),
                )
                for r in abgleich.einzelreste
            ],
        ),
    )


def _offene_legs_der_auswahl(
    verbindung: Connection,
    ketten_ids: frozenset[int] | None,
    lose_legs: "LoseLegFilter | None | Literal[False]",
) -> list[dict]:
    """AP-07fu: offene Legs der Kontosicht, die zur Auswahl gehören — dieselbe
    Regel wie für das realisierte Ergebnis (AP-07f): Ketten der Auswahl; lose
    Legs nur, wenn kein Filter sie ausschließt, und dann nach den Werten, die ein
    offenes Leg kennt (Basiswert, Klasse, Währung und Tag der Eröffnung). Ein
    Schließungsfilter schließt offene lose Legs aus (sie sind nicht geschlossen)."""
    zeilen = [
        dict(z)
        for z in verbindung.execute(
            select(
                legs.c.structure_id, legs.c.conid, legs.c.open_exec_id, legs.c.menge,
                legs.c.kommission_gesamt, legs.c.open_faktor,
            ).where(legs.c.sicht == SICHT, legs.c.close_exec_id.is_(None))
        ).mappings()
    ]
    if ketten_ids is None and lose_legs is None:
        return zeilen
    kette_je_struktur = {
        s: k
        for s, k in verbindung.execute(
            select(chain_links.c.structure_id, chain_links.c.chain_id).where(
                chain_links.c.sicht == SICHT
            )
        )
    }
    instrumente = {
        z["conid"]: z
        for z in verbindung.execute(
            select(instruments.c.conid, instruments.c.underlying, instruments.c.symbol,
                   instruments.c.asset_class)
        ).mappings()
    }
    auswahl = []
    for leg in zeilen:
        if leg["structure_id"] is not None:
            if ketten_ids is None or kette_je_struktur.get(leg["structure_id"]) in ketten_ids:
                auswahl.append(leg)
            continue
        if lose_legs is False:
            continue
        if lose_legs is not None:
            if lose_legs.geschlossen_ab is not None or lose_legs.geschlossen_bis is not None:
                continue
            i = instrumente.get(leg["conid"], {})
            if lose_legs.basiswert is not None and (
                i.get("underlying") or i.get("symbol")
            ) != lose_legs.basiswert:
                continue
            klasse = i.get("asset_class")
            if lose_legs.anlageklasse is not None and klasse != lose_legs.anlageklasse:
                continue
            if (
                lose_legs.waehrung is not None
                or lose_legs.eroeffnet_ab is not None
                or lose_legs.eroeffnet_bis is not None
            ):
                a = verbindung.execute(
                    select(executions.c.waehrung, executions.c.handelszeit).where(
                        executions.c.exec_id == leg["open_exec_id"]
                    )
                ).first()
                if lose_legs.waehrung is not None and a[0] != lose_legs.waehrung:
                    continue
                tag = a[1].date()
                if lose_legs.eroeffnet_ab is not None and tag < lose_legs.eroeffnet_ab:
                    continue
                if lose_legs.eroeffnet_bis is not None and tag > lose_legs.eroeffnet_bis:
                    continue
        auswahl.append(leg)
    return auswahl


def _unrealisiert_der_auswahl(
    verbindung: Connection, offene: list[dict], bis: date | None
) -> AuswertungUnrealisiertAntwort:
    """AP-07fu: bewertet die offenen Legs mit dem jüngsten Bestand laut IB. Liegt
    ``bis`` vor dem Stichtag, gibt es keinen passenden Bestand — dann nichts."""
    stichtag = verbindung.execute(select(func.max(flex_open_positions.c.stichtag))).scalar()
    if stichtag is not None and bis is not None and bis < stichtag:
        stichtag = None
    bestand: dict[int, dict] = {}
    if stichtag is not None:
        for z in verbindung.execute(
            select(flex_open_positions.c.conid, flex_open_positions.c.menge,
                   flex_open_positions.c.roh_json).where(
                flex_open_positions.c.stichtag == stichtag)
        ).mappings():
            roh = json.loads(z["roh_json"])
            if roh.get("levelOfDetail") not in (None, "SUMMARY"):
                continue
            wert = _dezimal_oder_none(roh.get("positionValue"))
            kurs = _dezimal_oder_none(roh.get("fxRateToBase"))
            if wert is None or kurs is None:
                continue
            bestand[z["conid"]] = dict(menge=z["menge"], wert=wert, kurs=kurs)
    exec_ids = list({leg["open_exec_id"] for leg in offene})
    exec_je_id = {
        z["exec_id"]: dict(z)
        for z in verbindung.execute(
            select(executions.c.exec_id, executions.c.conid, executions.c.side,
                   executions.c.preis).where(executions.c.exec_id.in_(exec_ids))
        ).mappings()
    } if exec_ids else {}
    mult = {
        c: m
        for c, m in verbindung.execute(select(instruments.c.conid, instruments.c.multiplikator))
    }
    e = unrealisiert_auswertung(offene, exec_je_id, mult, bestand, stichtag)
    return AuswertungUnrealisiertAntwort(
        stichtag=e.stichtag, eur=_als_text(e.eur), anzahl_legs=e.anzahl_legs,
        ohne_kurs=e.ohne_kurs,
    )


_SEITE_JE_RIGHT = {"C": "Call", "P": "Put"}


def _dezimal_oder_none(wert: object) -> Decimal | None:
    """Rohwert der Quelle als Decimal; leer oder fehlend bleibt leer — kein
    stilles 0 (Regel 5)."""
    if wert is None or str(wert).strip() == "":
        return None
    return Decimal(str(wert))


def _depot_aufbauen(verbindung: Connection) -> DepotAntwort:
    """Bestand des jüngsten Stichtags aus ``flex_open_positions`` (AP-08d)."""
    stichtag = verbindung.execute(select(func.max(flex_open_positions.c.stichtag))).scalar()
    if stichtag is None:
        return DepotAntwort(
            stichtag=None,
            positionen=[],
            summen=DepotSummenAntwort(
                marktwert_eur=_als_text(Decimal("0.00")),
                unrealisiert_eur=_als_text(Decimal("0.00")),
                je_klasse=[],
            ),
        )
    zeilen = verbindung.execute(
        select(flex_open_positions).where(flex_open_positions.c.stichtag == stichtag)
    ).mappings().all()
    stamm = {
        z["conid"]: z
        for z in verbindung.execute(
            select(
                instruments.c.conid,
                instruments.c.underlying,
                instruments.c.expiry,
                instruments.c.strike,
                instruments.c.right,
                instruments.c.multiplikator,
            )
        ).mappings()
    }
    eintraege: list[tuple[DepotPositionAntwort, Decimal | None, Decimal | None]] = []
    for z in zeilen:
        roh = json.loads(z["roh_json"])
        # Die Summenebene trägt je conid genau eine Zeile; Einzellots (LOT)
        # gehören nicht in diese Ansicht.
        if roh.get("levelOfDetail") not in (None, "SUMMARY"):
            continue
        kurs_zu_eur = _dezimal_oder_none(roh.get("fxRateToBase"))
        wert = _dezimal_oder_none(roh.get("positionValue"))
        unrealisiert = _dezimal_oder_none(roh.get("fifoPnlUnrealized"))
        wert_eur = wert * kurs_zu_eur if wert is not None and kurs_zu_eur is not None else None
        unreal_eur = (
            unrealisiert * kurs_zu_eur
            if unrealisiert is not None and kurs_zu_eur is not None
            else None
        )
        s = stamm.get(z["conid"])
        position = DepotPositionAntwort(
            conid=z["conid"],
            symbol=z["symbol"],
            basiswert=(s["underlying"] if s and s["underlying"] else z["symbol"]),
            anlageklasse=z["asset_class"],
            seite=_SEITE_JE_RIGHT.get(s["right"]) if s and s["right"] else None,
            verfall=s["expiry"] if s else None,
            strike=_als_text(s["strike"]) if s else None,
            multiplikator=_als_text(s["multiplikator"]) if s else None,
            menge=_als_text(z["menge"]),
            waehrung=z["waehrung"],
            einstandskurs=_als_text(_dezimal_oder_none(roh.get("costBasisPrice"))),
            kurs=_als_text(_dezimal_oder_none(roh.get("markPrice"))),
            marktwert=_als_text(wert),
            unrealisiert=_als_text(unrealisiert),
            marktwert_eur=_als_text(wert_eur),
            unrealisiert_eur=_als_text(unreal_eur),
        )
        eintraege.append((position, wert_eur, unreal_eur))

    # Aktien zuerst, innerhalb nach Betrag des EUR-Marktwerts absteigend; ohne
    # Kurs ans Ende der jeweiligen Gruppe.
    def sortierschluessel(e: tuple) -> tuple:
        position, wert_eur, _ = e
        return (
            0 if position.anlageklasse == "STK" else 1,
            wert_eur is None,
            -abs(wert_eur) if wert_eur is not None else Decimal(0),
            position.symbol,
        )

    eintraege.sort(key=sortierschluessel)
    summe_wert = sum((w for _, w, _ in eintraege if w is not None), Decimal("0.00"))
    summe_unreal = sum((u for _, _, u in eintraege if u is not None), Decimal("0.00"))
    je_klasse: dict[str, list] = {}
    for position, wert_eur, unreal_eur in eintraege:
        k = je_klasse.setdefault(position.anlageklasse, [0, Decimal("0.00"), Decimal("0.00")])
        k[0] += 1
        k[1] += wert_eur if wert_eur is not None else Decimal(0)
        k[2] += unreal_eur if unreal_eur is not None else Decimal(0)
    klassen_reihenfolge = sorted(je_klasse, key=lambda name: (name != "STK", name))
    return DepotAntwort(
        stichtag=stichtag,
        positionen=[e[0] for e in eintraege],
        summen=DepotSummenAntwort(
            marktwert_eur=_als_text(summe_wert),
            unrealisiert_eur=_als_text(summe_unreal),
            je_klasse=[
                DepotKlasseAntwort(
                    anlageklasse=name,
                    anzahl=je_klasse[name][0],
                    marktwert_eur=_als_text(je_klasse[name][1]),
                    unrealisiert_eur=_als_text(je_klasse[name][2]),
                )
                for name in klassen_reihenfolge
            ],
        ),
    )


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
        # AP-07f: neue Positionsfilter — Schließung der Kette, Währung eines
        # Glieds, Strategie und „aktiv im Zeitraum“ (Z3, AP-08f). Bedeutung
        # und Tagesgrenzen stehen bei ``_ketten_bedingungen``.
        geschlossen_ab: date | None = None,
        geschlossen_bis: date | None = None,
        waehrung: str | None = None,
        strategie: str | None = None,
        von: date | None = None,
        bis: date | None = None,
        sortierung: Sortierspalte = "eroeffnet_am",
        richtung: Richtung = "desc",
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> KettenListeAntwort:
        """Liste der Ketten — `gesamt` zählt vor der Begrenzung (Vertrag 4)."""
        # AP-04sw, Plan §5: „Keine Abfrage liefert Zeilen aus beiden Sichten
        # in einer Summe." Die Lese-API zeigt ausschließlich die Kontosicht
        # — die Kettensicht hat noch keine eigene Oberfläche/Route.
        # AP-07f: ungültige Paare sind 422 — nicht stillschweigend
        # zurechtbiegen (Vertrag 16/17). ``eroeffnet_ab``/``eroeffnet_bis``
        # bleiben ohne solche Prüfung (Auftrag: unangetastet).
        _datumspaar_pruefen(
            geschlossen_ab, geschlossen_bis, "geschlossen_ab", "geschlossen_bis"
        )
        _datumspaar_pruefen(von, bis, "von", "bis")
        bedingungen = _ketten_bedingungen(
            basiswert=basiswert,
            anlageklasse=anlageklasse,
            seite=seite,
            endzustand=endzustand,
            min_rolls=min_rolls,
            max_rolls=max_rolls,
            eroeffnet_ab=eroeffnet_ab,
            eroeffnet_bis=eroeffnet_bis,
            geschlossen_ab=geschlossen_ab,
            geschlossen_bis=geschlossen_bis,
            waehrung=waehrung,
            strategie=strategie,
            von=von,
            bis=bis,
        )
        with engine.connect() as verbindung:
            gesamt = verbindung.execute(
                select(func.count()).select_from(chains).where(*bedingungen)
            ).scalar_one()
            # AP-07s: Die Sortierspalte wird über die Tabelle nachgeschlagen
            # (``chains.c[...]``) — der Name ist als ``Literal`` geprüft, SQL
            # wird nie aus der Eingabe zusammengesetzt.
            sortier_spalte = chains.c[sortierung]
            zeilen = verbindung.execute(
                select(chains)
                .where(*bedingungen)
                # Vertrag 4 und AP-07s: Vorgabe bleibt Eröffnung absteigend.
                # Leere Werte stehen in beiden Richtungen zuletzt (offene
                # Ketten haben kein Ende, Aktienketten keine Seite); bei
                # Gleichstand entscheidet die aufsteigende chain_id — so bleibt
                # die Reihenfolge deterministisch und das Blättern liefert
                # nichts doppelt und lässt nichts aus.
                .order_by(
                    sortier_spalte.is_(None),
                    sortier_spalte.desc() if richtung == "desc" else sortier_spalte.asc(),
                    chains.c.chain_id,
                )
                .limit(limit)
                .offset(offset)
            ).mappings().all()
            zuschuesse = _ketten_zuschuesse(verbindung, [z["chain_id"] for z in zeilen])
        leer = (0, [], None, None, None, None)
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
    # Kampagnen (AP-08-kampagnen): bestätigte Zuordnungen aus campaigns/
    # campaign_links — rein lesend. Offene (unbestätigte) Kandidaten werden
    # nicht berechnet und bleiben der CLI-Dateirundreise überlassen.
    # -----------------------------------------------------------------------

    @applikation.get("/kampagnen", response_model=KampagnenListeAntwort)
    def kampagnen(underlying: str | None = None) -> KampagnenListeAntwort:
        """Liste der bestätigten Kampagnen — Eröffnung absteigend (wie
        /ketten); ``eroeffnet_am`` ist pflichtgefüllt, bei Gleichstand
        entscheidet die aufsteigende ``campaign_id`` (Determinismus wie
        OF-44). Ohne Begrenzung zählt ``gesamt`` alle Treffer."""
        bedingungen = []
        if underlying:
            bedingungen.append(campaigns.c.underlying == underlying)
        with engine.connect() as verbindung:
            zeilen = verbindung.execute(
                select(
                    campaigns,
                    func.count(campaign_links.c.chain_id).label("anzahl_ketten"),
                )
                .outerjoin(
                    campaign_links, campaign_links.c.campaign_id == campaigns.c.campaign_id
                )
                .where(*bedingungen)
                .group_by(campaigns.c.campaign_id)
                .order_by(campaigns.c.eroeffnet_am.desc(), campaigns.c.campaign_id)
            ).mappings().all()
        return KampagnenListeAntwort(
            gesamt=len(zeilen),
            treffer=[
                KampagneAntwort(**_kampagne_als_dict(zeile, zeile["anzahl_ketten"]))
                for zeile in zeilen
            ],
        )

    @applikation.get("/kampagnen/{campaign_id}", response_model=KampagneDetailAntwort)
    def kampagne_einzeln(campaign_id: int) -> KampagneDetailAntwort:
        """Eine Kampagne mit ihren verknüpften Ketten — nach ``chain_id``
        aufsteigend, damit die Reihenfolge deterministisch bleibt. Der
        Naturschlüssel kommt aus ``chains`` (chain_id ist dort alleiniger
        Primärschlüssel, der Join trifft also genau eine Zeile)."""
        with engine.connect() as verbindung:
            zeile = verbindung.execute(
                select(campaigns).where(campaigns.c.campaign_id == campaign_id)
            ).mappings().one_or_none()
            if zeile is None:
                raise HTTPException(status_code=404, detail="Kampagne nicht gefunden")
            anzahl_ketten = verbindung.execute(
                select(func.count())
                .select_from(campaign_links)
                .where(campaign_links.c.campaign_id == campaign_id)
            ).scalar_one()
            ketten_zeilen = verbindung.execute(
                select(
                    campaign_links.c.chain_id,
                    campaign_links.c.beziehungstyp,
                    campaign_links.c.erkennung,
                    campaign_links.c.bestaetigt_am,
                    chains.c.natur_schluessel,
                )
                .join(chains, chains.c.chain_id == campaign_links.c.chain_id)
                .where(campaign_links.c.campaign_id == campaign_id)
                .order_by(campaign_links.c.chain_id)
            ).mappings().all()
        return KampagneDetailAntwort(
            **_kampagne_als_dict(zeile, anzahl_ketten),
            ketten=[
                KampagnenKetteAntwort(
                    chain_id=z["chain_id"],
                    natur_schluessel=z["natur_schluessel"],
                    beziehungstyp=z["beziehungstyp"],
                    erkennung=z["erkennung"],
                    bestaetigt_am=z["bestaetigt_am"],
                )
                for z in ketten_zeilen
            ],
        )

    # -----------------------------------------------------------------------
    # Equity-Kurve und Drawdown (AP-06e): rein lesend, immer aktiv, immer
    # Kontosicht (analytics.equity, E1 — Geld ist Kontosicht-Sache). Keine
    # Parameter: die ganze Historie, wie journal kennzahlen --equity.
    # -----------------------------------------------------------------------

    @applikation.get("/filterwerte", response_model=FilterwerteAntwort)
    def filterwerte() -> FilterwerteAntwort:
        """Die wählbaren Werte der Positionsfilter (AP-07fw), Kontosicht.

        Basiswerte, Anlageklassen und Währungen schließen die Werte loser Legs
        ein (AP-06i/AP-07f): Sie sind filterbar, also müssen sie wählbar sein.
        Der Basiswert eines Instruments ist ``underlying``, sonst ``symbol``
        (53 Aktien-Instrumente tragen kein ``underlying``, OF-78).
        """

        def werte(*mengen: Iterable[str | None]) -> list[str]:
            """Vereinigt, ohne ``NULL`` und leere Zeichenketten, aufsteigend."""
            return sorted({w for menge in mengen for w in menge if w})

        lose_leg = and_(legs.c.sicht == SICHT, legs.c.structure_id.is_(None))
        with engine.connect() as verbindung:
            def ketten_spalte(spalte: ColumnElement[str]) -> set[str | None]:
                return set(
                    verbindung.execute(
                        select(spalte).where(chains.c.sicht == SICHT).distinct()
                    ).scalars()
                )

            lose_instrumente = verbindung.execute(
                select(
                    instruments.c.underlying,
                    instruments.c.symbol,
                    instruments.c.asset_class,
                )
                .select_from(legs.join(instruments, instruments.c.conid == legs.c.conid))
                .where(lose_leg)
                .distinct()
            ).all()
            lose_waehrungen = set(
                verbindung.execute(
                    select(executions.c.waehrung)
                    .select_from(
                        legs.join(
                            executions, executions.c.exec_id == legs.c.close_exec_id
                        )
                    )
                    .where(lose_leg)
                    .distinct()
                ).scalars()
            )
            struktur_waehrungen = set(
                verbindung.execute(
                    select(structures.c.waehrung)
                    .where(structures.c.sicht == SICHT)
                    .distinct()
                ).scalars()
            )
            return FilterwerteAntwort(
                basiswerte=werte(
                    ketten_spalte(chains.c.underlying),
                    {basis or symbol for basis, symbol, _ in lose_instrumente},
                ),
                anlageklassen=werte(
                    ketten_spalte(chains.c.asset_class),
                    {klasse for _, _, klasse in lose_instrumente},
                ),
                waehrungen=werte(struktur_waehrungen, lose_waehrungen),
                strategien=werte(ketten_spalte(chains.c.oa_strategie)),
                seiten=werte(ketten_spalte(chains.c.seite)),
                endzustaende=werte(ketten_spalte(chains.c.endzustand)),
            )

    @applikation.get("/depot", response_model=DepotAntwort)
    def depot() -> DepotAntwort:
        """Der Bestand laut IB (AP-08d): jüngster Stichtag der Flex-Auswertung,
        je Position Menge, Einstandskurs, letzter bekannter Kurs, Marktwert und
        unrealisiertes Ergebnis — in Positionswährung und in EUR. Nur lesend."""
        with engine.connect() as verbindung:
            return _depot_aufbauen(verbindung)

    @applikation.get("/ueberleitung", response_model=UeberleitungAntwort)
    def ueberleitung() -> UeberleitungAntwort:
        """Vom Gewinn laut IB (Kontowert − Einzahlungen) zu realisiert,
        unrealisiert, sonstigen Buchungen und Rest — daneben das realisierte
        Ergebnis des Journals (AP-08u). Nur lesend."""
        return _ueberleitung_aufbauen(engine, db_pfad)

    @applikation.get("/performance", response_model=PerformanceAntwort)
    def performance(von: date | None = None, bis: date | None = None) -> PerformanceAntwort:
        """Wertentwicklung des Kontos (AP-08p): je Tag Kontowert, Gewinn laut IB,
        zeitgewichteter Index und Drawdown vom Höchststand; Wochen und Monate.
        Im Zeitraum ist der Vortag die Basis. Nur lesend."""
        if von is not None and bis is not None and von > bis:
            raise HTTPException(status_code=422, detail="von liegt nach bis")
        e = performance_bericht(db_pfad, von=von, bis=bis)
        hundert = Decimal(100)

        def periode(p) -> PeriodeAntwort:
            return PeriodeAntwort(
                schluessel=p.schluessel, beginn=p.beginn, ende=p.ende,
                gewinn_ib=_als_text(p.gewinn_ib), realisiert=_als_text(p.realisiert),
                rendite_quote=_als_text(p.rendite_quote),
            )

        return PerformanceAntwort(
            tage=[
                PerformanceTagAntwort(
                    datum=t.datum, kontowert=_als_text(t.kontowert),
                    gewinn_ib=_als_text(t.gewinn_ib), index=_als_text(t.index),
                    drawdown_quote=_als_text(t.drawdown_quote),
                    drawdown_prozent=_als_text(t.drawdown_quote * hundert),
                )
                for t in e.tage
            ],
            max_drawdown_quote=_als_text(e.max_drawdown_quote),
            max_drawdown_prozent=_als_text(e.max_drawdown_quote * hundert),
            max_drawdown_datum=e.max_drawdown_datum,
            kontowert_ende=_als_text(e.tage[-1].kontowert) if e.tage else None,
            gewinn_ib_zeitraum=_als_text(sum((t.gewinn_ib for t in e.tage), Decimal("0"))),
            rendite_zeitraum_quote=_als_text(
                (e.tage[-1].index if e.tage else Decimal("1")) - Decimal("1")
            ),
            realisiert_zeitraum=_als_text(sum((m.realisiert for m in e.monate), Decimal("0"))),
            wochen=[periode(p) for p in e.wochen],
            monate=[periode(p) for p in e.monate],
            realisiert_kumuliert=[
                PunktAntwort(datum=d, wert=_als_text(w)) for d, w in e.realisiert_kumuliert
            ],
        )

    @applikation.get("/equity", response_model=EquityAntwort)
    def equity(von: date | None = None, bis: date | None = None) -> EquityAntwort:
        """Equity-Kurve, Monatsübersicht und maximaler Drawdown (AP-06e),
        wahlweise für einen Zeitraum (AP-08f2: beide Enden einschließlich,
        Kurve beginnt bei 0). Rechnet nichts Neues — reicht nur durch, was
        ``analytics.equity.equity_bericht`` liefert."""
        if von is not None and bis is not None and von > bis:
            raise HTTPException(status_code=422, detail="von liegt nach bis")
        # AP-07f: die Umwandlung teilen sich ``/equity`` und ``/auswertung``.
        return _equity_als_antwort(equity_bericht(db_pfad, von=von, bis=bis))

    @applikation.get("/auswertung", response_model=AuswertungAntwort)
    def auswertung(
        basiswert: str | None = None,
        anlageklasse: str | None = None,
        seite: str | None = None,
        endzustand: str | None = None,
        min_rolls: Annotated[int | None, Query(ge=0)] = None,
        max_rolls: Annotated[int | None, Query(ge=0)] = None,
        eroeffnet_ab: date | None = None,
        eroeffnet_bis: date | None = None,
        geschlossen_ab: date | None = None,
        geschlossen_bis: date | None = None,
        waehrung: str | None = None,
        strategie: str | None = None,
        von: date | None = None,
        bis: date | None = None,
    ) -> AuswertungAntwort:
        """Equity-Kurve und Ergebnis der gefilterten Ketten (AP-07f).

        Die Kettenfilter sind die von ``/ketten`` — ohne Sortierung und
        Blättern. ``von``/``bis`` bedeuten hier Z2/Z4 wie bei ``/equity``:
        Gezählt wird am Schließungstag, die Kurve beginnt im Zeitraum bei 0;
        die Z3-Bedingung (aktiv im Zeitraum) greift nicht auf die Ketten.

        ``anzahl_ketten`` zählt die Ketten, die die Kettenfilter erfüllen —
        unabhängig von ``von``/``bis``, offene Ketten mit. Ist mindestens ein
        Kettenfilter gesetzt, rechnet die Equity nur noch mit diesen Ketten.
        Lose Legs (AP-06i) folgen der Nutzerregel: Filter, die nur die Kette
        kennt (Strategie, Seite, Endzustand, Rolls), schließen sie aus; die
        übrigen Filter gelten auch für sie — ``lose_legs_eingeschlossen``
        sagt, ob sie mitrechnen dürfen, nicht ob eines vorkam.
        """
        _datumspaar_pruefen(
            geschlossen_ab, geschlossen_bis, "geschlossen_ab", "geschlossen_bis"
        )
        _datumspaar_pruefen(von, bis, "von", "bis")
        bedingungen = _ketten_bedingungen(
            basiswert=basiswert,
            anlageklasse=anlageklasse,
            seite=seite,
            endzustand=endzustand,
            min_rolls=min_rolls,
            max_rolls=max_rolls,
            eroeffnet_ab=eroeffnet_ab,
            eroeffnet_bis=eroeffnet_bis,
            geschlossen_ab=geschlossen_ab,
            geschlossen_bis=geschlossen_bis,
            waehrung=waehrung,
            strategie=strategie,
        )
        # „Ein Filter ist gesetzt“ heißt hier so viel wie in
        # ``_ketten_bedingungen``: Zeichenketten wirkungsleer, Rest nicht-None.
        hat_kettenfilter = bool(
            basiswert or anlageklasse or seite or endzustand or waehrung or strategie
        ) or any(
            wert is not None
            for wert in (
                min_rolls,
                max_rolls,
                eroeffnet_ab,
                eroeffnet_bis,
                geschlossen_ab,
                geschlossen_bis,
            )
        )
        # AP-07f, Regel des Nutzers: Filter, die nur die Kette kennt
        # (Strategie, Seite, Endzustand, Rolls), schließen lose Legs aus;
        # die übrigen Filter prüft das Leg selbst (LoseLegFilter).
        schliesst_loese_legs_aus = (
            bool(strategie or seite or endzustand)
            or min_rolls is not None
            or max_rolls is not None
        )
        lose_legs: LoseLegFilter | None | Literal[False]
        if schliesst_loese_legs_aus:
            lose_legs = False
        elif hat_kettenfilter:
            lose_legs = LoseLegFilter(
                basiswert=basiswert or None,
                anlageklasse=anlageklasse or None,
                waehrung=waehrung or None,
                geschlossen_ab=geschlossen_ab,
                geschlossen_bis=geschlossen_bis,
                eroeffnet_ab=eroeffnet_ab,
                eroeffnet_bis=eroeffnet_bis,
            )
        else:
            lose_legs = None
        with engine.connect() as verbindung:
            anzahl_ketten = verbindung.execute(
                select(func.count()).select_from(chains).where(*bedingungen)
            ).scalar_one()
            ketten_ids = None
            if hat_kettenfilter:
                ketten_ids = frozenset(
                    verbindung.execute(
                        select(chains.c.chain_id).where(*bedingungen)
                    ).scalars()
                )
        bericht = equity_bericht(
            db_pfad, von=von, bis=bis, ketten_ids=ketten_ids, lose_legs=lose_legs
        )
        basis = _equity_als_antwort(bericht)
        summe_netto_eur = Decimal("0.00")
        anzahl_strukturen = 0
        anzahl_kurs_fehlt = 0
        for tag in bericht.tage:
            summe_netto_eur += tag.netto_eur
            anzahl_strukturen += tag.anzahl_strukturen
            anzahl_kurs_fehlt += (
                tag.anzahl_strukturen_kurs_fehlt + tag.anzahl_lose_legs_kurs_fehlt
            )
        # AP-07fu: Wochen (ISO, Mo–So) aus den Tagen — als Decimal summiert.
        wochen: dict[str, list] = {}
        for tag in bericht.tage:
            jahr, woche, _ = tag.datum.isocalendar()
            montag = tag.datum - timedelta(days=tag.datum.weekday())
            eintrag = wochen.setdefault(
                f"{jahr}-W{woche:02d}", [montag, montag + timedelta(days=6), Decimal("0")]
            )
            eintrag[2] += tag.netto_eur
        verlauf: list[VerlaufPunktAntwort] = []
        if bericht.tage:
            je_tag = {t.datum: t.kumuliert_eur for t in bericht.tage}
            tag, stand = bericht.tage[0].datum, bericht.tage[0].kumuliert_eur
            while tag <= bericht.tage[-1].datum:
                stand = je_tag.get(tag, stand)
                verlauf.append(VerlaufPunktAntwort(datum=tag, kumuliert_eur=_als_text(stand)))
                tag += timedelta(days=1)
        with engine.connect() as verbindung:
            unrealisiert = _unrealisiert_der_auswahl(
                verbindung, _offene_legs_der_auswahl(verbindung, ketten_ids, lose_legs), bis
            )
        return AuswertungAntwort(
            tage=basis.tage,
            monate=basis.monate,
            max_drawdown_eur=basis.max_drawdown_eur,
            max_drawdown_datum=basis.max_drawdown_datum,
            ergebnis=AuswertungErgebnisAntwort(
                anzahl_ketten=anzahl_ketten,
                anzahl_strukturen=anzahl_strukturen,
                summe_netto_eur=_als_text(summe_netto_eur),
                anzahl_kurs_fehlt=anzahl_kurs_fehlt,
                lose_legs_eingeschlossen=not schliesst_loese_legs_aus,
            ),
            verlauf=verlauf,
            netto_je_waehrung=[
                WaehrungsbetragAntwort(waehrung=w, summe=_als_text(s))
                for w, s in bericht.netto_je_waehrung
            ],
            wochen=[
                AuswertungWocheAntwort(
                    schluessel=s, beginn=w[0], ende=w[1], summe_netto_eur=_als_text(w[2])
                )
                for s, w in sorted(wochen.items())
            ],
            unrealisiert=unrealisiert.model_copy(
                update={
                    "mit_realisiert_eur": _als_text(
                        summe_netto_eur + Decimal(unrealisiert.eur)
                    )
                }
            ),
        )

    @applikation.get("/nav", response_model=NavAntwort)
    def nav(von: date | None = None, bis: date | None = None) -> NavAntwort:
        """Kontowert je Tag laut IB und Gewinn laut IB (AP-06h) — reicht durch,
        was ``analytics.nav.nav_bericht`` liefert."""
        if von is not None and bis is not None and von > bis:
            raise HTTPException(status_code=422, detail="von liegt nach bis")
        e = nav_bericht(db_pfad, von=von, bis=bis)
        return NavAntwort(
            tage=[
                NavTagAntwort(
                    datum=t.datum,
                    gesamt=_als_text(t.gesamt),
                    cash=_als_text(t.cash),
                    aktien=_als_text(t.aktien),
                    optionen=_als_text(t.optionen),
                    rohstoffe=_als_text(t.rohstoffe),
                    einzahlungen_kumuliert=_als_text(t.einzahlungen_kumuliert),
                    gewinn=_als_text(t.gewinn),
                )
                for t in e.tage
            ],
            anfangswert=_als_text(e.anfangswert),
            endwert=_als_text(e.endwert),
            anzahl_kurs_fehlt=e.anzahl_kurs_fehlt,
        )

    @applikation.get("/kapital", response_model=KapitalAntwort)
    def kapital(von: date | None = None, bis: date | None = None) -> KapitalAntwort:
        """Kapitalentwicklung, realisiert (AP-06g) — Einzahlungen, Ergebnis,
        Cash-Posten; kein NAV. Im Zeitraum der Bestand, nicht ab 0."""
        if von is not None and bis is not None and von > bis:
            raise HTTPException(status_code=422, detail="von liegt nach bis")
        e = kapital_bericht(db_pfad, von=von, bis=bis)
        return KapitalAntwort(
            tage=[
                KapitalTagAntwort(
                    datum=t.datum,
                    einzahlungen_kumuliert=_als_text(t.einzahlungen_kumuliert),
                    ergebnis_kumuliert=_als_text(t.ergebnis_kumuliert),
                    cash_kumuliert=_als_text(t.cash_kumuliert),
                    kapital=_als_text(t.kapital),
                )
                for t in e.tage
            ],
            anfangskapital=_als_text(e.anfangskapital),
            endkapital=_als_text(e.endkapital),
            einzahlungen_im_zeitraum=_als_text(e.einzahlungen_im_zeitraum),
            ergebnis_im_zeitraum=_als_text(e.ergebnis_im_zeitraum),
            cash_im_zeitraum=_als_text(e.cash_im_zeitraum),
            anzahl_kurs_fehlt=e.anzahl_kurs_fehlt,
        )

    @applikation.get("/cashflows", response_model=CashflowAntwort)
    def cashflows(von: date | None = None, bis: date | None = None) -> CashflowAntwort:
        """Kosten & Erträge je Kategorie und Monat in EUR (AP-06f) — reicht
        durch, was ``analytics.cashflows.cashflow_bericht`` liefert."""
        if von is not None and bis is not None and von > bis:
            raise HTTPException(status_code=422, detail="von liegt nach bis")
        ergebnis = cashflow_bericht(db_pfad, von=von, bis=bis)
        return CashflowAntwort(
            kategorien=[
                CashflowKategorieAntwort(
                    kategorie=k.kategorie,
                    anzahl=k.anzahl,
                    summe_eur=_als_text(k.summe_eur),
                    anzahl_kurs_fehlt=k.anzahl_kurs_fehlt,
                    im_ergebnis_enthalten=k.im_ergebnis_enthalten,
                )
                for k in ergebnis.kategorien
            ],
            monate=[
                CashflowMonatAntwort(
                    monat=m.monat,
                    kategorie=m.kategorie,
                    anzahl=m.anzahl,
                    summe_eur=_als_text(m.summe_eur),
                    anzahl_kurs_fehlt=m.anzahl_kurs_fehlt,
                )
                for m in ergebnis.monate
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
