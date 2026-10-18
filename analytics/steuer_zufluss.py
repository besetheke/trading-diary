# ruff: noqa: E501
"""Steuerliche Aufbereitung nach Zufluss je Zahlungsstrom (AP-10c, Regeln R1–R16 aus AP-10b).

Rein: keine Datenbank, keine Uhr, kein Netz, alle Beträge ``Decimal``. Keine Steuerberatung und **keine
Verlustverrechnung** — die Funktion zerlegt Ausführungen und Cash-Buchungen in Zahlungsströme, ordnet jeden einem
Topf, einem Zuflussjahr und einem Kurs zu und weist Gewinne und Verluste getrennt aus. Arbeitsstand des
Steuerberaters (OF-92/OF-93), vor Abnahme zu bestätigen.

Grundsätze:

- **Jeder Strom steht für sich** (R14). Ein fehlender Kurs lässt nur den betroffenen Strom in die ``datenluecken``
  fallen, nie eine bekannte Eröffnungsprämie. ``analytics.kennzahlen.leg_seiten`` ist deshalb nicht die Grundlage
  (sie liefert bei fehlendem Kurs ``None`` für die ganze Leg-Liste).
- **Jede Eröffnungsprämie und jede Kommission genau einmal**: die Kommission einer Ausführung wird nach Leg-Menge
  auf die Legs verteilt, die sie nennen (wie ``leg_seiten``); offene Beine zählen.
- **Stillhalter** (verkauft eröffnet): Prämie im Zuflussjahr, Rückkauf als negative Einnahme im Zahlungsjahr,
  Verfall ohne Wirkung, Barausgleich als Termingeschäftsverlust, Lieferung ohne Zahlung (die Aktie kommt zum Strike).
- **Gekaufte Optionen:** Glattstellung/Verfall/Barausgleich = Termingeschäft; bei **Lieferung** gehen die Kosten in
  die Aktie (Long Call: Anschaffungskosten, Long Put: Veräußerungsergebnis).
- **Aktien:** Ergebnis je Bein, jede Seite zum Kurs ihrer Ausführung; Erwerbskosten erhöhen die Anschaffungskosten,
  Veräußerungskosten mindern den Erlös. ETF/ETN/ETP sind „ungeklärt (InvStG)“.
- **Cash:** Dividenden, Ersatzzahlungen (SO-Kandidat), Quellensteuer als vorläufige Obergrenze in drei Zuständen,
  Zinsen, nicht abziehbare Posten.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from analytics.steuer_konfig import (
    FELD_ABRECHNUNG,
    FELD_HANDEL,
    QUELLENHIERARCHIE,
    REGELN,
    STANDARD_KONFIG,
    VORSICHTIG,
    Konfig,
    kap_zeilen,
)

_NULL = Decimal("0")
_ETF_KATEGORIEN = {"ETF", "ETN", "ETP"}
_LIEFERUNG_EREIGNISSE = {"assignment", "exercise"}

TOPF_STILLHALTER = "stillhalter"
TOPF_TERMIN = "termingeschaefte"
TOPF_AKTIEN = "aktien"
TOPF_DIVIDENDEN = "dividenden"
TOPF_ZINSEN = "zinsen"
TOPF_NICHT_ABZIEHBAR = "nicht_abziehbar"
TOPF_SO = "so_kandidat"  # Ersatzzahlungen (PIL) abzüglich Stornos: Anlage SO, § 22 Nr. 3
TOPF_SO_SYEP = "so_syep"  # laufende SYEP-Vergütung: Anlage SO, getrennt ausgewiesen
TOPF_SO_BELASTUNG = "so_belastung"  # gezahlte Kompensation aus Leerverkauf: nicht saldiert, nicht angesetzt
TOPF_QUELLENSTEUER = "quellensteuer"

_QUELLENSTEUER_SCHLUESSEL = {
    "quellensteuer_anrechenbar": "vorlaeufig_anrechenbar",
    "quellensteuer_erstattungsfaehig": "erstattungsfaehig",
    "quellensteuer_ungeklaert": "ungeklaert",
    "quellensteuer_ersatzzahlung": "ersatzzahlung_zu_pruefen",
}


@dataclass(frozen=True)
class Anfangsbestand:
    """Steuerlicher Anfangsbestand eines Instruments (Eingabe, R16)."""

    conid: int
    menge: Decimal
    ak_je_stueck: Decimal
    datum: date
    waehrung: str
    kurs: Decimal


@dataclass(frozen=True)
class Strom:
    vorgang: str
    regel: str  # Schlüssel der Datumsregel (analytics.steuer_konfig)
    topf: str
    jahr: int
    steuerdatum: date
    fx_datum: date | None
    pruefstatus: str  # "ok" | "kursdatum_abweichend"
    brutto_eur: Decimal
    kommission_eur: Decimal
    optionskosten_eur: Decimal
    betrag_eur: Decimal
    waehrung: str
    symbol: str
    leg_id: int | None
    exec_id: str | None
    jahr_alternativ: int
    land: str | None = None  # Emittentenland (ISIN-Präfix) bei Aktien und Dividenden


@dataclass(frozen=True)
class Datenluecke:
    schluessel: str
    grund: str
    text: str


@dataclass(frozen=True)
class RegelOffen:
    art: str
    text: str
    anzahl: int
    betrag_eur: Decimal
    details: list = field(default_factory=list)  # Einzelfälle (Dicts) für die Listen an den Steuerberater


@dataclass
class SteuerZuflussErgebnis:
    stroeme: list[Strom]
    datenluecken: list[Datenluecke]
    regeln_offen: list[RegelOffen]
    warnungen: list[str]
    methode: dict
    konfig: Konfig = field(repr=False, default=STANDARD_KONFIG)

    def jahre(self) -> dict[int, dict]:
        """Je Zuflussjahr: Töpfe mit Gewinnen, Verlusten und Saldo (nicht verrechnet), Quellensteuer in vier
        Zuständen, Betroffenheit bei Regelwechsel und die KAP-Vorschau (vorläufig)."""
        jahre: dict[int, dict] = {}

        def block(j: int) -> dict:
            return jahre.setdefault(
                j,
                {
                    "toepfe": {},
                    "quellensteuer": {v: _NULL for v in _QUELLENSTEUER_SCHLUESSEL.values()},
                    "betroffen": 0,
                    "rueckkaeufe": _NULL,
                    "de_saldo": _NULL,
                    "kurs_abweichend": [0, _NULL],
                },
            )

        for s in self.stroeme:
            b = block(s.jahr)
            if s.jahr_alternativ != s.jahr:
                b["betroffen"] += 1
            if s.pruefstatus != "ok":
                b["kurs_abweichend"][0] += 1
                b["kurs_abweichend"][1] += abs(s.betrag_eur)
            if s.topf == TOPF_STILLHALTER and s.vorgang == "glattstellung" and s.betrag_eur < _NULL:
                b["rueckkaeufe"] += -s.betrag_eur
            if s.land == "DE" and s.topf in (TOPF_AKTIEN, TOPF_DIVIDENDEN):
                b["de_saldo"] += s.betrag_eur
            if s.topf == TOPF_QUELLENSTEUER:
                b["quellensteuer"][_QUELLENSTEUER_SCHLUESSEL[s.vorgang]] += s.betrag_eur
                continue
            t = b["toepfe"].setdefault(
                s.topf, {"gewinne": _NULL, "verluste": _NULL, "saldo": _NULL, "anzahl": 0}
            )
            if s.betrag_eur >= _NULL:
                t["gewinne"] += s.betrag_eur
            else:
                t["verluste"] += s.betrag_eur
            t["saldo"] += s.betrag_eur
            t["anzahl"] += 1
        for j, b in jahre.items():
            b["so"] = _so_block(b)
            b["kap"] = _kap_vorschau(j, b, self.konfig)
            b["deklarationsstatus"] = self._deklarationsstatus(j, b)
        return dict(sorted(jahre.items()))

    def _deklarationsstatus(self, jahr: int, b: dict) -> dict:
        """Je Jahr: ob die Zahlen mit einer Erläuterung als Grundlage der Steuererklärung taugen.

        ``gruende`` sind blockierend (Datenlücken, nicht zugeordnete Fälle wie ETF-Anteile oder Optionskosten ohne
        Lieferung); solange eine besteht, ist das Jahr „nicht deklarationsfähig“. Ohne blockierenden Grund gilt
        „deklarierbar mit Erläuterung“: Berechnung und kurze Erläuterung unter „Ergänzende Angaben zur
        Steuererklärung“ (§ 150 Abs. 7 AO) einreichen. ``hinweise`` sind nicht blockierend."""
        gruende, hinweise = [], []
        if self.datenluecken:
            gruende.append(f"{len(self.datenluecken)} Datenlücken (fehlender Kurs, Datum oder Ausführung).")
        for r in self.regeln_offen:
            if r.art in _BLOCKIEREND:
                gruende.append(f"{r.art}: {r.anzahl} Fälle ({_geld(r.betrag_eur)} EUR) nicht zugeordnet.")
            else:
                hinweise.append(f"{r.art}: {r.anzahl} Fälle ({_geld(r.betrag_eur)} EUR) in der Standardbehandlung.")
        vorsichtig = [r["id"] for r in REGELN if r["marker"] == VORSICHTIG]
        hinweise.append(
            f"{len(vorsichtig)} Regeln als vorsichtige Standardbehandlung markiert (Tabelle „Regeln und Grundlage“); "
            "mit Erläuterung unter „Ergänzende Angaben zur Steuererklärung“ einreichen (§ 150 Abs. 7 AO)."
        )
        if b["kap"]["status"] == VORSICHTIG:
            hinweise.append(f"KAP-Zeilen {b['kap']['formularjahr']}: Vordruck liegt nicht vor, Zeilen wie 2025 angenommen.")
        n, summe = b["kurs_abweichend"]
        if n:
            hinweise.append(
                f"{n} Zahlungsströme mit Kursdatum ≠ Regeldatum (Summe der Beträge {_geld(summe)} EUR; der IB-Kurs "
                "gehört zum Handelstag, die Regel verlangt teils den Abrechnungstag)."
            )
        hinweise.append("Verlustvorträge und Verlustverrechnung nicht berücksichtigt (Veranlagung).")
        status = "nicht_deklarationsfaehig" if gruende else "deklarierbar_mit_erlaeuterung"
        return {"status": status, "gruende": gruende, "hinweise": hinweise}

# Fälle, die ein Jahr blockieren: ohne diese Zuordnung stimmt eine Zahl der Vorschau nicht.
_BLOCKIEREND = frozenset({"etf_investmentsteuer", "basis_ungeklaert", "optionskosten_ohne_lieferung"})


def _so_block(b: dict) -> dict:
    """Anlage SO (§ 22 Nr. 3 EStG): empfangene Ersatzzahlungen (netto nach Stornos) und SYEP-Vergütung getrennt, die
    Summe gegen die Freigrenze von 256 € (für alle Einkünfte dieser Kategorie zusammen; ab 256 € überschritten),
    die nicht saldierte Belastung aus dem Leerverkauf und die Quellensteuer auf die Ersatzzahlungen."""
    t = b["toepfe"]

    def saldo(topf: str) -> Decimal:
        return t.get(topf, {}).get("saldo", _NULL)

    pil, syep = saldo(TOPF_SO), saldo(TOPF_SO_SYEP)
    return {
        "ersatzzahlungen_netto": pil,
        "syep_verguetung": syep,
        "summe": pil + syep,
        "freigrenze": Decimal("256"),
        "freigrenze_ueberschritten": (pil + syep) >= Decimal("256"),
        "belastung_nicht_saldiert": saldo(TOPF_SO_BELASTUNG),
        "pil_quellensteuer": b["quellensteuer"]["ersatzzahlung_zu_pruefen"],
    }


KAP_POSTEN = (
    "inl_kapitalertraege_saldo",
    "ausl_kapitalertraege_saldo",
    "aktiengewinne",
    "verluste_ohne_aktien",
    "aktienverluste",
    "anrechenbare_quellensteuer",
)


def kap_block(
    formularjahr: int,
    variante: str,
    name: str,
    beschreibung: str,
    teile: dict[str, Decimal],
    aktiengewinne: Decimal,
    verluste_ohne_aktien: Decimal,
    aktienverluste: Decimal,
    quellensteuer: Decimal,
    alternativen: list[dict] | None = None,
    hinweise: list[str] | None = None,
    inland: Decimal = _NULL,
) -> dict:
    """Eine KAP-Vorschau (**vorläufig, nicht verrechnet**). ``teile`` sind die Bestandteile des Saldos der
    ausländischen Kapitalerträge (Zeile 19); ``verluste_ohne_aktien`` und ``aktienverluste`` sind positive
    Beträge (die „davon“-Zeilen 22 und 23). Zeilen und Status kommen aus der Konfiguration je Formularjahr."""
    z = kap_zeilen(formularjahr)
    werte = {
        "inl_kapitalertraege_saldo": inland,
        "ausl_kapitalertraege_saldo": sum(teile.values(), _NULL) - inland,
        "aktiengewinne": aktiengewinne,
        "verluste_ohne_aktien": verluste_ohne_aktien,
        "aktienverluste": aktienverluste,
        "anrechenbare_quellensteuer": quellensteuer,
    }
    return {
        "variante": variante,
        "name": name,
        "beschreibung": beschreibung,
        "formularjahr": formularjahr,
        "status": z["status"],
        "vorlaeufig": True,
        "posten": {n: {"zeile": z["zeilen"][n], "betrag": werte[n]} for n in KAP_POSTEN},
        "zusammensetzung": dict(teile),
        "alternativen": alternativen or [],
        "hinweise": hinweise or [],
    }


def _kap_vorschau(formularjahr: int, block: dict, konfig: Konfig = STANDARD_KONFIG) -> dict:
    """Variante A: Zufluss je Zahlungsstrom, Stillhalterprämie separat (Arbeitsstand des Steuerberaters).

    Stillhalterprämien und Rückkäufe sind **Einnahmen und negative Einnahmen derselben Art** und werden zu einem
    Saldo zusammengefasst (Zeile 19). Nach BMF 14.05.2025, Rn. 25, ist die gezahlte Rückkaufprämie zugleich ein
    **enthaltener Verlust** (Zeile 22, Standard ``rueckkauf_als_verlust``); der Vergleich ohne Rückkäufe bleibt als
    Alternative sichtbar. Verluste ohne Aktien sind außerdem die Verluste der Termingeschäfte (gekaufte Optionen,
    Barausgleich, Futures)."""
    t = block["toepfe"]

    def feld(topf: str, name: str) -> Decimal:
        return t.get(topf, {}).get(name, _NULL)

    still = feld(TOPF_STILLHALTER, "saldo")
    termin_verluste = -feld(TOPF_TERMIN, "verluste")
    nur_saldo = termin_verluste + (-still if still < _NULL else _NULL)
    mit_rueckkaeufen = termin_verluste + block["rueckkaeufe"]
    if konfig.rueckkauf_als_verlust:
        verluste_ohne_aktien, andere, andere_text = (
            mit_rueckkaeufen, nur_saldo,
            "Vergleichsrechnung: Zeile 22 ohne die Rückkäufe (nur im Saldo der Stillhalter, nicht die BMF-Behandlung)")
    else:
        verluste_ohne_aktien, andere, andere_text = (
            nur_saldo, mit_rueckkaeufen,
            "Vergleichsrechnung: Zeile 22, wenn Rückkäufe nur im Saldo stehen (nicht die BMF-Behandlung)")
    hinweise = []
    if block["de_saldo"]:
        hinweise.append(
            f"Zeile 18: {_geld(block['de_saldo'])} EUR aus Aktien deutscher Emittenten (ISIN DE, ohne deutschen "
            "Steuerabzug, § 34d EStG); Zeile 20 enthält den Aktiengewinn weiterhin, Zeile 18 und 19 zusammen "
            "bleiben unverändert.")
    return kap_block(
        formularjahr, "zufluss", "Zufluss, Prämie separat",
        "Stillhalterprämie im Zuflussjahr, Rückkauf im Zahlungsjahr, Aktie zum Strike (BMF 14.05.2025); offene "
        "Positionen sind enthalten.",
        {
            "Aktien": feld(TOPF_AKTIEN, "saldo"),
            "Stillhalter (Prämien abzüglich Rückkäufe)": still,
            "Termingeschäfte (inkl. Barausgleich)": feld(TOPF_TERMIN, "saldo"),
            "Dividenden": feld(TOPF_DIVIDENDEN, "saldo"),
            "Habenzinsen": feld(TOPF_ZINSEN, "saldo"),
        },
        feld(TOPF_AKTIEN, "gewinne"), verluste_ohne_aktien, -feld(TOPF_AKTIEN, "verluste"),
        block["quellensteuer"]["vorlaeufig_anrechenbar"],
        inland=block["de_saldo"],
        alternativen=[{"posten": "verluste_ohne_aktien", "zeile": kap_zeilen(formularjahr)["zeilen"]["verluste_ohne_aktien"],
                       "name": andere_text, "betrag": andere}],
        hinweise=hinweise,
    )


# --------------------------------------------------------------------------------------------- Hilfen


def _datum(e: dict, feld: str) -> date:
    if feld == FELD_HANDEL:
        return e.get("trade_date") or e["handelszeit"].date()
    if feld == FELD_ABRECHNUNG:
        return e.get("settle_date") or e["handelszeit"].date()
    return e["handelszeit"].date()


def _basiswert(i: dict) -> str | None:
    """Basiswert eines Instruments: ``underlying``, bei Aktien (dort oft leer) das Symbol."""
    return i.get("underlying") or i.get("symbol")


def _faktor(leg: dict, schluessel: str) -> Decimal:
    f = leg.get("open_faktor" if schluessel == "open" else "close_faktor")
    return Decimal(1) if f is None else Decimal(str(f))


def _wert(e: dict, faktor: Decimal, menge: Decimal, mult: Decimal, preis: Decimal | None = None) -> Decimal:
    p = e["preis"] if preis is None else preis
    return (p if faktor == 1 else p / faktor) * menge * mult


def _komm(e: dict, faktor: Decimal, menge: Decimal) -> Decimal:
    if e.get("kommission") is None:
        return _NULL
    gesamt = abs(e["menge"]) * faktor
    return _NULL if gesamt == _NULL else e["kommission"] * (menge / gesamt)


def _komm_eur(s: "_Sammler", e: dict, faktor: Decimal, menge: Decimal, kurs: Decimal) -> Decimal:
    """Kommissionsanteil in EUR. Steht die Kommission in EUR, braucht sie keinen Kurs; in einer dritten Währung
    fehlt der Kurs — dann Datenlücke, und nur die Kommission (nicht der ganze Strom) fehlt."""
    k = _komm(e, faktor, menge)
    if k == _NULL:
        return _NULL
    w = e.get("kommission_waehrung") or e.get("waehrung")
    if w == e.get("waehrung"):
        return k * kurs
    if w == "EUR":
        return k
    s.luecke(e["exec_id"], "kommission_waehrung_abweichend",
             f"Kommission in {w}, Ausführung in {e.get('waehrung')}: kein Kurs für die Kommission")
    return _NULL


class _Sammler:
    def __init__(self, konfig: Konfig):
        self.konfig = konfig
        self.stroeme: list[Strom] = []
        self.luecken: dict[tuple[str, str], Datenluecke] = {}
        self.offen: dict[str, list] = {}  # art -> [text, anzahl, betrag, details]
        self.heuristisch = 0  # Optionskosten ohne assignment_links über Basiswert und Zeitstempel zugeordnet
        self.ohne_kategorie: set[str] = set()  # Aktien ohne IB-Kategorie (ETF oder Aktie nicht unterscheidbar)

    def luecke(self, schluessel: str, grund: str, text: str) -> None:
        self.luecken.setdefault((schluessel, grund), Datenluecke(schluessel, grund, text))

    def regel_offen(self, art: str, text: str, betrag: Decimal = _NULL, detail: dict | None = None) -> None:
        eintrag = self.offen.setdefault(art, [text, 0, _NULL, []])
        eintrag[1] += 1
        eintrag[2] += betrag
        if detail is not None:
            eintrag[3].append(detail)

    def strom(self, *, vorgang, regel, topf, e, brutto, komm, optionskosten=_NULL, waehrung, symbol, leg_id=None,
              land=None):
        r = self.konfig.regeln[regel]
        datum = _datum(e, r["steuerdatum"])
        kursdatum = _datum(e, self.konfig.kursdatum_feld)
        gewuenscht = _datum(e, r["fx"])
        alternativ = _datum(e, self.konfig.alternative(regel))
        status = "ok" if kursdatum == gewuenscht else "kursdatum_abweichend"
        if FELD_ABRECHNUNG in (r["steuerdatum"], r["fx"], self.konfig.alternative(regel)) and not e.get("settle_date"):
            # Kein stilles Ersetzen: ohne Abrechnungsdatum steht der Handelstag, und die Lücke wird gemeldet.
            self.luecke(str(e["exec_id"]), "abrechnungsdatum_fehlt",
                        f"Ausführung {e['exec_id']}: kein Abrechnungsdatum, Handelstag ersatzweise verwendet")
            status = "abrechnungsdatum_fehlt"
        self.stroeme.append(
            Strom(
                vorgang=vorgang, regel=regel, topf=topf, jahr=datum.year, steuerdatum=datum,
                fx_datum=kursdatum, pruefstatus=status,
                brutto_eur=brutto, kommission_eur=komm, optionskosten_eur=optionskosten,
                betrag_eur=brutto + komm + optionskosten, waehrung=waehrung, symbol=symbol,
                leg_id=leg_id, exec_id=e["exec_id"], jahr_alternativ=alternativ.year, land=land,
            )
        )


# ------------------------------------------------------------------------------------------- Legs


def steuer_zufluss(
    legs,
    ausfuehrungen,
    instrumente,
    cash_zeilen=(),
    *,
    konfig: Konfig = STANDARD_KONFIG,
    anfangsbestaende=(),
    assignment_links=(),
) -> SteuerZuflussErgebnis:
    ex = {e["exec_id"]: e for e in ausfuehrungen}
    link_je_option: dict[str, set[str]] = {}
    for opt_id, aktien_id in assignment_links:
        link_je_option.setdefault(opt_id, set()).add(aktien_id)
    inst = {i["conid"]: i for i in instrumente}
    ab = {a.conid: a for a in anfangsbestaende}
    s = _Sammler(konfig)
    ergebnis_legs: list[dict] = []  # Aktien/Termingeschäfte/Futures: erst nach der Verteilung der Optionskosten buchen
    lieferungskosten: list[dict] = []

    for leg in legs:
        i = inst.get(leg["conid"])
        if i is None:
            s.luecke(str(leg.get("leg_id")), "instrument_fehlt", f"Instrument {leg['conid']} fehlt")
            continue
        klasse = i["asset_class"]
        if klasse == "CASH":
            s.regel_offen("cash_ausgeschlossen", "Geschäfte in Devisen (CASH) sind ausgeschlossen (USD-Konto, AP-10d).")
            continue
        menge = abs(Decimal(str(leg["menge"])))
        mult = i.get("multiplikator") or Decimal(1)
        o, c = ex.get(leg["open_exec_id"]), ex.get(leg["close_exec_id"]) if leg["close_exec_id"] else None
        if leg["open_exec_id"] and o is None:
            s.luecke(leg["open_exec_id"], "ausfuehrung_fehlt", "Eröffnungsausführung fehlt")
            continue
        if leg["close_exec_id"] and c is None:
            s.luecke(leg["close_exec_id"], "ausfuehrung_fehlt", "Schließungsausführung fehlt")
            if klasse in ("OPT", "FOP") and o is not None and o["side"] == "SELL":
                _option(s, leg, i, o, None, menge, mult, lieferungskosten)  # die zugeflossene Prämie bleibt
            continue
        if klasse in ("OPT", "FOP"):
            _option(s, leg, i, o, c, menge, mult, lieferungskosten)
        else:
            _ergebnisbein(s, leg, i, o, c, menge, mult, klasse, ab, ergebnis_legs)

    _optionskosten_verteilen(s, lieferungskosten, ergebnis_legs, link_je_option)
    for r in ergebnis_legs:
        _ergebnis_buchen(s, r)
    _cash(s, cash_zeilen)

    warnungen = []
    if not anfangsbestaende:
        warnungen.append(
            "Anfangsbestand: Es wird angenommen, dass das Depot seit dem 01.04.2022 besteht und keine Vorbestände "
            "hatte (Bestätigung des Nutzers); Verlustvorträge sind nicht berücksichtigt."
        )
    if s.heuristisch:
        warnungen.append(
            f"{s.heuristisch} ausgeübte gekaufte Optionen ohne assignment_links: die Kosten wurden über Basiswert und "
            "Zeitstempel der Lieferung zugeordnet (heuristisch, bei mehreren Ausübungen zum selben Zeitpunkt prüfen)."
        )
    if s.ohne_kategorie:
        warnungen.append(
            f"{len(s.ohne_kategorie)} Aktien ohne IB-Kategorie (ETF oder Aktie nicht unterscheidbar) wurden als Aktie "
            "behandelt: " + ", ".join(sorted(s.ohne_kategorie)[:10]) + (" …" if len(s.ohne_kategorie) > 10 else "")
        )
    return SteuerZuflussErgebnis(
        stroeme=sorted(s.stroeme, key=lambda x: (x.steuerdatum, x.exec_id or "", x.vorgang)),
        datenluecken=sorted(s.luecken.values(), key=lambda d: (d.schluessel, d.grund)),
        regeln_offen=[RegelOffen(a, t, n, b, d) for a, (t, n, b, d) in sorted(s.offen.items())],
        warnungen=warnungen,
        methode={
            "verfahren": "Zufluss je Zahlungsstrom",
            "kursquelle": konfig.kursquelle,
            "kursdatum_feld": konfig.kursdatum_feld,
            "pruefstatus": konfig.pruefstatus,
            "quellenhierarchie": list(QUELLENHIERARCHIE),
            "regeln": [dict(r) for r in REGELN],
            "datumsregeln": {k: dict(v) for k, v in konfig.regeln.items()},
        },
        konfig=konfig,
    )


def _art(s: _Sammler, i: dict, c: dict) -> str | None:
    """Abwicklungsart einer ausgeübten oder zugeteilten Option: ``lieferung`` oder ``barausgleich``; unbekannt
    ist eine Datenlücke (keine stille Annahme „Lieferung“)."""
    art = i.get("abwicklungsart")
    if art not in ("lieferung", "barausgleich"):
        s.luecke(c["exec_id"], "abwicklungsart_unbekannt",
                 f"Instrument {i.get('symbol')}: Abwicklungsart {art!r} unbekannt — Zuteilung/Ausübung nicht bewertet")
        return None
    return art


def _kurs(s: _Sammler, e: dict) -> Decimal | None:
    if e.get("buchungskurs") is None:
        s.luecke(e["exec_id"], "kurs_fehlt", f"Ausführung {e['exec_id']}: kein Buchungskurs")
        return None
    return e["buchungskurs"]


def _option(s: _Sammler, leg, i, o, c, menge, mult, lieferungskosten) -> None:
    fo, fc = _faktor(leg, "open"), _faktor(leg, "close")
    symbol = i.get("symbol") or ""
    w = o["waehrung"]
    if o["side"] == "SELL":  # Stillhalter
        ko = _kurs(s, o)
        if ko is not None:
            s.strom(vorgang="stillhalterpraemie", regel="stillhalterpraemie", topf=TOPF_STILLHALTER, e=o,
                    brutto=_wert(o, fo, menge, mult) * ko, komm=_komm_eur(s, o, fo, menge, ko), waehrung=w,
                    symbol=symbol, leg_id=leg.get("leg_id"))
        if c is None:
            return
        _stillhalter_schluss(s, leg, i, c, menge, mult, fc, symbol)
        return
    # gekaufte Option: Ergebnis erst bei Schließung
    if c is None:
        return
    ko = _kurs(s, o)
    ereignis = c["ereignistyp"]
    art = i.get("abwicklungsart")
    if ereignis in _LIEFERUNG_EREIGNISSE:
        art = _art(s, i, c)
        if art is None:
            return
    if ereignis in _LIEFERUNG_EREIGNISSE and art == "lieferung":
        if ko is not None:
            kosten = _wert(o, fo, menge, mult) * ko - _komm_eur(s, o, fo, menge, ko)
            lieferungskosten.append({"underlying": _basiswert(i), "zeit": c["handelszeit"], "exec_id": c["exec_id"],
                                     "right": i.get("right"), "kosten": kosten, "symbol": symbol})
        return
    kc = None
    if ereignis in ("expiry",):
        brutto_c = komm_c = _NULL
    else:
        kc = _kurs(s, c)
        if kc is None:
            return
        preis = _barausgleich_preis(s, c, ereignis, art)
        if preis is None:
            return
        brutto_c = _wert(c, fc, menge, mult, preis) * kc * (1 if c["side"] == "SELL" else -1)
        komm_c = _komm_eur(s, c, fc, menge, kc)
    if ko is None:
        return
    brutto = brutto_c - _wert(o, fo, menge, mult) * ko
    komm = komm_c + _komm_eur(s, o, fo, menge, ko)
    s.strom(vorgang="termingeschaeft", regel="termingeschaeft", topf=TOPF_TERMIN, e=c, brutto=brutto, komm=komm,
            waehrung=w, symbol=symbol, leg_id=leg.get("leg_id"))


def _barausgleich_preis(s: _Sammler, c: dict, ereignis: str, art: str | None) -> Decimal | None:
    if ereignis in _LIEFERUNG_EREIGNISSE and art == "barausgleich":
        if c.get("schlusskurs") is None:
            s.luecke(c["exec_id"], "schlusskurs_fehlt", f"Ausführung {c['exec_id']}: Barausgleich ohne Schlusskurs")
            return None
        return c["schlusskurs"]
    return c["preis"]


def _stillhalter_schluss(s: _Sammler, leg, i, c, menge, mult, fc, symbol) -> None:
    ereignis = c["ereignistyp"]
    art = i.get("abwicklungsart")
    if ereignis == "expiry":
        return  # Prämie ist längst zugeflossen
    if ereignis in _LIEFERUNG_EREIGNISSE:
        art = _art(s, i, c)
        if art is None:
            return
    kc = _kurs(s, c)
    if kc is None:
        return
    komm = _komm_eur(s, c, fc, menge, kc)
    if ereignis in _LIEFERUNG_EREIGNISSE and art == "lieferung":
        if komm != _NULL:  # Lieferung: keine Zahlung, nur eine eventuelle Kommission
            s.strom(vorgang="glattstellung", regel="glattstellung", topf=TOPF_STILLHALTER, e=c, brutto=_NULL,
                    komm=komm, waehrung=c["waehrung"], symbol=symbol, leg_id=leg.get("leg_id"))
        return
    preis = _barausgleich_preis(s, c, ereignis, art)
    if preis is None:
        return
    brutto = -_wert(c, fc, menge, mult, preis) * kc
    if ereignis in _LIEFERUNG_EREIGNISSE:  # Barausgleich: Termingeschäftsverlust
        s.strom(vorgang="barausgleich", regel="barausgleich", topf=TOPF_TERMIN, e=c, brutto=brutto, komm=komm,
                waehrung=c["waehrung"], symbol=symbol, leg_id=leg.get("leg_id"))
    else:  # Rückkauf: negative Einnahme
        s.strom(vorgang="glattstellung", regel="glattstellung", topf=TOPF_STILLHALTER, e=c, brutto=brutto,
                komm=komm, waehrung=c["waehrung"], symbol=symbol, leg_id=leg.get("leg_id"))


def _ergebnisbein(s: _Sammler, leg, i, o, c, menge, mult, klasse, ab, ergebnis_legs) -> None:
    if leg.get("basis_ungeklaert"):
        a = ab.get(leg["conid"])
        if a is None:
            s.regel_offen("basis_ungeklaert", "Herkunft der Basis ungeklärt: ohne steuerlichen Anfangsbestand nicht gerechnet.",
                          detail={"leg_id": leg.get("leg_id"), "symbol": i.get("symbol")})
            return
        offen_seite = ("anfang", a)
    else:
        offen_seite = ("exec", o)
    if c is None:
        # Offen: nichts realisiert. Entsteht das Bein durch Lieferung (z. B. Leerverkauf durch Ausübung eines gekauften
        # Puts), nimmt es die Optionskosten trotzdem auf, damit sie nicht als „ohne Lieferung“ gelten.
        if o is not None and o.get("ereignistyp") in _LIEFERUNG_EREIGNISSE:
            ergebnis_legs.append({"leg": leg, "i": i, "o": o, "c": None, "brutto": _NULL, "komm": _NULL,
                                  "optionskosten": _NULL, "menge": menge, "klasse": klasse, "etf": False, "offen": True})
        return
    brutto = komm = _NULL
    kurse_ok = True
    for art, e in (offen_seite, ("exec", c)):
        if art == "anfang":
            brutto += -(e.ak_je_stueck * menge * mult) * e.kurs
            continue
        k = _kurs(s, e)
        if k is None:
            kurse_ok = False
            continue
        f = _faktor(leg, "open" if e is o else "close")
        vorzeichen = 1 if e["side"] == "SELL" else -1
        brutto += vorzeichen * _wert(e, f, menge, mult) * k
        komm += _komm_eur(s, e, f, menge, k)
    if not kurse_ok:
        return
    kategorien = {str(x).upper() for x in (i.get("unterkategorie"), (o or {}).get("unterkategorie"),
                                           (c or {}).get("unterkategorie")) if x}
    etf = klasse == "STK" and bool(kategorien & _ETF_KATEGORIEN)
    if klasse == "STK" and not kategorien:
        s.ohne_kategorie.add(i.get("symbol") or str(leg["conid"]))
    ergebnis_legs.append({"leg": leg, "i": i, "o": o, "c": c, "brutto": brutto, "komm": komm,
                          "optionskosten": _NULL, "menge": menge, "klasse": klasse, "etf": etf})


def _optionskosten_verteilen(s: _Sammler, kosten_liste, ergebnis_legs, link_je_option) -> None:
    """Verteilt die Kosten ausgeübter gekaufter Optionen auf die gelieferten Aktienbeine. Zuerst über die
    ``assignment_links`` (Option → Aktienausführung); ohne Verknüpfung über Basiswert und Zeitstempel (heuristisch,
    wird als Warnung gezählt)."""
    for k in kosten_liste:
        stock_ids = link_je_option.get(k.get("exec_id"))
        treffer = []
        if stock_ids:
            treffer = [r for r in ergebnis_legs if r["klasse"] == "STK"
                       and any(e is not None and e["exec_id"] in stock_ids for e in (r["o"], r["c"]))]
        if not treffer:
            for r in ergebnis_legs:
                if r["klasse"] != "STK" or _basiswert(r["i"]) != k["underlying"]:
                    continue
                if any(
                    e is not None and e.get("ereignistyp") in _LIEFERUNG_EREIGNISSE and e["handelszeit"] == k["zeit"]
                    for e in (r["o"], r["c"])
                ):
                    treffer.append(r)
            if treffer:
                s.heuristisch += 1
        gesamt = sum((r["menge"] for r in treffer), _NULL)
        if not treffer or gesamt == _NULL:
            s.regel_offen("optionskosten_ohne_lieferung",
                          "Kosten einer ausgeübten gekauften Option ohne zugeordnete Lieferung: nicht gerechnet.", -k["kosten"],
                          detail={"symbol": k["symbol"], "zeit": k["zeit"].isoformat(), "kosten_eur": k["kosten"]})
            continue
        for r in treffer:
            r["optionskosten"] -= k["kosten"] * r["menge"] / gesamt


def _ergebnis_buchen(s: _Sammler, r: dict) -> None:
    if r.get("offen"):
        return  # noch nicht realisiert
    leg, i, c = r["leg"], r["i"], r["c"]
    symbol = i.get("symbol") or ""
    gesamt = r["brutto"] + r["komm"] + r["optionskosten"]
    if r["etf"]:
        s.regel_offen("etf_investmentsteuer",
                      "ETF/ETN/ETP-Anteile: steuerliche Behandlung (Investmentsteuergesetz, Teilfreistellung) fehlt; nicht im Aktien-Topf.",
                      gesamt,
                      detail={"leg_id": leg.get("leg_id"), "symbol": symbol, "exec_id": c["exec_id"],
                              "eroeffnet": r["o"]["handelszeit"].date().isoformat() if r["o"] else "",
                              "geschlossen": c["handelszeit"].date().isoformat(), "ergebnis_eur": gesamt})
        return
    stk = r["klasse"] == "STK"
    regel = "wertpapierverkauf" if stk else "termingeschaeft"
    s.strom(vorgang="aktien_ergebnis" if stk else "termingeschaeft", regel=regel,
            topf=TOPF_AKTIEN if stk else TOPF_TERMIN, e=c, brutto=r["brutto"], komm=r["komm"],
            optionskosten=r["optionskosten"], waehrung=c["waehrung"], symbol=symbol, leg_id=leg.get("leg_id"),
            land=i.get("land") if stk else None)


# ------------------------------------------------------------------------------------------- Cash


_RE_STEUER = re.compile(r"\s+-\s+([A-Z]{2})\s+TAX$")
_RE_KLAMMER = re.compile(r"\s*\([^()]*\)\s*$")


def _basis_beschreibung(text: str, steuer: bool) -> str:
    text = (text or "").strip()
    text = _RE_STEUER.sub("", text) if steuer else _RE_KLAMMER.sub("", text)
    return text.replace(" - REVERSAL", "")  # Storno und Original gehören zur selben Zahlung


def _cash(s: _Sammler, cash_zeilen) -> None:
    brutto_gruppen: dict[tuple, dict] = {}
    steuer_zeilen: list[dict] = []
    for c in cash_zeilen:
        typ = c["typ"]
        tag = (c.get("settle_date") or c["datum"].date())
        schluessel = f"cash:{c.get('symbol') or ''}:{tag}"
        if typ in ("Deposits/Withdrawals",):
            continue
        if c.get("kurs") is None:
            s.luecke(schluessel, "kurs_fehlt", f"Cash-Buchung {typ} ohne Kurs")
            continue
        eur = c["betrag"] * c["kurs"]
        if typ in ("Dividends", "Payment In Lieu Of Dividends"):
            ersatz = typ.startswith("Payment")
            vorgang, topf = ("dividende", TOPF_DIVIDENDEN)
            if ersatz:
                if "REVERSAL" in (c.get("beschreibung") or "").upper():
                    vorgang, topf = "ersatzzahlung_storno", TOPF_SO  # mindert die empfangenen Ersatzzahlungen
                elif eur < _NULL:
                    vorgang, topf = "ersatzzahlung_belastung", TOPF_SO_BELASTUNG  # Kompensation aus Leerverkauf
                else:
                    vorgang, topf = "ersatzzahlung", TOPF_SO
            _cash_strom(s, c, vorgang, "dividende", topf, eur)
            if ersatz:
                s.regel_offen("ersatzzahlung",
                              "Ersatzzahlungen (PIL) und SYEP-Vergütung: Standardbehandlung Anlage SO, § 22 Nr. 3 EStG "
                              "(vorsichtige Standardbehandlung), getrennt ausgewiesen; Freigrenze 256 € für alle "
                              "Einkünfte dieser Kategorie zusammen; Nachweis der Leihe über das Activity Statement "
                              "(Securities Lent Activity, Fee Details).", eur,
                              detail={"datum": tag.isoformat(), "symbol": c.get("symbol") or "", "betrag_eur": eur,
                                      "waehrung": c.get("waehrung") or "", "beschreibung": c.get("beschreibung") or ""})
            key = (c.get("symbol"), _basis_beschreibung(c.get("beschreibung"), False), tag, ersatz)
            g = brutto_gruppen.setdefault(key, {"brutto": _NULL, "land": c.get("land"), "ersatz": ersatz})
            g["brutto"] += eur
        elif typ == "Withholding Tax":
            steuer_zeilen.append({**c, "_eur": eur, "_tag": tag})
        elif typ == "Broker Interest Received" and "(SYEP)" in (c.get("beschreibung") or "").upper():
            _cash_strom(s, c, "syep_verguetung", "zins", TOPF_SO_SYEP, eur)  # laufende Vergütung der Wertpapierleihe
        elif typ == "Broker Interest Received":
            _cash_strom(s, c, "habenzinsen", "zins", TOPF_ZINSEN, eur)
        elif typ == "Broker Interest Paid":
            _cash_strom(s, c, "sollzinsen", "zins", TOPF_NICHT_ABZIEHBAR, eur)
        elif typ == "Other Fees":
            _cash_strom(s, c, "gebuehr", "zins", TOPF_NICHT_ABZIEHBAR, eur)
        else:
            s.regel_offen("cash_sonstige", f"Cash-Buchungen vom Typ „{typ}“ sind nicht zugeordnet.", eur)

    steuer_je_gruppe: dict[tuple, dict] = {}
    for z in steuer_zeilen:
        beschr = z.get("beschreibung") or ""
        if "CREDIT INT" in beschr.upper():  # Zinsquellensteuer (Irland): nicht anrechenbar
            _cash_strom(s, z, "zinsquellensteuer_nicht_anrechenbar", "zins", TOPF_NICHT_ABZIEHBAR, z["_eur"])
            continue
        if "PAYMENT IN LIEU" in beschr.upper():  # Steuer auf Ersatzzahlungen (auch Erstattungen): nie in Zeile 41
            _cash_strom(s, z, "quellensteuer_ersatzzahlung", "dividende", TOPF_QUELLENSTEUER, -z["_eur"])
            continue
        basis = _basis_beschreibung(beschr, True)
        passend = [k for k in brutto_gruppen if k[0] == z.get("symbol") and k[1] == basis and k[2] == z["_tag"]]
        if not passend:
            passend = [k for k in brutto_gruppen if k[0] == z.get("symbol") and k[1] == basis]
        if len(passend) != 1:
            _cash_strom(s, z, "quellensteuer_ungeklaert", "dividende", TOPF_QUELLENSTEUER, -z["_eur"])
            continue
        treffer = _RE_STEUER.search(beschr.strip())
        g = steuer_je_gruppe.setdefault(passend[0], {"einbehalten": _NULL, "land": None, "zeile": z})
        g["einbehalten"] += -z["_eur"]
        g["land"] = (treffer.group(1) if treffer else None) or z.get("land")

    for key, g in steuer_je_gruppe.items():
        brutto = brutto_gruppen[key]
        z = g["zeile"]
        if brutto["ersatz"]:
            _cash_strom(s, z, "quellensteuer_ersatzzahlung", "dividende", TOPF_QUELLENSTEUER, g["einbehalten"])
            continue
        satz = s.konfig.laender_saetze.get(g["land"] or brutto["land"])
        if satz is None:
            _cash_strom(s, z, "quellensteuer_ungeklaert", "dividende", TOPF_QUELLENSTEUER, g["einbehalten"])
            continue
        anrechenbar = min(g["einbehalten"], satz * brutto["brutto"])
        _cash_strom(s, z, "quellensteuer_anrechenbar", "dividende", TOPF_QUELLENSTEUER, anrechenbar)
        if g["einbehalten"] > anrechenbar:
            _cash_strom(s, z, "quellensteuer_erstattungsfaehig", "dividende", TOPF_QUELLENSTEUER,
                        g["einbehalten"] - anrechenbar)


def _cash_strom(s: _Sammler, c: dict, vorgang: str, regel: str, topf: str, eur: Decimal) -> None:
    r = s.konfig.regeln[regel]
    e = {"exec_id": None, "handelszeit": c["datum"], "trade_date": c["datum"].date(),
         "settle_date": c.get("settle_date")}
    datum = _datum(e, r["steuerdatum"])
    alt = _datum(e, s.konfig.alternative(regel))
    status = "ok" if _datum(e, r["fx"]) == c["datum"].date() else "kursdatum_abweichend"
    if not c.get("settle_date") and FELD_ABRECHNUNG in (r["steuerdatum"], r["fx"], s.konfig.alternative(regel)):
        s.luecke(f"cash:{c.get('symbol') or ''}:{c['datum'].date()}", "abrechnungsdatum_fehlt",
                 f"Cash-Buchung {c['typ']}: kein Abrechnungsdatum, Buchungsdatum ersatzweise verwendet")
        status = "abrechnungsdatum_fehlt"
    s.stroeme.append(
        Strom(vorgang=vorgang, regel=regel, topf=topf, jahr=datum.year, steuerdatum=datum, fx_datum=c["datum"].date(),
              pruefstatus=status, brutto_eur=eur, kommission_eur=_NULL, optionskosten_eur=_NULL, betrag_eur=eur,
              waehrung=c.get("waehrung") or "", symbol=c.get("symbol") or "", leg_id=None, exec_id=None,
              jahr_alternativ=alt.year, land=c.get("land"))
    )


# --------------------------------------------------------------------------------------------- CSV


def _geld(wert: Decimal | None) -> str:
    """Geldbetrag auf Cent kaufmännisch gerundet — gerundet wird nur dargestellt, nie gerechnet (Regel 5)."""
    return "" if wert is None else str(wert.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def als_csv(ergebnis: SteuerZuflussErgebnis, jahr: int | None = None) -> str:
    """CSV der Aufbereitung nach Zufluss: Kopfzeilen mit Methode und Hinweis, dann Abschnitte ``topf``,
    ``quellensteuer``, ``strom``, ``datenluecke``, ``regel_offen``, ``warnung`` (Semikolon; ``jahr`` filtert die
    Zeilen mit Jahresspalte, Datenlücken, offene Regeln und Warnungen bleiben vollständig)."""
    m = ergebnis.methode
    zeilen = [
        "# Steuer nach Zufluss je Zahlungsstrom — Aufbereitung für den Steuerberater, keine Steuerberatung, "
        "keine Verlustverrechnung; Marker je Regel (amtlich_belegt, aus_daten_belegt, vorsichtige_standardbehandlung)",
        f"# Kursquelle: {m['kursquelle']} (Kursdatum: {m['kursdatum_feld']}); Datumsregeln: "
        + ", ".join(f"{k}={v['steuerdatum']}/{v['fx']}" for k, v in m["datumsregeln"].items()),
        "abschnitt;jahr;topf;gewinne;verluste;saldo;anzahl;zustand;betrag;steuerdatum;fx_datum;pruefstatus;"
        "vorgang;symbol;brutto_eur;kommission_eur;optionskosten_eur;betrag_eur;exec_id;leg_id;text",
    ]
    for j, b in ergebnis.jahre().items():
        if jahr is not None and j != jahr:
            continue
        for topf, t in sorted(b["toepfe"].items()):
            zeilen.append(
                ";".join(
                    ["topf", str(j), topf, _geld(t["gewinne"]), _geld(t["verluste"]), _geld(t["saldo"]),
                     str(t["anzahl"])] + [""] * 14
                )
            )
        for zustand, betrag in b["quellensteuer"].items():
            zeilen.append(";".join(["quellensteuer", str(j)] + [""] * 5 + [zustand, _geld(betrag)] + [""] * 12))
    for st in ergebnis.stroeme:
        if jahr is not None and st.jahr != jahr:
            continue
        zeilen.append(
            ";".join(
                [
                    "strom", str(st.jahr), st.topf, "", "", "", "", "", "", st.steuerdatum.isoformat(),
                    st.fx_datum.isoformat() if st.fx_datum else "", st.pruefstatus, st.vorgang, st.symbol,
                    _geld(st.brutto_eur), _geld(st.kommission_eur), _geld(st.optionskosten_eur),
                    _geld(st.betrag_eur), st.exec_id or "", "" if st.leg_id is None else str(st.leg_id), "",
                ]
            )
        )
    for d in ergebnis.datenluecken:
        zeilen.append(";".join(["datenluecke", "", d.grund] + [""] * 15 + [d.schluessel, "", d.text]))
    for r in ergebnis.regeln_offen:
        zeilen.append(
            ";".join(["regel_offen", "", r.art, "", "", "", str(r.anzahl), "", _geld(r.betrag_eur)] + [""] * 11 + [r.text])
        )
    for w in ergebnis.warnungen:
        zeilen.append(";".join(["warnung"] + [""] * 19 + [w]))
    return "\n".join(zeilen) + "\n"
