"""Persistenz des OA-Abgleichs (AP-13wk, Plan §6, AP-13 — „Strategy und
Status ergänzen Kette und Strukturen").

Liest die importierten OA-Trades (``optionapp_trades``/``optionapp_legs``),
ruft die reine Funktion ``engine.oa_abgleich.oa_abgleich()`` mit den bereits
im Speicher gebildeten Ketten auf und schreibt ``oa_strategie``/
``oa_status``/``oa_erkennung`` auf die betroffene Kette **und** jede ihrer
Strukturen — derselbe Wert, denn OA kennt keine feinere Ebene als den Trade.

Die Naturschlüssel der betroffenen Ketten/Strukturen werden über
Objektidentität ermittelt (``id()``-Umkehrabbildung), nicht über
``journal.rebuild._kette_schluessel()`` importiert — ``rebuild.py``
importiert dieses Modul, der Rückweg wäre ein Zirkelimport.
"""

from collections.abc import Mapping

from sqlalchemy import select, update
from sqlalchemy.engine import Connection

from engine.chains import Chain as Kette
from engine.oa_abgleich import OALegSignatur, OATradeEintrag, oa_abgleich
from engine.structures import Structure as Struktur
from journal.schema import chains, optionapp_legs, optionapp_trades, structures


def oa_werte_schreiben(
    verbindung: Connection,
    kette_je_schluessel: dict[str, Kette],
    struktur_je_schluessel: dict[str, Struktur],
    struktur_id_je_schluessel: dict[str, int],
    ketten_id_je_schluessel: dict[str, int],
    exec_je_id: Mapping[str, Mapping],
    instrument_je_conid: Mapping[int, Mapping],
) -> tuple[int, int]:
    """OA-Werte schreiben und ``(Anzahl zugeordnet, Anzahl Fehler)``
    zurückgeben (Vertrag ``auftraege/AP-13w.md``).

    Nicht zugeordnete oder fehlerhafte OA-Trades schreiben nichts — die
    Fehler erscheinen nur als Zählwert (``RebuildErgebnis.oa_fehler``),
    sichtbar statt stillschweigend, aber ohne Abbruch: Ein OA-Fehler ist
    kein Datenintegritätsbruch.
    """
    # 1: importierte OA-Trades lesen — die Spalten tragen bereits die
    # passenden Typen (Vertrag), direkte Übernahme ohne Mapping.
    legs_je_trade_id: dict[int, list[OALegSignatur]] = {}
    for zeile in verbindung.execute(
        select(optionapp_legs).order_by(
            optionapp_legs.c.optionapp_trade_id, optionapp_legs.c.position
        )
    ).mappings():
        legs_je_trade_id.setdefault(zeile["optionapp_trade_id"], []).append(
            OALegSignatur(
                right=zeile["right"],
                strike=zeile["strike"],
                expiry=zeile["expiry"],
                richtung=zeile["richtung"],
                menge=zeile["menge"],
            )
        )
    # Der Primärschlüssel von optionapp_trades heißt `id` — genau die
    # Nummer, auf die optionapp_legs.optionapp_trade_id zeigt.
    oa_trades = [
        OATradeEintrag(
            oa_trade=zeile["oa_trade"],
            legs=tuple(legs_je_trade_id.get(zeile["id"], ())),
            profit=zeile["profit"],
            strategie=zeile["strategie"],
            status=zeile["status"],
        )
        for zeile in verbindung.execute(
            select(optionapp_trades).order_by(optionapp_trades.c.oa_trade)
        ).mappings()
    ]

    # 2: der reine Abgleich (AP-13k) über die bereits gebildeten Ketten.
    ergebnis = oa_abgleich(
        oa_trades, list(kette_je_schluessel.values()), exec_je_id, instrument_je_conid
    )

    # 3: Naturschlüssel über Objektidentität — z.chain ist dasselbe Objekt,
    # das in kette_je_schluessel steht (Vertrag), keine Kopie.
    kette_schluessel_je_objekt = {
        id(kette): schluessel for schluessel, kette in kette_je_schluessel.items()
    }
    struktur_schluessel_je_objekt = {
        id(struktur): schluessel
        for schluessel, struktur in struktur_je_schluessel.items()
    }

    # 4: gezielt überschreiben — die Baseline None stand seit
    # _struktur_zeile()/_kette_zeile(). Zeigen zwei OA-Nummern auf
    # dieselbe Kette, gewinnt deterministisch die spätere Zuordnung
    # (oa_abgleich sortiert nach oa_trade).
    for zuordnung in ergebnis.zuordnungen:
        kette_schluessel = kette_schluessel_je_objekt[id(zuordnung.chain)]
        verbindung.execute(
            update(chains)
            .where(chains.c.chain_id == ketten_id_je_schluessel[kette_schluessel])
            .values(
                oa_strategie=zuordnung.strategie,
                oa_status=zuordnung.status,
                oa_erkennung=zuordnung.erkennung,
            )
        )
        for glied in zuordnung.chain.glieder:
            struktur_schluessel = struktur_schluessel_je_objekt[id(glied.structure)]
            verbindung.execute(
                update(structures)
                .where(
                    structures.c.structure_id
                    == struktur_id_je_schluessel[struktur_schluessel]
                )
                .values(
                    oa_strategie=zuordnung.strategie,
                    oa_status=zuordnung.status,
                    oa_erkennung=zuordnung.erkennung,
                )
            )

    # 5: nur Zählwerte, keine Fehlerliste in der Datenbank (Vertragsgrenze).
    return len(ergebnis.zuordnungen), len(ergebnis.fehler)
