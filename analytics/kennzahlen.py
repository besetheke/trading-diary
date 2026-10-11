"""Kennzahlen je Ebene und EUR-Fundament (AP-06, Tranche I „Analytik I").

Vertrag ist ``auftraege/AP-06v.md``; die Abnahmetests in
``tests/test_kennzahlen.py`` sind unveränderlich — jede Abweichung dieser
Implementierung von den Tests ist ein Fehler hier, nicht dort. Alle Beträge
sind ``Decimal``: kein float, keine stillen Rundungen (CLAUDE.md, Regel 5).

Aufteilung nach P2/P3:

- ``kennzahlen_auswertung`` und ``fx_tageskurse`` sind rein — keine Uhr,
  kein Netzwerk, kein Zufall; gleiche Eingabe liefert bitgleiche Ausgabe.
- ``kennzahlen_bericht`` ist die einzige Stelle mit Schreibzugriffen: Sie
  schreibt ``fx_rates`` und ``metrics_by_chain`` vollständig neu (Regel 11)
  und lässt ``chains.netto_pnl_eur`` leer (E2).

Freigegebene Entscheidungen, hier wirksam: E1 — die Auswertungssicht ist
Parameter, jede Ergebniszeile trägt ihre Sicht, niemals gemischt. E2 — die
wirtschaftliche EUR-Sicht ist maßgeblich, gespeichert wird in
``metrics_by_chain``. E3 — ``fx_rates`` ist Materialisierung mit
``quelle = 'abgeleitet_letzte_ausfuehrung'``, keine Rechenquelle. E4 — ein
fehlender buchungskurs ist ein gezählter Mangel, nie ein stiller Kurs 1.
E5 — netto exakt 0,00 zählt in den Nenner der Trefferquote, nicht in den
Zähler. E6 — die Qualitätsstufe ist das Minimum über die beteiligten
Ausführungen, gebildet über eine explizite Rangfolge im Code.
"""

import pathlib
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, insert, select

from journal.db import create_db_engine
from journal.schema import (
    chain_links,
    chains,
    executions,
    fx_rates,
    instruments,
    legs,
    metrics_by_chain,
    structures,
)

# E6: explizite Rangfolge statt Stringvergleich — A < B < C ist heute
# zufällig alphabetisch, eine dazukommende Stufe bräche sonst still.
STUFEN_RANG = {"A": 0, "B": 1, "C": 2}

# E3: Kennzeichnung der abgeleiteten Tageskurse — nicht mit einer echten
# Kursquelle verwechselbar.
QUELLE_ABGELEITET = "abgeleitet_letzte_ausfuehrung"

# OF-69 (AP-06x): Bei Zuteilung oder Ausübung einer Option mit Barausgleich
# trägt die Ereigniszeile den Preis 0 — der Abrechnungskurs steht in
# ``schlusskurs``. ``bewerte_barausgleich`` setzt ihn an einer Stelle ein,
# von Kennzahlen und Kommissionsattribution gemeinsam genutzt (AP-06xk).
BARAUSGLEICH_EREIGNISSE = frozenset({"assignment", "exercise"})
BARAUSGLEICH_ART = "barausgleich"

_VORZEICHEN = {"SELL": 1, "BUY": -1}
_NULL = Decimal("0")
_VIER_STELLEN = Decimal("0.0001")


@dataclass(frozen=True)
class KennzahlKette:
    chain_id: int
    sicht: str                      # 'kette' oder 'konto' — immer gefüllt
    underlying: str
    asset_class: str
    anzahl_rolls: int
    abgeschlossen: bool             # beendet_am ist nicht leer
    waehrung: str                   # der Strukturen der Kette
    netto: Decimal | None           # Instrumentenwährung, Summe der Strukturen
    netto_eur_wirtschaftlich: Decimal | None
    netto_eur_ib: Decimal | None
    waehrungseffekt_eur: Decimal | None   # wirtschaftlich − IB
    eur_kurs_fehlt: int             # Ausführungen der Kette ohne buchungskurs
    qualitaetsstufe: str            # schlechteste beteiligte Ausführung


@dataclass(frozen=True)
class KennzahlStruktur:
    structure_id: int
    chain_id: int
    sicht: str
    typ: str
    waehrung: str
    brutto: Decimal | None
    kommission: Decimal | None
    netto: Decimal | None
    netto_eur_wirtschaftlich: Decimal | None


