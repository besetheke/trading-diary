"""Ergebnis je Titel, über alle Instrumente (AP-16, Nutzerwunsch 16.10.2026).

Frage: *Was habe ich mit WDC insgesamt gemacht — Optionen, Aktien, Futures zusammen?* Die
Positionsliste zeigt Ketten (ein Trade je Zeile); diese Auswertung fasst alle Ketten und losen
Beine **eines Basiswerts** zusammen und trennt das Ergebnis nach Anlageklasse.

Rechengrundlage — keine zweite EUR-Rechnung (AP-06e, I2):

- **Realisiert** zählt wie die Equity (``analytics/equity.py``): abgeschlossene Strukturen der
  Kontosicht mit ``kennzahlen_auswertung`` (EUR, jede Seite zum Kurs ihres Tages), dazu
  abgeschlossene lose Beine (zwei Nachkommastellen wie dort). Die Summe je Titel ist deshalb
  dieselbe Zahl wie ``ergebnis.summe_netto_eur`` der Auswertung mit Basiswertfilter.
- **Aufteilung nach Anlageklasse**: je Bein ``_wirtschaftlich([bein])``, der Klasse seines
  Instruments zugeordnet. ``_wirtschaftlich`` addiert je Seite eines Beins, die Beine einer
  Struktur ergeben also ihre Strukturzahl; bleibt ein Unterschied, steht er in
  ``nicht_aufgeteilt_eur`` (nie stillschweigend verteilt). Optionsprämien stehen bei den
  Optionen, das Kursergebnis einer zugeteilten Aktie bei den Aktien (Einstand = Zuteilungspreis)
  — IBs Methode, die Prämie in den Einstand der Aktie zu schieben, gilt hier nicht.
- **Unrealisiert**: offene Beine mit IBs Bestand des jüngsten Stichtags
  (``unrealisiert_auswertung``), je Klasse und gesamt.
- Nicht enthalten: Dividenden, Zinsen, Gebühren außerhalb der Ausführungen (OF-89).

Rein: keine Uhr, kein Netzwerk, keine Schreibzugriffe. Alle Beträge ``Decimal``.
"""

import json
import pathlib
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from analytics.kennzahlen import _wirtschaftlich, bewerte_barausgleich, kennzahlen_auswertung
from analytics.unrealisiert import unrealisiert_auswertung
from journal.db import create_db_engine
from journal.schema import (
    chain_links,
    chains,
    executions,
    flex_open_positions,
    instruments,
    legs,
    structures,
)

_NULL = Decimal("0")
_ZWEI = Decimal("0.01")


@dataclass
class TitelZeile:
    basiswert: str
    ketten: int = 0
    ketten_offen: int = 0
    strukturen_geschlossen: int = 0
    realisiert_eur: Decimal = _NULL
    realisiert_je_klasse: dict = field(default_factory=dict)
    nicht_aufgeteilt_eur: Decimal = _NULL
    unrealisiert_eur: Decimal = _NULL
    unrealisiert_je_klasse: dict = field(default_factory=dict)
    kurs_fehlt: int = 0  # geschlossene Strukturen/lose Beine ohne Buchungskurs (zählen nicht)
    offene_ohne_kurs: int = 0  # offene Beine ohne Bestandszeile (zählen nicht)
    waehrungen: set = field(default_factory=set)

    @property
    def gesamt_eur(self) -> Decimal:
        return self.realisiert_eur + self.unrealisiert_eur


def _klasse(instrument: dict | None) -> str:
    return (instrument or {}).get("asset_class") or "?"


