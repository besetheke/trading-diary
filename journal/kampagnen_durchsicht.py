"""Durchsicht der Campaign-Kandidaten über eine Datei-Rundreise (AP-05dk).

Seit AP-05k schlägt ``engine.campaigns`` Paare von Ketten als mögliche
Kampagnen-Glieder vor: IC-Kandidaten („diese beiden Ketten ergeben zusammen
einen Iron Condor") und Financing-Kandidaten („diese Kette ist die
Gegenfinanzierung jenes Rolls"). Vorschläge werden nie automatisch übernommen
(Plan §6): Der Nutzer klassifiziert. ``kampagnen_ausschreiben()`` schreibt die
offenen Kandidaten als XLSX, gruppiert nach Kette A; der Nutzer entscheidet in
der Tabellenkalkulation; ``kampagnen_urteile_einlesen()`` schreibt die
Entscheidungen nach ``campaign_links`` (Bestätigung, ``erkennung = 'manuell'``)
und ``campaign_ablehnungen`` (Ablehnung).

Verbindlich ist der Vertrag in ``auftraege/AP-05d.md`` (Nummern in den
Kommentaren folgen ihm); Vorbild ist die Rollkandidaten-Durchsicht
(``journal/durchsicht.py``, AP-04d) — gleiche Bauart, gleiche Sicherungen:
Schutz der Zieldatei, „erst prüfen, dann in einer kurzen Transaktion
schreiben", Abbruch ohne Teilzustand. Kandidaten werden nicht neu erfunden:
Lesen und Rechnen kommen aus ``bestand_berechnen()`` in ``journal.rebuild``
und ``campaign_kandidaten()`` in ``engine.campaigns`` — ein Lesepfad. Alle
Nachschlagen in ``chains`` filtern ausdrücklich auf die Kontosicht: Die IDs in
``campaign_links`` und ``campaign_ablehnungen`` sind Kontosicht-Ketten.

Dokumentierte Annahmen (Regel 10 — das Abnahmekriterium zur ``git diff``
lässt neben den Journal-Modulen keine Änderung an ``OFFENE_FRAGEN.md`` zu):

- **Kampagnen-Underlying bei verschiedenen Underlyings der Ketten**: Möglich
  über ``independent``. Gewinnt das alphabetisch erste — deterministisch,
  ohne die Daten zu mischen; dieselbe Regel wie beim Nachziehen der Zeiten
  im Rebuild (AP-05d).
- **Die Vorbelegung „Typ Kette A/B"** folgt OF-71 (``ic`` → beide ``ic_leg``,
  ``financing`` → A ``ic_leg``, B ``financing``) und ist ein Vorschlag: Der
  Nutzer ändert sie in der Datei, das Einlesen übernimmt sie ungeprüft gegen
  die Datenbank, aber geprüft gegen die Werteliste.
- **Ablehnung desselben Paares zweimal** (Datei oder Datenbank) zählt
  ``unveraendert`` — wie eine wiederholte Bestätigung; ``erstellt_am``
  bleibt dann die erste Zeit.
"""

import pathlib
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from openpyxl import Workbook, load_workbook
from sqlalchemy import delete, insert, select, update

from engine.campaigns import campaign_kandidaten
from journal.db import STANDARD_BUSY_TIMEOUT_MS, create_db_engine
from journal.rebuild import _kette_schluessel, bestand_berechnen
from journal.schema import (
    campaign_ablehnungen,
    campaign_links,
    campaigns,
    chains,
)

# Vertrag 8 analog AP-04d, Regel 2: Aus der echten Datenbank enthält die
# Datei echte Kontodaten — sie darf nicht im Repository landen (nur unter
# fixtures/golden/, das nicht versioniert wird).
PROJEKTWURZEL = pathlib.Path(__file__).resolve().parents[1]
GOLDEN_VERZEICHNIS = PROJEKTWURZEL / "fixtures" / "golden"

# Feste Spaltenreihenfolge, Kopfzeile in Zeile 1 (Vertrag: „KOPF" der Tests).
KOPF = [
    "Gruppe", "Kandidaten in Gruppe", "Rang", "Typ", "Basiswert",
    "Kette A: Seite", "Kette A: eröffnet", "Kette A: beendet", "Kette A: Rolls",
    "Kette B: Seite", "Kette B: eröffnet", "Kette B: beendet", "Kette B: Rolls",
    "Abstand Minuten", "Überlappung Tage", "Typ Kette A", "Typ Kette B",
    "Entscheidung", "Bemerkung", "Schlüssel Kette A", "Schlüssel Kette B",
]

