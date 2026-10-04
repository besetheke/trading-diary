"""Steuerliche Auswertung: Töpfe, Jahresabgrenzung, Erträge (AP-10).

Vertrag ist ``auftraege/AP-10v.md``; die Abnahmetests in
``tests/test_steuer.py`` sind unveränderlich — jede Abweichung dieser
Implementierung von den Tests ist ein Fehler hier, nicht dort (CLAUDE.md,
Regel 1b). Alle Beträge sind ``Decimal``: kein float, keine stillen
Rundungen (Regel 5).

Aufteilung nach P2/P3:

- ``steuer_auswertung`` und ``als_csv`` sind rein — keine Datenbank, keine
  Uhr, kein Zufall (Vertrag 11); gleiche Eingabe liefert bitgleiche Ausgabe.
- ``journal.steuer.steuer_bericht`` ist die I/O-Hülle: Sie liest und übergibt.

Freigegebene Entscheidungen (AP-10v 1–6), hier wirksam: Zufluss im Jahr der
schließenden Ausführung; naive Zeitstempel (OF-58); EUR über den
Buchungskurs der Schließung, nie ein stiller Kurs 1 (OF-59);
``basis_ungeklaert`` außerhalb der Summen; Zuteilung/Ausübung realisiert an
der Options-Leg; CASH ausgeschlossen. Das Paket bereitet die Zahlen für den
Steuerberater auf — es ist keine Steuerberatung und bildet insbesondere
keine Verlustverrechnung ab.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

TOPF_AKTIEN = "aktien"
TOPF_TERMIN = "termingeschaefte"

# Vertrag 4: STK → Aktien, OPT/FOP/FUT → Termingeschäfte. CASH und jeder
# unbekannte Wert sind Fehler, nie ein stiller Topf.
_TOPF_JE_ASSET_CLASS = {
    "STK": TOPF_AKTIEN,
    "OPT": TOPF_TERMIN,
    "FOP": TOPF_TERMIN,
    "FUT": TOPF_TERMIN,
}

_NULL = Decimal("0")
_GELD = Decimal("0.01")


@dataclass(frozen=True)
class TopfZeile:
    jahr: int
    topf: str  # TOPF_AKTIEN oder TOPF_TERMIN
    waehrung: str  # Instrumentwährung der Legs
    brutto: Decimal
    kommission: Decimal  # negativ, wie gespeichert
    netto: Decimal  # brutto + kommission
    netto_eur_ib: Decimal  # Summe über Legs mit Buchungskurs
    eur_kurs_fehlt: int  # Legs ohne Buchungskurs in diesem Topf
    anzahl_legs: int
    basis_ungeklaert: int  # immer 0 — ungeklärte Legs stehen separat


@dataclass(frozen=True)
class SteuerLegZeile:
    """Drilldown: jede bewertete Leg einzeln (Details wie Ungeklärtes)."""

    leg_id: int | None
    close_exec_id: str
    conid: int
    symbol: str
    handelszeit: datetime  # naive Schließungszeit
    jahr: int
    topf: str
    waehrung: str
    menge: Decimal
    brutto: Decimal
    kommission: Decimal
    netto: Decimal
    buchungskurs: Decimal | None
    netto_eur_ib: Decimal | None  # None, wenn buchungskurs fehlt
    basis_ungeklaert: bool


@dataclass(frozen=True)
class ErtragsZeile:
    """E8/Kapitalerträge aus flex_cash_transactions, außerhalb der Töpfe."""

    jahr: int
    typ: str  # Quellwert aus flex_cash_transactions.typ
    waehrung: str
    betrag: Decimal  # vorzeichentreu wie Quelle


@dataclass(frozen=True)
class SteuerFehler:
    schluessel: str  # close_exec_id der betroffenen Leg
    grund: str  # siehe Regeln 1, 3–6


@dataclass(frozen=True)
class SteuerErgebnis:
    toepfe: tuple[TopfZeile, ...]
    details: tuple[SteuerLegZeile, ...]
    ungeklaert: tuple[SteuerLegZeile, ...]
    ertraege: tuple[ErtragsZeile, ...]
    fehler: tuple[SteuerFehler, ...]


def steuer_auswertung(
    legs,
    exec_je_id,
    instrument_je_conid,
    cash_transaktionen=(),
) -> SteuerErgebnis:
    """Reine Auswertung nach AP-10v, Regeln 1–11.

    ``legs``: Iterierbares von Abbildungen mit den legs-Spalten (leg_id,
    sicht, conid, close_exec_id, offen_ja_nein, basis_ungeklaert, menge,
    brutto_pnl, kommission_gesamt). ``exec_je_id``: exec_id → Abbildung mit
    handelszeit und buchungskurs. ``instrument_je_conid``: conid → Abbildung
    mit asset_class, symbol, waehrung. ``cash_transaktionen``: Abbildungen
    mit datum, typ, betrag, waehrung — bewusst ohne Typ-Semantik, das
    Filtern gehört dem Leser (Vertrag 13).
    """
    details: list[SteuerLegZeile] = []
    ungeklaert: list[SteuerLegZeile] = []
    fehler: list[SteuerFehler] = []
    # Vertrag 8: Töpfe entstehen ausschließlich aus den Details — die Summen
    # deckeln den Drilldown dadurch konstruktionsgemäß.
    toepfe: dict[tuple[int, str, str], dict[str, object]] = {}

    for leg in legs:
        # Vertrag 1: Nur Kontosicht. Eine Zeile der Kettensicht ist eine
        # vermischte Abfrage, keine Auswertungsgrundlage (Plan §5).
        if leg["sicht"] != "konto":
            schluessel = leg.get("close_exec_id")
            fehler.append(SteuerFehler(str(schluessel) if schluessel else "", "sicht_vermischung"))
            continue
        # Vertrag 2: Offene Legs haben keinen Zufluss — kein Fehler, keine
        # Zeile (auch nicht, wenn einzeln andere Felder fehlen).
        close_exec_id = leg["close_exec_id"]
        if leg["offen_ja_nein"] or close_exec_id is None:
            continue
        # Vertrag 3: Zuflussjahr aus der handelszeit der Schließung, naiv wie
        # gespeichert (OF-04/OF-58).
        schliessung = exec_je_id.get(close_exec_id)
        if schliessung is None:
            fehler.append(SteuerFehler(close_exec_id, "schliessung_fehlt"))
            continue
        # Vertrag 4: Topf über die Stammdatei — Unbekanntes ist ein Fehler,
        # kein stiller Topf (asset_class trägt kein erschöpfendes CHECK).
        instrument = instrument_je_conid.get(leg["conid"])
        if instrument is None:
            fehler.append(SteuerFehler(close_exec_id, "instrument_fehlt"))
            continue
        asset_class = instrument["asset_class"]
        topf = _TOPF_JE_ASSET_CLASS.get(asset_class)
        if asset_class == "CASH":
            fehler.append(SteuerFehler(close_exec_id, "cash_ausgeschlossen"))
            continue
        if topf is None:
            fehler.append(SteuerFehler(close_exec_id, "asset_class_unbekannt"))
            continue
        # Vertrag 5: brutto_pnl None an einer geschlossenen Leg ist benannt;
        # kommission None ist bei Ereignis-Schließungen normal und gilt als 0.
        brutto = leg["brutto_pnl"]
        if brutto is None:
            fehler.append(SteuerFehler(close_exec_id, "ergebnis_fehlt"))
            continue
        kommission = leg["kommission_gesamt"]
        if kommission is None:
            kommission = _NULL
        netto = brutto + kommission
        # Vertrag 6: EUR ausschließlich über den buchungskurs der Schließung —
        # kein stiller Kurs 1, auch nicht bei EUR-Instrumenten (OF-59).
        buchungskurs = schliessung["buchungskurs"]
        netto_eur_ib = netto * buchungskurs if buchungskurs is not None else None
        if netto_eur_ib is None:
            fehler.append(SteuerFehler(close_exec_id, "buchungskurs_fehlt"))
        handelszeit = schliessung["handelszeit"]
        zeile = SteuerLegZeile(
            leg_id=leg.get("leg_id"),
            close_exec_id=close_exec_id,
            conid=leg["conid"],
            symbol=instrument["symbol"],
            handelszeit=handelszeit,
            jahr=handelszeit.year,
            topf=topf,
            waehrung=instrument["waehrung"],
            menge=leg["menge"],
            brutto=brutto,
            kommission=kommission,
            netto=netto,
            buchungskurs=buchungskurs,
            netto_eur_ib=netto_eur_ib,
            basis_ungeklaert=bool(leg["basis_ungeklaert"]),
        )
        if zeile.basis_ungeklaert:
            # Vertrag 7: realisiert, aber Herkunft der Basis ungeklärt — volle
            # Zeile, kein Topfbeitrag (Scheingewinn-Problem, schema.py).
            ungeklaert.append(zeile)
            continue
        details.append(zeile)
        schluessel = (zeile.jahr, zeile.topf, zeile.waehrung)
        eintrag = toepfe.setdefault(
            schluessel,
            {
                "brutto": _NULL,
                "kommission": _NULL,
                "netto": _NULL,
                "netto_eur_ib": _NULL,
                "eur_kurs_fehlt": 0,
                "anzahl_legs": 0,
            },
        )
        eintrag["brutto"] += zeile.brutto
        eintrag["kommission"] += zeile.kommission
        eintrag["netto"] += zeile.netto
        if zeile.netto_eur_ib is None:
            eintrag["eur_kurs_fehlt"] += 1
        else:
            eintrag["netto_eur_ib"] += zeile.netto_eur_ib
        eintrag["anzahl_legs"] += 1

    # Vertrag 9: Erträge gruppiert (Jahr aus datum, typ, waehrung), Betrag
    # vorzeichentreu summiert — nie in den Töpfen, nie in netto_eur_ib.
    ertraege_acc: dict[tuple[int, str, str], Decimal] = {}
    for satz in cash_transaktionen:
        schluessel = (satz["datum"].year, satz["typ"], satz["waehrung"])
        ertraege_acc[schluessel] = ertraege_acc.get(schluessel, _NULL) + satz["betrag"]

    return SteuerErgebnis(
        toepfe=tuple(
            TopfZeile(
                jahr=jahr,
                topf=topf,
                waehrung=waehrung,
                brutto=wert["brutto"],
                kommission=wert["kommission"],
                netto=wert["netto"],
                netto_eur_ib=wert["netto_eur_ib"],
                eur_kurs_fehlt=wert["eur_kurs_fehlt"],
                anzahl_legs=wert["anzahl_legs"],
                basis_ungeklaert=0,
            )
            for (jahr, topf, waehrung), wert in sorted(toepfe.items())
        ),
        # Vertrag 10: details/ungeklaert nach (handelszeit, close_exec_id),
        # ertraege nach (jahr, typ, waehrung), fehler nach (schluessel,
        # grund) — deterministisch, unveränderlich.
        details=tuple(sorted(details, key=lambda z: (z.handelszeit, z.close_exec_id))),
        ungeklaert=tuple(sorted(ungeklaert, key=lambda z: (z.handelszeit, z.close_exec_id))),
        ertraege=tuple(
            ErtragsZeile(jahr=jahr, typ=typ, waehrung=waehrung, betrag=betrag)
            for (jahr, typ, waehrung), betrag in sorted(ertraege_acc.items())
        ),
        fehler=tuple(sorted(dict.fromkeys(fehler), key=lambda f: (f.schluessel, f.grund))),
    )


def _geld(wert: Decimal | None) -> str:
    """Geldbeträge als Text: None leer (Vertrag 12), sonst auf Cent
    kaufmännisch gerundet — Decimal-Multiplikationen wie 397.00 × 0.93
    tragen vier Dezimalstellen, der Bericht zeigt zwei (Regel 5: gerundet
    wird nur dargestellt, nie gerechnet)."""
    if wert is None:
        return ""
    return str(wert.quantize(_GELD, rounding=ROUND_HALF_UP))


def _ja_nein(wert: bool | int) -> str:
    return "ja" if wert else "nein"


def als_csv(ergebnis: SteuerErgebnis, jahr: int | None = None) -> str:
    """CSV nach Vertrag 12: Eine flache Tabelle, Semikolon-getrennt, 21
    Spalten, Kopf deutsch; None als leeres Feld, Boolean als ja/nein,
    handelszeit als ISO. Abschnitte fest: topf, detail, ungeklaert, ertrag,
    fehler — je in der Sortierung der Ergebnistupel (Vertrag 10). ``jahr``
    filtert die Zeilen mit Jahresspalte; die Fehlerliste bleibt —
    Datenqualität kennt kein Jahr."""
    kopf = (
        "abschnitt;sicht;jahr;topf;waehrung;brutto;kommission;netto;netto_eur_ib;"
        "eur_kurs_fehlt;anzahl_legs;basis_ungeklaert;conid;symbol;close_exec_id;"
        "handelszeit;menge;typ;betrag;schluessel;grund"
    )
    zeilen = [kopf]
    for z in ergebnis.toepfe:
        if jahr is not None and z.jahr != jahr:
            continue
        # basis_ungeklaert ist am Topf immer 0 — die Spalte ist die der
        # Detailzeilen, deshalb als ja/nein (Vertrag 12).
        zeilen.append(
            ";".join(
                [
                    "topf",
                    "konto",
                    str(z.jahr),
                    z.topf,
                    z.waehrung,
                    _geld(z.brutto),
                    _geld(z.kommission),
                    _geld(z.netto),
                    _geld(z.netto_eur_ib),
                    str(z.eur_kurs_fehlt),
                    str(z.anzahl_legs),
                    _ja_nein(z.basis_ungeklaert),
                ]
                + [""] * 9
            )
        )
    for abschnitt, leg_zeilen in (
        ("detail", ergebnis.details),
        ("ungeklaert", ergebnis.ungeklaert),
    ):
        for z in leg_zeilen:
            if jahr is not None and z.jahr != jahr:
                continue
            zeilen.append(
                ";".join(
                    [
                        abschnitt,
                        "konto",
                        str(z.jahr),
                        z.topf,
                        z.waehrung,
                        _geld(z.brutto),
                        _geld(z.kommission),
                        _geld(z.netto),
                        _geld(z.netto_eur_ib),
                        "",
                        "",
                        "",
                        str(z.conid),
                        z.symbol,
                        z.close_exec_id,
                        z.handelszeit.isoformat(),
                        str(z.menge),
                    ]
                    + [""] * 4
                )
            )
    for z in ergebnis.ertraege:
        if jahr is not None and z.jahr != jahr:
            continue
        zeilen.append(
            ";".join(
                ["ertrag", "", str(z.jahr), "", z.waehrung]
                + [""] * 12
                + [z.typ, _geld(z.betrag), "", ""]
            )
        )
    for f in ergebnis.fehler:
        # Spalten 2–19 bleiben leer: 18 Felder zwischen abschnitt und
        # schluessel, mit grund endet die Zeile bei 21 Spalten.
        zeilen.append(";".join(["fehler"] + [""] * 18 + [f.schluessel, f.grund]))
    return "\n".join(zeilen) + "\n"
