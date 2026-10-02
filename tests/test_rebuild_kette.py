"""Abnahmetests für AP-04sw: Persistenz der Kettensicht (`sicht`-Feld,
Wiring in `journal/rebuild.py`, `journal/durchsicht.py`, `api/app.py`).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-04sw.md`.

Eigener, in sich geschlossener Bestand (SPX/RUT) nach demselben Muster
wie `tests/test_kettensicht.py` — AUSFUEHRUNGEN_SPX reproduziert exakt
das OF-36-Muster (A1 wird umgeleitet, B1 eröffnet seine eigene Struktur
erst in der Kettensicht). `fixtures_rebuild.AUSFUEHRUNGEN` bleibt
unberührt (gemeinsames Fixture vieler bestehender, unveränderlicher
Tests, die ihre Zeilenzahlen genau prüfen, Regel 1).
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import befuelle
from sqlalchemy import select

from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import chain_links, chains, legs, structures

INSTRUMENTE = [
    dict(conid=601, symbol="SPX   260918P5000", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5000"), right="P",
         multiplikator=Decimal("100"), waehrung="USD"),
    dict(conid=701, symbol="SPX   260918C5200", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5200"), right="C",
         multiplikator=Decimal("100"), waehrung="USD"),
]

# Das OF-36-Muster: A1 (oa_trade 100) wird von B1 (oa_rolle 'Open Order',
# oa_trade 200) kontoweit geschlossen; B1 eröffnet seine eigene Struktur
# (mit B2) erst in der Kettensicht, geschlossen durch die freie B3.
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


def _zeilen(db_pfad, tabelle, **wo) -> list[dict]:
    engine = create_db_engine(db_pfad)
    stmt = select(tabelle)
    for spalte, wert in wo.items():
        stmt = stmt.where(tabelle.c[spalte] == wert)
    with engine.begin() as verbindung:
        return [dict(z) for z in verbindung.execute(stmt).mappings()]


def test_jede_abgeleitete_tabelle_bekommt_eine_sicht(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)

    for tabelle in (legs, structures, chains, chain_links):
        zeilen = _zeilen(migrated_db, tabelle)
        assert zeilen, f"{tabelle.name}: keine Zeilen geschrieben"
        assert all(z["sicht"] in ("konto", "kette") for z in zeilen)
        assert any(z["sicht"] == "konto" for z in zeilen)
        assert any(z["sicht"] == "kette" for z in zeilen), (
            f"{tabelle.name}: keine Kettensicht-Zeile - B1 hätte eine eigene "
            "Struktur bekommen müssen"
        )


def test_bestehende_rebuild_ergebnis_felder_zaehlen_weiterhin_nur_die_kontosicht(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)

    ergebnis = rebuild(migrated_db)

    konto_strukturen = _zeilen(migrated_db, structures, sicht="konto")
    assert ergebnis.structures == len(konto_strukturen)
    konto_ketten = _zeilen(migrated_db, chains, sicht="konto")
    assert ergebnis.chains == len(konto_ketten)
    konto_legs = _zeilen(migrated_db, legs, sicht="konto")
    assert ergebnis.legs == len(konto_legs)


def test_vorgang_b_hat_in_der_kontosicht_nur_eine_struktur_in_der_kettensicht_zwei(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)

    # B2 allein bildet in der Kontosicht eine einbeinige Struktur (B1 fehlt).
    legs_konto_b2 = [
        z for z in _zeilen(migrated_db, legs, sicht="konto") if z["open_exec_id"] == "B2"
    ]
    assert len(legs_konto_b2) == 1
    structure_id_b2_konto = legs_konto_b2[0]["structure_id"]
    legs_dieser_struktur_konto = [
        z for z in _zeilen(migrated_db, legs, sicht="konto")
        if z["structure_id"] == structure_id_b2_konto
    ]
    assert len(legs_dieser_struktur_konto) == 1

    legs_kette_b2 = [
        z for z in _zeilen(migrated_db, legs, sicht="kette") if z["open_exec_id"] == "B2"
    ]
    assert len(legs_kette_b2) == 1
    structure_id_b2_kette = legs_kette_b2[0]["structure_id"]
    legs_dieser_struktur_kette = [
        z for z in _zeilen(migrated_db, legs, sicht="kette")
        if z["structure_id"] == structure_id_b2_kette
    ]
    # In der Kettensicht gehört B1s eigene Eröffnung zur selben Struktur.
    assert {z["open_exec_id"] for z in legs_dieser_struktur_kette} == {"B1", "B2"}


def test_jahresabgrenzung_kann_zwischen_den_sichten_abweichen(migrated_db):
    # AP-04s-Abnahme: B3 schließt in der Kontosicht nichts (bleibt offen,
    # kein realisiertes Ergebnis); in der Kettensicht schließt dieselbe
    # Ausführung B1s eigene Struktur (realisiertes Ergebnis). Das ist die
    # dokumentierte, erlaubte Abweichung innerhalb eines Jahres (Plan §5)
    # - keine Abfrage darf sie vermischen, aber sie dürfen sich unterscheiden.
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)

    konto_b3 = next(
        z for z in _zeilen(migrated_db, legs, sicht="konto") if z["open_exec_id"] == "B3"
    )
    assert konto_b3["offen_ja_nein"] is True
    assert konto_b3["brutto_pnl"] is None

    kette_b1 = next(
        z for z in _zeilen(migrated_db, legs, sicht="kette") if z["open_exec_id"] == "B1"
    )
    assert kette_b1["offen_ja_nein"] is False
    # Handrechnung: B1 (Buy 3.00) -> B3 (Sell 2.00), brutto =
    # (2.00-3.00)*1*100 = -100.00.
    assert kette_b1["brutto_pnl"] == Decimal("-100.00")


def test_zweiter_lauf_aendert_an_vorhandenen_sicht_zeilen_nichts_unerwartetes(migrated_db):
    # Abgleich statt Neuanlage (AP-04v) muss je Sicht getrennt funktionieren
    # - sonst würde ein zweiter Lauf dieselbe natur_schluessel+sicht-Zeile
    # verdoppeln oder die andere Sicht fälschlich löschen.
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)
    erster_lauf = {
        (z["sicht"], z["natur_schluessel"]): z["chain_id"]
        for z in _zeilen(migrated_db, chains)
    }

    rebuild(migrated_db)
    zweiter_lauf = {
        (z["sicht"], z["natur_schluessel"]): z["chain_id"]
        for z in _zeilen(migrated_db, chains)
    }

    assert zweiter_lauf == erster_lauf


def test_durchsicht_loest_naturschluessel_trotz_zwei_sichten_eindeutig_auf(migrated_db, tmp_path):
    # Seit AP-04sw ist natur_schluessel nur noch je Sicht eindeutig. Die
    # Rollkandidaten-Durchsicht (ein reines Kontosicht-Konzept) darf dadurch
    # nicht auf eine zufällige der beiden Zeilen (konto/kette) treffen, sonst
    # bricht der Rücklese-Check aus Vertrag 9 ("keine vorhandene Zeile") an
    # einer Stelle, die es vor AP-04sw nicht gab.
    pytest.importorskip("journal.durchsicht")
    from journal.durchsicht import kandidaten_ausschreiben  # noqa: PLC0415

    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)

    ziel = tmp_path / "kandidaten.xlsx"
    ergebnis = kandidaten_ausschreiben(migrated_db, ziel)

    assert ziel.exists()
    assert ergebnis.kandidaten >= 0


def test_api_liefert_nur_kontosicht_auch_wenn_kettensicht_zeilen_existieren(migrated_db):
    # Plan §5: „Keine Abfrage liefert Zeilen aus beiden Sichten in einer
    # Summe." Die Liste /ketten darf durch die neuen Kettensicht-Zeilen
    # nicht mehr Treffer zeigen als zuvor.
    pytest.importorskip("fastapi")
    pytest.importorskip("api.app")
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from api.app import erzeuge_app  # noqa: PLC0415

    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN, instrumente_=INSTRUMENTE)
    rebuild(migrated_db)

    konto_ketten = _zeilen(migrated_db, chains, sicht="konto")
    kette_ketten = _zeilen(migrated_db, chains, sicht="kette")
    assert len(kette_ketten) > 0  # sonst testet dieser Fall nichts

    with TestClient(erzeuge_app(migrated_db)) as klient:
        antwort = klient.get("/ketten", params={"limit": 100})
    assert antwort.status_code == 200
    treffer = antwort.json()["treffer"]

    assert antwort.json()["gesamt"] == len(konto_ketten)
    kette_chain_ids = {z["chain_id"] for z in kette_ketten}
    assert all(t["chain_id"] not in kette_chain_ids for t in treffer)