# Umgebende Leerzeichen und Groß-/Kleinschreibung egal; alles andere — auch
# Wahrheitswerte und Zahlen — ist Abbruch.
BESTAETIGT_TEXT = frozenset({"ja", "j"})
ABGELEHNT_TEXT = frozenset({"nein", "n"})

# Nur diese Beziehungstypen darf eine Bestätigung eintragen (Vertrag).
BEZIEHUNGSTYPEN = frozenset({"ic_leg", "financing", "contract_roll", "independent"})
# Vorbelegung nach OF-71, vom Nutzer änderbar (Vertrag „Ausschreiben").
TYP_JE_KANDIDATTYP = {
    "ic": ("ic_leg", "ic_leg"),
    "financing": ("ic_leg", "financing"),
}

# Überlappung in Tagen: Decimal, auf zwei Stellen gerundet — kein float für
# einen angezeigten Betrag (Regel 5 sinngemäß).
_TAG_IN_SEKUNDEN = Decimal(86400)
_ZWEI_STELLEN = Decimal("0.01")


@dataclass(frozen=True)
class KampagnenAusschreibErgebnis:
    """Zählwerte des Ausschreibens."""

    gruppen: int
    kandidaten: int


@dataclass(frozen=True)
class KampagnenEinleseErgebnis:
    """Zählwerte des Einlesens."""

    neu_bestaetigt: int
    neu_abgelehnt: int
    kampagnen_neu: int
    verknuepfungen_neu: int
    unveraendert: int
    geaendert: int
    unentschieden: int


# ---------------------------------------------------------------------------
# Ausschreiben
# ---------------------------------------------------------------------------


def kampagnen_ausschreiben(
    db_pfad: str | pathlib.Path,
    ziel: str | pathlib.Path,
    *,
    busy_timeout_ms: int = STANDARD_BUSY_TIMEOUT_MS,
) -> KampagnenAusschreibErgebnis:
    """Schreibt die offenen Campaign-Kandidaten als XLSX nach ``ziel``.

    Vor jedem Schreibversuch: Existiert das Ziel, ``FileExistsError``; liegt
    es im Projektverzeichnis, aber nicht unter ``fixtures/golden/``,
    ``ValueError`` (echte Kontodaten gehören nicht ins Repository). Fehlt zu
    einem Naturschlüssel die Zeile in ``chains`` (Kontosicht), ``ValueError``
    mit Hinweis auf ``journal rebuild`` — dann entstünde keine Datei.
    """
    ziel = pathlib.Path(ziel)
    if ziel.exists():
        raise FileExistsError(
            f"Zieldatei {ziel} existiert bereits — eine vorhandene Datei kann "
            "Entscheidungen tragen"
        )
    aufgeloest = ziel.resolve()
    if aufgeloest.is_relative_to(PROJEKTWURZEL) and not aufgeloest.is_relative_to(
        GOLDEN_VERZEICHNIS
    ):
        raise ValueError(
            f"Ziel {ziel} liegt im Projektverzeichnis — eine Kandidatendatei "
            "aus der echten Datenbank enthält echte Kontodaten und gehört "
            "nicht ins Repository (Regel 2)"
        )

    engine = create_db_engine(db_pfad, busy_timeout_ms=busy_timeout_ms)
    try:
        with engine.connect() as verbindung:
            gruppen = _gruppen_bilden(verbindung)
    finally:
        engine.dispose()

    _mappe_schreiben(ziel, gruppen)
    return KampagnenAusschreibErgebnis(
        gruppen=len(gruppen),
        kandidaten=sum(len(eintraege) for eintraege in gruppen.values()),
    )


