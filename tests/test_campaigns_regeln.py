"""Abnahmetests für AP-05r: Kandidatenregeln nach der Praxis des Nutzers
(Ergänzung zu `tests/test_campaigns.py`, das unverändert bleibt).

Geschrieben nach §11.2 des Plans durch das starke Modell — für das
günstige Modell unveränderlich. Maßgeblich ist der Vertrag in
`auftraege/AP-05r.md`.

Drei Änderungen an `engine.campaigns.campaign_kandidaten`:

1. **IC-Kandidat über irgendein Glied.** Zwei Ketten sind ein IC-Kandidat,
   wenn es je Kette ein Glied gibt, die dieselbe Expiry tragen und zeitlich
   überlappen (Glied-Intervall: Eröffnung bis Schließung der Struktur, offen
   = unbegrenzt) — nicht nur, wenn die *letzten* Glieder dieselbe Expiry
   haben. Wer beide Seiten dauerhaft hält und einzeln rollt, hat selten am
   Ende dieselbe Expiry.
2. **Doppel-Roll ist kein Financing.** Hat die Gegenseite-Kette B eine
   Vorgängerkette C derselben Seite und desselben Basiswerts, die höchstens
   15 Minuten (einschließlich) vor B's Eröffnung endete, ist B ein Roll oder
   Wiedereinstieg der eigenen Seite, nicht die Gegenfinanzierung eines Rolls
   der anderen Seite: Das Paar wird nicht als Financing angeboten.
3. **Ranggrößen.** Jeder Kandidat trägt `abstand` und `ueberlappung`
   (beide `timedelta | None`, Standard `None`), damit die Durchsicht sortieren
   kann. Die Reihenfolge des Ergebnisses bleibt (typ, Naturschlüssel A,
   Naturschlüssel B).

Alle Daten sind frei erfunden. `fixtures/golden/` wird nicht gelesen.
"""

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("engine.campaigns")

from test_campaigns import _gerollte_kette, _vertikale_kette  # noqa: E402

from engine.campaigns import campaign_kandidaten  # noqa: E402

ROLL = datetime(2026, 9, 15, 15, 0, 0)


def _put_gerollt():
    return _gerollte_kette("P", underlying="DAX", right="P",
                            eroeffnet=datetime(2026, 9, 1, 10, 0, 0), roll_zeit=ROLL,
                            conid_alt_a=601, conid_alt_b=602, conid_neu_a=605, conid_neu_b=606)


# ---------------------------------------------------------------- IC über ein Glied


def test_ic_kandidat_ueber_ein_frueheres_glied():
    """Die Put-Kette trägt im ersten Glied die Expiry 18.09. (bis zum Roll am
    15.09.), im zweiten 16.10. Die Call-Kette (Expiry 18.09., eröffnet 02.09.,
    offen) überlappt das erste Glied und teilt dessen Expiry -> IC-Kandidat,
    obwohl die letzten Glieder verschiedene Expiries haben. Der Abstand zum
    Roll beträgt 13 Tage, also kein Financing."""
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 9, 18),
                             conid_short=611, conid_long=612,
                             eroeffnet=datetime(2026, 9, 2, 10, 0, 0))

    kandidaten = campaign_kandidaten([_put_gerollt(), call])

    assert [k.typ for k in kandidaten] == ["ic"]


def test_gleiche_expiry_aber_glieder_nie_gleichzeitig_kein_ic():
    """Die Call-Kette (Expiry 16.10.) endet am 10.09. - fünf Tage, bevor das
    zweite Put-Glied (Expiry 16.10.) am 15.09. entsteht; zum ersten Put-Glied
    (Expiry 18.09.) passt die Expiry nicht. Die Ketten überlappen als Ganzes
    (Put ab 01.09. offen, Call 02.09.-10.09.), aber kein Gliederpaar teilt
    Expiry und Zeit -> kein Kandidat. (Die alte Regel hätte hier wegen der
    gleichen letzten Expiry einen IC angeboten.)"""
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 10, 16),
                             conid_short=611, conid_long=612,
                             eroeffnet=datetime(2026, 9, 2, 10, 0, 0),
                             beendet=datetime(2026, 9, 10, 10, 0, 0))

    assert campaign_kandidaten([_put_gerollt(), call]) == ()


# ---------------------------------------------------------------- Doppel-Roll


def _gegenseite_neu(eroeffnet):
    return _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 11, 20),
                             conid_short=611, conid_long=612, eroeffnet=eroeffnet)


def _gegenseite_alt(beendet):
    return _vertikale_kette("D", underlying="DAX", right="C", expiry=date(2026, 11, 20),
                             conid_short=631, conid_long=632,
                             eroeffnet=datetime(2026, 9, 1, 10, 0, 0), beendet=beendet)


def test_kontrolle_ohne_vorgaengerkette_ist_es_ein_financing_kandidat():
    kandidaten = campaign_kandidaten([_put_gerollt(), _gegenseite_neu(ROLL + timedelta(minutes=1))])

    assert [k.typ for k in kandidaten] == ["financing"]


