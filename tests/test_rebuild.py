"""Abnahmetests für die Persistenz der Ketten (AP-04p).

Geschrieben nach §11.2 des Plans durch das starke Modell (AP-04v) — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-04v.md`.

Das Modul springt still ab, solange `journal/rebuild.py` nicht existiert;
sobald es existiert, laufen alle Tests scharf — dieselbe Regel wie bei
`tests/test_matching.py`.

Die Ausführungen liegen in `tests/fixtures_rebuild.py` und sind frei
erfunden. `fixtures/golden/` wird hier nicht gelesen (Regel 2).

**Die Geldbeträge sind von Hand nachgerechnet** (Regel 8), nicht aus der
Implementierung übernommen — siehe `test_geldbetraege_der_dax_struktur`.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from fixtures_rebuild import AUSFUEHRUNGEN, INSTRUMENTE, befuelle
from sqlalchemy import insert, select

pytest.importorskip("journal.rebuild")

from journal.db import create_db_engine  # noqa: E402
from journal.rebuild import rebuild  # noqa: E402
from journal.schema import (  # noqa: E402
    assignment_links,
    chain_links,
    chain_overrides,
    chains,
    executions,
    journal_entries,
    legs,
    structures,
)


def _zeilen(db_pfad, tabelle) -> list[dict]:
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return [dict(z) for z in verbindung.execute(select(tabelle)).mappings().all()]


def _je_schluessel(db_pfad, tabelle) -> dict:
    return {z["natur_schluessel"]: z for z in _zeilen(db_pfad, tabelle)}


def _glieder(db_pfad) -> dict:
    """Kettenglieder als {Struktur-Naturschlüssel: Zeile aus chain_links}."""
    strukturen = {z["structure_id"]: z["natur_schluessel"] for z in _zeilen(db_pfad, structures)}
    return {strukturen[z["structure_id"]]: z for z in _zeilen(db_pfad, chain_links)}


# ---------------------------------------------------------------------------
# Grundlauf
# ---------------------------------------------------------------------------


def test_grundlauf_schreibt_die_erwarteten_zeilen(migrated_db):
    """Der Bestand aus `fixtures_rebuild` ergibt 10 Legs, 6 Strukturen,
    4 Ketten und 6 Kettenglieder.

    Von Hand abgezählt: DAX bringt zwei Strukturen in **einer** Kette — der
    Roll lief in einer Order und ist über die Order-Nummer belegt. ESTX50
    lief in zwei Orders und wird seit AP-04k **nicht** mehr verkettet: zwei
    eigene Ketten und ein offener Rollkandidat (Plan §6, Block B, Regel 2).
    Die beiden Aktientranchen bleiben je eine eigene Kette (Regel 4).
    """
    befuelle(migrated_db)

    ergebnis = rebuild(migrated_db)

    assert ergebnis.legs == 10
    assert ergebnis.structures == 6
    assert ergebnis.chains == 5
    assert ergebnis.chain_links == 6
    assert ergebnis.nicht_strukturiert == 0
    assert ergebnis.kandidaten_offen == 1
    assert len(_zeilen(migrated_db, legs)) == 10
    assert len(_zeilen(migrated_db, structures)) == 6
    assert len(_zeilen(migrated_db, chains)) == 5
    assert len(_zeilen(migrated_db, chain_links)) == 6


def test_naturschluessel_folgen_dem_vertrag(migrated_db):
    """Vertrag 7 und 8: Struktur = sortierte `open_exec_id` mit `|`,
    Kette = Naturschlüssel der eröffnenden Struktur mit `k:` davor."""
    befuelle(migrated_db)
    rebuild(migrated_db)

    assert set(_je_schluessel(migrated_db, structures)) == {
        "E1|E2", "E5|E6", "Z1|Z2", "Z5|Z6", "A1", "A2",
    }
    assert set(_je_schluessel(migrated_db, chains)) == {
        "k:E1|E2", "k:Z1|Z2", "k:Z5|Z6", "k:A1", "k:A2",
    }


def test_legs_zeigen_auf_ihre_struktur(migrated_db):
    """Vertrag 15: `legs.structure_id` zeigt auf die Struktur, in der die
    Leg gelandet ist. Hier landet jede — es gibt keinen P7-Ausschluss."""
    befuelle(migrated_db)
    rebuild(migrated_db)

    strukturen = {
        z["structure_id"]: z["natur_schluessel"] for z in _zeilen(migrated_db, structures)
    }
    zuordnung = {
        z["open_exec_id"]: strukturen.get(z["structure_id"]) for z in _zeilen(migrated_db, legs)
    }
    assert zuordnung["E1"] == "E1|E2"
    assert zuordnung["E2"] == "E1|E2"
    assert zuordnung["E5"] == "E5|E6"
    assert zuordnung["A1"] == "A1"
    assert all(wert is not None for wert in zuordnung.values())


# ---------------------------------------------------------------------------
# Geld (Regel 5, Regel 8)
# ---------------------------------------------------------------------------


def test_geldbetraege_der_dax_struktur(migrated_db):
    """Von Hand nachgerechnet, nicht aus der Implementierung übernommen.

    Die DAX-Vertikale, Multiplikator 5, Menge 1:

    - Leg E1→E3: short, verkauft zu 100, zurückgekauft zu 40
      → (100 − 40) × 5 × 1 = **+300,00**
    - Leg E2→E4: long, gekauft zu 60, verkauft zu 20
      → (20 − 60) × 5 × 1 = **−200,00**
    - Brutto der Struktur: 300 − 200 = **+100,00**
    - Kommission: vier Ausführungen zu je −2,00 = **−8,00**
    - Netto: 100 + (−8) = **+92,00** — **addiert** (Vertrag 10a), weil das
      Vorzeichen von IB kommt und negativ „kostet Geld" heißt.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)

    dax = _je_schluessel(migrated_db, structures)["E1|E2"]
    assert dax["brutto_pnl"] == Decimal("100.00")
    assert dax["kommission"] == Decimal("-8.00")
    assert dax["netto_pnl"] == Decimal("92.00")
    assert dax["waehrung"] == "EUR"
    assert dax["status"] == "geschlossen"