def _gruppen_bilden(verbindung) -> dict[str, list[tuple[tuple, dict]]]:
    """Offene Kandidaten, gruppiert nach Kette A (früher eröffnete).

    Offen heißt: Die beiden Ketten haben keine gemeinsame Kampagne, und das
    Paar steht nicht in ``campaign_ablehnungen``. Innerhalb einer Gruppe
    sortiert: ``financing`` vor ``ic``; ``financing`` nach Abstand
    aufsteigend, ``ic`` nach Überlappung absteigend (unbegrenzt zuerst), bei
    Gleichstand nach Schlüssel Kette B. Die Ketten-Zeilen kommen aus der
    Kontosicht — die IDs der Klassifikation sind Kontosicht-Ketten.
    """
    bestand = bestand_berechnen(verbindung)
    ketten_zeile_je_schluessel = {
        z["natur_schluessel"]: dict(z)
        for z in verbindung.execute(
            select(chains).where(chains.c.sicht == "konto")
        ).mappings()
    }
    kampagnen_je_chain_id: dict[int, set[int]] = {}
    for zeile in verbindung.execute(select(campaign_links)).mappings():
        kampagnen_je_chain_id.setdefault(zeile["chain_id"], set()).add(
            zeile["campaign_id"]
        )
    abgelehnt = {
        (z["chain_id_a"], z["chain_id_b"], z["typ"])
        for z in verbindung.execute(select(campaign_ablehnungen)).mappings()
    }

    kette_je_schluessel = {
        _kette_schluessel(kette): kette for kette in bestand.ketten_ergebnis.chains
    }
    gruppen: dict[str, list[tuple[tuple, dict]]] = {}
    for kandidat in campaign_kandidaten(kette_je_schluessel.values()):
        schluessel_a = _kette_schluessel(kandidat.kette_a)
        schluessel_b = _kette_schluessel(kandidat.kette_b)
        zeile_a = ketten_zeile_je_schluessel.get(schluessel_a)
        zeile_b = ketten_zeile_je_schluessel.get(schluessel_b)
        if zeile_a is None or zeile_b is None:
            raise ValueError(
                f"Kandidat {schluessel_a} → {schluessel_b} verweist auf keine "
                "vorhandene Zeile in chains (Kontosicht) — zuerst `journal "
                "rebuild` ausführen"
            )
        if kampagnen_je_chain_id.get(zeile_a["chain_id"], set()) & kampagnen_je_chain_id.get(
            zeile_b["chain_id"], set()
        ):
            continue
        if (zeile_a["chain_id"], zeile_b["chain_id"], kandidat.typ) in abgelehnt:
            continue
        gruppen.setdefault(schluessel_a, []).append(
            (
                _gruppenschluessel(kandidat, schluessel_b),
                _zeile_bilden(kandidat, zeile_a, zeile_b, schluessel_a, schluessel_b),
            )
        )
    for eintraege in gruppen.values():
        eintraege.sort(key=lambda eintrag: eintrag[0])
    return gruppen


def _gruppenschluessel(kandidat, schluessel_b: str) -> tuple:
    """Sortierung innerhalb einer Gruppe: ``financing`` vor ``ic``;
    ``financing`` nach Abstand aufsteigend, ``ic`` nach Überlappung
    absteigend (unbegrenzt = ``None`` zuerst), bei Gleichstand nach Schlüssel
    Kette B. Sekunden als Reihenfolgemaß — kein Betrag, kein Decimal nötig."""
    if kandidat.typ == "financing":
        abstand = kandidat.abstand
        return (
            0,
            float("inf") if abstand is None else abstand.total_seconds(),
            schluessel_b,
        )
    ueberlappung = kandidat.ueberlappung
    return (
        1,
        float("-inf") if ueberlappung is None else -ueberlappung.total_seconds(),
        schluessel_b,
    )


def _ueberlappung_tage(ueberlappung) -> Decimal | None:
    """Überlappung in Tagen, auf zwei Stellen gerundet; unbegrenzt = leer."""
    if ueberlappung is None:
        return None
    tage = Decimal(ueberlappung.total_seconds()) / _TAG_IN_SEKUNDEN
    return tage.quantize(_ZWEI_STELLEN)


