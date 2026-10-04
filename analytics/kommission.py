"""Kommissionsattribution (AP-06, Tranche II).

Vertrag ist ``auftraege/AP-06w.md`` (E1-E7 freigegeben am 04.10.2026); die
Abnahmetests in ``tests/test_kommissions_attribution.py`` sind unveränderlich
— jede Abweichung dieser Implementierung von den Tests ist ein Fehler hier,
nicht dort. Alle Beträge sind ``Decimal``: kein float, keine stillen
Rundungen (CLAUDE.md, Regel 5).

Aufteilung nach P2/P3:

- ``kommissions_attribution`` ist rein — keine Uhr, kein Netzwerk, kein
  Zufall, keine Schreibzugriffe; die Attribution braucht keinen Cache
  (Cache-Tabellen sind Tranche IV/V, OF-01).
- ``kommissions_bericht`` liest nur (Regel 1: Zeilen der falschen Sicht
  werden gar nicht gelesen); der Bericht schreibt ausschließlich eine CSV.

Freigegebene Entscheidungen, hier wirksam: E1 — die Auswertungssicht ist
Parameter, jede Gruppe trägt ihre Sicht. E2 — der Strategie-Schlüssel ist
``chains.oa_strategie`` mit Bucket '(ohne)'. E3 — der Anteil ist ein
Betragsverhältnis |Kommission|/|Brutto|, None bei Brutto 0. E4 — nur
abgeschlossene Ketten tragen Summen; offene und kursfehlende zählen. E5 —
Roll-Gruppen '0'/'1'/'2'/'3+' als Text. E6 — eine CSV für alle vier
Dimensionen. E7 — kein neuer Cache, keine Migration.
"""

import pathlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from analytics.kennzahlen import STUFEN_RANG
from journal.db import create_db_engine
from journal.schema import (
    chain_links,
    chains,
    executions,
    instruments,
    legs,
    structures,
)

# E2: Bucket für Ketten ohne oa_strategie — heute der Regelfall, bis der
# OA-Import läuft (optionapp_trades ist leer, AP-13 Teil 1).
OHNE_STRATEGIE = "(ohne)"

_VORZEICHEN = {"SELL": 1, "BUY": -1}
_NULL = Decimal("0")
_VIER_STELLEN = Decimal("0.0001")
_ZWEI_STELLEN = Decimal("0.01")


@dataclass(frozen=True)
class KommissionsGruppe:
    """Eine Gruppe einer Dimension (Regel 4); Summen wirtschaftlich in EUR."""

    dimension: str  # 'index' | 'anlageklasse' | 'strategie' | 'roll_anzahl'
    schluessel: str  # Text: Underlying, asset_class, Strategie oder Roll-Gruppe
    sicht: str  # immer die angeforderte Sicht (E1)
    anzahl_ketten: int  # abgeschlossene mit Kurs — genau die in den Summen
    kommission_eur: Decimal  # negativ, wie gespeichert
    brutto_eur: Decimal
    netto_eur: Decimal  # brutto + kommission
    kommissionsanteil: Decimal | None  # |kommission|/|brutto|, 4 Stellen HALF_UP
    anzahl_ketten_kurs_fehlt: int  # abgeschlossen ohne vollständigen Kurs
    anzahl_ketten_abgeschlossen: int  # anzahl_ketten + anzahl_ketten_kurs_fehlt


@dataclass(frozen=True)
class KommissionsErgebnis:
    sicht: str
    gruppen: tuple[KommissionsGruppe, ...]  # sortiert nach (dimension, schluessel)
    anzahl_ketten_gesamt: int  # inklusive offener und mangelbehafteter Ketten


def _beteiligt(
    structure_ids: list[int], legs_je_struktur: dict[int, list[dict]], exec_je_id: dict
) -> list[dict]:
    """Je Ausführung genau einmal — gleiche Konvention wie Tranche I
    (AP-06v, Regel 3): teilt ein Roll eine Ausführung zwischen Legs, zahlt
    sie insgesamt genau einmal; die Anteile bilden sich je Leg-Seite in
    ``_eur_teile``."""
    ids: list[str] = []
    for structure_id in structure_ids:
        for leg in legs_je_struktur.get(structure_id, ()):
            ids.append(leg["open_exec_id"])
            if leg["close_exec_id"] is not None:
                ids.append(leg["close_exec_id"])
    try:
        return [exec_je_id[i] for i in dict.fromkeys(ids)]
    except KeyError as e:
        raise ValueError(
            f"Ausführung {e.args[0]!r} ist in einem Leg referenziert, aber nicht "
            "unter den Ausführungszeilen — kein Raten (AP-06w, Regel 3)"
        ) from None


