"""Abnahmetests für AP-04sz: Bestätigte Rolls (`chain_overrides`) gelten auch
in der Kettensicht (OF-61).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-04sz.md`.

Regel in einem Satz: Ein Override ist eine Aussage über das reale Geschehen
(„diese Struktur setzt jene Kette fort") und wird deshalb einmal gegeben,
in der Kontosicht, wo der Nutzer ihn sieht. Die Kettensicht übernimmt ihn
über die Naturschlüssel: Struktur und Kette müssen dort unter demselben
Naturschlüssel existieren. Fehlt eine von beiden (die Kettensicht hat andere
Strukturen, wo Ausführungen umgeleitet sind), wird der Override dort nicht
angewandt, gezählt und nie als Fehler behandelt.
"""

from datetime import date, datetime
from decimal import Decimal

from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import chain_links, chain_overrides, chains, structures


def _zeilen(db_pfad, tabelle, sicht) -> list[dict]:
    stmt = select(tabelle).where(tabelle.c.sicht == sicht)
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return [dict(z) for z in verbindung.execute(stmt).mappings().all()]


def _je_schluessel(db_pfad, tabelle, sicht) -> dict:
    return {z["natur_schluessel"]: z for z in _zeilen(db_pfad, tabelle, sicht)}


def _glieder(db_pfad, sicht) -> dict:
    """{Struktur-Naturschlüssel: chain_links-Zeile} einer Sicht."""
    strukturen = {
        z["structure_id"]: z["natur_schluessel"] for z in _zeilen(db_pfad, structures, sicht)
    }
    return {strukturen[z["structure_id"]]: z for z in _zeilen(db_pfad, chain_links, sicht)}


def _override(db_pfad, ziel_kette: str, struktur: str, urteil="bestaetigt") -> None:
    """Der Nutzer entscheidet in der Kontosicht (dort stehen seine Listen)."""
    ketten = _je_schluessel(db_pfad, chains, "konto")
    strukturen = _je_schluessel(db_pfad, structures, "konto")
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        verbindung.execute(
            insert(chain_overrides).values(
                chain_id=ketten[ziel_kette]["chain_id"],
                structure_id=strukturen[struktur]["structure_id"],
                notiz="Tranchen von Hand gebündelt",
                erstellt_am=datetime(2026, 9, 20, 8, 0, 0),
                urteil=urteil,
            )
        )


def _overrides(db_pfad) -> list[dict]:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return [dict(z) for z in verbindung.execute(select(chain_overrides)).mappings().all()]


# ---------------------------------------------------------------------------
# Bestand 1: die Aktientranchen A1/A2 aus fixtures_rebuild — in beiden Sichten
# gleiche Naturschlüssel (keine umgeleitete Ausführung).
# ---------------------------------------------------------------------------