def _zeile_bilden(
    kandidat, zeile_a: dict, zeile_b: dict, schluessel_a: str, schluessel_b: str
) -> dict:
    """Spaltenwerte eines Kandidaten; ``Typ Kette A/B`` vorbelegt nach OF-71
    (vom Nutzer änderbar), ``Entscheidung``/``Bemerkung`` leer."""
    typ_a, typ_b = TYP_JE_KANDIDATTYP[kandidat.typ]
    return {
        "Gruppe": None,  # setzt _mappe_schreiben je Gruppe
        "Kandidaten in Gruppe": None,
        "Rang": None,
        "Typ": kandidat.typ,
        "Basiswert": zeile_a["underlying"],
        "Kette A: Seite": zeile_a["seite"],
        "Kette A: eröffnet": zeile_a["eroeffnet_am"],
        "Kette A: beendet": zeile_a["beendet_am"],
        "Kette A: Rolls": zeile_a["anzahl_rolls"],
        "Kette B: Seite": zeile_b["seite"],
        "Kette B: eröffnet": zeile_b["eroeffnet_am"],
        "Kette B: beendet": zeile_b["beendet_am"],
        "Kette B: Rolls": zeile_b["anzahl_rolls"],
        "Abstand Minuten": (
            None
            if kandidat.abstand is None
            else round(kandidat.abstand.total_seconds() / 60)
        ),
        "Überlappung Tage": _ueberlappung_tage(kandidat.ueberlappung),
        "Typ Kette A": typ_a,
        "Typ Kette B": typ_b,
        "Entscheidung": None,
        "Bemerkung": None,
        "Schlüssel Kette A": schluessel_a,
        "Schlüssel Kette B": schluessel_b,
    }


def _mappe_schreiben(ziel: pathlib.Path, gruppen: dict[str, list[tuple[tuple, dict]]]) -> None:
    """XLSX mit den Blättern ``Kandidaten`` und ``Anleitung``; Gruppen
    nummeriert nach dem ersten Auftreten, Rang nach der Gruppen-Sortierung."""
    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Kandidaten"
    blatt.append(KOPF)
    for nummer, eintraege in enumerate(gruppen.values(), start=1):
        zeilen = [zeile for _, zeile in eintraege]
        for rang, zeile in enumerate(zeilen, start=1):
            zeile["Gruppe"] = nummer
            zeile["Kandidaten in Gruppe"] = len(zeilen)
            zeile["Rang"] = rang
            blatt.append([zeile[name] for name in KOPF])

    anleitung = mappe.create_sheet("Anleitung")
    anleitung["A1"] = (
        "Entscheidung: `ja` (oder `j`) ordnet die beiden Ketten einer Kampagne "
        "zu, `nein` (oder `n`) lehnt das Paar ab. Eine Zeile leer lassen "
        "heißt unentschieden."
    )
    anleitung["A2"] = (
        "Nicht „Wahr“ oder „Falsch“ eintragen — Excel macht daraus "
        "Wahrheitswerte, die das Einlesen ablehnt."
    )
    anleitung["A3"] = (
        "„Typ Kette A/B“ sind Vorschläge (ic: beide ic_leg; financing: A "
        "ic_leg, B financing) und änderbar: ic_leg, financing, contract_roll, "
        "independent."
    )
    anleitung["A4"] = (
        "Eine Gruppe ist eine Kette A mit allen möglichen Partnern. Bei "
        "„Kandidaten in Gruppe“ größer 1 ist die Lage mehrdeutig — dort "
        "beginnt die Durchsicht."
    )
    anleitung["A5"] = (
        "Nach dem Einlesen (`journal kampagnen-einlesen`) ist `journal "
        "rebuild` auszuführen."
    )
    mappe.save(ziel)


# ---------------------------------------------------------------------------
# Einlesen
# ---------------------------------------------------------------------------


def kampagnen_urteile_einlesen(
    db_pfad: str | pathlib.Path,
    quelle: str | pathlib.Path,
    *,
    ueberschreiben: bool = False,
    jetzt: datetime | None = None,
    busy_timeout_ms: int = STANDARD_BUSY_TIMEOUT_MS,
) -> KampagnenEinleseErgebnis:
    """Liest Entscheidungen aus einer ausgeschriebenen Datei ein und schreibt
    sie nach ``campaign_links`` (Bestätigung) bzw. ``campaign_ablehnungen``
    (Ablehnung).

    Erst wird alles geprüft — ungültige Werte, unbekannte Schlüssel,
    Widersprüche in der Datei oder gegen die Datenbank —, dann in einer
    kurzen Transaktion geschrieben (Regel 9): Bricht irgendetwas ab, steht
    danach nichts Neues in der Datenbank. Kein ``rebuild``; der ist Sache des
    Aufrufenden. ``ueberschreiben=True`` ändert gespeicherte Entscheidungen,
    statt bei Widerspruch abzubrechen — ein ``nein`` nach ``ja`` in
    derselben Datei bleibt dennoch immer ein Abbruch.
    """
    if jetzt is None:
        jetzt = datetime.now()

    zeilen = _entscheidungen_lesen(pathlib.Path(quelle))
    engine = create_db_engine(db_pfad, busy_timeout_ms=busy_timeout_ms)
    try:
        with engine.begin() as verbindung:
            plan = _plan_bilden(verbindung, zeilen, ueberschreiben=ueberschreiben)
            _plan_ausfuehren(verbindung, plan, jetzt=jetzt)
            return plan.ergebnis
    finally:
        engine.dispose()


