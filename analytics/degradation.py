"""Roll-Degradation (AP-06, Tranche III „Analytik III").

Vertrag ist ``auftraege/AP-06d.md``; die Abnahmetests in
``tests/test_degradation.py`` sind unveränderlich — jede Abweichung dieser
Implementierung von den Tests ist ein Fehler hier, nicht dort. Alle Beträge
sind ``Decimal``: kein float, keine stillen Rundungen (CLAUDE.md, Regel 5).

Aufteilung nach P2/P3:

- ``degradations_auswertung`` ist rein — keine Uhr, kein Netzwerk, kein
  Zufall, keine Schreibzugriffe. Die EUR-Werte kommen ausschließlich aus
  ``kennzahlen_auswertung`` (Tranche I): keine zweite EUR-Rechnung, Netto je
  Kette ist ``netto_eur_wirtschaftlich`` (Ketten ohne Kurs: ``None``).
- ``degradations_bericht`` liest nur (Regel 1: Zeilen der falschen Sicht
  werden gar nicht gelesen) — dieselben Spalten wie ``kennzahlen_bericht``,
  einschließlich ``ereignistyp``/``schlusskurs``/``abwicklungsart`` (OF-69),
  zusätzlich ``sequenz``/``verknuepfungstyp``/``erkennung`` aus
  ``chain_links``. ``fx_rates``/``metrics_by_chain`` zu schreiben gehört zur
  Tranche I, nicht hierher. Die offenen Rollkandidaten ermittelt die Hülle
  selbst, wenn sie nicht übergeben werden.

Freigegebene Entscheidungen (AP-06d), hier wirksam: E1 — nur die Kettensicht;
eine andere Sicht ist ein Fehler, der die Kettensicht nennt. E2 — Gruppen
'0'/'1'/'2'/'3+' wie die Roll-Dimension der Kommissionsattribution; das
Ergebnis nach n Rolls ist das der Ketten mit n Rolls, kein kumulierter
Verlauf je Kette. E3 — je Gruppe Anzahl, Summe, Durchschnitt (zwei Stellen
HALF_UP) und Trefferquote (vier Stellen, Tranche I E5); Ketten ohne Kurs
zählen nur als Mangel; leere Gruppe: 0, 0.00, None, None. E4 — Modus
'belegt' lässt nur Ketten zu, deren Rollverknüpfungen sämtlich 'auto'
tragen, 'belegt_bestaetigt' zusätzlich 'manuell'; 'heuristik' geht in
keinen Modus. E5 — Abdeckung je Modus über Ketten und Rollverknüpfungen;
ohne Angabe der offenen Kandidaten bleibt die Roll-Abdeckung ``None``.
E6 — Ketten an offenen Kandidaten werden nicht ausgeschlossen, sondern über
die Abdeckung ausgewiesen. E7 — ``--nur-stufe-a`` entfernt Ketten ganz, auch
aus der Abdeckung (der Filter steckt in ``kennzahlen_auswertung``). E8 — die
CSV (Semicolon, UTF-8 mit BOM, Zeilenende ``\\n``) schreibt die CLI.
"""

import pathlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from analytics.kennzahlen import _quote, kennzahlen_auswertung
from journal.db import create_db_engine
from journal.rebuild import offene_rollkandidaten
from journal.schema import (
    chain_links,
    chains,
    executions,
    instruments,
    legs,
    structures,
)

# E2: Reihenfolge der Gruppen in Ergebnis und CSV — '3+' sortiert in der
# Textsortierung hinter '2' (wie AP-06w, E5).
ROLL_GRUPPEN = ("0", "1", "2", "3+")

# E4: je Modus die zulässigen Erkennungen aller Rollverknüpfungen einer Kette.
_BELEGT_ERKENNUNGEN = frozenset({"auto"})
_BELEGT_BESTAETIGT_ERKENNUNGEN = frozenset({"auto", "manuell"})
MODI = (("belegt", _BELEGT_ERKENNUNGEN), ("belegt_bestaetigt", _BELEGT_BESTAETIGT_ERKENNUNGEN))

_NULL = Decimal("0")
_ZWEI_STELLEN = Decimal("0.01")