@dataclass(frozen=True)
class KennzahlFehler:
    """Fehlerzeile nach AP-06v — ``KennzahlErgebnis.fehler`` trägt die Paare
    als einfache Tupel ``(schluessel, grund)``, weil die Abnahmebasis sie so
    vergleicht; diese Klasse benennt nur die Bedeutung der Felder."""

    schluessel: str                 # Ketten-Id als Text
    grund: str                      # 'buchungskurs_fehlt' | 'waehrung_gemischt'


@dataclass(frozen=True)
class KennzahlErgebnis:
    sicht: str
    ketten: tuple[KennzahlKette, ...]
    strukturen: tuple[KennzahlStruktur, ...]
    fehler: tuple[tuple[str, str], ...]
    summe_netto_eur: Decimal | None     # wirtschaftlich, ohne mangelbehaftete
    trefferquote_kette: Decimal | None  # 4 Stellen, HALF_UP
    trefferquote_struktur: Decimal | None
    anzahl_ketten_abgeschlossen: int
    anzahl_strukturen_abgeschlossen: int


def _beteiligt(
    structure_ids: list[int], legs_je_struktur: dict[int, list[dict]], exec_je_id: dict
) -> list[dict]:
    """Je Ausführung genau einmal (Regel 3): Der Zahlungsstrom läuft je
    beteiligter Ausführung mit deren Menge — teilt ein Roll eine Ausführung
    zwischen zwei Legs, zahlt sie trotzdem nur einmal; die Leg-Mengen
    summieren sich zur Ausführungsmenge, ein Doppelanschluss verdoppelte den
    Strom sonst still.
    """
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
            "unter den Ausführungszeilen — kein Raten (AP-06v, Regel 3)"
        ) from None


@dataclass(frozen=True)
class LegSeite:
    """Eine eröffnete oder geschlossene Seite eines Legs — die Bestandteile
    der EUR-Rechnung (AP-06xr), noch ohne Formel. Die Zusammensetzung bleibt
    eigene Rechnung der Aufrufer: Kennzahlen addieren je Seite
    (Prämie + Kommission) × Kurs, die Kommissionsattribution hält Brutto und
    Kommission als getrennte Summen × Kurs. Nicht zu einer Formel
    verschmelzen — Decimal rundet an der 28. Stelle, die Berichtssummen
    stünden sonst im letzten Zeichen anders.
    """

    ausfuehrung: dict           # Ausführungszeile (bereits barausgleich-bewertet)
    vorzeichen: int             # Seitenvorzeichen: SELL +1, BUY −1
    menge: Decimal              # vorzeichenlose Leg-Menge (AP-03, Regel 1 / OF-13)
    menge_vorzeichen: int       # Vorzeichen der gespeicherten Leg-Menge (+1 oder −1)
    multiplikator: Decimal
    kommissionsanteil: Decimal  # Kommission × menge / Gesamtmenge der Ausführung
    buchungskurs: Decimal
    # AP-03vz2: Faktor der Kapitalmaßnahmen an dieser Ausführung (1 ohne).
    # ``menge`` ist in neuen Stücken, ``ausfuehrung['preis']`` in alten: der
    # Stückpreis in neuen Stücken ist ``preis / faktor`` (``stueckpreis``).
    faktor: Decimal = Decimal("1")

    @property
    def stueckpreis(self) -> Decimal:
        preis = self.ausfuehrung["preis"]
        return preis if self.faktor == 1 else preis / self.faktor