def test_offene_struktur_hat_kein_ergebnis(migrated_db):
    """Vertrag 10a: ohne `brutto_pnl` bleibt auch `netto_pnl` leer — kein
    stiller Nullwert, der später wie ein Nullergebnis aussähe."""
    befuelle(migrated_db)
    rebuild(migrated_db)

    offen = _je_schluessel(migrated_db, structures)["E5|E6"]
    assert offen["status"] == "offen"
    assert offen["brutto_pnl"] is None
    assert offen["netto_pnl"] is None


def test_kein_euro_betrag_ohne_umrechnung(migrated_db):
    """Entscheidung 2: Die FX-Umrechnung nach P4 ist AP-06. Hier einen Kurs
    zu unterstellen hieße raten (Regel 10)."""
    befuelle(migrated_db)
    rebuild(migrated_db)

    assert all(z["netto_pnl_eur"] is None for z in _zeilen(migrated_db, chains))


def test_waehrungskonflikt_in_einer_struktur_bricht_ab(migrated_db):
    """Vertrag 11: `structures.waehrung` kommt aus den Ausführungen der
    Legs. Sind sie uneinig, ist das ein Abbruch mit Nennung — nicht die
    häufigste Währung, nicht die erste."""
    instrumente = [satz for satz in INSTRUMENTE if satz["conid"] in (601, 602)]
    ausfuehrungen = [
        dict(exec_id="K1", conid=601, side="SELL", preis=Decimal("100.00"),
             waehrung="EUR", handelszeit=datetime(2026, 9, 1, 10, 0, 0), exec_batch="9.1"),
        dict(exec_id="K2", conid=602, side="BUY", preis=Decimal("60.00"),
             waehrung="USD", handelszeit=datetime(2026, 9, 1, 10, 0, 0), exec_batch="9.1"),
    ]
    befuelle(migrated_db, ausfuehrungen=ausfuehrungen, instrumente_=instrumente)

    with pytest.raises(ValueError, match="K1|K2"):
        rebuild(migrated_db)