def _eur_teile(
    legs: list[dict], exec_je_id: dict, mult_je_conid: dict
) -> tuple[Decimal, Decimal] | None:
    """(brutto_eur, kommission_eur) einer Kette — wirtschaftliche Sicht.

    Wie die Tranche-I-Rechnung (AP-06vk, OF-62-Konvention), nur nach Brutto
    und Kommission getrennt: je Leg-Seite ``preis × vorzeichenlose
    Leg-Menge × multiplikator`` mit Vorzeichen der Seite (SELL +, BUY −;
    OF-13: das Seitenvorzeichen steht nicht zusätzlich in der Menge),
    multipliziert mit dem buchungskurs derselben Ausführung. Die Kommission
    derselben Ausführung läuft mit demselben Kurs, anteilig nach Leg-Menge
    zur Gesamtmenge der Ausführung (AP-03, Regel 5). Fehlt ein Kurs (E4):
    None — kein Wert, keine Summe, kein stiller Kurs 1.
    """
    for leg in legs:
        for schluessel in ("open_exec_id", "close_exec_id"):
            if leg[schluessel] is None:
                continue
            try:
                a = exec_je_id[leg[schluessel]]
            except KeyError as e:
                raise ValueError(
                    f"Ausführung {e.args[0]!r} ist in einem Leg referenziert, "
                    "aber nicht unter den Ausführungszeilen — kein Raten "
                    "(AP-06w, Regel 3)"
                ) from None
            if a["buchungskurs"] is None:
                return None
    brutto = _NULL
    kommission = _NULL
    for leg in legs:
        # Regel 5 (kein float): Leg-Mengen können als int ankommen — hier
        # normalisieren, nicht bei jeder Rechnung.
        leg_menge = leg["menge"] if isinstance(leg["menge"], Decimal) else Decimal(leg["menge"])
        anteil_menge = abs(leg_menge)
        for schluessel in ("open_exec_id", "close_exec_id"):
            exec_id = leg[schluessel]
            if exec_id is None:
                continue
            a = exec_je_id[exec_id]
            vorzeichen = _VORZEICHEN.get(a["side"])
            if vorzeichen is None:
                raise ValueError(
                    f"Ausführung {exec_id}: unbekannte Seite {a['side']!r} — "
                    "kein Vorzeichen ableitbar (AP-06w, Regel 3)"
                )
            try:
                multiplikator = mult_je_conid[a["conid"]]
            except KeyError:
                raise ValueError(
                    f"Ausführung {exec_id}: kein Instrument zu conid {a['conid']} "
                    "— kein Multiplikator ableitbar (AP-06w, Regel 3)"
                ) from None
            gesamtmenge = abs(a["menge"])
            if gesamtmenge == _NULL:
                raise ValueError(
                    f"Ausführung {exec_id}: menge 0 — kein Kommissionsanteil "
                    "ableitbar (AP-06w, Regel 3; AP-03, Regel 5)"
                )
            exec_anteil = (
                a["kommission"] * (anteil_menge / gesamtmenge)
                if a["kommission"] is not None
                else _NULL
            )
            brutto += vorzeichen * a["preis"] * anteil_menge * multiplikator * a["buchungskurs"]
            kommission += exec_anteil * a["buchungskurs"]
    return brutto, kommission


def _qualitaetsstufe(ausfuehrungen: list[dict]) -> str:
    """E6 wie Tranche I: Minimum über die beteiligten Ausführungen, über die
    gemeinsame Rangfolge STUFEN_RANG. Ohne Ausführungen vakant 'A'; eine
    unbekannte Stufe wirft benannt statt still zu sortieren."""
    try:
        rang = min(STUFEN_RANG[a["qualitaetsstufe"]] for a in ausfuehrungen)
    except KeyError as e:
        raise ValueError(
            f"Unbekannte qualitaetsstufe {e.args[0]!r} — keine Rangfolge definiert (AP-06w, E6)"
        ) from None
    except ValueError:
        rang = 0
    return next(stufe for stufe, r in STUFEN_RANG.items() if r == rang)


def _roll_gruppe(anzahl_rolls: int) -> str:
    """E5: '0' | '1' | '2' | '3+' als Text — '3+' liegt in der Textsortierung
    hinter '2' (Regel 6)."""
    return "3+" if anzahl_rolls >= 3 else str(anzahl_rolls)


