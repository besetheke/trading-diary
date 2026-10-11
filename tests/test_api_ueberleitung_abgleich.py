"""Abnahmetests für AP-08u2: `GET /ueberleitung` zeigt Journal und IB
nebeneinander und zerlegt den Unterschied des realisierten Ergebnisses.

Welt wie tests/test_api_ueberleitung.py (dieselbe Fixture): EUR, Kurs 1, keine
offene Aktie, alle Strukturen geschlossen. Journal realisiert 56.00, IB 50.00,
unrealisiert laut IB −20.00, Einzahlungen 1000.00, sonstige 5.00, Kontowert
1100.00.

Von Hand:
  Journal-Spalte: unrealisiert = IB −20.00 − Prämien im Einstand 0 = −20.00;
  Rest = 1100.00 − (1000.00 + 56.00 − 20.00 + 5.00) = 59.00.
  Abgleich: Prämien 0, Währungsmethode 0 (alles EUR zum Kurs 1), Zeitpunkt 0;
  nicht zugeordnet = 6.00 (die IB-Werte der Welt sind frei erfunden).
"""

from decimal import Decimal

from test_api_ueberleitung import klient  # noqa: F401  (Fixture)


def _d(text):
    assert isinstance(text, str), text
    return Decimal(text)


def test_journal_spalte_neben_ib(klient):  # noqa: F811
    daten = klient.get("/ueberleitung").json()
    j = daten["journal_spalte"]
    assert _d(j["einzahlungen"]) == _d(daten["einzahlungen"])           # gleiche Quelle
    assert _d(j["sonstige_buchungen"]) == _d(daten["ib"]["sonstige_buchungen"])
    assert _d(j["realisiert"]) == Decimal("56.00")
    assert _d(j["unrealisiert"]) == Decimal("-20.00")
    assert _d(j["rest"]) == Decimal("59.00")


def test_beide_spalten_ergeben_den_kontowert(klient):  # noqa: F811
    daten = klient.get("/ueberleitung").json()
    for spalte in (daten["journal_spalte"], {**daten["ib"], "einzahlungen": daten["einzahlungen"]}):
        summe = sum(_d(spalte[k]) for k in (
            "einzahlungen", "realisiert", "unrealisiert", "sonstige_buchungen", "rest"))
        assert summe == _d(daten["kontowert"])


def test_zerlegung_des_unterschieds(klient):  # noqa: F811
    daten = klient.get("/ueberleitung").json()
    a = daten["abgleich_realisiert"]
    assert _d(a["praemien_im_einstand"]) == 0
    assert _d(a["waehrungsmethode"]) == 0
    assert _d(a["zeitpunkt_offene_strukturen"]) == 0
    assert _d(a["nicht_zugeordnet"]) == Decimal("6.00")
    teile = (_d(a["praemien_im_einstand"]) + _d(a["waehrungsmethode"])
             - _d(a["zeitpunkt_offene_strukturen"]) + _d(a["nicht_zugeordnet"]))
    assert teile == _d(daten["journal"]["differenz_realisiert"])


def test_zeilenzaehlung(klient):  # noqa: F811
    a = klient.get("/ueberleitung").json()["abgleich_realisiert"]
    assert isinstance(a["zeilen_gleich"], int) and isinstance(a["zeilen_abweichend"], int)


def test_unterschied_je_zeile_kommt_von_der_api(klient):  # noqa: F811
    """Journal minus IB je Zeile: realisiert 56 − 50 = 6.00; unrealisiert 0;
    Rest 59.00 − 65.00 = −6.00; Einzahlungen und sonstige 0. Die Unterschiede
    summieren sich zu 0 (beide Spalten ergeben denselben Kontowert)."""
    u = klient.get("/ueberleitung").json()["unterschied_spalte"]
    assert _d(u["realisiert"]) == Decimal("6.00")
    assert _d(u["unrealisiert"]) == 0
    assert _d(u["rest"]) == Decimal("-6.00")
    assert _d(u["einzahlungen"]) == 0 and _d(u["sonstige_buchungen"]) == 0
    assert sum(_d(v) for v in u.values()) == 0


def test_beitraege_summieren_sich_zum_unterschied(klient):  # noqa: F811
    """Die Anzeige addiert nur: Prämien + Währung + Zeitpunkt-Beitrag (= −Zeitpunkt)
    + nicht zugeordnet = Unterschied."""
    daten = klient.get("/ueberleitung").json()
    a = daten["abgleich_realisiert"]
    assert _d(a["zeitpunkt_beitrag"]) == -_d(a["zeitpunkt_offene_strukturen"])
    teile = (_d(a["praemien_im_einstand"]) + _d(a["waehrungsmethode"])
             + _d(a["zeitpunkt_beitrag"]) + _d(a["nicht_zugeordnet"]))
    assert teile == _d(daten["journal"]["differenz_realisiert"])


def test_rest_im_einzelnen(klient):  # noqa: F811
    """AP-08u3: In der Welt ist der ganze Rest ein Einzelrest der Gruppe TST
    (nativ 6.00 EUR = 6.00 EUR, frei erfundene IB-Werte); kein Kurseffekt."""
    a = klient.get("/ueberleitung").json()["abgleich_realisiert"]
    assert _d(a["kurseffekt_praemien"]) == 0
    reste = [(r["gruppe"], r["waehrung"], _d(r["nativ"]), _d(r["eur"])) for r in a["einzelreste"]]
    assert reste == [("TST", "EUR", Decimal("6.00"), Decimal("6.00"))]