# E8: feste Spaltenreihenfolge der Degradations-CSV — Gruppenzeilen füllen die
# ersten acht Spalten, Abdeckungszeilen die letzten sechs.
_KOPF = (
    "abschnitt",
    "modus",
    "roll_gruppe",
    "anzahl_ketten",
    "summe_netto_eur",
    "durchschnitt_netto_eur",
    "trefferquote",
    "anzahl_ketten_kurs_fehlt",
    "ketten_abgeschlossen",
    "ketten_ausgewertet",
    "abdeckung_ketten",
    "rollverknuepfungen",
    "offene_kandidaten",
    "abdeckung_rollverknuepfungen",
)


@dataclass(frozen=True)
class DegradationsGruppe:
    """Eine Gruppe eines Modus (E2/E3); Summen wirtschaftlich in EUR."""

    modus: str  # 'belegt' | 'belegt_bestaetigt'
    roll_gruppe: str  # '0' | '1' | '2' | '3+'
    anzahl_ketten: int  # abgeschlossene, zugelassene mit Kurs — genau die in der Summe
    summe_netto_eur: Decimal  # wirtschaftlich, Tranche I; leere Gruppe: 0
    durchschnitt_netto_eur: Decimal | None  # zwei Stellen HALF_UP; None ohne Ketten
    trefferquote: Decimal | None  # Anteil netto > 0, vier Stellen (Tranche I E5)
    anzahl_ketten_kurs_fehlt: int  # zugelassen, aber ohne vollständigen Kurs
    # Drilldown (AP-17g, M01): die Ketten hinter Summe und Durchschnitt bzw. ohne Kurs, sortiert.
    ketten_ids: tuple = ()
    ketten_ids_kurs_fehlt: tuple = ()


@dataclass(frozen=True)
class DegradationsAbdeckung:
    """Abdeckung eines Modus (E5/E6) — Ausweis statt Ausschluss."""

    modus: str
    ketten_abgeschlossen: int  # alle abgeschlossenen Ketten der Sicht nach Stufenfilter
    ketten_ausgewertet: int  # zugelassene, auch mit Kursmangel
    abdeckung_ketten: Decimal | None  # ausgewertet / abgeschlossen
    rollverknuepfungen: int  # Roll-Glieder der zugelassenen Ketten
    offene_kandidaten: int | None  # übergeben oder ermittelt; ohne Angabe None
    abdeckung_rollverknuepfungen: Decimal | None  # rolls / (rolls + offene)


@dataclass(frozen=True)
class DegradationsErgebnis:
    sicht: str  # immer 'kette' (E1)
    gruppen: tuple[DegradationsGruppe, ...]  # je Modus alle vier Gruppen, auch leere
    abdeckung: tuple[DegradationsAbdeckung, ...]  # je Modus eine Zeile


def _roll_gruppe(anzahl_rolls: int) -> str:
    """E2: '0' | '1' | '2' | '3+' — wie die Roll-Dimension der
    Kommissionsattribution (AP-06w, E5), auf ``chains.anzahl_rolls``."""
    return "3+" if anzahl_rolls >= 3 else str(anzahl_rolls)


