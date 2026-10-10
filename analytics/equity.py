"""Equity-Kurve und Drawdown (AP-06, Tranche IV „Analytik IV").

Vertrag ist ``auftraege/AP-06e.md``; die Abnahmetests in
``tests/test_equity.py`` sind unveränderlich — jede Abweichung dieser
Implementierung von den Tests ist ein Fehler hier, nicht dort. Alle Beträge
sind ``Decimal``: kein float, keine stillen Rundungen (CLAUDE.md, Regel 5).

Aufteilung nach P2/P3 wie Tranche I/III:

- ``equity_auswertung`` ist rein — keine Uhr, kein Netzwerk, kein Zufall,
  keine Schreibzugriffe. Die EUR-Werte kommen ausschließlich aus
  ``kennzahlen_auswertung`` (Tranche I): keine zweite EUR-Rechnung.
- ``equity_bericht`` liest nur, dieselben Spalten wie
  ``kennzahlen_bericht``/``degradations_bericht``.

Freigegebene Entscheidungen (AP-06e), hier wirksam:

E1 — **Nur Kontosicht.** Anders als die Roll-Degradation (AP-06d, E1), die
bewusst nur die Kettensicht zulässt: Geld ist Kontosicht-Sache (Plan §5,
„Diese Sicht ist für Geld maßgeblich" — sie speist auch die steuerliche
Auswertung). Eine Equity-Kurve in der Kettensicht würde Gegenläufer doppelt
zählen.

E2 — **Ein Tag = eine geschlossene Struktur zählt an ihrem
``geschlossen_am``-Datum** (nur das Datum, keine Uhrzeit). Mehrere
Strukturen am selben Tag summieren sich. Tage ohne abgeschlossene Struktur
erzeugen keine Zeile (wie die Kalenderübersicht, AP-07t: „nur Tage mit
Ereignissen") — die kumulierte Summe läuft über die vorhandenen Tage
trotzdem lückenlos weiter, weil ein ausgelassener Tag ohnehin 0 beiträgt.

E3 — **Kursmangel zählt als eigener Tag, wenn er der einzige Beitrag ist**,
mit ``netto_eur=0`` und ``anzahl_strukturen_kurs_fehlt`` > 0 — kein stilles
Verschwinden (Regel 7 sinngemäß: automatisch Fehlendes bleibt sichtbar).
Offene (nicht abgeschlossene) Strukturen tragen nirgends bei.

E4 — **Drawdown** je Tag: ``kumuliert − laufendes_hoch`` (laufendes Hoch ist
das Maximum aller bisherigen ``kumuliert``-Werte, inklusive des Tages
selbst) — immer ≤ 0. Der **maximale Drawdown** ist das Minimum dieser Reihe;
ohne Tage ist er 0 und das Datum ``None``.

E5 — **Monatsübersicht** je Kalendermonat (``JJJJ-MM`` aus
``geschlossen_am``): Anzahl, Summe, Durchschnitt (zwei Stellen HALF_UP) und
Trefferquote (vier Stellen, wie Tranche I E5) über die abgeschlossenen
Strukturen mit Kurs; Kursmangel zählt nur im Zähler der Anzahl mit Mangel.

E6 — ``--nur-stufe-a`` filtert wie in Tranche I/III: Strukturen schlechterer
Qualitätsstufe fehlen ganz, auch in der Tagesreihe.

E7 — Die CSV (wie Degradation/Kommission: Semicolon, UTF-8 mit BOM,
Zeilenende ``\\n``, von der CLI gesetzt) hat einen Abschnitt ``tag`` und
einen Abschnitt ``monat``, erkennbar am ersten Feld.
"""

import pathlib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from analytics.kennzahlen import _quote, kennzahlen_auswertung
from journal.db import create_db_engine
from journal.schema import chain_links, chains, executions, instruments, legs, structures

_NULL = Decimal("0.00")
_ZWEI_STELLEN = Decimal("0.01")

_KOPF = (
    "abschnitt",
    "datum_oder_monat",
    "anzahl_strukturen",
    "netto_eur",
    "kumuliert_eur",
    "drawdown_eur",
    "durchschnitt_netto_eur",
    "trefferquote",
    "anzahl_strukturen_kurs_fehlt",
)


@dataclass(frozen=True)
class EquityTag:
    datum: date
    netto_eur: Decimal              # Summe der an diesem Tag geschlossenen Strukturen
    kumuliert_eur: Decimal          # laufende Summe bis einschließlich diesem Tag
    drawdown_eur: Decimal           # kumuliert - laufendes Hoch, immer <= 0
    anzahl_strukturen: int          # mit Kurs, genau die in netto_eur
    anzahl_strukturen_kurs_fehlt: int