# ---------------------------------------------------------------------------
# Erkennungsart (Regel 7)
# ---------------------------------------------------------------------------


def test_erkennung_unterscheidet_ordernummer_von_heuristik(migrated_db):
    """Vertrag 12: `structures.erkennung` kommt aus `Structure.methode`,
    nicht aus dem gleichnamigen Dataclass-Feld.

    DAX entsteht über den gemeinsamen `exec_batch` — die Order-Nummer belegt
    die Struktur. ESTX50 entsteht über das Zeitfenster — das ist ein Schluss
    aus zeitlicher Nähe. Der Plan verlangt genau diese Unterscheidung.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)

    je_schluessel = _je_schluessel(migrated_db, structures)
    assert je_schluessel["E1|E2"]["erkennung"] == "order_id"
    assert je_schluessel["E5|E6"]["erkennung"] == "order_id"
    assert je_schluessel["Z1|Z2"]["erkennung"] == "heuristik"
    assert je_schluessel["Z5|Z6"]["erkennung"] == "heuristik"


def test_rollverknuepfung_traegt_ihre_erkennungsart(migrated_db):
    """Vertrag 14: `chain_links.erkennung` kommt unverändert aus
    `ChainGlied` und unterscheidet bereits belegt von erschlossen.

    Der DAX-Roll lief in einer Order (gemeinsamer `exec_batch`) — `auto`.

    Der ESTX50-Fall lief in zwei Orders zwei Minuten auseinander. Seit
    AP-04k verkettet das nicht mehr, deshalb kann `erkennung = 'heuristik'`
    in `chain_links` gar nicht mehr vorkommen: Eine erschlossene Nähe ist
    ein Vorschlag, keine Verknüpfung (Plan §6, Block B, Regel 5). Geprüft
    wird stattdessen, dass dort **kein** Roll steht und der Fall als
    offener Kandidat gezählt wird.
    """
    befuelle(migrated_db)
    ergebnis = rebuild(migrated_db)

    glieder = _glieder(migrated_db)
    assert glieder["E1|E2"]["sequenz"] == 1
    assert glieder["E1|E2"]["verknuepfungstyp"] == "open"
    assert glieder["E5|E6"]["verknuepfungstyp"] == "roll"
    assert glieder["E5|E6"]["erkennung"] == "auto"

    assert glieder["Z5|Z6"]["verknuepfungstyp"] == "open"
    assert glieder["Z5|Z6"]["sequenz"] == 1
    assert all(
        zeile["erkennung"] != "heuristik" for zeile in _zeilen(migrated_db, chain_links)
    )
    assert ergebnis.kandidaten_offen == 1


# ---------------------------------------------------------------------------
# Idempotenz (Vertrag 23) — der Kern von Entscheidung 1
# ---------------------------------------------------------------------------


def test_zweiter_lauf_aendert_nichts(migrated_db):
    """Zweimal `rebuild` ergibt denselben Inhalt **und dieselben Nummern**.

    Die Nummern sind der eigentliche Punkt: `chain_overrides` verweist per
    Fremdschlüssel auf sie. Würden sie sich ändern, zeigte jeder Override
    nach einem Rebuild woandershin.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)
    vorher_strukturen = _je_schluessel(migrated_db, structures)
    vorher_ketten = _je_schluessel(migrated_db, chains)

    zweites = rebuild(migrated_db)

    assert zweites.structures == 6
    assert zweites.chains == 5
    nachher_strukturen = _je_schluessel(migrated_db, structures)
    nachher_ketten = _je_schluessel(migrated_db, chains)
    assert {s: z["structure_id"] for s, z in nachher_strukturen.items()} == {
        s: z["structure_id"] for s, z in vorher_strukturen.items()
    }
    assert {s: z["chain_id"] for s, z in nachher_ketten.items()} == {
        s: z["chain_id"] for s, z in vorher_ketten.items()
    }


