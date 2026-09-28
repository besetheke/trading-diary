"""Chains → Campaign-Kandidaten (AP-05k, Plan §6 „Kandidatenregeln").

Zwei Kandidatenregeln als reine Funktion über bereits gebildete Ketten
(``engine.chains.Chain``): der **IC-Kandidat** — zwei Ketten, die zusammen
einen Iron Condor ergeben könnten — und der **Financing-Kandidat** — eine
neue Kette als mögliche Gegenfinanzierung eines Rolls.

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

# Entscheidung 3 in auftraege/AP-05v.md: „im zeitlichen Umfeld eines Rolls"
# ohne Zahl im Plan. Gemessen am echten Bestand (nur Zählwerte, Regel 2)
# ergaben sich 161 Paare bei 1 Stunde, 351 bei 6, 518 bei 24, 1.029 bei 72,
# 2.193 bei einer Woche — kein natürlicher Sprung. 24 Stunden (ein
# Handelstag) ist die plausibelste Lesart und als Annahme in
# OFFENE_FRAGEN.md festgehalten. Benannter Modulwert, keine Zahl im Code.
FINANCING_FENSTER = timedelta(hours=24)

# Ende einer offenen Kette im Intervallvergleich (Entscheidung 1):
# ``beendet_am = None`` heißt „bis auf Weiteres", zählt also als unbegrenzt.
_UNBEGRENZT = datetime.max


@dataclass(frozen=True)
class CampaignKandidat:
    """Ein Vorschlag, keine Tatsache (Plan §6, Block B, Regel 5 sinngemäß).

    ``typ`` ist ``"ic"`` oder ``"financing"``. ``kette_a`` ist stets die
    chronologisch früher eröffnete der beiden Ketten (``eroeffnet_am``, bei
    Gleichstand der Naturschlüssel); bei ``"financing"`` ist das genau die
    Bestandskette mit dem Roll — das ergibt sich zwangsläufig aus der Regel.
    """

    typ: str
    kette_a: Chain
    kette_b: Chain


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


def _intervalle_ueberlappen(a: Chain, b: Chain) -> bool:
    """Überlappen ``[eroeffnet_am, beendet_am oder unbegrenzt)`` beider
    Ketten (Vertrag 4, Entscheidung 1)? Eine Kette schließt per Definition
    genau einmal, „keine zwischenzeitliche Schließung" ist damit automatisch
    erfüllt — der Intervallvergleich trägt die ganze Bedingung."""
    a_ende = a.beendet_am if a.beendet_am is not None else _UNBEGRENZT
    b_ende = b.beendet_am if b.beendet_am is not None else _UNBEGRENZT
    return a.eroeffnet_am < b_ende and b.eroeffnet_am < a_ende


def _erste_expiry(kette: Chain):
    """Expiry des letzten Glieds — der Zustand, der gerade gilt (Vertrag 4,
    Entscheidung 2), nicht die Historie der Kette."""
    return kette.glieder[-1].structure.expiry


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
    return (
        a.underlying == b.underlying
        and _seite_gegenlaeufig(a, b)
        and _erste_expiry(a) is not None
        and _erste_expiry(a) == _erste_expiry(b)
        and _intervalle_ueberlappen(a, b)
    )


def _financing_kandidat(a: Chain, b: Chain) -> bool:
    roll_zeitpunkt = _erster_roll_zeitpunkt(a)
    return (
        roll_zeitpunkt is not None
        and a.underlying == b.underlying
        and _seite_gegenlaeufig(a, b)
        and abs(b.eroeffnet_am - roll_zeitpunkt) <= FINANCING_FENSTER
    )


def campaign_kandidaten(chains: Iterable[Chain]) -> tuple[CampaignKandidat, ...]:
    """IC- und Financing-Kandidaten über die gegebenen Ketten (AP-05v,
    Vertrag 1–7).

    Reine Funktion: das Ergebnis hängt nicht von der Reihenfolge der
    Eingabe ab — sortiert nach ``typ`` (``"financing"`` vor ``"ic"``), dann
    Naturschlüssel von ``kette_a``, dann von ``kette_b``.
    """
    # Dieselbe Kette zweimal in der Eingabe wäre derselbe Naturschlüssel;
    # sie erzeugt keinen Kandidaten gegen sich selbst.
    eindeutig: dict[str, Chain] = {}
    for kette in chains:
        eindeutig.setdefault(_naturschluessel(kette), kette)
    ketten = list(eindeutig.values())

    kandidaten: list[CampaignKandidat] = []
    for i, a in enumerate(ketten):
        for b in ketten[i + 1 :]:
            fruehere, spaetere = _chronologisch(a, b)
            if _ic_kandidat(a, b):
                kandidaten.append(
                    CampaignKandidat(typ="ic", kette_a=fruehere, kette_b=spaetere)
                )
            # A ist die Bestandskette mit dem Roll (Vertrag 5) — sie ist
            # kette_a, unabhängig davon, in welcher Reihenfolge das Paar
            # hier anliegt; deshalb der zweite Durchlauf mit getauschten
            # Rollen.
            if _financing_kandidat(b, a):
                kandidaten.append(
                    CampaignKandidat(typ="financing", kette_a=b, kette_b=a)
                )
            if _financing_kandidat(a, b):
                kandidaten.append(
                    CampaignKandidat(typ="financing", kette_a=a, kette_b=b)
                )

    kandidaten.sort(
        key=lambda k: (
            k.typ,
            _naturschluessel(k.kette_a),
            _naturschluessel(k.kette_b),
        )
    )
    return tuple(kandidaten)


def _chronologisch(a: Chain, b: Chain) -> tuple[Chain, Chain]:
    """Die beiden Ketten in der Reihenfolge (kette_a, kette_b): früher
    eröffnet zuerst, bei Gleichstand nach Naturschlüssel (Vertrag 2)."""
    if (a.eroeffnet_am, _naturschluessel(a)) <= (b.eroeffnet_am, _naturschluessel(b)):
        return a, b
    return b, a