@dataclass(frozen=True)
class EquityMonat:
    monat: str                      # 'JJJJ-MM'
    anzahl_strukturen: int
    summe_netto_eur: Decimal
    durchschnitt_netto_eur: Decimal | None
    trefferquote: Decimal | None
    anzahl_strukturen_kurs_fehlt: int


@dataclass(frozen=True)
class EquityErgebnis:
    sicht: str                      # immer 'konto' (E1)
    tage: tuple[EquityTag, ...]      # chronologisch aufsteigend, nur Tage mit Aktivität
    monate: tuple[EquityMonat, ...]  # chronologisch aufsteigend
    max_drawdown_eur: Decimal        # Minimum der Tagesreihe; 0 ohne Tage
    max_drawdown_datum: date | None


def equity_auswertung(
    ketten_zeilen: list[dict],
    struktur_zeilen: list[dict],
    glieder_zeilen: list[dict],
    leg_zeilen: list[dict],
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    *,
    sicht: str = "konto",
    nur_qualitaetsstufe_a: bool = False,
    von: date | None = None,
    bis: date | None = None,
) -> EquityErgebnis:
    """Equity-Kurve und Drawdown nach AP-06e, E1-E6 (rein, P2).

    Eingangszeilen sind plain dicts mit den Spaltennamen der Tabellen, wie
    bei ``degradations_auswertung`` — ``struktur_zeilen`` tragen zusätzlich
    ``geschlossen_am`` (E2).

    ``von``/``bis`` (AP-08f2, Z2/Z4): nur Strukturen, deren Schließungsdatum
    im Zeitraum liegt (beide Enden einschließlich); die Kurve beginnt am
    Zeitraumanfang bei 0, der Drawdown zählt nur innerhalb des Zeitraums.
    """
    if sicht != "konto":
        raise ValueError(
            f"Die Equity-Kurve läuft nur auf der Kontosicht — sicht "
            f"{sicht!r} ist nicht erlaubt (AP-06e, E1)"
        )
    if von is not None and bis is not None and von > bis:
        raise ValueError(f"Zeitraum ungültig: von {von} liegt nach bis {bis}")

    def im_zeitraum(tag: date) -> bool:
        return (von is None or tag >= von) and (bis is None or tag <= bis)
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
    geschlossen_am_je_struktur = {
        s["structure_id"]: s["geschlossen_am"] for s in struktur_zeilen
    }

    # E2/E3: je Tag Summe mit Kurs und Anzahl ohne Kurs, nur abgeschlossene
    # Strukturen (geschlossen_am gesetzt) der zugelassenen Qualitätsstufe.
    netto_je_tag: dict[date, Decimal] = {}
    anzahl_je_tag: dict[date, int] = {}
    mangel_je_tag: dict[date, int] = {}
    for struktur in grundlage.strukturen:
        zeitpunkt = geschlossen_am_je_struktur.get(struktur.structure_id)
        if zeitpunkt is None:
            continue
        tag = zeitpunkt.date()
        if not im_zeitraum(tag):
            continue
        if struktur.netto_eur_wirtschaftlich is None:
            mangel_je_tag[tag] = mangel_je_tag.get(tag, 0) + 1
            continue
        netto_je_tag[tag] = netto_je_tag.get(tag, _NULL) + struktur.netto_eur_wirtschaftlich
        anzahl_je_tag[tag] = anzahl_je_tag.get(tag, 0) + 1

    alle_tage = sorted(set(netto_je_tag) | set(mangel_je_tag))

    tage: list[EquityTag] = []
    kumuliert = _NULL
    hoch = _NULL
    max_drawdown = _NULL
    max_drawdown_datum: date | None = None
    for tag in alle_tage:
        netto = netto_je_tag.get(tag, _NULL)
        kumuliert += netto
        hoch = max(hoch, kumuliert)
        drawdown = kumuliert - hoch
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            max_drawdown_datum = tag
        tage.append(
            EquityTag(
                datum=tag,
                netto_eur=netto,
                kumuliert_eur=kumuliert,
                drawdown_eur=drawdown,
                anzahl_strukturen=anzahl_je_tag.get(tag, 0),
                anzahl_strukturen_kurs_fehlt=mangel_je_tag.get(tag, 0),
            )
        )

    # E5: Monatsübersicht über dieselbe Grundlage, nur anders gruppiert.
    netto_je_monat: dict[str, Decimal] = {}
    anzahl_je_monat: dict[str, int] = {}
    treffer_je_monat: dict[str, int] = {}
    mangel_je_monat: dict[str, int] = {}
    for struktur in grundlage.strukturen:
        zeitpunkt = geschlossen_am_je_struktur.get(struktur.structure_id)
        if zeitpunkt is None:
            continue
        if not im_zeitraum(zeitpunkt.date()):
            continue
        monat = f"{zeitpunkt.year:04d}-{zeitpunkt.month:02d}"
        if struktur.netto_eur_wirtschaftlich is None:
            mangel_je_monat[monat] = mangel_je_monat.get(monat, 0) + 1
            continue
        netto_je_monat[monat] = netto_je_monat.get(monat, _NULL) + struktur.netto_eur_wirtschaftlich
        anzahl_je_monat[monat] = anzahl_je_monat.get(monat, 0) + 1
        if struktur.netto_eur_wirtschaftlich > _NULL:
            treffer_je_monat[monat] = treffer_je_monat.get(monat, 0) + 1

    monate: list[EquityMonat] = []
    for monat in sorted(set(netto_je_monat) | set(mangel_je_monat)):
        anzahl = anzahl_je_monat.get(monat, 0)
        summe = netto_je_monat.get(monat, _NULL)
        monate.append(
            EquityMonat(
                monat=monat,
                anzahl_strukturen=anzahl,
                summe_netto_eur=summe,
                durchschnitt_netto_eur=(
                    (summe / anzahl).quantize(_ZWEI_STELLEN, rounding=ROUND_HALF_UP)
                    if anzahl
                    else None
                ),
                trefferquote=_quote(treffer_je_monat.get(monat, 0), anzahl),
                anzahl_strukturen_kurs_fehlt=mangel_je_monat.get(monat, 0),
            )
        )

    return EquityErgebnis(
        sicht=sicht,
        tage=tuple(tage),
        monate=tuple(monate),
        max_drawdown_eur=max_drawdown,
        max_drawdown_datum=max_drawdown_datum,
    )