def test_zuwachs_laesst_bestehende_nummern_unberuehrt(migrated_db):
    """Ein Rebuild nach zusätzlichen Ausführungen darf die Nummern der
    unveränderten Strukturen nicht neu vergeben."""
    ohne_aktien = [satz for satz in AUSFUEHRUNGEN if not satz["exec_id"].startswith("A")]
    nur_optionen = [satz for satz in INSTRUMENTE if satz["conid"] != 901]
    befuelle(migrated_db, ausfuehrungen=ohne_aktien, instrumente_=nur_optionen)
    rebuild(migrated_db)
    vorher = {s: z["structure_id"] for s, z in _je_schluessel(migrated_db, structures).items()}

    aktien = [satz for satz in AUSFUEHRUNGEN if satz["exec_id"].startswith("A")]
    befuelle(migrated_db, ausfuehrungen=aktien,
             instrumente_=[satz for satz in INSTRUMENTE if satz["conid"] == 901])
    rebuild(migrated_db)

    nachher = {s: z["structure_id"] for s, z in _je_schluessel(migrated_db, structures).items()}
    assert set(nachher) - set(vorher) == {"A1", "A2"}
    for schluessel, nummer in vorher.items():
        assert nachher[schluessel] == nummer


# ---------------------------------------------------------------------------
# Overrides (Vertrag 16–21)
# ---------------------------------------------------------------------------


def _setze_override(db_pfad, ziel_kette: str, struktur: str) -> None:
    ketten = _je_schluessel(db_pfad, chains)
    strukturen = _je_schluessel(db_pfad, structures)
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        verbindung.execute(
            insert(chain_overrides).values(
                chain_id=ketten[ziel_kette]["chain_id"],
                structure_id=strukturen[struktur]["structure_id"],
                notiz="Tranchen von Hand gebündelt",
                erstellt_am=datetime(2026, 9, 20, 8, 0, 0),
            )
        )


def test_override_ueberlebt_den_rebuild(migrated_db):
    """Plan §6, AP-04: „Manuelle Overrides überleben ein vollständiges
    `rebuild`."

    Die zweite Aktientranche wird von Hand in die Kette der ersten gelegt —
    genau der Fall, den Block B, Regel 4 offenlässt. Danach hängt sie dort
    mit `erkennung = 'manuell'`, und `chain_overrides` ist unverändert.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)
    _setze_override(migrated_db, ziel_kette="k:A1", struktur="A2")
    vorher = _zeilen(migrated_db, chain_overrides)

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_angewandt == 1
    assert ergebnis.overrides_verwaist == 0
    ketten = _je_schluessel(migrated_db, chains)
    assert "k:A2" not in ketten, "Die leer gewordene Kette wird gelöscht (Vertrag 19)"
    glieder = _glieder(migrated_db)
    assert glieder["A2"]["chain_id"] == ketten["k:A1"]["chain_id"]
    assert glieder["A2"]["erkennung"] == "manuell"
    assert _zeilen(migrated_db, chain_overrides) == vorher


def test_override_zieht_die_kennzahlen_der_kette_nach(migrated_db):
    """Vertrag 18: Nach dem Umhängen stimmen Reihenfolge und Kennzahlen.

    Von Hand: Tranche A1 wurde am 02.03.2026 eröffnet, A2 am 04.05.2026.
    Die gebündelte Kette beginnt also am 02.03.2026, hat zwei Glieder und
    damit `anzahl_rolls = 1`. Beide sind offen, deshalb bleibt sie offen.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)
    _setze_override(migrated_db, ziel_kette="k:A1", struktur="A2")
    rebuild(migrated_db)

    kette = _je_schluessel(migrated_db, chains)["k:A1"]
    assert kette["eroeffnet_am"] == datetime(2026, 3, 2, 10, 0, 0)
    assert kette["anzahl_rolls"] == 1
    assert kette["beendet_am"] is None
    assert kette["endzustand"] == "Offen"
    glieder = _glieder(migrated_db)
    assert glieder["A1"]["sequenz"] == 1
    assert glieder["A1"]["verknuepfungstyp"] == "open"
    assert glieder["A2"]["sequenz"] == 2
    assert glieder["A2"]["verknuepfungstyp"] == "roll"


