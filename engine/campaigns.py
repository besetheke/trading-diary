"""Chains → Campaign-Kandidaten (AP-05k, Plan §6 „Kandidatenregeln").

Zwei Kandidatenregeln als reine Funktion über bereits gebildete Ketten
(``engine.chains.Chain``): der **IC-Kandidat** — zwei Ketten, die zusammen
einen Iron Condor ergeben könnten — und der **Financing-Kandidat** — eine
neue Kette als mögliche Gegenfinanzierung eines Rolls.

Die Regeln folgen der Praxis des Nutzers (AP-05r, OF-71): Der IC-Kandidat
läuft über irgendein Gliederpaar mit gemeinsamer Expiry und überlappendem
Glied-Intervall — nicht nur über die letzten Glieder, denn wer beide
Seiten dauerhaft hält und einzeln rollt, hat selten am Ende dieselbe
Expiry. Ein „Doppel-Roll“ — beide Seiten in wenigen Minuten neu
aufgebaut — ist keine Gegenfinanzierung und wird herausgefiltert. Jeder
Kandidat trägt ``abstand`` und ``ueberlappung`` als Ranggrößen für die
Durchsicht; hier wird nicht danach sortiert.

Beides sind **Vorschläge, keine Tatsachen** (Plan §6, Block B, Regel 5
sinngemäß): nichts wird entschieden, nichts gespeichert, nichts
klassifiziert. Ob eine Kette „die IC-Seite" ist oder die Gegenfinanzierung,
ist eine Absichtsfrage und bleibt beim Nutzer.

Rein im Sinne von CLAUDE.md Regel 6: keine Datenbank, keine Uhrzeit, kein
Zufall. Der Naturschlüssel der Kette wird lokal gebildet, weil ein Import
aus ``journal.rebuild`` einen Zirkel schließen würde — dasselbe Muster wie
``journal/preise.py._schluessel``.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from engine.chains import Chain
from engine.structures import Structure

# Entscheidung 3 in auftraege/AP-05v.md: „im zeitlichen Umfeld eines Rolls"
# ohne Zahl im Plan. Gemessen am echten Bestand (nur Zählwerte, Regel 2)
# ergaben sich 161 Paare bei 1 Stunde, 351 bei 6, 518 bei 24, 1.029 bei 72,
# 2.193 bei einer Woche — kein natürlicher Sprung. 24 Stunden (ein
# Handelstag) ist die plausibelste Lesart und als Annahme in
# OFFENE_FRAGEN.md festgehalten. Benannter Modulwert, keine Zahl im Code.
FINANCING_FENSTER = timedelta(hours=24)

# AP-05r, Regel 2 (Nutzerangaben 08.10.2026, OF-71): Zu Beginn — und nach
# einem Take Profit — rollt oder setzt der Nutzer häufig beide Seiten neu
# auf, alles in wenigen Minuten. Eine Gegenseite-Kette, die so kurz nach
# dem Ende einer gleichseitigen Vorgängerkette eröffnet wird, ist
# Fortsetzung oder Wiedereinstieg der eigenen Seite, nicht die
# Gegenfinanzierung eines Rolls der anderen Seite. 15 Minuten,
# einschließlich der Grenze; benannter Modulwert, keine Zahl im Code.
DOPPEL_ROLL_FENSTER = timedelta(minutes=15)

# Ende einer offenen Kette oder Struktur im Intervallvergleich
# (Entscheidung 1): ``beendet_am``/``geschlossen_am`` gleich ``None``
# heißt „bis auf Weiteres", zählt also als unbegrenzt.
_UNBEGRENZT = datetime.max


@dataclass(frozen=True)
class CampaignKandidat:
    """Ein Vorschlag, keine Tatsache (Plan §6, Block B, Regel 5 sinngemäß).

    ``typ`` ist ``"ic"`` oder ``"financing"``. ``kette_a`` ist stets die
    chronologisch früher eröffnete der beiden Ketten (``eroeffnet_am``, bei
    Gleichstand der Naturschlüssel); bei ``"financing"`` ist das genau die
    Bestandskette mit dem Roll — das ergibt sich zwangsläufig aus der Regel.

    ``abstand`` und ``ueberlappung`` (AP-05r, Regel 3) sind Ranggrößen für
    die Durchsicht, kein Sortierkriterium hier: ``abstand`` ist bei ``"ic"``
    der Betrag zwischen den beiden Ketten-Eröffnungen, bei ``"financing"``
    der Betrag zwischen dem frühesten Roll der Bestandskette und der
    Eröffnung der Gegenseite. ``ueberlappung`` ist die gemeinsame Zeit der
    beiden Ketten — ``None``, wenn beide offen (unbegrenzt) sind.
    """

    typ: str
    kette_a: Chain
    kette_b: Chain
    abstand: timedelta | None = None
    ueberlappung: timedelta | None = None


def _naturschluessel(kette: Chain) -> str:
    """Naturschlüssel der Kette über die Legs ihres ersten Glieds
    (AP-05v, Vertrag 6) — lokal statt aus ``journal.rebuild``, s. Modulkopf."""
    return "k:" + "|".join(
        sorted(k.open_exec_id for k in kette.glieder[0].structure.leg_schluessel)
    )


def _seite_gegenlaeufig(a: Chain, b: Chain) -> bool:
    """Beide Seiten gesetzt und unterschiedlich — eine ``"Call"``, die andere
    ``"Put"`` (nicht ``"n.a."``, nicht ``None``). Dieselbe Bedingung für IC-
    und Financing-Kandidat (Vertrag 4/5: „Gegenseite")."""
    return {a.seite, b.seite} == {"Call", "Put"}


def _intervall(struktur: Structure) -> tuple[datetime, datetime]:
    """``[eroeffnet_am, geschlossen_am oder unbegrenzt)`` — das Intervall
    eines Glieds (AP-05r, Regel 1); offen zählt wie bei der Kette als
    unbegrenzt (Entscheidung 1)."""
    return (
        struktur.eroeffnet_am,
        _UNBEGRENZT if struktur.geschlossen_am is None else struktur.geschlossen_am,
    )


def _erster_roll_zeitpunkt(kette: Chain) -> datetime | None:
    """Frühester Rollzeitpunkt: die Eröffnung des rollenden Glieds — der
    Moment, in dem die Fortsetzung entstand (Vertrag 5), nicht die Schließung
    des vorigen Glieds."""
    roll_zeitpunkte = [
        glied.structure.eroeffnet_am
        for glied in kette.glieder
        if glied.verknuepfungstyp == "roll"
    ]
    return min(roll_zeitpunkte) if roll_zeitpunkte else None


def _ic_kandidat(a: Chain, b: Chain) -> bool:
    """AP-05r, Regel 1: Zwei Ketten sind ein IC-Kandidat, wenn es je Kette
    ein Glied gibt, die dieselbe (nicht leere) Expiry tragen und deren
    Glied-Intervalle überlappen — das ersetzt den Vergleich der letzten
    Glieder (Vertrag 4, Entscheidung 2)."""
    if a.underlying != b.underlying or not _seite_gegenlaeufig(a, b):
        return False
    for glied_a in a.glieder:
        expiry = glied_a.structure.expiry
        if expiry is None:  # leere Expiry (Aktie, Future) trägt nichts bei
            continue
        beginn_a, ende_a = _intervall(glied_a.structure)
        for glied_b in b.glieder:
            if glied_b.structure.expiry != expiry:
                continue
            beginn_b, ende_b = _intervall(glied_b.structure)
            if beginn_a < ende_b and beginn_b < ende_a:
                return True
    return False


def _financing_roll_zeitpunkt(a: Chain, b: Chain) -> datetime | None:
    """Frühester Rollzeitpunkt der Bestandskette ``a``, wenn (a, b) ein
    Financing-Kandidat ist (AP-05v, Vertrag 5), sonst ``None``. Der
    zurückgegebene Zeitpunkt ist zugleich der Bezugspunkt des ``abstand``
    (AP-05r, Regel 3)."""
    roll_zeitpunkt = _erster_roll_zeitpunkt(a)
    if (
        roll_zeitpunkt is not None
        and a.underlying == b.underlying
        and _seite_gegenlaeufig(a, b)
        and abs(b.eroeffnet_am - roll_zeitpunkt) <= FINANCING_FENSTER
    ):
        return roll_zeitpunkt
    return None


def _doppel_roll(b: Chain, ketten: list[Chain]) -> bool:
    """AP-05r, Regel 2: Ist die Gegenseite-Kette ``b`` die Fortsetzung oder
    der Wiedereinstieg der eigenen Seite — es gibt eine andere Kette ``c``
    mit demselben Basiswert und derselben Seite wie ``b``, die mit
    ``0 <= b.eroeffnet_am - c.beendet_am <= DOPPEL_ROLL_FENSTER`` vor ``b``
    endete —, ist das Paar kein Financing-Kandidat. Die Prüfung läuft über
    **alle** übergebenen Ketten, nicht nur über das Paar."""
    for c in ketten:
        if c is b or c.underlying != b.underlying or c.seite != b.seite:
            continue
        if c.beendet_am is None:
            continue  # eine offene Kette endete nicht
        if timedelta(0) <= b.eroeffnet_am - c.beendet_am <= DOPPEL_ROLL_FENSTER:
            return True
    return False


def _ueberlappung(a: Chain, b: Chain) -> timedelta | None:
    """Gemeinsame Zeit der beiden Ketten (AP-05r, Regel 3): vom späteren
    Beginn bis zum früheren Ende, mindestens 0. Beide Ketten offen heißt
    unbegrenzt — ``None``."""
    a_ende = _UNBEGRENZT if a.beendet_am is None else a.beendet_am
    b_ende = _UNBEGRENZT if b.beendet_am is None else b.beendet_am
    if a_ende == _UNBEGRENZT and b_ende == _UNBEGRENZT:
        return None
    gemeinsam = min(a_ende, b_ende) - max(a.eroeffnet_am, b.eroeffnet_am)
    return max(gemeinsam, timedelta(0))


def campaign_kandidaten(chains: Iterable[Chain]) -> tuple[CampaignKandidat, ...]:
    """IC- und Financing-Kandidaten über die gegebenen Ketten (AP-05v,
    Vertrag 1–7).

    Reine Funktion: das Ergebnis hängt nicht von der Reihenfolge der
    Eingabe ab — sortiert nach ``typ`` (``"financing"`` vor ``"ic"``), dann
    Naturschlüssel von ``kette_a``, dann von ``kette_b``. Die Ranggrößen
    ``abstand``/``ueberlappung`` gehen nicht in die Reihenfolge ein;
    sortiert wird erst in der Durchsicht (AP-05r, Regel 3).
    """
    # Dieselbe Kette zweimal in der Eingabe wäre derselbe Naturschlüssel;
    # sie erzeugt keinen Kandidaten gegen sich selbst.
    eindeutig: dict[str, Chain] = {}
    for kette in chains:
        eindeutig.setdefault(_naturschluessel(kette), kette)
    ketten = list(eindeutig.values())
    schluessel_je_kette = {id(kette): schluessel for schluessel, kette in eindeutig.items()}

    # Beide Kandidatenregeln verlangen denselben Basiswert und gegenläufige Seiten
    # (Call gegen Put). Statt alle Paare zu prüfen, laufen nur die Partner der
    # Gegenseite desselben Basiswerts, in der ursprünglichen Reihenfolge (AP-17g, M02:
    # bei Tausenden Ketten brauchte die Vollprüfung über zwei Minuten).
    positionen: dict[tuple[str, str], list[int]] = {}
    for position, kette in enumerate(ketten):
        positionen.setdefault((kette.underlying, kette.seite), []).append(position)
    je_basis_seite = {
        schluessel: [ketten[i] for i in liste] for schluessel, liste in positionen.items()
    }

    kandidaten: list[CampaignKandidat] = []
    for i, a in enumerate(ketten):
        if a.seite not in ("Call", "Put"):
            continue
        gegenseite = "Put" if a.seite == "Call" else "Call"
        for j in positionen.get((a.underlying, gegenseite), ()):
            if j <= i:
                continue
            b = ketten[j]
            fruehere, spaetere = _chronologisch(a, b)
            if _ic_kandidat(a, b):
                kandidaten.append(
                    CampaignKandidat(
                        typ="ic",
                        kette_a=fruehere,
                        kette_b=spaetere,
                        abstand=abs(spaetere.eroeffnet_am - fruehere.eroeffnet_am),
                        ueberlappung=_ueberlappung(fruehere, spaetere),
                    )
                )
            # A ist die Bestandskette mit dem Roll (Vertrag 5) — sie ist
            # kette_a, unabhängig davon, in welcher Reihenfolge das Paar
            # hier anliegt; deshalb der zweite Durchlauf mit getauschten
            # Rollen. Ein Doppel-Roll auf der Gegenseite (AP-05r, Regel 2)
            # filtert das Paar heraus.
            for bestand, gegenseite in ((b, a), (a, b)):
                roll_zeitpunkt = _financing_roll_zeitpunkt(bestand, gegenseite)
                if roll_zeitpunkt is None or _doppel_roll(
                    gegenseite, je_basis_seite.get((gegenseite.underlying, gegenseite.seite), [])
                ):
                    continue
                kandidaten.append(
                    CampaignKandidat(
                        typ="financing",
                        kette_a=bestand,
                        kette_b=gegenseite,
                        abstand=abs(gegenseite.eroeffnet_am - roll_zeitpunkt),
                        ueberlappung=_ueberlappung(bestand, gegenseite),
                    )
                )

    kandidaten.sort(
        key=lambda k: (
            k.typ,
            schluessel_je_kette[id(k.kette_a)],
            schluessel_je_kette[id(k.kette_b)],
        )
    )
    return tuple(kandidaten)


def _chronologisch(a: Chain, b: Chain) -> tuple[Chain, Chain]:
    """Die beiden Ketten in der Reihenfolge (kette_a, kette_b): früher
    eröffnet zuerst, bei Gleichstand nach Naturschlüssel (Vertrag 2)."""
    if a.eroeffnet_am != b.eroeffnet_am:
        return (a, b) if a.eroeffnet_am < b.eroeffnet_am else (b, a)
    return (a, b) if _naturschluessel(a) <= _naturschluessel(b) else (b, a)