def degradations_auswertung(
    ketten_zeilen: list[dict],
    struktur_zeilen: list[dict],
    glieder_zeilen: list[dict],
    leg_zeilen: list[dict],
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    *,
    sicht: str = "kette",
    offene_kandidaten: int | None = None,
    nur_qualitaetsstufe_a: bool = False,
) -> DegradationsErgebnis:
    """Roll-Degradationskurve nach AP-06d, E1–E7 (rein, P2).

    Eingangszeilen sind plain dicts mit den Spaltennamen der Tabellen;
    ``glieder_zeilen`` tragen zusätzlich ``verknuepfungstyp`` und
    ``erkennung``. Die EUR-Werte je Kette liefert ``kennzahlen_auswertung``
    (Tranche I) — inklusive des Stufenfilters E7, der Ketten ganz entfernt.
    """
    if sicht != "kette":
        raise ValueError(
            f"Die Roll-Degradation läuft nur auf der Kettensicht — sicht "
            f"{sicht!r} ist nicht erlaubt (AP-06d, E1)"
        )
    grundlage = kennzahlen_auswertung(
        ketten_zeilen,
        struktur_zeilen,
        glieder_zeilen,
        leg_zeilen,
        ausfuehrungs_zeilen,
        instrumenten_zeilen,
        sicht=sicht,
        nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )

    # E4: Erkennungen der Rollverknüpfungen je Kette — nur sie entscheiden
    # über die Zulassung. Roll-Glieder offener Kandidaten (E6) fehlen hier
    # ohnehin, weil die Engine sie nicht verknüpft; die Kandidaten selbst
    # gehen nie als Roll ein.
    roll_erkennungen_je_kette: dict[int, list[str]] = {}
    for glied in glieder_zeilen:
        if glied["verknuepfungstyp"] == "roll":
            roll_erkennungen_je_kette.setdefault(glied["chain_id"], []).append(
                glied["erkennung"]
            )

    ketten_abgeschlossen = sum(1 for kette in grundlage.ketten if kette.abgeschlossen)
    gruppen: list[DegradationsGruppe] = []
    abdeckung: list[DegradationsAbdeckung] = []
    for modus, erlaubte_erkennungen in MODI:
        zugelassen = [
            kette
            for kette in grundlage.ketten
            if kette.abgeschlossen
            and all(
                erkennung in erlaubte_erkennungen
                for erkennung in roll_erkennungen_je_kette.get(kette.chain_id, ())
            )
        ]
        for roll_gruppe in ROLL_GRUPPEN:
            in_gruppe = [
                kette
                for kette in zugelassen
                if _roll_gruppe(kette.anzahl_rolls) == roll_gruppe
            ]
            mit_kurs = [k for k in in_gruppe if k.netto_eur_wirtschaftlich is not None]
            summe = sum((k.netto_eur_wirtschaftlich for k in mit_kurs), _NULL)
            gruppen.append(
                DegradationsGruppe(
                    modus=modus,
                    roll_gruppe=roll_gruppe,
                    anzahl_ketten=len(mit_kurs),
                    summe_netto_eur=summe,
                    durchschnitt_netto_eur=(
                        (summe / len(mit_kurs)).quantize(_ZWEI_STELLEN, rounding=ROUND_HALF_UP)
                        if mit_kurs
                        else None
                    ),
                    trefferquote=_quote(
                        sum(1 for k in mit_kurs if k.netto_eur_wirtschaftlich > _NULL),
                        len(mit_kurs),
                    ),
                    anzahl_ketten_kurs_fehlt=len(in_gruppe) - len(mit_kurs),
                    ketten_ids=tuple(sorted(k.chain_id for k in mit_kurs)),
                    ketten_ids_kurs_fehlt=tuple(sorted(
                        k.chain_id for k in in_gruppe if k.netto_eur_wirtschaftlich is None)),
                )
            )
        rollverknuepfungen = sum(
            len(roll_erkennungen_je_kette.get(kette.chain_id, ())) for kette in zugelassen
        )
        abdeckung.append(
            DegradationsAbdeckung(
                modus=modus,
                ketten_abgeschlossen=ketten_abgeschlossen,
                ketten_ausgewertet=len(zugelassen),
                abdeckung_ketten=_quote(len(zugelassen), ketten_abgeschlossen),
                rollverknuepfungen=rollverknuepfungen,
                offene_kandidaten=offene_kandidaten,
                abdeckung_rollverknuepfungen=(
                    _quote(rollverknuepfungen, rollverknuepfungen + offene_kandidaten)
                    if offene_kandidaten is not None
                    else None
                ),
            )
        )
    return DegradationsErgebnis(sicht=sicht, gruppen=tuple(gruppen), abdeckung=tuple(abdeckung))



