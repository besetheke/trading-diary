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
    STANDARD_KONFIG,
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
TOPF_SO = "so_kandidat"
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
                },
            )

        for s in self.stroeme:
            b = block(s.jahr)
            if s.jahr_alternativ != s.jahr:
                b["betroffen"] += 1
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
            b["kap"] = _kap_vorschau(j, b)
        return dict(sorted(jahre.items()))


def _kap_vorschau(formularjahr: int, block: dict) -> dict:
    """Werte je KAP-Posten, **vorläufig und nicht verrechnet** (Zeilen je Formularjahr, Status wie in der Konfig)."""
    t = block["toepfe"]

    def feld(topf: str, name: str) -> Decimal:
        return t.get(topf, {}).get(name, _NULL)

    aktien_gewinne = feld(TOPF_AKTIEN, "gewinne")
    aktien_verluste = -feld(TOPF_AKTIEN, "verluste")
    ohne_aktien_verluste = -(feld(TOPF_STILLHALTER, "verluste") + feld(TOPF_TERMIN, "verluste"))
    saldo = sum(
        (feld(topf, "saldo") for topf in (TOPF_AKTIEN, TOPF_TERMIN, TOPF_STILLHALTER, TOPF_DIVIDENDEN, TOPF_ZINSEN)),
        _NULL,
    )
    werte = {
        "ausl_kapitalertraege_saldo": saldo,
        "aktiengewinne": aktien_gewinne,
        "verluste_ohne_aktien": ohne_aktien_verluste,
        "aktienverluste": aktien_verluste,
        "anrechenbare_quellensteuer": block["quellensteuer"]["vorlaeufig_anrechenbar"],
    }
    z = kap_zeilen(formularjahr)
    return {
        "formularjahr": formularjahr,
        "status": z["status"],
        "vorlaeufig": True,
        "posten": {name: {"zeile": z["zeilen"][name], "betrag": wert} for name, wert in werte.items()},
    }


# --------------------------------------------------------------------------------------------- Hilfen