def _entscheidungen_lesen(quelle: pathlib.Path) -> list[dict]:
    """Zeilen des Blatts ``Kandidaten`` als Abbild der Spalten."""
    mappe = load_workbook(quelle, data_only=True)
    if "Kandidaten" not in mappe.sheetnames:
        raise ValueError(f"Blatt 'Kandidaten' fehlt in {quelle} — keine Entscheidungen")
    blatt = mappe["Kandidaten"]
    kopf = [zelle.value for zelle in blatt[1]]
    fehlend = [name for name in KOPF if name not in kopf]
    if fehlend:
        raise ValueError(
            f"Kopfzeile unvollständig (fehlt: {', '.join(fehlend)}) — keine "
            "Kandidatendatei"
        )
    spalte_je_name = {name: kopf.index(name) for name in KOPF}

    zeilen = []
    for werte in blatt.iter_rows(min_row=2, values_only=True):
        if not any(wert is not None for wert in werte):
            continue
        zeilen.append({name: werte[index] for name, index in spalte_je_name.items()})
    return zeilen


def _urteil_aus_wert(wert, gruppe, rang) -> str | None:
    """``bestaetigt``/``abgelehnt`` aus dem Zellenwert, ``None`` für leer.
    Alles andere — auch Wahrheitswerte, die Excel aus „Wahr“/„Falsch“ macht
    (``bool`` ist Unterklasse von ``int``, deshalb die String-Prüfung vor
    allem anderen), und Zahlen — bricht ab und nennt Gruppe und Rang."""
    if wert is None:
        return None
    if not isinstance(wert, str):
        raise ValueError(
            f"Gruppe {gruppe}, Rang {rang}: ungültige Entscheidung {wert!r} — "
            "nur 'ja' oder 'nein' eintragen, leer lassen heißt unentschieden"
        )
    text = wert.strip().lower()
    if not text:
        return None
    if text in BESTAETIGT_TEXT:
        return "bestaetigt"
    if text in ABGELEHNT_TEXT:
        return "abgelehnt"
    raise ValueError(
        f"Gruppe {gruppe}, Rang {rang}: ungültige Entscheidung {wert!r} — "
        "nur 'ja' oder 'nein' eintragen, leer lassen heißt unentschieden"
    )


def _beziehungstyp_aus_wert(wert, gruppe, rang, spalte: str) -> str:
    """Beziehungstyp aus ``Typ Kette A/B``: nur die vier Werte des
    CHECK-Constraints, alles andere — auch leere Zellen — bricht ab."""
    if isinstance(wert, str) and wert.strip() in BEZIEHUNGSTYPEN:
        return wert.strip()
    raise ValueError(
        f"Gruppe {gruppe}, Rang {rang}: ungültiger Typ {wert!r} in "
        f"„{spalte}“ — nur ic_leg, financing, contract_roll oder independent"
    )


@dataclass
class _SchreibPlan:
    """Alles, was das Einlesen zu schreiben gedenkt — erst vollständig
    geprüft (``_plan_bilden``), dann in einem Rutsch ausgeführt
    (``_plan_ausfuehren``). Temporäre Kampagnen-IDs sind negativ, echte aus
    der Datenbank positiv; ersetzte werden erst beim Ausführen vergeben."""

    ketten_zeile_je_id: dict[int, dict]
    ketten_je_kampagne: dict[int, set[int]]
    neue_kampagnen: list[int] = field(default_factory=list)
    neue_links: list[tuple[int, int, str]] = field(default_factory=list)
    typ_aenderungen: list[tuple[int, int, str]] = field(default_factory=list)
    loeschbare_ablehnungen: set[tuple[int, int, str]] = field(default_factory=set)
    neue_ablehnungen: dict[tuple[int, int, str], str | None] = field(
        default_factory=dict
    )
    betroffene_kampagnen: set[int] = field(default_factory=set)
    ergebnis: KampagnenEinleseErgebnis | None = None