def test_verwaister_override_wird_gezaehlt_und_nicht_geloescht(migrated_db):
    """Vertrag 20: Verweist ein Override auf eine Struktur, die die
    Automatik nicht mehr findet, wird er gezählt und benannt — nicht
    gelöscht (Regel 4) und nicht stillschweigend übergangen.

    Aufgebaut wie es wirklich passiert: Der Override wird gesetzt, danach
    verschwindet die Ausführung, auf der die Struktur beruhte (etwa weil
    ein fehlerhafter Import zurückgenommen wurde). Die Struktur selbst
    bleibt stehen, weil der Override auf sie verweist.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)
    _setze_override(migrated_db, ziel_kette="k:A1", struktur="A2")

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        # Die abgeleiteten Zeilen gehen mit: `legs.open_exec_id` verweist auf
        # `executions.exec_id`, und eine zurückgenommene Fehleinspielung nimmt
        # das Abgeleitete ohnehin mit (AP-04vk, OF-38).
        verbindung.execute(legs.delete().where(legs.c.open_exec_id == "A2"))
        verbindung.execute(executions.delete().where(executions.c.exec_id == "A2"))

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_verwaist == 1
    assert ergebnis.overrides_angewandt == 0
    assert len(_zeilen(migrated_db, chain_overrides)) == 1
    assert "A2" in _je_schluessel(migrated_db, structures)


def test_dieselbe_struktur_in_zwei_ketten_bricht_ab(migrated_db):
    """Vertrag 21: Zwei Overrides, die dieselbe Struktur beanspruchen, sind
    ein Widerspruch in den Benutzerdaten. Keine Reihenfolgeregel, keine
    stille Entscheidung — Abbruch mit Nennung."""
    befuelle(migrated_db)
    rebuild(migrated_db)
    _setze_override(migrated_db, ziel_kette="k:A1", struktur="A2")
    _setze_override(migrated_db, ziel_kette="k:E1|E2", struktur="A2")

    with pytest.raises(ValueError):
        rebuild(migrated_db)


# ---------------------------------------------------------------------------
# Regel 4: keine Löschung von Benutzerdaten
# ---------------------------------------------------------------------------


def test_benutzerdaten_ueberstehen_den_rebuild(migrated_db):
    """Regel 4: Ein Rebuild fasst nur die abgeleiteten Tabellen an. Dass
    eine Tabelle leer ist, ist keine Erlaubnis, sie zu beschreiben."""
    befuelle(migrated_db)
    rebuild(migrated_db)

    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        verbindung.execute(
            insert(journal_entries).values(
                scope_typ="chain",
                scope_id=str(_je_schluessel(migrated_db, chains)["k:A1"]["chain_id"]),
                text="Nicht anfassen.",
                erstellt_am=datetime(2026, 9, 20, 9, 0, 0),
                geaendert_am=datetime(2026, 9, 20, 9, 0, 0),
            )
        )
    vorher = _zeilen(migrated_db, journal_entries)

    rebuild(migrated_db)

    assert _zeilen(migrated_db, journal_entries) == vorher


# ---------------------------------------------------------------------------
# Ablehnungen (AP-04k, Plan §6, Block B, Regel 2)
# ---------------------------------------------------------------------------


def _entscheide(db_pfad, ziel_kette: str, struktur: str, urteil: str) -> None:
    ketten = _je_schluessel(db_pfad, chains)
    strukturen = _je_schluessel(db_pfad, structures)
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        verbindung.execute(
            insert(chain_overrides).values(
                chain_id=ketten[ziel_kette]["chain_id"],
                structure_id=strukturen[struktur]["structure_id"],
                notiz=None,
                erstellt_am=datetime(2026, 9, 21, 18, 0, 0),
                urteil=urteil,
            )
        )


def test_abgelehnter_kandidat_kommt_nicht_wieder(migrated_db):
    """Eine Ablehnung ist ebenso ein Benutzerdatum wie eine Bestätigung
    (Plan §6, Block B, Regel 2).

    Ohne sie erschiene jeder abgelehnte Rollkandidat bei jedem `rebuild`
    erneut, und eine Durchsicht von mehreren hundert Paaren wäre nie
    dauerhaft. Der ESTX50-Fall ist der eine offene Kandidat des Fixtures;
    nach der Ablehnung ist keiner mehr offen, die beiden Ketten bleiben
    getrennt, und `chain_overrides` bleibt unverändert stehen.
    """
    befuelle(migrated_db)
    assert rebuild(migrated_db).kandidaten_offen == 1

    _entscheide(migrated_db, ziel_kette="k:Z1|Z2", struktur="Z5|Z6", urteil="abgelehnt")
    vorher = _zeilen(migrated_db, chain_overrides)

    ergebnis = rebuild(migrated_db)

    assert ergebnis.kandidaten_offen == 0
    assert ergebnis.overrides_angewandt == 0
    assert ergebnis.overrides_verwaist == 0
    assert ergebnis.chains == 5
    assert _glieder(migrated_db)["Z5|Z6"]["verknuepfungstyp"] == "open"
    assert _zeilen(migrated_db, chain_overrides) == vorher

    # Auch ein zweiter Lauf bringt ihn nicht zurück.
    assert rebuild(migrated_db).kandidaten_offen == 0


def test_bestaetigter_kandidat_wird_zur_kette(migrated_db):
    """Die Gegenrichtung: Wird derselbe Kandidat bestätigt, entsteht die
    Kette — mit `erkennung = 'manuell'`, nie `heuristik`."""
    befuelle(migrated_db)
    rebuild(migrated_db)

    _entscheide(migrated_db, ziel_kette="k:Z1|Z2", struktur="Z5|Z6", urteil="bestaetigt")

    ergebnis = rebuild(migrated_db)

    assert ergebnis.overrides_angewandt == 1
    assert ergebnis.kandidaten_offen == 0
    ketten = _je_schluessel(migrated_db, chains)
    assert "k:Z5|Z6" not in ketten
    glieder = _glieder(migrated_db)
    assert glieder["Z5|Z6"]["chain_id"] == ketten["k:Z1|Z2"]["chain_id"]
    assert glieder["Z5|Z6"]["erkennung"] == "manuell"
    assert glieder["Z5|Z6"]["verknuepfungstyp"] == "roll"


# ---------------------------------------------------------------------------
# Zuteilung mit mehreren Legs (AP-04pk, Fund am echten Bestand)
# ---------------------------------------------------------------------------


def test_zuteilung_mit_zwei_legs_schreibt_das_paar_einmal(migrated_db):
    """`assignment_links` ist eine Menge von Paaren, keine Liste.

    Schließt **eine** Zuteilungsausführung **zwei Legs** derselben Struktur,
    entstand das Paar (Optionsausführung, Aktienausführung) zweimal und der
    Rebuild brach am Primärschlüssel ab. Gefunden beim ersten Lauf über den
    echten Bestand: 330 erzeugte Paare, 320 verschiedene, 10 doppelte — in
    den erfundenen Beständen schloss eine Zuteilung bis dahin immer genau
    ein Leg.

    Aufbau: zwei Eröffnungen desselben Kontrakts in einer Order (gemeinsamer
    `exec_batch`, also eine Struktur mit zwei Legs), eine Zuteilung über
    beide, eine Aktiengegenbuchung zur selben Zeit.
    """
    instrumente = [
        dict(conid=500, symbol="IDX5 260821P50", underlying="IDX5", asset_class="OPT",
             expiry=date(2026, 8, 21), strike=Decimal("50"), right="P",
             multiplikator=Decimal("100"), waehrung="EUR", abwicklungsart="lieferung"),
        dict(conid=501, symbol="IDX5", underlying="IDX5", asset_class="STK",
             expiry=None, strike=None, right=None,
             multiplikator=Decimal("1"), waehrung="EUR"),
    ]
    eroeffnung = datetime(2026, 8, 1, 10, 0, 0)
    zuteilung = datetime(2026, 8, 21, 21, 0, 0)
    ausfuehrungen = [
        dict(exec_id="O1", conid=500, side="SELL", preis=Decimal("2.00"),
             handelszeit=eroeffnung, exec_batch="5.1"),
        dict(exec_id="O2", conid=500, side="SELL", preis=Decimal("2.00"),
             handelszeit=eroeffnung, exec_batch="5.1"),
        dict(exec_id="A1", conid=500, side="BUY", menge=Decimal("2"),
             preis=Decimal("0.00"), handelszeit=zuteilung, ereignistyp="assignment"),
        dict(exec_id="S1", conid=501, side="BUY", menge=Decimal("200"),
             preis=Decimal("50.00"), handelszeit=zuteilung, ereignistyp="assignment"),
    ]
    befuelle(migrated_db, ausfuehrungen=ausfuehrungen, instrumente_=instrumente)

    rebuild(migrated_db)

    paare = [
        (z["option_exec_id"], z["stock_exec_id"], z["erkennung"])
        for z in _zeilen(migrated_db, assignment_links)
    ]
    assert paare == [("A1", "S1", "auto")]

    # Und ein zweiter Lauf bleibt dabei (Idempotenz, Vertrag 23).
    rebuild(migrated_db)
    assert len(_zeilen(migrated_db, assignment_links)) == 1


# ---------------------------------------------------------------------------
# Eröffnungs- und Schlussprämie (AP-07p)
# ---------------------------------------------------------------------------


def test_praemien_sind_von_hand_nachgerechnet(migrated_db):
    """Vertrag P1–P3: Nettoprämie je Kontrakt, Verkauf positiv, Kauf negativ.

    Von Hand für die DAX-Vertikale (Menge 1):

    - Eröffnung: E1 verkauft 19000er Put zu 100,00 (+100), E2 kauft den
      18900er zu 60,00 (−60) → **+40,00** eingenommen.
    - Schließung: E3 kauft den 19000er zu 40,00 zurück (−40), E4 verkauft
      den 18900er zu 20,00 (+20) → **−20,00** gezahlt.

    Die Probe aufs Exempel steht im Test selbst: (40 − 20) × Menge 1 ×
    Multiplikator 5 = 100,00 — und genau das ist das bereits geprüfte
    Bruttoergebnis der Struktur. Stimmen Prämien und Brutto nicht überein,
    ist eine der beiden Rechnungen falsch.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)

    dax = _je_schluessel(migrated_db, structures)["E1|E2"]

    assert dax["eroeffnungspreis"] == Decimal("40")
    assert dax["schlusspreis"] == Decimal("-20")
    summe = dax["eroeffnungspreis"] + dax["schlusspreis"]
    assert summe * dax["menge"] * Decimal("5") == dax["brutto_pnl"]