def _datum(e: dict, feld: str) -> date:
    if feld == FELD_HANDEL:
        return e.get("trade_date") or e["handelszeit"].date()
    if feld == FELD_ABRECHNUNG:
        return e.get("settle_date") or e["handelszeit"].date()
    return e["handelszeit"].date()


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
        self.offen: dict[str, list] = {}  # art -> [text, anzahl, betrag]

    def luecke(self, schluessel: str, grund: str, text: str) -> None:
        self.luecken.setdefault((schluessel, grund), Datenluecke(schluessel, grund, text))

    def regel_offen(self, art: str, text: str, betrag: Decimal = _NULL) -> None:
        eintrag = self.offen.setdefault(art, [text, 0, _NULL])
        eintrag[1] += 1
        eintrag[2] += betrag

    def strom(self, *, vorgang, regel, topf, e, brutto, komm, optionskosten=_NULL, waehrung, symbol, leg_id=None):
        r = self.konfig.regeln[regel]
        datum = _datum(e, r["steuerdatum"])
        kursdatum = _datum(e, self.konfig.kursdatum_feld)
        gewuenscht = _datum(e, r["fx"])
        alternativ = _datum(e, self.konfig.alternative(regel))
        self.stroeme.append(
            Strom(
                vorgang=vorgang, regel=regel, topf=topf, jahr=datum.year, steuerdatum=datum,
                fx_datum=kursdatum, pruefstatus="ok" if kursdatum == gewuenscht else "kursdatum_abweichend",
                brutto_eur=brutto, kommission_eur=komm, optionskosten_eur=optionskosten,
                betrag_eur=brutto + komm + optionskosten, waehrung=waehrung, symbol=symbol,
                leg_id=leg_id, exec_id=e["exec_id"], jahr_alternativ=alternativ.year,
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
) -> SteuerZuflussErgebnis:
    ex = {e["exec_id"]: e for e in ausfuehrungen}
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
            continue
        if klasse in ("OPT", "FOP"):
            _option(s, leg, i, o, c, menge, mult, lieferungskosten)
        else:
            _ergebnisbein(s, leg, i, o, c, menge, mult, klasse, ab, ergebnis_legs)

    _optionskosten_verteilen(s, lieferungskosten, ergebnis_legs, inst)
    for r in ergebnis_legs:
        _ergebnis_buchen(s, r)
    _cash(s, cash_zeilen)

    warnungen = []
    if not anfangsbestaende:
        warnungen.append(
            "Anfangsbestand fehlt: steuerliche Anschaffungskosten und -daten der übernommenen Bestände sind nicht "
            "erfasst, das Jahresergebnis kann unvollständig sein. Verlustvorträge sind nicht berücksichtigt."
        )
    return SteuerZuflussErgebnis(
        stroeme=sorted(s.stroeme, key=lambda x: (x.steuerdatum, x.exec_id or "", x.vorgang)),
        datenluecken=sorted(s.luecken.values(), key=lambda d: (d.schluessel, d.grund)),
        regeln_offen=[RegelOffen(a, t, n, b) for a, (t, n, b) in sorted(s.offen.items())],
        warnungen=warnungen,
        methode={
            "verfahren": "Zufluss je Zahlungsstrom",
            "kursquelle": konfig.kursquelle,
            "kursdatum_feld": konfig.kursdatum_feld,
            "pruefstatus": konfig.pruefstatus,
            "datumsregeln": {k: dict(v) for k, v in konfig.regeln.items()},
        },
        konfig=konfig,
    )


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
    if ereignis in _LIEFERUNG_EREIGNISSE and art != "barausgleich":
        if ko is not None:
            kosten = _wert(o, fo, menge, mult) * ko - _komm_eur(s, o, fo, menge, ko)
            lieferungskosten.append({"underlying": i.get("underlying"), "zeit": c["handelszeit"],
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
    kc = _kurs(s, c)
    if kc is None:
        return
    komm = _komm_eur(s, c, fc, menge, kc)
    if ereignis in _LIEFERUNG_EREIGNISSE and art != "barausgleich":
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
            s.regel_offen("basis_ungeklaert", "Herkunft der Basis ungeklärt: ohne steuerlichen Anfangsbestand nicht gerechnet.")
            return
        offen_seite = ("anfang", a)
    else:
        offen_seite = ("exec", o)
    if c is None:
        return  # offen: nichts realisiert
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
    etf = klasse == "STK" and any(
        str((e or {}).get("unterkategorie") or "").upper() in _ETF_KATEGORIEN for e in (o, c)
    )
    ergebnis_legs.append({"leg": leg, "i": i, "o": o, "c": c, "brutto": brutto, "komm": komm,
                          "optionskosten": _NULL, "menge": menge, "klasse": klasse, "etf": etf})


def _optionskosten_verteilen(s: _Sammler, kosten_liste, ergebnis_legs, inst) -> None:
    for k in kosten_liste:
        call = k["right"] == "C"
        treffer = []
        for r in ergebnis_legs:
            if r["klasse"] != "STK" or (r["i"].get("underlying") != k["underlying"]):
                continue
            e = r["o"] if call else r["c"]
            if e is not None and e.get("ereignistyp") in _LIEFERUNG_EREIGNISSE and e["handelszeit"] == k["zeit"]:
                treffer.append(r)
        gesamt = sum((r["menge"] for r in treffer), _NULL)
        if not treffer or gesamt == _NULL:
            s.regel_offen("optionskosten_ohne_lieferung",
                          "Kosten einer ausgeübten gekauften Option ohne zugeordnete Lieferung: nicht gerechnet.", -k["kosten"])
            continue
        for r in treffer:
            r["optionskosten"] -= k["kosten"] * r["menge"] / gesamt


def _ergebnis_buchen(s: _Sammler, r: dict) -> None:
    leg, i, c = r["leg"], r["i"], r["c"]
    symbol = i.get("symbol") or ""
    gesamt = r["brutto"] + r["komm"] + r["optionskosten"]
    if r["etf"]:
        s.regel_offen("etf_investmentsteuer",
                      "ETF/ETN/ETP-Anteile: steuerliche Behandlung (Investmentsteuergesetz, Teilfreistellung) fehlt; nicht im Aktien-Topf.",
                      gesamt)
        return
    stk = r["klasse"] == "STK"
    regel = "wertpapierverkauf" if stk else "termingeschaeft"
    s.strom(vorgang="aktien_ergebnis" if stk else "termingeschaeft", regel=regel,
            topf=TOPF_AKTIEN if stk else TOPF_TERMIN, e=c, brutto=r["brutto"], komm=r["komm"],
            optionskosten=r["optionskosten"], waehrung=c["waehrung"], symbol=symbol, leg_id=leg.get("leg_id"))


# ------------------------------------------------------------------------------------------- Cash


_RE_STEUER = re.compile(r"\s+-\s+([A-Z]{2})\s+TAX$")
_RE_KLAMMER = re.compile(r"\s*\([^()]*\)\s*$")


def _basis_beschreibung(text: str, steuer: bool) -> str:
    text = (text or "").strip()
    return _RE_STEUER.sub("", text) if steuer else _RE_KLAMMER.sub("", text)


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
            _cash_strom(s, c, "ersatzzahlung" if ersatz else "dividende", "dividende",
                        TOPF_SO if ersatz else TOPF_DIVIDENDEN, eur)
            if ersatz:
                s.regel_offen("ersatzzahlung",
                              "Ersatzzahlungen (Wertpapierleihe/SYEP): Einordnung offen (SO-Kandidat, § 22 Nr. 3 EStG vorbehaltlich Bestätigung); "
                              "Freigrenze nicht abschließend geprüft; Ursache je Buchung ungeklärt.", eur)
            key = (c.get("symbol"), _basis_beschreibung(c.get("beschreibung"), False), tag, ersatz)
            g = brutto_gruppen.setdefault(key, {"brutto": _NULL, "land": c.get("land"), "ersatz": ersatz})
            g["brutto"] += eur
        elif typ == "Withholding Tax":
            steuer_zeilen.append({**c, "_eur": eur, "_tag": tag})
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
         "settle_date": c.get("settle_date") or c["datum"].date()}
    datum = _datum(e, r["steuerdatum"])
    alt = _datum(e, s.konfig.alternative(regel))
    s.stroeme.append(
        Strom(vorgang=vorgang, regel=regel, topf=topf, jahr=datum.year, steuerdatum=datum, fx_datum=c["datum"].date(),
              pruefstatus="ok", brutto_eur=eur, kommission_eur=_NULL, optionskosten_eur=_NULL, betrag_eur=eur,
              waehrung=c.get("waehrung") or "", symbol=c.get("symbol") or "", leg_id=None, exec_id=None,
              jahr_alternativ=alt.year)
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
        "keine Verlustverrechnung; Arbeitsstand, Prüfstatus: " + m["pruefstatus"],
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