def _plan_bilden(verbindung, zeilen: list[dict], *, ueberschreiben: bool) -> _SchreibPlan:
    """Prüft jede Zeile gegen die Datei selbst und die Datenbank und sammelt
    die Schritte. Bricht bei jedem Widerspruch ab — vor jedem Schreiben."""
    ketten_zeile_je_schluessel = {
        z["natur_schluessel"]: dict(z)
        for z in verbindung.execute(
            select(chains).where(chains.c.sicht == "konto")
        ).mappings()
    }
    ketten_zeile_je_id = {z["chain_id"]: z for z in ketten_zeile_je_schluessel.values()}
    kampagnen_je_chain: dict[int, set[int]] = {}
    typ_je_link: dict[tuple[int, int], str] = {}
    ketten_je_kampagne: dict[int, set[int]] = {}
    for zeile in verbindung.execute(select(campaign_links)).mappings():
        kampagnen_je_chain.setdefault(zeile["chain_id"], set()).add(
            zeile["campaign_id"]
        )
        typ_je_link[(zeile["chain_id"], zeile["campaign_id"])] = zeile["beziehungstyp"]
        if zeile["chain_id"] in ketten_zeile_je_id:
            ketten_je_kampagne.setdefault(zeile["campaign_id"], set()).add(
                zeile["chain_id"]
            )
    vorhandene_ablehnungen = {
        (z["chain_id_a"], z["chain_id_b"], z["typ"])
        for z in verbindung.execute(select(campaign_ablehnungen)).mappings()
    }

    plan = _SchreibPlan(ketten_zeile_je_id=ketten_zeile_je_id,
                        ketten_je_kampagne=ketten_je_kampagne)
    zaehler = dict.fromkeys(
        ("neu_bestaetigt", "neu_abgelehnt", "kampagnen_neu", "verknuepfungen_neu",
         "unveraendert", "geaendert", "unentschieden"), 0
    )
    abgelehnt_datei: set[tuple[int, int, str]] = set()
    datei_typen: set[tuple[int, int]] = set()
    naechste_kampagne_id = 0

    for zeile in zeilen:
        gruppe, rang = zeile["Gruppe"], zeile["Rang"]
        schluessel_a = zeile["Schlüssel Kette A"]
        schluessel_b = zeile["Schlüssel Kette B"]
        zeile_a = ketten_zeile_je_schluessel.get(schluessel_a)
        zeile_b = ketten_zeile_je_schluessel.get(schluessel_b)
        if zeile_a is None:
            raise ValueError(
                f"Gruppe {gruppe}, Rang {rang}: unbekannter Schlüssel "
                f"{schluessel_a!r} (Kette A)"
            )
        if zeile_b is None:
            raise ValueError(
                f"Gruppe {gruppe}, Rang {rang}: unbekannter Schlüssel "
                f"{schluessel_b!r} (Kette B)"
            )

        urteil = _urteil_aus_wert(zeile["Entscheidung"], gruppe, rang)
        if urteil is None:
            # Leer lassen heißt unentschieden — keine Zeile, keine Prüfung.
            zaehler["unentschieden"] += 1
            continue
        bemerkung = zeile["Bemerkung"]
        notiz = bemerkung if isinstance(bemerkung, str) and bemerkung.strip() else None
        kandidat_typ = zeile["Typ"]
        if kandidat_typ not in TYP_JE_KANDIDATTYP:
            raise ValueError(
                f"Gruppe {gruppe}, Rang {rang}: unbekannter Kandidat-Typ "
                f"{kandidat_typ!r} — nur ic oder financing"
            )
        a_id, b_id = zeile_a["chain_id"], zeile_b["chain_id"]
        paar = (a_id, b_id, kandidat_typ)

        if urteil == "abgelehnt":
            # Ablehnung: Zeile in campaign_ablehnungen. Steht das Paar
            # bereits in einer gemeinsamen Kampagne, ist das ein Widerspruch
            # — eine Ablehnung löscht nie eine Verknüpfung.
            if kampagnen_je_chain.get(a_id, set()) & kampagnen_je_chain.get(
                b_id, set()
            ):
                raise ValueError(
                    f"Gruppe {gruppe}, Rang {rang}: Ablehnung von {schluessel_a} → "
                    f"{schluessel_b} — beide Ketten liegen bereits in derselben "
                    "Kampagne, eine Ablehnung löscht keine Verknüpfung"
                )
            if paar in abgelehnt_datei or paar in vorhandene_ablehnungen:
                zaehler["unveraendert"] += 1
            else:
                plan.neue_ablehnungen[paar] = notiz
                abgelehnt_datei.add(paar)
                zaehler["neu_abgelehnt"] += 1
            continue

        # -- Bestätigung: Typen prüfen, Basiswerte vergleichen, Ziel-Kampagne
        #    bestimmen — auch innerhalb derselben Datei (zwei Zeilen mit
        #    einer gemeinsamen Kette ergeben eine Kampagne).
        typ_a = _beziehungstyp_aus_wert(zeile["Typ Kette A"], gruppe, rang, "Typ Kette A")
        typ_b = _beziehungstyp_aus_wert(zeile["Typ Kette B"], gruppe, rang, "Typ Kette B")
        if zeile_a["underlying"] != zeile_b["underlying"]:
            raise ValueError(
                f"Gruppe {gruppe}, Rang {rang}: {schluessel_a} "
                f"({zeile_a['underlying']}) und {schluessel_b} "
                f"({zeile_b['underlying']}) haben unterschiedliche Basiswerte — "
                "keine gemeinsame Kampagne"
            )

        zeile_geaendert = False
        if paar in abgelehnt_datei or paar in vorhandene_ablehnungen:
            # ``nein`` nach ``ja`` in derselben Datei: immer Abbruch, auch mit
            # ueberschreiben. Gegen eine gespeicherte Ablehnung: Abbruch, mit
            # ueberschreiben wird sie gelöscht und dann bestätigt (geaendert).
            if paar in abgelehnt_datei or not ueberschreiben:
                raise ValueError(
                    f"Gruppe {gruppe}, Rang {rang}: Bestätigung von "
                    f"{schluessel_a} → {schluessel_b} ({kandidat_typ}) "
                    "widerspricht der Ablehnung — erneut einlesen nur mit "
                    "ueberschreiben=True"
                )
            plan.loeschbare_ablehnungen.add(paar)
            zeile_geaendert = True

        menge_a = kampagnen_je_chain.get(a_id, set())
        menge_b = kampagnen_je_chain.get(b_id, set())
        gemeinsam = menge_a & menge_b
        if gemeinsam:
            ziel = next(iter(gemeinsam))
        elif menge_a and menge_b:
            raise ValueError(
                f"Gruppe {gruppe}, Rang {rang}: {schluessel_a} und "
                f"{schluessel_b} liegen bereits in zwei verschiedenen "
                "Kampagnen — Zusammenführen ist nicht Sache des Einlesens"
            )
        else:
            if menge_a:
                ziel = next(iter(menge_a))
            elif menge_b:
                ziel = next(iter(menge_b))
            else:
                naechste_kampagne_id += 1
                ziel = -naechste_kampagne_id
                plan.neue_kampagnen.append(ziel)
                ketten_je_kampagne[ziel] = set()
                zaehler["kampagnen_neu"] += 1

        zeile_schreibt = False
        for kette, schluessel, typ_datei in (
            (a_id, schluessel_a, typ_a),
            (b_id, schluessel_b, typ_b),
        ):
            if ziel in kampagnen_je_chain.get(kette, set()):
                # Schon verknüpft (Datenbank oder frühere Zeile): Der Typ
                # muss passen. Abweichung aus der Datei selbst bricht ab;
                # aus der Datenbank nur mit ueberschreiben (geaendert).
                typ_alt = typ_je_link[(kette, ziel)]
                if typ_alt == typ_datei:
                    continue
                if (kette, ziel) in datei_typen:
                    raise ValueError(
                        f"Gruppe {gruppe}, Rang {rang}: Kette {schluessel} "
                        f"hätte in dieser Datei bereits den Typ {typ_alt!r} — "
                        f"{typ_datei!r} widerspricht dem"
                    )
                if not ueberschreiben:
                    raise ValueError(
                        f"Gruppe {gruppe}, Rang {rang}: Kette {schluessel} hat "
                        f"in der Kampagne bereits den Typ {typ_alt!r} — "
                        f"{typ_datei!r} nur mit ueberschreiben=True"
                    )
                plan.typ_aenderungen.append((kette, ziel, typ_datei))
                typ_je_link[(kette, ziel)] = typ_datei
                datei_typen.add((kette, ziel))
                zeile_geaendert = True
                zeile_schreibt = True
            else:
                kampagnen_je_chain.setdefault(kette, set()).add(ziel)
                typ_je_link[(kette, ziel)] = typ_datei
                datei_typen.add((kette, ziel))
                plan.neue_links.append((kette, ziel, typ_datei))
                zaehler["verknuepfungen_neu"] += 1
                ketten_je_kampagne.setdefault(ziel, set()).add(kette)
                zeile_schreibt = True
        if ziel > 0 and zeile_schreibt:
            # Zeiten einer bestehenden Kampagne nachziehen (neue Kampagnen
            # bekommen ihre Zeiten beim Anlegen).
            plan.betroffene_kampagnen.add(ziel)

        if zeile_geaendert:
            zaehler["geaendert"] += 1
        elif gemeinsam:
            zaehler["unveraendert"] += 1
        else:
            zaehler["neu_bestaetigt"] += 1

    plan.ergebnis = KampagnenEinleseErgebnis(**zaehler)
    return plan


