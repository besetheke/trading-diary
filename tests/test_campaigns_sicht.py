"""Abnahmetests für AP-05s: Sichtbarkeit offener Campaign-Kandidaten.

Geschrieben nach §11.2 durch das starke Modell — für das günstige Modell
unveränderlich. Maßgeblich ist der Vertrag in `auftraege/AP-05s.md`.

Zwei Ebenen: reine Zähllogik (`journal.campaigns_sicht.offene_kandidaten_zaehlen`,
ohne DB) und die Anbindung an `journal rebuild` (mit DB, eigener,
in sich geschlossener Bestand — nicht `fixtures_rebuild`, siehe
`tests/test_rebuild_oa.py` für die Begründung desselben Musters).
"""

from datetime import date, datetime
from decimal import Decimal

from fixtures_rebuild import befuelle
from sqlalchemy import insert, select

from engine.campaigns import CampaignKandidat
from journal.campaigns_sicht import offene_kandidaten_zaehlen
from journal.db import create_db_engine
from journal.rebuild import rebuild
from journal.schema import campaign_links, campaigns, chains

# ---------------------------------------------------------------------------
# Reine Zähllogik
# ---------------------------------------------------------------------------


def test_kandidat_ohne_gemeinsame_kampagne_ist_offen():
    kette_a, kette_b = object(), object()
    kandidat = CampaignKandidat(typ="ic", kette_a=kette_a, kette_b=kette_b)
    chain_id_je_objekt = {id(kette_a): 1, id(kette_b): 2}

    assert offene_kandidaten_zaehlen([kandidat], {}, chain_id_je_objekt) == 1


def test_kandidat_mit_gemeinsamer_kampagne_ist_nicht_offen():
    kette_a, kette_b = object(), object()
    kandidat = CampaignKandidat(typ="ic", kette_a=kette_a, kette_b=kette_b)
    chain_id_je_objekt = {id(kette_a): 1, id(kette_b): 2}
    kampagnen_je_chain_id = {1: {100}, 2: {100}}

    assert offene_kandidaten_zaehlen([kandidat], kampagnen_je_chain_id, chain_id_je_objekt) == 0


def test_kandidat_mit_verschiedenen_kampagnen_bleibt_offen():
    # Beide Ketten sind bereits klassifiziert, aber nicht miteinander —
    # keine gemeinsame Kampagne heißt: dieser Kandidat ist immer noch offen.
    kette_a, kette_b = object(), object()
    kandidat = CampaignKandidat(typ="financing", kette_a=kette_a, kette_b=kette_b)
    chain_id_je_objekt = {id(kette_a): 1, id(kette_b): 2}
    kampagnen_je_chain_id = {1: {100}, 2: {200}}

    assert offene_kandidaten_zaehlen([kandidat], kampagnen_je_chain_id, chain_id_je_objekt) == 1


# ---------------------------------------------------------------------------
# Anbindung an journal rebuild — eigener, in sich geschlossener Bestand:
# SPX Put und SPX Call, gleiche Expiry, überlappend -> IC-Kandidat.
# ---------------------------------------------------------------------------

INSTRUMENTE_IC = [
    dict(conid=601, symbol="SPX   260918P5000", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5000"), right="P",
         multiplikator=Decimal("100"), waehrung="USD"),
    dict(conid=602, symbol="SPX   260918C5200", underlying="SPX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("5200"), right="C",
         multiplikator=Decimal("100"), waehrung="USD"),
]

AUSFUEHRUNGEN_IC = [
    # Put-Seite, bleibt offen.
    dict(exec_id="P1", conid=601, side="SELL", preis=Decimal("12.00"),
         handelszeit=datetime(2026, 9, 1, 10, 0, 0)),
    # Call-Seite, andere Kette, überlappt zeitlich, bleibt offen.
    dict(exec_id="C1", conid=602, side="SELL", preis=Decimal("10.00"),
         handelszeit=datetime(2026, 9, 1, 10, 5, 0)),
]


def _chain_ids(db_pfad) -> list[int]:
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        return [z["chain_id"] for z in verbindung.execute(select(chains)).mappings()]


def test_ic_kandidat_ohne_klassifikation_ist_offen(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_IC, instrumente_=INSTRUMENTE_IC)

    ergebnis = rebuild(migrated_db)

    assert ergebnis.campaign_kandidaten_offen == 1


def test_bereits_verknuepfte_ketten_zaehlen_nicht_mehr_als_offen(migrated_db):
    befuelle(migrated_db, ausfuehrungen=AUSFUEHRUNGEN_IC, instrumente_=INSTRUMENTE_IC)
    rebuild(migrated_db)
    chain_ids = _chain_ids(migrated_db)
    assert len(chain_ids) == 2

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        campaign_id = verbindung.execute(
            insert(campaigns).values(
                underlying="SPX", eroeffnet_am=datetime(2026, 9, 1, 10, 0, 0),
                beendet_am=None, netto_pnl_eur=None,
            )
        ).inserted_primary_key[0]
        for chain_id in chain_ids:
            verbindung.execute(
                insert(campaign_links).values(
                    campaign_id=campaign_id, chain_id=chain_id, beziehungstyp="ic_leg",
                    erkennung="manuell", bestaetigt_am=datetime(2026, 9, 2, 8, 0, 0),
                )
            )

    ergebnis = rebuild(migrated_db)

    assert ergebnis.campaign_kandidaten_offen == 0