def leg_seiten(
    legs: list[dict], exec_je_id: dict, mult_je_conid: dict, *, vertrag: str
) -> list[LegSeite] | None:
    """Gemeinsame Zerlegung einer Leg-Liste in ihre Seiten (AP-06xr): die
    Vorstufe beider EUR-Rechnungen, benutzt von ``_wirtschaftlich`` (AP-06v)
    und ``_eur_teile`` (AP-06w).

    Alle bisherigen Prüfungen, in der bisherigen Reihenfolge: je Leg zuerst
    (Eröffnung vor Schließung) die Ausführung auffindbar und ihr buchungskurs
    vorhanden — fehlt ein Kurs, gibt es ``None`` für die ganze Kette (E4,
    kein stiller Ersatzkurs) —, danach je Seite das Seitenvorzeichen, das
    Instrument und die von 0 verschiedene Ausführungsmenge. Die Fehlertexte
    nennen den jeweiligen Vertrag (``vertrag``, etwa ``"AP-06v"``), weil die
    Abnahmebasen sie prüfen.

    ``menge_vorzeichen`` trägt das Vorzeichen der gespeicherten Leg-Menge
    (IB Flex: SELL negativ) getrennt mit: ``_wirtschaftlich`` setzt es an
    den Kommissionsanteil; die Multiplikation mit ±1 ist in Decimal exakt,
    das Ergebnis bleibt stellenidentisch zur direkten Rechnung mit der
    vorzeichenbehafteten Menge.
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
                    f"({vertrag}, Regel 3)"
                ) from None
            if a["buchungskurs"] is None:
                return None
    seiten: list[LegSeite] = []
    for leg in legs:
        # Regel 5 (kein float): Leg-Mengen können als int ankommen — hier
        # normalisieren, nicht bei jeder Rechnung.
        leg_menge = (
            leg["menge"] if isinstance(leg["menge"], Decimal) else Decimal(leg["menge"])
        )
        anteil = abs(leg_menge)
        menge_vorzeichen = -1 if leg_menge < _NULL else 1
        for schluessel in ("open_exec_id", "close_exec_id"):
            exec_id = leg[schluessel]
            if exec_id is None:
                continue
            a = exec_je_id[exec_id]
            vorzeichen = _VORZEICHEN.get(a["side"])
            if vorzeichen is None:
                raise ValueError(
                    f"Ausführung {exec_id}: unbekannte Seite {a['side']!r} — "
                    f"kein Vorzeichen ableitbar ({vertrag}, Regel 3)"
                )
            try:
                multiplikator = mult_je_conid[a["conid"]]
            except KeyError:
                raise ValueError(
                    f"Ausführung {exec_id}: kein Instrument zu conid {a['conid']} "
                    f"— kein Multiplikator ableitbar ({vertrag}, Regel 3)"
                ) from None
            faktor = leg.get("open_faktor" if schluessel == "open_exec_id" else "close_faktor")
            faktor = Decimal(1) if faktor is None else Decimal(str(faktor))
            # Die Ausführung steht in alten Stücken, ``anteil`` in neuen.
            gesamtmenge = abs(a["menge"]) * faktor
            if gesamtmenge == _NULL:
                raise ValueError(
                    f"Ausführung {exec_id}: menge 0 — kein Kommissionsanteil "
                    f"ableitbar ({vertrag}, Regel 3; AP-03, Regel 5)"
                )
            kommissionsanteil = (
                a["kommission"] * (anteil / gesamtmenge)
                if a["kommission"] is not None
                else _NULL
            )
            seiten.append(
                LegSeite(
                    ausfuehrung=a,
                    vorzeichen=vorzeichen,
                    menge=anteil,
                    menge_vorzeichen=menge_vorzeichen,
                    multiplikator=multiplikator,
                    kommissionsanteil=kommissionsanteil,
                    buchungskurs=a["buchungskurs"],
                    faktor=faktor,
                )
            )
    return seiten


def _wirtschaftlich(
    legs: list[dict], exec_je_id: dict, mult_je_conid: dict
) -> Decimal | None:
    """Regel 3, je Leg-Seite: ``preis × leg.menge × multiplikator`` mit
    Vorzeichen der Seite (SELL +, BUY −), multipliziert mit dem buchungskurs
    derselben Ausführung; die Kommission derselben Ausführung läuft mit
    demselben Kurs, anteilig nach Leg-Menge (AP-03, Regel 5 — die Menge einer
    Ausführung kann über mehrere Legs, Strukturen oder Sichten geteilt sein).

    AP-06vk (03.10.2026, Echtlauf): zwei Korrekturen gegenüber der ersten
    Fassung, beide an der Abnahmebasis vorbei entstanden, weil deren Welt
    „alle Mengen je Leg 1" und je Ausführung 1 testet:

    - Die Menge ist vorzeichenlos einzusetzen (AP-03, Regel 1 / OF-13): IB Flex
      trägt das Seitenvorzeichen zusätzlich in der Menge (SELL = negativ); die
      Doppelverwendung kippte jeden Verkaufscashflow (Kette 7184 als
      Handrechnung: SELL 5,82 × menge −1 × mult 100 ergab −582 statt +582).
    - Geldwert ist der Leg-Anteil, nicht die Gesamtausführung (AP-03, Regel 5):
      Bei Teilablösungen (Roll) und Assignments steht in ``legs.menge`` der
      zugeordnete Anteil; die volle Ausführung je Leg zu werten zählte
      geteilte Ströme doppelt (Kette 9533: exec SELL 262,30 × 40 auf zwei
      Legs mit je menge 10 — +52.460 doppelt) und Assignment-Cashflows
      verzerrt (Kette 9215: leg menge 5 gegen exec menge 100).

    E4: fehlt ein Kurs einer beteiligten Ausführung, gibt es keinen Wert —
    None, kein Ersatzkurs.

    AP-06xr: Prüfung und Zerlegung liegen in ``leg_seiten``; diese Funktion
    behält ihre Formel — der Kommissionsanteil läuft hier (historisch so,
    bewusst erhalten) mit der vorzeichenbehafteten Leg-Menge, eingesetzt als
    ``kommissionsanteil × menge_vorzeichen`` (in Decimal exakt).
    """
    seiten = leg_seiten(legs, exec_je_id, mult_je_conid, vertrag="AP-06v")
    if seiten is None:
        return None
    summe = _NULL
    for seite in seiten:
        kommission = seite.kommissionsanteil * seite.menge_vorzeichen
        summe += (
            seite.vorzeichen * seite.stueckpreis * seite.menge * seite.multiplikator
            + kommission
        ) * seite.buchungskurs
    return summe


def _letzte_schliessung(legs: list[dict], exec_je_id: dict) -> dict | None:
    """Regel 4: die zeitlich letzte schließende Ausführung der übergebenen
    Legs; bei Gleichstand der handelszeit entscheidet die größte exec_id
    (Textvergleich, wie executions.exec_id gespeichert ist)."""
    schliessungen = [
        exec_je_id[leg["close_exec_id"]] for leg in legs if leg["close_exec_id"] is not None
    ]
    if not schliessungen:
        return None
    return max(schliessungen, key=lambda a: (a["handelszeit"], a["exec_id"]))


def _qualitaetsstufe(ausfuehrungen: list[dict]) -> str:
    """E6: Minimum über die beteiligten Ausführungen, über die explizite
    Rangfolge STUFEN_RANG. Ohne Ausführungen vakant 'A'; eine unbekannte
    Stufe wirft benannt statt still zu sortieren."""
    try:
        rang = min(STUFEN_RANG[a["qualitaetsstufe"]] for a in ausfuehrungen)
    except KeyError as e:
        raise ValueError(
            f"Unbekannte qualitaetsstufe {e.args[0]!r} — keine Rangfolge "
            "definiert (AP-06v, E6)"
        ) from None
    except ValueError:
        rang = 0
    return next(stufe for stufe, r in STUFEN_RANG.items() if r == rang)


def _quote(zaehler: int, nenner: int) -> Decimal | None:
    """E5: Quote als Decimal, vier Stellen, HALF_UP — Nenner 0 liefert None."""
    if nenner == 0:
        return None
    return (Decimal(zaehler) / Decimal(nenner)).quantize(
        _VIER_STELLEN, rounding=ROUND_HALF_UP
    )


def bewerte_barausgleich(
    ausfuehrungs_zeilen: list[dict], instrumenten_zeilen: list[dict]
) -> list[dict]:
    """Bewertet Barausgleich-Ereignisse zum Abrechnungskurs (OF-69, AP-06x).

    Gibt die Ausführungszeilen zurück, in denen betroffene Zeilen mit ihrem
    ``schlusskurs`` bewertet werden statt mit dem ``preis``: ``ereignistyp``
    'assignment' oder 'exercise' und ein Instrument mit ``abwicklungsart``
    'barausgleich'. Alles andere bleibt beim ``preis`` — gewöhnlicher Handel
    auch mit gesetztem ``schlusskurs``, Lieferung, Aktienzeilen. Fehlt der
    ``schlusskurs`` einer betroffenen Zeile: ``ValueError``, der die
    Ausführung nennt — kein Raten. Fehlen die Schlüssel (alte Aufrufer),
    gilt das bisherige Verhalten. Die Eingabezeilen werden nicht verändert;
    nur ersetzte Zeilen entstehen als Kopie (AP-06xk).
    """
    art_je_conid = {z["conid"]: z.get("abwicklungsart") for z in instrumenten_zeilen}
    bewertet: list[dict] = []
    for zeile in ausfuehrungs_zeilen:
        if zeile.get("ereignistyp") not in BARAUSGLEICH_EREIGNISSE:
            bewertet.append(zeile)
            continue
        if art_je_conid.get(zeile["conid"]) != BARAUSGLEICH_ART:
            bewertet.append(zeile)
            continue
        schlusskurs = zeile.get("schlusskurs")
        if schlusskurs is None:
            raise ValueError(
                f"Ausführung {zeile['exec_id']!r}: Zuteilung oder Ausübung "
                "eines Barausgleich-Instruments ohne schlusskurs — kein "
                "Raten (AP-06x, OF-69)"
            )
        bewertet.append({**zeile, "preis": schlusskurs})
    return bewertet


def kennzahlen_auswertung(
    ketten_zeilen: list[dict],
    struktur_zeilen: list[dict],
    glieder_zeilen: list[dict],
    leg_zeilen: list[dict],
    ausfuehrungs_zeilen: list[dict],
    instrumenten_zeilen: list[dict],
    *,
    sicht: str = "kette",
    nur_qualitaetsstufe_a: bool = False,
) -> KennzahlErgebnis:
    """Ketten- und Strukturkennzahlen nach AP-06v, Regeln 1–10 (rein, P2).

    Eingangszeilen sind plain dicts mit den Spaltennamen der Tabellen; die
    Zuordnung Struktur → Kette läuft über ``glieder_zeilen`` (chain_links,
    Regel 2). Regel 1: Zeilen der falschen Sicht liest die Hülle gar nicht
    erst — das Ergebnis trägt die angeforderte Sicht in jeder Zeile.
    """
    if sicht not in ("kette", "konto"):
        raise ValueError(
            f"Unbekannte sicht {sicht!r} — erlaubt sind 'kette' und 'konto' "
            "(AP-06v, Regel 1)"
        )
    # OF-69 (AP-06xk): Barausgleich-Zuteilungen und -Ausübungen zum
    # Abrechnungskurs bewerten — vor jeder Verwendung der Preise.
    ausfuehrungs_zeilen = bewerte_barausgleich(ausfuehrungs_zeilen, instrumenten_zeilen)
    exec_je_id = {z["exec_id"]: z for z in ausfuehrungs_zeilen}
    mult_je_conid = {z["conid"]: z["multiplikator"] for z in instrumenten_zeilen}
    kette_je_id = {z["chain_id"]: z for z in ketten_zeilen}
    struktur_je_id = {z["structure_id"]: z for z in struktur_zeilen}
    chain_je_struktur = {z["structure_id"]: z["chain_id"] for z in glieder_zeilen}
    legs_je_struktur: dict[int, list[dict]] = {}
    for leg in leg_zeilen:
        legs_je_struktur.setdefault(leg["structure_id"], []).append(leg)

    def _ketten_legs(structure_ids: list[int]) -> list[dict]:
        gesamt: list[dict] = []
        for structure_id in structure_ids:
            gesamt.extend(legs_je_struktur.get(structure_id, ()))
        return gesamt

    # Strukturen je Kette einmal vorab gruppiert (vorher je Kette ein Lauf über
    # alle Glieder — quadratisch, bei ~17.000 Ketten über eine Sekunde).
    strukturen_je_kette: dict[int, list[int]] = {}
    for sid, cid in chain_je_struktur.items():
        strukturen_je_kette.setdefault(cid, []).append(sid)

    ketten_ergebnisse: list[KennzahlKette] = []
    fehler_menge: set[tuple[str, str]] = set()
    for chain_id in sorted(kette_je_id):
        zeile = kette_je_id[chain_id]
        structure_ids = sorted(strukturen_je_kette.get(chain_id, ()))
        betroffene = [struktur_je_id[sid] for sid in structure_ids if sid in struktur_je_id]
        fehlende_strukturen = [sid for sid in structure_ids if sid not in struktur_je_id]
        if fehlende_strukturen:
            raise ValueError(
                f"Kette {chain_id}: chain_links ohne structures-Zeile "
                f"{fehlende_strukturen} — kein Raten (AP-06v, Regel 2)"
            )
        waehrungen = sorted({s["waehrung"] for s in betroffene})
        gemischt = len(waehrungen) > 1
        if gemischt:
            # Regel 10: defensive Fehlerzeile statt gemischter Summe.
            fehler_menge.add((str(chain_id), "waehrung_gemischt"))
        netto = None
        if not gemischt and betroffene and all(s["netto_pnl"] is not None for s in betroffene):
            # Regel 2: Summe der Strukturen; offen oder ohne netto → None.
            netto = sum((s["netto_pnl"] for s in betroffene), _NULL)
        beteiligte = _beteiligt(structure_ids, legs_je_struktur, exec_je_id)
        eur_kurs_fehlt = sum(1 for a in beteiligte if a["buchungskurs"] is None)
        if eur_kurs_fehlt:
            fehler_menge.add((str(chain_id), "buchungskurs_fehlt"))
        wirtschaftlich = (
            _wirtschaftlich(_ketten_legs(structure_ids), exec_je_id, mult_je_conid)
            if netto is not None
            else None
        )
        letzte = _letzte_schliessung(_ketten_legs(structure_ids), exec_je_id)
        ib = None
        if netto is not None and letzte is not None and letzte["buchungskurs"] is not None:
            # Regel 4: netto × Kurs der letzten schließenden Ausführung.
            ib = netto * letzte["buchungskurs"]
        effekt = None
        if wirtschaftlich is not None and ib is not None:
            # Regel 5: wirtschaftlich − IB; None, sobald ein Kurs fehlt.
            effekt = wirtschaftlich - ib
        ketten_ergebnisse.append(
            KennzahlKette(
                chain_id=chain_id,
                sicht=sicht,
                underlying=zeile["underlying"],
                asset_class=zeile["asset_class"],
                anzahl_rolls=zeile["anzahl_rolls"],
                abgeschlossen=zeile["beendet_am"] is not None,
                waehrung=waehrungen[0] if waehrungen else "",
                netto=netto,
                netto_eur_wirtschaftlich=wirtschaftlich,
                netto_eur_ib=ib,
                waehrungseffekt_eur=effekt,
                eur_kurs_fehlt=eur_kurs_fehlt,
                qualitaetsstufe=_qualitaetsstufe(beteiligte),
            )
        )

    struktur_ergebnisse: list[KennzahlStruktur] = []
    for structure_id in sorted(struktur_je_id):
        s = struktur_je_id[structure_id]
        chain_id = chain_je_struktur.get(structure_id, s.get("chain_id"))
        if chain_id is None:
            raise ValueError(
                f"Struktur {structure_id}: weder chain_links noch die Zeile "
                "nennen eine Kette — kein Raten (AP-06v, Regel 2)"
            )
        netto = s["netto_pnl"]
        wirtschaftlich = (
            _wirtschaftlich(
                legs_je_struktur.get(structure_id, []), exec_je_id, mult_je_conid
            )
            if netto is not None
            else None
        )
        struktur_ergebnisse.append(
            KennzahlStruktur(
                structure_id=structure_id,
                chain_id=chain_id,
                sicht=sicht,
                typ=s["typ"],
                waehrung=s["waehrung"],
                brutto=s["brutto_pnl"],
                kommission=s["kommission"],
                netto=netto,
                netto_eur_wirtschaftlich=wirtschaftlich,
            )
        )

    if nur_qualitaetsstufe_a:
        # E6: Zeilen mit Minimum ≠ A verschwinden ganz (unbewertet gewollt
        # weggefiltert) — aus Ketten, Strukturen, Summen, Quoten, Anzahlen.
        # Nach der Abnahmebasis ([1, 2, 4] ohne die offene Kette 3) geht mit
        # ihnen jede offene, unbewertete Zeile fort: Der Stufe-A-Bericht
        # zeigt nur Bewertbares — die Fehlerliste der Kursmängel bleibt.
        erlaubt = {k.chain_id for k in ketten_ergebnisse if k.qualitaetsstufe == "A"}
        ketten_ergebnisse = [
            k for k in ketten_ergebnisse if k.chain_id in erlaubt and k.abgeschlossen
        ]
        struktur_ergebnisse = [
            s
            for s in struktur_ergebnisse
            if s.chain_id in erlaubt
            and s.netto is not None
            and _qualitaetsstufe(_beteiligt([s.structure_id], legs_je_struktur, exec_je_id))
            == "A"
        ]

    bewertbare_ketten = [k for k in ketten_ergebnisse if k.abgeschlossen and k.netto is not None]
    bewertbare_strukturen = [s for s in struktur_ergebnisse if s.netto is not None]
    beitraege = [
        k.netto_eur_wirtschaftlich
        for k in ketten_ergebnisse
        if k.netto_eur_wirtschaftlich is not None
    ]
    return KennzahlErgebnis(
        sicht=sicht,
        ketten=tuple(ketten_ergebnisse),
        strukturen=tuple(
            sorted(struktur_ergebnisse, key=lambda s: (s.chain_id, s.structure_id))
        ),
        fehler=tuple(sorted(fehler_menge)),
        summe_netto_eur=sum(beitraege, _NULL) if beitraege else None,
        trefferquote_kette=_quote(
            sum(1 for k in bewertbare_ketten if k.netto > _NULL),
            len(bewertbare_ketten),
        ),
        trefferquote_struktur=_quote(
            sum(1 for s in bewertbare_strukturen if s.netto > _NULL),
            len(bewertbare_strukturen),
        ),
        anzahl_ketten_abgeschlossen=sum(1 for k in ketten_ergebnisse if k.abgeschlossen),
        anzahl_strukturen_abgeschlossen=len(bewertbare_strukturen),
    )


def fx_tageskurse(ausfuehrungs_zeilen: list[dict]) -> list[dict]:
    """Tageskurse nach Regel 11 (rein): je (datum, waehrung ≠ EUR) der
    buchungskurs der letzten Ausführung des Tages — max handelszeit, bei
    Gleichstand die größte exec_id. Hat die gewählte Ausführung keinen Kurs,
    gibt es den Eintrag nicht (E4: kein stiller Ersatzkurs durch eine
    frühere Ausführung desselben Tages). EUR braucht keinen Eintrag (Regel
    3). Sortierung nach (datum, waehrung); quelle nach E3.
    """
    letzte: dict[tuple, dict] = {}
    for a in ausfuehrungs_zeilen:
        if a["waehrung"] == "EUR":
            continue
        schluessel = (a["handelszeit"].date(), a["waehrung"])
        bisher = letzte.get(schluessel)
        if bisher is None or (a["handelszeit"], a["exec_id"]) > (
            bisher["handelszeit"],
            bisher["exec_id"],
        ):
            letzte[schluessel] = a
    kurse = []
    for datum, waehrung in sorted(letzte):
        a = letzte[(datum, waehrung)]
        if a["buchungskurs"] is None:
            continue
        kurse.append(
            dict(
                datum=datum,
                waehrung=waehrung,
                kurs_eur=a["buchungskurs"],
                quelle=QUELLE_ABGELEITET,
            )
        )
    return kurse


def _geld(wert: Decimal | None) -> str:
    """Regel 13: Beträge mit zwei Nachkommastellen, None als leeres Feld."""
    return "" if wert is None else f"{wert:.2f}"


def _quote_text(wert: Decimal | None) -> str:
    """Regel 13: Quoten mit vier Nachkommastellen, None als leeres Feld."""
    return "" if wert is None else f"{wert:.4f}"


def als_csv(ergebnis: KennzahlErgebnis) -> str:
    """CSV nach Regel 13: Semikolon-getrennt, 22 Spalten, Kopf exakt; Zeilen
    in der Reihenfolge Kopf, kette (nach chain_id), struktur (nach
    chain_id, structure_id), fehler (nach schluessel, grund), eine
    summe-Zeile zuletzt. Spalte 13 der summe-Zeile zählt die Ketten mit
    Kursmangel."""
    kopf = (
        "abschnitt;sicht;chain_id;underlying;asset_class;status;anzahl_rolls;waehrung;"
        "netto;netto_eur_wirtschaftlich;netto_eur_ib;waehrungseffekt_eur;eur_kurs_fehlt;"
        "qualitaetsstufe;structure_id;typ;brutto;kommission;schluessel;grund;"
        "trefferquote_kette;trefferquote_struktur"
    )
    zeilen = [kopf]
    for k in ergebnis.ketten:
        zeilen.append(
            ";".join(
                [
                    "kette",
                    ergebnis.sicht,
                    str(k.chain_id),
                    k.underlying,
                    k.asset_class,
                    "abgeschlossen" if k.abgeschlossen else "offen",
                    str(k.anzahl_rolls),
                    k.waehrung,
                    _geld(k.netto),
                    _geld(k.netto_eur_wirtschaftlich),
                    _geld(k.netto_eur_ib),
                    _geld(k.waehrungseffekt_eur),
                    str(k.eur_kurs_fehlt),
                    k.qualitaetsstufe,
                ]
                + [""] * 8
            )
        )
    for s in ergebnis.strukturen:
        if s.netto is None:
            # Offene Strukturen haben kein netto — Regel 13 füllt Spalte 9,
            # deshalb erscheinen sie nicht als CSV-Zeile. Die offene KETTE
            # hat ihre 'offen'-Zeile, die offene Struktur keine.
            continue
        zeilen.append(
            ";".join(
                [
                    "struktur",
                    ergebnis.sicht,
                    str(s.chain_id),
                    "",
                    "",
                    "",
                    "",
                    s.waehrung,
                    _geld(s.netto),
                    _geld(s.netto_eur_wirtschaftlich),
                    "",
                    "",
                    "",
                    "",
                    str(s.structure_id),
                    s.typ,
                    _geld(s.brutto),
                    _geld(s.kommission),
                ]
                + [""] * 4
            )
        )
    for schluessel, grund in ergebnis.fehler:
        zeilen.append(";".join(["fehler", ergebnis.sicht] + [""] * 16
                               + [schluessel, grund, "", ""]))
    anzahl_mangel = sum(1 for k in ergebnis.ketten if k.eur_kurs_fehlt)
    zeilen.append(
        ";".join(
            ["summe", ergebnis.sicht]
            + [""] * 7
            + [
                _geld(ergebnis.summe_netto_eur),
                "",
                "",
                str(anzahl_mangel),
            ]
            + [""] * 7
            + [
                _quote_text(ergebnis.trefferquote_kette),
                _quote_text(ergebnis.trefferquote_struktur),
            ]
        )
    )
    return "\n".join(zeilen)


def kennzahlen_bericht(
    db_pfad: str | pathlib.Path,
    *,
    sicht: str = "kette",
    nur_qualitaetsstufe_a: bool = False,
) -> KennzahlErgebnis:
    """I/O-Hülle (P3) nach AP-06v: Liest chains, structures, chain_links,
    legs, executions und instruments — je abgeleitete Tabelle gefiltert auf
    die jeweilige Sicht (Regel 1: Zeilen der falschen Sicht werden nicht
    gelesen) — ruft die reine Funktion und schreibt in einer Transaktion:

    - ``fx_rates`` vollständig neu (Regel 11): Tageskurse über ALLE
      Ausführungen, unabhängig von der angeforderten Sicht.
    - ``metrics_by_chain`` vollständig neu (Regel 11): je Kette BEIDER
      Sichten eine Zeile — aus dem ungefilterten Ergebnis, damit der
      Berichtsfilter ``nur_qualitaetsstufe_a`` den Cache nicht lückenhaft
      macht. NULL nur für offene oder kursmangelbehaftete Ketten.
    - ``chains.netto_pnl_eur`` bleibt leer (E2 — der Rebuild setzt die
      Spalte ohnehin bei jedem Lauf auf None).

    Zurück kommt das (ggf. gefilterte) Ergebnis der angeforderten Sicht.
    """
    if sicht not in ("kette", "konto"):
        raise ValueError(
            f"Unbekannte sicht {sicht!r} — erlaubt sind 'kette' und 'konto' "
            "(AP-06v, Regel 1)"
        )
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
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

        ergebnis: KennzahlErgebnis | None = None
        materialisierung: list[KennzahlErgebnis] = []
        for laufende_sicht in ("kette", "konto"):
            ketten_zeilen = [
                dict(z)
                for z in verbindung.execute(
                    select(
                        chains.c.chain_id,
                        chains.c.underlying,
                        chains.c.asset_class,
                        chains.c.anzahl_rolls,
                        chains.c.beendet_am,
                    ).where(chains.c.sicht == laufende_sicht)
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
                    ).where(structures.c.sicht == laufende_sicht)
                ).mappings()
            ]
            glieder_zeilen = [
                dict(z)
                for z in verbindung.execute(
                    select(chain_links.c.chain_id, chain_links.c.structure_id).where(
                        chain_links.c.sicht == laufende_sicht
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
                    legs.c.open_faktor,
                    legs.c.close_faktor,
                    ).where(legs.c.sicht == laufende_sicht)
                ).mappings()
            ]
            ungefiltert = kennzahlen_auswertung(
                ketten_zeilen,
                struktur_zeilen,
                glieder_zeilen,
                leg_zeilen,
                ausfuehrungs_zeilen,
                instrumenten_zeilen,
                sicht=laufende_sicht,
            )
            materialisierung.append(ungefiltert)
            if laufende_sicht == sicht:
                ergebnis = (
                    ungefiltert
                    if not nur_qualitaetsstufe_a
                    else kennzahlen_auswertung(
                        ketten_zeilen,
                        struktur_zeilen,
                        glieder_zeilen,
                        leg_zeilen,
                        ausfuehrungs_zeilen,
                        instrumenten_zeilen,
                        sicht=laufende_sicht,
                        nur_qualitaetsstufe_a=True,
                    )
                )

        verbindung.execute(delete(fx_rates))
        for satz in fx_tageskurse(ausfuehrungs_zeilen):
            verbindung.execute(insert(fx_rates).values(**satz))

        verbindung.execute(delete(metrics_by_chain))
        for teil in materialisierung:
            for kette in teil.ketten:
                verbindung.execute(
                    insert(metrics_by_chain).values(
                        chain_id=kette.chain_id,
                        netto_eur_wirtschaftlich=kette.netto_eur_wirtschaftlich,
                        netto_eur_ib=kette.netto_eur_ib,
                    )
                )

    assert ergebnis is not None  # sicht ist oben auf kette/konto begrenzt
    return ergebnis