def titel_auswertung(
    ketten_zeilen: list[dict],
    struktur_zeilen: list[dict],
    glieder_zeilen: list[dict],
    leg_zeilen: list[dict],
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    bestand_je_conid: dict[int, dict],
    stichtag,
) -> list[TitelZeile]:
    """Je Basiswert eine ``TitelZeile`` (Kontosicht).

    ``bestand_je_conid``: conid → ``menge``, ``wert``, ``kurs`` wie bei
    ``unrealisiert_auswertung``.
    """
    grundlage = kennzahlen_auswertung(
        ketten_zeilen,
        struktur_zeilen,
        glieder_zeilen,
        leg_zeilen,
        ausfuehrungs_zeilen,
        instrumenten_zeilen,
        sicht="konto",
        nur_qualitaetsstufe_a=False,
    )
    bewertet = bewerte_barausgleich(ausfuehrungs_zeilen, instrumenten_zeilen)
    exec_je_id = {z["exec_id"]: z for z in bewertet}
    mult_je_conid = {z["conid"]: z["multiplikator"] for z in instrumenten_zeilen}
    instrument_je_conid = {z["conid"]: z for z in instrumenten_zeilen}

    kette_je_id = {k["chain_id"]: k for k in ketten_zeilen}
    kette_je_struktur = {
        g["structure_id"]: g["chain_id"] for g in glieder_zeilen if g["structure_id"] is not None
    }
    geschlossen_am = {s["structure_id"]: s["geschlossen_am"] for s in struktur_zeilen}
    legs_je_struktur: dict[int, list[dict]] = {}
    for leg in leg_zeilen:
        if leg["structure_id"] is not None:
            legs_je_struktur.setdefault(leg["structure_id"], []).append(leg)

    zeilen: dict[str, TitelZeile] = {}

    def zeile(basiswert: str) -> TitelZeile:
        return zeilen.setdefault(basiswert, TitelZeile(basiswert=basiswert))

    def basiswert_des_beins(leg: dict) -> str:
        i = instrument_je_conid.get(leg["conid"])
        return (i and (i.get("underlying") or i.get("symbol"))) or "?"

    for kette in ketten_zeilen:
        z = zeile(kette["underlying"])
        z.ketten += 1
        if kette.get("beendet_am") is None:
            z.ketten_offen += 1

    # --- Realisiert: abgeschlossene Strukturen (Kontosicht), je Bein nach Klasse aufgeteilt
    for struktur in grundlage.strukturen:
        if geschlossen_am.get(struktur.structure_id) is None:
            continue
        kette = kette_je_id.get(kette_je_struktur.get(struktur.structure_id))
        if kette is None:
            continue
        z = zeile(kette["underlying"])
        z.strukturen_geschlossen += 1
        z.waehrungen.add(struktur.waehrung)
        if struktur.netto_eur_wirtschaftlich is None:
            z.kurs_fehlt += 1
            continue
        aufgeteilt = _NULL
        for leg in legs_je_struktur.get(struktur.structure_id, ()):
            betrag = _wirtschaftlich([leg], exec_je_id, mult_je_conid)
            if betrag is None:
                continue
            klasse = _klasse(instrument_je_conid.get(leg["conid"]))
            z.realisiert_je_klasse[klasse] = z.realisiert_je_klasse.get(klasse, _NULL) + betrag
            aufgeteilt += betrag
        z.realisiert_eur += struktur.netto_eur_wirtschaftlich
        z.nicht_aufgeteilt_eur += struktur.netto_eur_wirtschaftlich - aufgeteilt

    # --- Realisiert: abgeschlossene lose Beine (ohne Struktur), zwei Stellen wie in der Equity
    for leg in leg_zeilen:
        if leg["structure_id"] is not None or leg["close_exec_id"] is None:
            continue
        z = zeile(basiswert_des_beins(leg))
        betrag = _wirtschaftlich([leg], exec_je_id, mult_je_conid)
        if betrag is None:
            z.kurs_fehlt += 1
            continue
        betrag = betrag.quantize(_ZWEI, rounding=ROUND_HALF_UP)
        klasse = _klasse(instrument_je_conid.get(leg["conid"]))
        z.realisiert_eur += betrag
        z.realisiert_je_klasse[klasse] = z.realisiert_je_klasse.get(klasse, _NULL) + betrag
        z.waehrungen.add(exec_je_id[leg["close_exec_id"]]["waehrung"])

    # --- Unrealisiert: offene Beine je Titel und Klasse
    offene_je_gruppe: dict[tuple[str, str], list[dict]] = {}
    for leg in leg_zeilen:
        if leg["close_exec_id"] is not None:
            continue
        if leg["structure_id"] is not None:
            kette = kette_je_id.get(kette_je_struktur.get(leg["structure_id"]))
            basiswert = kette["underlying"] if kette else basiswert_des_beins(leg)
        else:
            basiswert = basiswert_des_beins(leg)
        klasse = _klasse(instrument_je_conid.get(leg["conid"]))
        offene_je_gruppe.setdefault((basiswert, klasse), []).append(leg)
    for (basiswert, klasse), offene in offene_je_gruppe.items():
        u = unrealisiert_auswertung(offene, exec_je_id, mult_je_conid, bestand_je_conid, stichtag)
        z = zeile(basiswert)
        z.unrealisiert_eur += u.eur
        z.unrealisiert_je_klasse[klasse] = z.unrealisiert_je_klasse.get(klasse, _NULL) + u.eur
        z.offene_ohne_kurs += u.ohne_kurs
    return sorted(zeilen.values(), key=lambda t: t.basiswert)


def titel_bericht(db_pfad: str | pathlib.Path) -> tuple[list[TitelZeile], object]:
    """Liest die Kontosicht und wertet aus (Hülle, nur lesend): Zeilen und Stichtag."""
    engine = create_db_engine(db_pfad)
    with engine.begin() as v:
        ketten_zeilen = [
            dict(z)
            for z in v.execute(
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
            for z in v.execute(
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
            for z in v.execute(
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
            for z in v.execute(
                select(
                    legs.c.structure_id,
                    legs.c.conid,
                    legs.c.open_exec_id,
                    legs.c.close_exec_id,
                    legs.c.menge,
                    legs.c.open_faktor,
                    legs.c.close_faktor,
                    legs.c.brutto_pnl,
                    legs.c.kommission_gesamt,
                ).where(legs.c.sicht == "konto")
            ).mappings()
        ]
        ausfuehrungs_zeilen = [
            dict(z)
            for z in v.execute(
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
            for z in v.execute(
                select(
                    instruments.c.conid,
                    instruments.c.multiplikator,
                    instruments.c.abwicklungsart,
                    instruments.c.underlying,
                    instruments.c.asset_class,
                    instruments.c.symbol,
                )
            ).mappings()
        ]
        stichtag = v.execute(
            select(flex_open_positions.c.stichtag)
            .order_by(flex_open_positions.c.stichtag.desc())
            .limit(1)
        ).scalar()
        bestand: dict[int, dict] = {}
        if stichtag is not None:
            for z in v.execute(
                select(
                    flex_open_positions.c.conid,
                    flex_open_positions.c.menge,
                    flex_open_positions.c.roh_json,
                ).where(flex_open_positions.c.stichtag == stichtag)
            ).mappings():
                roh = json.loads(z["roh_json"])
                if roh.get("levelOfDetail") not in (None, "SUMMARY"):
                    continue
                wert, kurs = roh.get("positionValue"), roh.get("fxRateToBase")
                if wert is None or kurs is None:
                    continue
                bestand[z["conid"]] = {
                    "menge": z["menge"],
                    "wert": Decimal(str(wert)),
                    "kurs": Decimal(str(kurs)),
                }
    return titel_auswertung(
        ketten_zeilen,
        struktur_zeilen,
        glieder_zeilen,
        leg_zeilen,
        ausfuehrungs_zeilen,
        instrumenten_zeilen,
        bestand,
        stichtag,
    ), stichtag