def _plan_ausfuehren(verbindung, plan: _SchreibPlan, *, jetzt: datetime) -> None:
    """Führt den geprüften Plan aus: erst die Löschungen (damit der
    Primärschlüssel frei wird), dann Kampagnen, Verknüpfungen, Typen und
    Ablehnungen. Läuft innerhalb der Transaktion von
    ``kampagnen_urteile_einlesen``."""
    for chain_id_a, chain_id_b, typ in sorted(plan.loeschbare_ablehnungen):
        verbindung.execute(
            delete(campaign_ablehnungen).where(
                campaign_ablehnungen.c.chain_id_a == chain_id_a,
                campaign_ablehnungen.c.chain_id_b == chain_id_b,
                campaign_ablehnungen.c.typ == typ,
            )
        )

    echte_id_je_temp: dict[int, int] = {}
    for temp_id in plan.neue_kampagnen:
        werte = _kampagnen_werte(plan.ketten_je_kampagne[temp_id], plan.ketten_zeile_je_id)
        echte_id_je_temp[temp_id] = verbindung.execute(
            insert(campaigns).values(**werte)
        ).inserted_primary_key[0]

    for chain_id, ziel, typ in plan.neue_links:
        verbindung.execute(
            insert(campaign_links).values(
                campaign_id=echte_id_je_temp.get(ziel, ziel),
                chain_id=chain_id,
                beziehungstyp=typ,
                erkennung="manuell",
                bestaetigt_am=jetzt,
            )
        )

    for chain_id, ziel, typ in plan.typ_aenderungen:
        verbindung.execute(
            update(campaign_links)
            .where(
                campaign_links.c.chain_id == chain_id,
                campaign_links.c.campaign_id == ziel,
            )
            .values(beziehungstyp=typ, bestaetigt_am=jetzt)
        )

    for kampagne_id in sorted(plan.betroffene_kampagnen):
        werte = _kampagnen_werte(
            plan.ketten_je_kampagne[kampagne_id], plan.ketten_zeile_je_id
        )
        verbindung.execute(
            update(campaigns)
            .where(campaigns.c.campaign_id == kampagne_id)
            .values(**werte)
        )

    for (chain_id_a, chain_id_b, typ), notiz in sorted(plan.neue_ablehnungen.items()):
        verbindung.execute(
            insert(campaign_ablehnungen).values(
                chain_id_a=chain_id_a,
                chain_id_b=chain_id_b,
                typ=typ,
                notiz=notiz,
                erstellt_am=jetzt,
            )
        )


def _kampagnen_werte(ketten_ids: set[int], ketten_zeile_je_id: dict[int, dict]) -> dict:
    """``underlying``/``eroeffnet_am``/``beendet_am`` einer Kampagne aus
    ihren Ketten (Kontosicht): früheste Eröffnung, ``beendet_am`` leer, solange
    eine Kette offen ist, sonst die späteste Schließung. Bei mehreren
    Underlyings (über ``independent`` möglich) gewinnt das alphabetisch
    erste — deterministisch (Annahme, Regel 10; siehe Modul-Docstring)."""
    zeilen = [ketten_zeile_je_id[chain_id] for chain_id in sorted(ketten_ids)]
    if not zeilen:
        raise ValueError(
            "Kampagne ohne Ketten der Kontosicht — keine Zeiten bestimmbar"
        )
    return dict(
        underlying=min(z["underlying"] for z in zeilen),
        eroeffnet_am=min(z["eroeffnet_am"] for z in zeilen),
        beendet_am=(
            None
            if any(z["beendet_am"] is None for z in zeilen)
            else max(z["beendet_am"] for z in zeilen)
        ),
    )
