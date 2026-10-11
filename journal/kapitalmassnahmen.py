"""Kapitalmaßnahmen aus den Flex-Rohzeilen ableiten (AP-03vk).

``flex_corporate_actions`` trägt die Rohzeilen (AP-02); die Engine
(``engine.matching.bilde_legs``, AP-03vm) erwartet Maßnahmen als **Transfer**
von einer alten auf eine neue ``conid`` oder als reinen Zugang. Dieses Modul
macht aus den Rohzeilen solche Maßnahmen und füllt ``corporate_actions``.

Aufteilung wie sonst im Projekt:

- ``kapitalmassnahmen_ableiten`` ist rein — keine Datenbank, keine Uhr.
- ``kapitalmassnahmen_befuellen`` ist die Hülle: liest die Rohzeilen und
  **ergänzt** ``corporate_actions`` um Maßnahmen, die dort noch fehlen. Keine
  Zeile wird überschrieben oder gelöscht (Regel 4) — von Hand eingetragene
  Maßnahmen bleiben, der Aufruf ist wiederholbar.

Regeln (Regel 10: nichts wird geraten — was sich nicht eindeutig zuordnen
lässt, wird mit Grund unter ``uebersprungen`` gemeldet):

1. Gruppiert wird nach (``konto``, ``actionID``); dieselbe Zeile aus zwei
   Exporten (gleiche ``conid``, Menge und Zeit) zählt einmal.
2. Je Gruppe werden die Zeilen der Optionen (``OPT``/``FOP``) abgetrennt und
   übersprungen: Eine Optionsanpassung braucht das Kennzeichen am Instrument
   (OF-23, ``instruments.angepasst``) und ist aus den Zeilen allein nicht
   eindeutig zu paaren (gemessen: Call −9 neben Put +9 unter einer Aktion).
3. Bei den übrigen Zeilen: **ein Abgang und ein Zugang auf verschiedenen
   ``conid``s** sind ein Transfer (Menge je Seite aus ``quantity``).
4. **Ein einzelner Zugang** ist ein reiner Zugang — aber nur mit
   Kostenangabe (``costBasis`` ungleich leer und 0). Ohne sie würde ein Lot
   eröffnet, das nie ausgebucht wird (Rechte verfallen als ``ED``, das die
   Engine nicht abbildet): kein Scheinlot, keine stille Nullbasis (OF-23,
   Punkt 3). Die Zeile wird gemeldet.
5. Alles andere (Abgang ohne Zugang, mehrere Zeilen derselben ``conid``,
   mehrere Abgänge/Zugänge) wird gemeldet und nicht bewegt.

Offen (OFFENE_FRAGEN, OF-80): der Barteil einer Fusion (``TC`` mit
``proceeds``) wird nicht als realisiert gebucht; die Ausbuchung verfallener
Rechte (``ED``) und Optionsanpassungen sind nicht modelliert.
"""

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from journal.schema import corporate_actions, flex_corporate_actions

# Anlageklassen, deren Zeilen nicht abgeleitet werden (Regel 2).
_OPTIONEN = frozenset({"OPT", "FOP"})


@dataclass(frozen=True)
class Uebersprungen:
    aktion_id: str
    grund: str


@dataclass(frozen=True)
class Ableitung:
    massnahmen: tuple[dict, ...]
    uebersprungen: tuple[Uebersprungen, ...]


def _stichtag(text: str) -> date:
    """``20240123;202500`` oder ``20240123`` — nur das Datum zählt (der
    Stichtag der Engine hat keine Uhrzeit, OF-15)."""
    return date(int(text[:4]), int(text[4:6]), int(text[6:8]))


def _kosten(roh: Mapping) -> Decimal | None:
    wert = roh.get("costBasis")
    if wert is None or str(wert).strip() == "":
        return None
    betrag = abs(Decimal(str(wert)))
    return betrag if betrag != 0 else None


def _massnahme(
    konto: str, aktion_id: str, abgang: Mapping | None, zugang: Mapping,
    quellen: list[Mapping], kosten: Decimal | None,
) -> dict:
    return dict(
        aktion_id=aktion_id,
        konto=konto,
        typ=zugang.get("type") or "?",
        stichtag=_stichtag(zugang["dateTime"]),
        alter_conid=int(abgang["conid"]) if abgang is not None else None,
        alte_menge=abs(Decimal(str(abgang["quantity"]))) if abgang is not None else None,
        neuer_conid=int(zugang["conid"]),
        neue_menge=abs(Decimal(str(zugang["quantity"]))),
        kosten_neu=kosten,
        roh_json=json.dumps(
            sorted(quellen, key=lambda r: (str(r.get("conid")), str(r.get("quantity")))),
            sort_keys=True,
        ),
    )