def test_offene_struktur_hat_keinen_schlusspreis(migrated_db):
    """Vertrag P2: Was nicht geschlossen ist, hat keinen Schlusspreis — und
    bekommt auch keine Null, die wie ein Rückkauf zum Nulltarif aussähe.

    Von Hand: E5 verkauft zu 90,00 (+90), E6 kauft zu 55,00 (−55) → +35,00.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)

    offen = _je_schluessel(migrated_db, structures)["E5|E6"]

    assert offen["status"] == "offen"
    assert offen["eroeffnungspreis"] == Decimal("35")
    assert offen["schlusspreis"] is None


def test_praemie_der_estx50_struktur(migrated_db):
    """Gegenprobe mit anderem Multiplikator (10).

    Von Hand: Eröffnung Z1 +30,00 und Z2 −18,00 → **+12,00**; Schließung
    Z3 −12,00 und Z4 +6,00 → **−6,00**. Probe: (12 − 6) × 1 × 10 = 60,00 =
    Bruttoergebnis.
    """
    befuelle(migrated_db)
    rebuild(migrated_db)

    estx = _je_schluessel(migrated_db, structures)["Z1|Z2"]

    assert estx["eroeffnungspreis"] == Decimal("12")
    assert estx["schlusspreis"] == Decimal("-6")
    assert (estx["eroeffnungspreis"] + estx["schlusspreis"]) * Decimal("10") == estx[
        "brutto_pnl"
    ]


def test_praemie_wird_je_kontrakt_gerechnet(migrated_db):
    """Vertrag P1: geteilt durch die Menge der Struktur — sonst wäre der
    Preis nicht vergleichbar zwischen einer Einer- und einer Zehnerposition.

    Von Hand, Menge 2: verkauft 2× zu 100,00, gekauft 2× zu 60,00. Die
    Summe über die Legs ist 2×100 − 2×60 = 80,00; je Kontrakt sind das
    **40,00** — derselbe Preis wie bei der Einerposition oben.
    """
    instrumente = [satz for satz in INSTRUMENTE if satz["conid"] in (601, 602)]
    ausfuehrungen = [
        dict(exec_id="M1", conid=601, side="SELL", menge=Decimal("2"),
             preis=Decimal("100.00"), handelszeit=datetime(2026, 9, 1, 10, 0, 0),
             exec_batch="8.1"),
        dict(exec_id="M2", conid=602, side="BUY", menge=Decimal("2"),
             preis=Decimal("60.00"), handelszeit=datetime(2026, 9, 1, 10, 0, 0),
             exec_batch="8.1"),
    ]
    befuelle(migrated_db, ausfuehrungen=ausfuehrungen, instrumente_=instrumente)
    rebuild(migrated_db)

    struktur = _je_schluessel(migrated_db, structures)["M1|M2"]

    assert struktur["menge"] == Decimal("2")
    assert struktur["eroeffnungspreis"] == Decimal("40")


def test_nicht_aufgehende_division_wird_auf_acht_stellen_gekuerzt(migrated_db):
    """Vertrag P3: Geht die Division nicht auf, wird ausdrücklich auf acht
    Nachkommastellen gekürzt — nicht still bei 28, wie `Decimal` es täte
    (Regel 5).

    Dafür braucht es **ungleiche** Beinmengen: Sind alle gleich, kürzt sich
    die Menge heraus und die Division geht immer auf. Hier verkauft ein Bein
    3 Kontrakte zu 10,00 (+30,00), das andere kauft 4 zu 1,00 (−4,00) — in
    Summe 26,00.

    Die Größe der Struktur ist die kleinste verdichtete Beinmenge, also 3
    (`engine.structures`, Regel 10). 26 geteilt durch 3 ist 8,666…; auf acht
    Stellen kaufmännisch gerundet **8,66666667**.
    """
    instrumente = [satz for satz in INSTRUMENTE if satz["conid"] in (601, 602)]
    zeit = datetime(2026, 9, 1, 10, 0, 0)
    ausfuehrungen = [
        dict(exec_id="D1", conid=601, side="SELL", menge=Decimal("3"),
             preis=Decimal("10.00"), handelszeit=zeit, exec_batch="9.7"),
        dict(exec_id="D2", conid=602, side="BUY", menge=Decimal("4"),
             preis=Decimal("1.00"), handelszeit=zeit, exec_batch="9.7"),
    ]
    befuelle(migrated_db, ausfuehrungen=ausfuehrungen, instrumente_=instrumente)
    rebuild(migrated_db)

    struktur = _je_schluessel(migrated_db, structures)["D1|D2"]

    assert struktur["menge"] == Decimal("3")
    assert struktur["eroeffnungspreis"] == Decimal("8.66666667")