def test_bestaetigter_override_gilt_auch_in_der_kettensicht(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    ketten_vorher = len(_zeilen(migrated_db, chains, "kette"))
    _override(migrated_db, ziel_kette="k:A1", struktur="A2")

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_angewandt == 1  # Kontosicht, wie bisher
    assert ergebnis.overrides_kette_angewandt == 1
    assert ergebnis.overrides_kette_ohne_entsprechung == 0
    ketten = _je_schluessel(migrated_db, chains, "kette")
    assert "k:A2" not in ketten, "die leer gewordene Kette entfällt (wie in der Kontosicht)"
    assert len(ketten) == ketten_vorher - 1
    glieder = _glieder(migrated_db, "kette")
    assert glieder["A2"]["chain_id"] == ketten["k:A1"]["chain_id"]
    assert glieder["A2"]["erkennung"] == "manuell"
    assert glieder["A2"]["sicht"] == "kette"


def test_kettensicht_kennzahlen_der_gebuendelten_kette_stimmen(migrated_db):
    # Von Hand: A1 eröffnet am 02.03.2026 10:00, A2 am 04.05.2026; beide
    # offen -> zwei Glieder, anzahl_rolls 1, offen, Endzustand 'Offen'.
    befuelle(migrated_db)
    rebuild(migrated_db)
    _override(migrated_db, ziel_kette="k:A1", struktur="A2")
    rebuild(migrated_db)

    kette = _je_schluessel(migrated_db, chains, "kette")["k:A1"]
    assert kette["eroeffnet_am"] == datetime(2026, 3, 2, 10, 0, 0)
    assert kette["anzahl_rolls"] == 1
    assert kette["beendet_am"] is None
    assert kette["endzustand"] == "Offen"
    glieder = _glieder(migrated_db, "kette")
    assert glieder["A1"]["sequenz"] == 1
    assert glieder["A1"]["verknuepfungstyp"] == "open"
    assert glieder["A2"]["sequenz"] == 2
    assert glieder["A2"]["verknuepfungstyp"] == "roll"


def test_die_kontosicht_bleibt_vom_kettensicht_override_unberuehrt(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    _override(migrated_db, ziel_kette="k:A1", struktur="A2")
    rebuild(migrated_db)

    konto = _je_schluessel(migrated_db, chains, "konto")
    glieder = _glieder(migrated_db, "konto")
    assert "k:A2" not in konto
    assert glieder["A2"]["chain_id"] == konto["k:A1"]["chain_id"]
    assert all(z["sicht"] == "konto" for z in _zeilen(migrated_db, chain_links, "konto"))
    # Die Sichten teilen keine Zeilen: andere chain_ids je Sicht.
    kette = _je_schluessel(migrated_db, chains, "kette")
    assert kette["k:A1"]["chain_id"] != konto["k:A1"]["chain_id"]


def test_zweiter_lauf_aendert_nichts_und_der_override_bleibt_stehen(migrated_db):
    befuelle(migrated_db)
    rebuild(migrated_db)
    _override(migrated_db, ziel_kette="k:A1", struktur="A2")
    rebuild(migrated_db)
    vorher = (_glieder(migrated_db, "kette"), _overrides(migrated_db))

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_kette_angewandt == 1
    assert (_glieder(migrated_db, "kette"), _overrides(migrated_db)) == vorher


def test_abgelehnter_kandidat_aendert_die_kettensicht_nicht(migrated_db):
    # Ablehnungen sind ein Kontosicht-Konzept (Rollkandidaten-Liste); in der
    # Kettensicht verknüpft nichts und es wird auch nichts als fehlend gezählt.
    befuelle(migrated_db)
    rebuild(migrated_db)
    vorher = _glieder(migrated_db, "kette")
    _override(migrated_db, ziel_kette="k:A1", struktur="A2", urteil="abgelehnt")

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_kette_angewandt == 0
    assert ergebnis.overrides_kette_ohne_entsprechung == 0
    assert _glieder(migrated_db, "kette") == vorher


# ---------------------------------------------------------------------------
# Bestand 2: das OF-36-Muster (wie tests/test_rebuild_kette.py). Die Struktur
# 'B3' gibt es nur in der Kontosicht (in der Kettensicht schließt B3 die
# Eröffnung B1 und hat keine eigene Struktur).
# ---------------------------------------------------------------------------

INSTRUMENTE = [
    dict(conid=601, symbol="SPX   260918P5000", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5000"), right="P",
         multiplikator=Decimal("100"), waehrung="USD"),
    dict(conid=701, symbol="SPX   260918C5200", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5200"), right="C",
         multiplikator=Decimal("100"), waehrung="USD"),
]

AUSFUEHRUNGEN = [
    dict(exec_id="A1", conid=601, side="SELL", preis=Decimal("12.00"),
         handelszeit=datetime(2026, 9, 1, 10, 0, 0), oa_trade="100", oa_order="1",
         oa_rolle="Open Order"),
    dict(exec_id="B1", conid=601, side="BUY", preis=Decimal("3.00"),
         handelszeit=datetime(2026, 9, 5, 10, 0, 0), oa_trade="200", oa_order="1",
         oa_rolle="Open Order"),
    dict(exec_id="B2", conid=701, side="SELL", preis=Decimal("5.00"),
         handelszeit=datetime(2026, 9, 5, 10, 0, 0), oa_trade="200", oa_order="1",
         oa_rolle="Open Order"),
    dict(exec_id="B3", conid=601, side="SELL", preis=Decimal("2.00"),
         handelszeit=datetime(2026, 9, 10, 10, 0, 0), oa_trade="200", oa_order="2",
         oa_rolle="Close Order"),
]


def test_override_ohne_entsprechung_in_der_kettensicht_wird_gezaehlt_nicht_angewandt(
    migrated_db,
):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)
    assert "B3" in _je_schluessel(migrated_db, structures, "konto")
    assert "B3" not in _je_schluessel(migrated_db, structures, "kette")
    kette_vorher = _glieder(migrated_db, "kette")
    _override(migrated_db, ziel_kette="k:A1", struktur="B3")

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_angewandt == 1  # in der Kontosicht schon
    assert ergebnis.overrides_kette_angewandt == 0
    assert ergebnis.overrides_kette_ohne_entsprechung == 1
    assert _glieder(migrated_db, "kette") == kette_vorher
    assert len(_overrides(migrated_db)) == 1  # Benutzerdaten bleiben stehen (Regel 4)


def test_summen_beider_sichten_bleiben_mit_override_gleich(migrated_db):
    # Ein Override verschiebt nur die Zuordnung zu Ketten, nie Legs: die
    # Leg-Zeilen beider Sichten bleiben unverändert (nur die Kettenbildung
    # ändert sich).
    from journal.schema import legs  # noqa: PLC0415

    befuelle(migrated_db)
    rebuild(migrated_db)
    legs_vorher = {s: len(_zeilen(migrated_db, legs, s)) for s in ("konto", "kette")}
    _override(migrated_db, ziel_kette="k:A1", struktur="A2")

    rebuild(migrated_db)

    assert {s: len(_zeilen(migrated_db, legs, s)) for s in ("konto", "kette")} == legs_vorher