def kapitalmassnahmen_ableiten(zeilen: Iterable[Mapping]) -> Ableitung:
    """Rohzeilen (``konto``, ``roh_json``) zu Maßnahmen nach den Regeln im
    Modulkopf (rein)."""
    gruppen: dict[tuple[str, str], list[dict]] = defaultdict(list)
    ohne_aktion = 0
    for zeile in zeilen:
        roh = json.loads(zeile["roh_json"])
        aktion_id = str(roh.get("actionID") or "").strip()
        if not aktion_id:
            ohne_aktion += 1
            continue
        gruppen[(zeile["konto"], aktion_id)].append(roh)

    massnahmen: list[dict] = []
    uebersprungen: list[Uebersprungen] = []
    if ohne_aktion:
        uebersprungen.append(
            Uebersprungen("", f"{ohne_aktion} Zeile(n) ohne actionID — keine Gruppierung möglich")
        )

    for (konto, aktion_id), rohe in gruppen.items():
        # Regel 1: dieselbe Zeile aus zwei Exporten zählt einmal.
        eindeutig = {
            (r.get("conid"), r.get("quantity"), r.get("dateTime")): r for r in rohe
        }
        zeilen_der_gruppe = [
            r for r in eindeutig.values() if r.get("conid") and Decimal(str(r["quantity"])) != 0
        ]
        optionen = [r for r in zeilen_der_gruppe if r.get("assetCategory") in _OPTIONEN]
        uebrige = [r for r in zeilen_der_gruppe if r.get("assetCategory") not in _OPTIONEN]
        if optionen:
            uebersprungen.append(
                Uebersprungen(
                    aktion_id,
                    f"Option/Optionsanpassung ({len(optionen)} Zeile(n)): Paarung nicht "
                    "eindeutig, nicht geraten (OF-23, OF-80)",
                )
            )
        if not uebrige:
            continue

        abgang = [r for r in uebrige if Decimal(str(r["quantity"])) < 0]
        zugang = [r for r in uebrige if Decimal(str(r["quantity"])) > 0]

        if len(uebrige) == 1 and zugang:
            kosten = _kosten(zugang[0])
            if kosten is None:
                uebersprungen.append(
                    Uebersprungen(
                        aktion_id,
                        "reiner Zugang ohne Kostenangabe: würde ein Lot ohne Ausbuchung "
                        "eröffnen — nicht geraten (OF-23, OF-80)",
                    )
                )
            else:
                massnahmen.append(
                    _massnahme(konto, aktion_id, None, zugang[0], uebrige, kosten)
                )
        elif len(abgang) == 1 and len(zugang) == 1:
            if abgang[0]["conid"] == zugang[0]["conid"]:
                uebersprungen.append(
                    Uebersprungen(
                        aktion_id, "Abgang und Zugang auf derselben conid — kein Transfer"
                    )
                )
            else:
                massnahmen.append(
                    _massnahme(konto, aktion_id, abgang[0], zugang[0], uebrige, None)
                )
        elif abgang and not zugang:
            uebersprungen.append(
                Uebersprungen(
                    aktion_id, "Abgang ohne Zugang (Ausbuchung): nicht modelliert (OF-80)"
                )
            )
        else:
            uebersprungen.append(
                Uebersprungen(
                    aktion_id,
                    f"uneindeutig: {len(abgang)} Abgang/Abgänge, {len(zugang)} Zugang/Zugänge "
                    "— nicht geraten",
                )
            )

    massnahmen.sort(key=lambda m: (m["stichtag"], m["aktion_id"], m["konto"]))
    uebersprungen.sort(key=lambda u: (u.aktion_id, u.grund))
    return Ableitung(massnahmen=tuple(massnahmen), uebersprungen=tuple(uebersprungen))


def kapitalmassnahmen_befuellen(verbindung: Connection) -> Ableitung:
    """Leitet aus ``flex_corporate_actions`` ab und ergänzt ``corporate_actions``
    um fehlende Maßnahmen (Schlüssel: Konto, Aktion, alte und neue ``conid``).
    Vorhandene Zeilen bleiben unverändert (Regel 4); wiederholbar."""
    rohzeilen = [
        dict(z)
        for z in verbindung.execute(
            select(flex_corporate_actions.c.konto, flex_corporate_actions.c.roh_json)
        ).mappings()
    ]
    ergebnis = kapitalmassnahmen_ableiten(rohzeilen)
    vorhanden = {
        (z["konto"], z["aktion_id"], z["alter_conid"], z["neuer_conid"])
        for z in verbindung.execute(
            select(
                corporate_actions.c.konto,
                corporate_actions.c.aktion_id,
                corporate_actions.c.alter_conid,
                corporate_actions.c.neuer_conid,
            )
        ).mappings()
    }
    for massnahme in ergebnis.massnahmen:
        schluessel = (
            massnahme["konto"], massnahme["aktion_id"],
            massnahme["alter_conid"], massnahme["neuer_conid"],
        )
        if schluessel not in vorhanden:
            verbindung.execute(insert(corporate_actions).values(**massnahme))
    return ergebnis