def als_csv(ergebnis: EquityErgebnis) -> str:
    """E7: eine CSV — Kopf, je Tag eine ``tag``-Zeile, je Monat eine
    ``monat``-Zeile. Geldbeträge mit zwei, Quoten mit vier Stellen,
    ``None`` als leere Zelle. Zeilenende ``\\n`` und UTF-8 mit BOM setzt die
    CLI (wie Degradation/Kommission, Regel 13)."""
    zeilen = [";".join(_KOPF)]
    for tag in ergebnis.tage:
        zeilen.append(
            ";".join(
                [
                    "tag",
                    tag.datum.isoformat(),
                    str(tag.anzahl_strukturen),
                    _geld(tag.netto_eur),
                    _geld(tag.kumuliert_eur),
                    _geld(tag.drawdown_eur),
                    "",
                    "",
                    str(tag.anzahl_strukturen_kurs_fehlt),
                ]
            )
        )
    for monat in ergebnis.monate:
        zeilen.append(
            ";".join(
                [
                    "monat",
                    monat.monat,
                    str(monat.anzahl_strukturen),
                    _geld(monat.summe_netto_eur),
                    "",
                    "",
                    _geld(monat.durchschnitt_netto_eur),
                    _quote_text(monat.trefferquote),
                    str(monat.anzahl_strukturen_kurs_fehlt),
                ]
            )
        )
    return "\n".join(zeilen)


def _geld(wert: Decimal | None) -> str:
    return "" if wert is None else f"{wert:.2f}"


def _quote_text(wert: Decimal | None) -> str:
    return "" if wert is None else f"{wert:.4f}"


def equity_bericht(
    db_pfad: str | pathlib.Path,
    *,
    nur_qualitaetsstufe_a: bool = False,
    von: date | None = None,
    bis: date | None = None,
) -> EquityErgebnis:
    """Liest die Zeilen der Kontosicht und wertet aus (P3, Hülle).

    Schreibt nichts in die Datenbank (wie ``degradations_bericht``).
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
                ).where(chains.c.sicht == "konto")
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
                ).where(structures.c.sicht == "konto")
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
                ).where(chain_links.c.sicht == "konto")
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
                ).where(legs.c.sicht == "konto")
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
    return equity_auswertung(
        ketten_zeilen,
        struktur_zeilen,
        glieder_zeilen,
        leg_zeilen,
        ausfuehrungs_zeilen,
        instrumenten_zeilen,
        sicht="konto",
        nur_qualitaetsstufe_a=nur_qualitaetsstufe_a,
        von=von,
        bis=bis,
    )