def kommissions_attribution(
    ketten_zeilen: list[dict],
    struktur_zeilen: list[dict],
    glieder_zeilen: list[dict],
    leg_zeilen: list[dict],
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    *,
    sicht: str = "kette",
    nur_qualitaetsstufe_a: bool = False,
) -> KommissionsErgebnis:
    """Attribution nach AP-06w, Regeln 1-8 (rein, P2).

    Eingangssignatur wie ``kennzahlen_auswertung``: Zeilen als plain dicts
    mit den Spaltennamen der Tabellen; die Zuordnung Struktur → Kette läuft
    über ``glieder_zeilen`` (chain_links). Die Ketten-Zeilen brauchen
    ``chain_id``, ``underlying``, ``asset_class``, ``anzahl_rolls``,
    ``beendet_am`` und ``oa_strategie`` (E2).
    """
    if sicht not in ("kette", "konto"):
        raise ValueError(
            f"Unbekannte sicht {sicht!r} — erlaubt sind 'kette' und 'konto' (AP-06w, Regel 1)"
        )
    exec_je_id = {z["exec_id"]: z for z in ausfuehrungs_zeilen}
    mult_je_conid = {z["conid"]: z["multiplikator"] for z in instrumenten_zeilen}
    kette_je_id = {z["chain_id"]: z for z in ketten_zeilen}
    struktur_ids = {z["structure_id"] for z in struktur_zeilen}
    chain_je_struktur = {z["structure_id"]: z["chain_id"] for z in glieder_zeilen}
    legs_je_struktur: dict[int, list[dict]] = {}
    for leg in leg_zeilen:
        legs_je_struktur.setdefault(leg["structure_id"], []).append(leg)

    gruppen_acc: dict[tuple[str, str], dict[str, object]] = {}
    anzahl_ketten_gesamt = 0
    for chain_id in sorted(kette_je_id):
        zeile = kette_je_id[chain_id]
        structure_ids = sorted(sid for sid, cid in chain_je_struktur.items() if cid == chain_id)
        fehlende = [sid for sid in structure_ids if sid not in struktur_ids]
        if fehlende:
            raise ValueError(
                f"Kette {chain_id}: chain_links ohne structures-Zeile "
                f"{fehlende} — kein Raten (AP-06w, Regel 2)"
            )
        ketten_legs = [leg for sid in structure_ids for leg in legs_je_struktur.get(sid, ())]
        beteiligte = _beteiligt(structure_ids, legs_je_struktur, exec_je_id)
        if nur_qualitaetsstufe_a and _qualitaetsstufe(beteiligte) != "A":
            # E6 wie Tranche I: die Kette fällt ganz — Summen, Anzahlen und
            # anzahl_ketten_gesamt.
            continue
        anzahl_ketten_gesamt += 1
        if zeile["beendet_am"] is None:
            # Regel 2: offene Ketten haben noch keine endgültige Kommission.
            continue
        teile = _eur_teile(ketten_legs, exec_je_id, mult_je_conid)
        # Regel 4: dieselbe Kette zählt in allen vier Dimensionen.
        schluessel_je_dimension = (
            ("index", zeile["underlying"]),
            ("anlageklasse", zeile["asset_class"]),
            ("strategie", zeile["oa_strategie"] or OHNE_STRATEGIE),
            ("roll_anzahl", _roll_gruppe(zeile["anzahl_rolls"])),
        )
        for dimension, schluessel_text in schluessel_je_dimension:
            eintrag = gruppen_acc.setdefault(
                (dimension, schluessel_text),
                {
                    "anzahl": 0,
                    "kommission": _NULL,
                    "brutto": _NULL,
                    "kurs_fehlt": 0,
                    "abgeschlossen": 0,
                },
            )
            eintrag["abgeschlossen"] += 1
            if teile is None:
                # Regel 3: kein Wert, keine Summe, kein stiller Kurs 1.
                eintrag["kurs_fehlt"] += 1
                continue
            eintrag["anzahl"] += 1
            eintrag["brutto"] += teile[0]
            eintrag["kommission"] += teile[1]

    gruppen = tuple(
        KommissionsGruppe(
            dimension=dimension,
            schluessel=schluessel_text,
            sicht=sicht,
            anzahl_ketten=eintrag["anzahl"],
            kommission_eur=eintrag["kommission"],
            brutto_eur=eintrag["brutto"],
            netto_eur=eintrag["brutto"] + eintrag["kommission"],
            # Regel 5/8: der Anteil entsteht einmal am Ende aus den Summen.
            kommissionsanteil=(
                (abs(eintrag["kommission"]) / abs(eintrag["brutto"])).quantize(
                    _VIER_STELLEN, rounding=ROUND_HALF_UP
                )
                if eintrag["brutto"] != _NULL
                else None
            ),
            anzahl_ketten_kurs_fehlt=eintrag["kurs_fehlt"],
            anzahl_ketten_abgeschlossen=eintrag["abgeschlossen"],
        )
        for (dimension, schluessel_text), eintrag in sorted(gruppen_acc.items())
    )
    return KommissionsErgebnis(
        sicht=sicht,
        gruppen=gruppen,
        anzahl_ketten_gesamt=anzahl_ketten_gesamt,
    )