def test_gegenseite_die_ihre_eigene_seite_gerade_ersetzt_ist_kein_financing():
    """Die Call-Kette D endet um 14:55, die neue Call-Kette C wird um 15:01
    eröffnet - sechs Minuten später, innerhalb der 15 Minuten. C ist die
    Fortsetzung oder der Wiedereinstieg der Call-Seite, während die Put-Seite
    gerollt wird (Doppel-Roll). Weder (Put, C) noch (Put, D) ist ein
    Kandidat: D wurde am 01.09. eröffnet, 14 Tage vor dem Roll."""
    ketten = [_put_gerollt(), _gegenseite_neu(datetime(2026, 9, 15, 15, 1, 0)),
              _gegenseite_alt(datetime(2026, 9, 15, 14, 55, 0))]

    assert campaign_kandidaten(ketten) == ()


def test_doppel_roll_grenze_fuenfzehn_minuten_einschliesslich():
    """Exakt 15 Minuten zwischen Ende der Vorgängerkette und Eröffnung gelten
    noch als Doppel-Roll (einschließlich), 16 Minuten nicht mehr."""
    eroeffnet = datetime(2026, 9, 15, 15, 20, 0)

    genau = [_put_gerollt(), _gegenseite_neu(eroeffnet),
             _gegenseite_alt(eroeffnet - timedelta(minutes=15))]
    knapp_zu_spaet = [_put_gerollt(), _gegenseite_neu(eroeffnet),
                      _gegenseite_alt(eroeffnet - timedelta(minutes=16))]

    assert campaign_kandidaten(genau) == ()
    kandidaten = campaign_kandidaten(knapp_zu_spaet)
    assert [k.typ for k in kandidaten] == ["financing"]
    assert kandidaten[0].kette_b.eroeffnet_am == eroeffnet


def test_vorgaenger_der_anderen_seite_ist_kein_doppel_roll():
    """Eine Put-Kette, die kurz vor der neuen Call-Kette endete, ändert nichts:
    verglichen wird nur dieselbe Seite wie die Kette B (Call)."""
    put_alt = _vertikale_kette("D", underlying="DAX", right="P", expiry=date(2026, 11, 20),
                                conid_short=631, conid_long=632,
                                eroeffnet=datetime(2026, 9, 1, 10, 0, 0),
                                beendet=datetime(2026, 9, 15, 14, 55, 0))
    neu = _gegenseite_neu(datetime(2026, 9, 15, 15, 1, 0))

    typen = sorted(k.typ for k in campaign_kandidaten([_put_gerollt(), neu, put_alt]))

    assert typen.count("financing") == 1


# ---------------------------------------------------------------- Ranggrößen


def test_ic_traegt_abstand_und_ueberlappung():
    """Put-Kette: Expiry 16.10., eröffnet 01.09. 10:00, beendet 08.09. 10:00.
    Call-Kette: gleiche Expiry, eröffnet 01.09. 10:05, offen.
    Abstand = 5 Minuten. Überlappung = von 01.09. 10:05 bis 08.09. 10:00 =
    6 Tage 23 Stunden 55 Minuten."""
    put = _vertikale_kette("P", underlying="DAX", right="P", expiry=date(2026, 10, 16),
                            conid_short=601, conid_long=602,
                            eroeffnet=datetime(2026, 9, 1, 10, 0, 0),
                            beendet=datetime(2026, 9, 8, 10, 0, 0))
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 10, 16),
                             conid_short=611, conid_long=612,
                             eroeffnet=datetime(2026, 9, 1, 10, 5, 0))

    (kandidat,) = campaign_kandidaten([put, call])

    assert kandidat.typ == "ic"
    assert kandidat.abstand == timedelta(minutes=5)
    assert kandidat.ueberlappung == timedelta(days=6, hours=23, minutes=55)


def test_zwei_offene_ketten_haben_unbegrenzte_ueberlappung():
    """Beide Ketten offen: die Überlappung ist unbegrenzt (None), der Abstand
    bleibt bestimmt - hier 0 (gleichzeitig eröffnet)."""
    t0 = datetime(2026, 9, 1, 10, 0, 0)
    put = _vertikale_kette("P", underlying="DAX", right="P", expiry=date(2026, 10, 16),
                            conid_short=601, conid_long=602, eroeffnet=t0)
    call = _vertikale_kette("C", underlying="DAX", right="C", expiry=date(2026, 10, 16),
                             conid_short=611, conid_long=612, eroeffnet=t0)

    (kandidat,) = campaign_kandidaten([put, call])

    assert kandidat.abstand == timedelta(0)
    assert kandidat.ueberlappung is None


def test_financing_traegt_den_abstand_zum_roll():
    """Roll am 15.09. 15:00, Gegenseite eröffnet zwei Stunden später: Abstand
    2 Stunden. Beide Ketten sind offen: Überlappung unbegrenzt (None)."""
    (kandidat,) = campaign_kandidaten(
        [_put_gerollt(), _gegenseite_neu(ROLL + timedelta(hours=2))]
    )

    assert kandidat.typ == "financing"
    assert kandidat.abstand == timedelta(hours=2)
    assert kandidat.ueberlappung is None


def test_reihenfolge_bleibt_typ_und_naturschluessel():
    """Die Ranggrößen ändern die Ausgabereihenfolge nicht (AP-05v, Vertrag 7);
    sortiert wird erst in der Durchsicht."""
    ketten = [_put_gerollt(), _gegenseite_neu(ROLL + timedelta(hours=2))]

    assert campaign_kandidaten(ketten) == campaign_kandidaten(list(reversed(ketten)))