def als_csv(ergebnis: DegradationsErgebnis) -> str:
    """E8: eine CSV — Kopf, je Modus vier ``gruppe``-Zeilen, je Modus eine
    ``abdeckung``-Zeile. Geldbeträge mit zwei, Quoten mit vier Stellen,
    ``None`` als leere Zelle. Zeilenende ``\\n`` und UTF-8 mit BOM setzt die
    CLI (wie der Kennzahlen-Bericht, Regel 13)."""
    zeilen = [";".join(_KOPF)]
    for gruppe in ergebnis.gruppen:
        zeilen.append(
            ";".join(
                [
                    "gruppe",
                    gruppe.modus,
                    gruppe.roll_gruppe,
                    str(gruppe.anzahl_ketten),
                    _geld(gruppe.summe_netto_eur),
                    _geld(gruppe.durchschnitt_netto_eur),
                    _quote_text(gruppe.trefferquote),
                    str(gruppe.anzahl_ketten_kurs_fehlt),
                ]
                + [""] * 6
            )
        )
    for abdeckung in ergebnis.abdeckung:
        zeilen.append(
            ";".join(
                ["abdeckung", abdeckung.modus]
                + [""] * 6
                + [
                    str(abdeckung.ketten_abgeschlossen),
                    str(abdeckung.ketten_ausgewertet),
                    _quote_text(abdeckung.abdeckung_ketten),
                    str(abdeckung.rollverknuepfungen),
                    _zahl_text(abdeckung.offene_kandidaten),
                    _quote_text(abdeckung.abdeckung_rollverknuepfungen),
                ]
            )
        )
    return "\n".join(zeilen)


def _geld(wert: Decimal | None) -> str:
    """Geldbeträge wie im Tranche-I/II-CSV: Text mit Punkt, zwei Stellen,
    ``None`` als leere Zelle."""
    return "" if wert is None else f"{wert:.2f}"


def _quote_text(wert: Decimal | None) -> str:
    """Quoten wie im Tranche-I-CSV: vier Stellen, ``None`` als leere Zelle."""
    return "" if wert is None else f"{wert:.4f}"


def _zahl_text(wert: int | None) -> str:
    """Zählwerte; ``None`` (Kandidaten nicht angegeben) als leere Zelle."""
    return "" if wert is None else str(wert)



def degradations_bericht(
    db_pfad: str | pathlib.Path,
    *,
    nur_qualitaetsstufe_a: bool = False,
    offene_kandidaten: int | None = None,
) -> DegradationsErgebnis:
    """Liest die Zeilen der Kettensicht und wertet aus (P3, Hülle).

    Schreibt nichts in die Datenbank — ``fx_rates``/``metrics_by_chain``
    gehören zu ``kennzahlen_bericht`` (Tranche I). E5: Sind die offenen
    Rollkandidaten nicht übergeben, ermittelt sie die Hülle selbst über
    ``journal.rebuild.offene_rollkandidaten`` (liest selbst nur).
    """
    if offene_kandidaten is None:
        offene_kandidaten = offene_rollkandidaten(db_pfad)
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
                ).where(chains.c.sicht == "kette")
            ).mappings()
        ]
        struktur_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    structures.c.structure_id,
                    structures.c.typ,
                    structures.c.waehrung,
                    structures.c.brutto_pnl,
                    structures.c.kommission,
                    structures.c.netto_pnl,
                    structures.c.geschlossen_am,
                ).where(structures.c.sicht == "kette")
            ).mappings()
        ]
        glieder_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    chain_links.c.chain_id,
                    chain_links.c.structure_id,
                    chain_links.c.sequenz,
                    chain_links.c.verknuepfungstyp,
                    chain_links.c.erkennung,
                ).where(chain_links.c.sicht == "kette")
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
                    # Faktoren der Kapitalmaßnahmen (R09), sonst falsch nach Splits
                    legs.c.open_faktor,
                    legs.c.close_faktor,
                ).where(legs.c.sicht == "kette")
            ).mappings()
        ]
        ausfuehrungs_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    executions.c.exec_id,
                    executions.c.conid,
                    executions.c.side,
                    executions.c.menge,
                    executions.c.preis,
                    executions.c.waehrung,
                    executions.c.kommission,
                    executions.c.kommission_waehrung,
                    executions.c.buchungskurs,
                    executions.c.handelszeit,
                    executions.c.qualitaetsstufe,
                    executions.c.ereignistyp,
                    executions.c.schlusskurs,
                )
            ).mappings()
        ]
        instrumenten_zeilen = [
            dict(z)
            for z in verbindung.execute(
                select(
                    instruments.c.conid,
                    instruments.c.multiplikator,
                    instruments.c.abwicklungsart,
                )
            ).mappings()
        ]
    return degradations_auswertung(
        ketten_zeilen,
        struktur_zeilen,
        glieder_zeilen,
        leg_zeilen,
        ausfuehrungs_zeilen,
        instrumenten_zeilen,
        sicht="kette",
        offene_kandidaten=offene_kandidaten,
        nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
    )