def _geld(wert: Decimal | None) -> str:
    """Geldbeträge wie im Tranche-I-CSV: Text mit Punkt, zwei Stellen
    HALF_UP nur bei der Darstellung; None als leere Zelle."""
    if wert is None:
        return ""
    return str(wert.quantize(_ZWEI_STELLEN, rounding=ROUND_HALF_UP))


_KOPF = (
    "dimension;schluessel;sicht;anzahl_ketten;kommission_eur;brutto_eur;"
    "netto_eur;kommissionsanteil;anzahl_ketten_kurs_fehlt;"
    "anzahl_ketten_abgeschlossen"
)


def als_csv(ergebnis: KommissionsErgebnis) -> str:
    """Eine CSV für alle vier Dimensionen (E6), Semikolon-getrennt; die
    Gruppen stehen in der Sortierung des Ergebnisses (Regel 6). Der Anteil
    ist im Ergebnis bereits auf vier Stellen quantisiert — hier wird nur
    formatiert, nie gerundet (Regel 8)."""
    zeilen = [_KOPF]
    for gruppe in ergebnis.gruppen:
        zeilen.append(
            ";".join(
                [
                    gruppe.dimension,
                    gruppe.schluessel,
                    gruppe.sicht,
                    str(gruppe.anzahl_ketten),
                    _geld(gruppe.kommission_eur),
                    _geld(gruppe.brutto_eur),
                    _geld(gruppe.netto_eur),
                    ("" if gruppe.kommissionsanteil is None else str(gruppe.kommissionsanteil)),
                    str(gruppe.anzahl_ketten_kurs_fehlt),
                    str(gruppe.anzahl_ketten_abgeschlossen),
                ]
            )
        )
    return "\n".join(zeilen)


def kommissions_bericht(
    db_pfad: str | pathlib.Path,
    sicht: str = "kette",
    nur_qualitaetsstufe_a: bool = False,
) -> KommissionsErgebnis:
    """Liest die Zeilen der angeforderten Sicht und wertet aus (P3, Hülle).

    Schreibt nichts in die Datenbank (E7) — die Attribution ist eine reine
    Auswertung, Cache-Tabellen bleiben Tranche IV/V (OF-01). Regel 1: Zeilen
    der falschen Sicht werden gar nicht gelesen.
    """
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        ketten_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    chains.c.chain_id,
                    chains.c.underlying,
                    chains.c.asset_class,
                    chains.c.anzahl_rolls,
                    chains.c.beendet_am,
                    chains.c.oa_strategie,
                ).where(chains.c.sicht == sicht)
            ).mappings()
        ]
        struktur_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(structures.c.structure_id).where(structures.c.sicht == sicht)
            ).mappings()
        ]
        glieder_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(chain_links.c.chain_id, chain_links.c.structure_id).where(
                    chain_links.c.sicht == sicht
                )
            ).mappings()
        ]
        leg_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    legs.c.structure_id,
                    legs.c.conid,
                    legs.c.open_exec_id,
                    legs.c.close_exec_id,
                    legs.c.menge,
                ).where(legs.c.sicht == sicht)
            ).mappings()
        ]
        ausfuehrungs_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    executions.c.exec_id,
                    executions.c.conid,
                    executions.c.side,
                    executions.c.preis,
                    executions.c.menge,
                    executions.c.kommission,
                    executions.c.buchungskurs,
                    executions.c.qualitaetsstufe,
                )
            ).mappings()
        ]
        instrumenten_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(instruments.c.conid, instruments.c.multiplikator)
            ).mappings()
        ]
    return kommissions_attribution(
        ketten_zeilen,
        struktur_zeilen,
        glieder_zeilen,
        leg_zeilen,
        ausfuehrungs_zeilen,
        instrumenten_zeilen,
        sicht=sicht,
        nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )
