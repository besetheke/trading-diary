"""Abnahmetests für AP-13ab: Abgleich OA ↔ IB je OA-Trade und je Strategie
(`analytics/oa_vergleich.py`). Vertrag: auftraege/AP-13ab.md. Geschrieben durch
das starke Modell — für die Umsetzung unveränderlich. Werte von Hand.

IB-Ergebnis eines OA-Trades = Σ (brutto + Kommission) aller Legs, deren
eröffnende Ausführung die OA-Nummer trägt, plus die Legs der daraus
zugeteilten Aktien (assignment_links). Verglichen wird in der Währung des
Trades mit OA „Profit (orig.)".

  101 A CLOSED     OA 144.24 USD | IB 146.00 − 1.76 = 144.24           → gleich
  102 A EXPIRED (estimated) OA 154.48 | IB 66.00 − 1.52 = 64.48, Δ −90.00 → schaetzung
  103 B EXPIRED    OA 12406.46 | Option 12407.00 − 0.54, Aktie aus
                   Zuteilung −12811.00 − 1.72 → −406.26, Δ −12812.72      → zuteilung
  104 B RUNNING    Leg offen                                             → offen
  105 A CLOSED     OA 10.00, keine Ausführung bei IB                     → fehlt
  106 D EXPIRED    OA 100.00 EUR | IB 102.00 − 2.00 = 100.00 EUR          → gleich
  107 D EXPIRED    OA 50.00 USD (umgerechnet), IB in EUR                 → waehrung
  108 E CLOSED     OA −100.00 | IB: Leg eröffnet von 108, geschlossen von einer
                   Ausführung des Trades 109 (Konto-FIFO verrechnet): +500.00
  109 F CLOSED     OA −50.00  | IB −650.00
                   → Gruppe 108+109: OA −150.00, IB −150.00                → verrechnet
  110 G CLOSED     OA 20.00 | IB 20.10, Δ +0.10                          → gering
Toleranz für „gleich": |Δ| ≤ 0.05; „gering": |Δ| ≤ 1.00. „verrechnet": Trades,
die über Legs mit Ausführungen anderer OA-Trades verbunden sind, werden als
Gruppe verglichen; stimmt die Gruppe (|Δ| ≤ 0.05 je Trade), gilt jeder Trade
der Gruppe als verrechnet.

Je Strategie und Währung (nur vergleichbare Trades in den Summen):
  A USD: 3 Trades, gleich 1, abweichend 1, fehlt 1; OA 298.72, IB 208.72, Δ −90.00
  B USD: 2 Trades, abweichend 1, offen 1; OA 12406.46, IB −406.26, Δ −12812.72
  D EUR: 2 Trades, gleich 1, waehrung 1; OA 100.00, IB 100.00, Δ 0.00
  E USD: verrechnet 1, Δ +600.00; F USD: verrechnet 1, Δ −600.00
  G USD: gering 1, Δ +0.10
Reihenfolge nach |Δ| absteigend, bei Gleichstand nach Name: B, E, F, A, G, D.
"""

from datetime import datetime
from decimal import Decimal as D

from analytics.oa_vergleich import oa_vergleich

Z = datetime(2026, 9, 18, 16, 0)


def _t(nr, strategie, status, profit, waehrung="USD"):
    return dict(oa_trade=nr, strategie=strategie, status=status, profit=D(profit),
                waehrung=waehrung, schluss_zeit=Z)


OA = [
    _t("101", "A", "CLOSED", "144.24"),
    _t("102", "A", "EXPIRED (estimated)", "154.48"),
    _t("103", "B", "EXPIRED", "12406.46"),
    _t("104", "B", "RUNNING", "0"),
    _t("105", "A", "CLOSED", "10.00"),
    _t("106", "D", "EXPIRED", "100.00", "EUR"),
    _t("107", "D", "EXPIRED", "50.00", "USD"),
    _t("108", "E", "CLOSED", "-100.00"),
    _t("109", "F", "CLOSED", "-50.00"),
    _t("110", "G", "CLOSED", "20.00"),
]

EXECS = {
    "X1": dict(oa_trade="101", waehrung="USD"), "X2": dict(oa_trade=None, waehrung="USD"),
    "Y1": dict(oa_trade="102", waehrung="USD"), "Y2": dict(oa_trade=None, waehrung="USD"),
    "P1": dict(oa_trade="103", waehrung="USD"), "P2": dict(oa_trade=None, waehrung="USD"),
    "S1": dict(oa_trade=None, waehrung="USD"), "S2": dict(oa_trade=None, waehrung="USD"),
    "R1": dict(oa_trade="104", waehrung="USD"),
    "E1": dict(oa_trade="106", waehrung="EUR"), "E2": dict(oa_trade=None, waehrung="EUR"),
    "F1": dict(oa_trade="107", waehrung="EUR"), "F2": dict(oa_trade=None, waehrung="EUR"),
    "G1": dict(oa_trade="108", waehrung="USD"), "H1": dict(oa_trade="109", waehrung="USD"),
    "H2": dict(oa_trade="109", waehrung="USD"), "H3": dict(oa_trade=None, waehrung="USD"),
    "K1": dict(oa_trade="110", waehrung="USD"), "K2": dict(oa_trade=None, waehrung="USD"),
}


def _leg(o, c, brutto, komm):
    return dict(open_exec_id=o, close_exec_id=c,
                brutto_pnl=None if brutto is None else D(brutto), kommission_gesamt=D(komm))


LEGS = [
    _leg("X1", "X2", "146.00", "-1.76"),
    _leg("Y1", "Y2", "66.00", "-1.52"),
    _leg("P1", "P2", "12407.00", "-0.54"),
    _leg("S1", "S2", "-12811.00", "-1.72"),
    _leg("R1", None, None, "-1.00"),
    _leg("E1", "E2", "102.00", "-2.00"),
    _leg("F1", "F2", "60.00", "-2.00"),
    _leg("G1", "H1", "500.00", "0"),
    _leg("H2", "H3", "-650.00", "0"),
    _leg("K1", "K2", "20.10", "0"),
]
PAARE = [("P2", "S1")]


def _je_nr(e):
    return {t.oa_trade: t for t in e.trades}


def test_trades():
    t = _je_nr(oa_vergleich(OA, LEGS, EXECS, PAARE))
    assert (t["101"].grund, t["101"].ib_netto, t["101"].differenz) == (
        "gleich", D("144.24"), D("0.00"))
    assert (t["102"].grund, t["102"].differenz) == ("schaetzung", D("-90.00"))
    assert (t["103"].grund, t["103"].ib_netto, t["103"].differenz) == (
        "zuteilung", D("-406.26"), D("-12812.72"))
    assert (t["104"].grund, t["104"].ib_netto, t["104"].differenz) == ("offen", None, None)
    assert (t["105"].grund, t["105"].ib_netto) == ("fehlt", None)
    assert (t["106"].grund, t["106"].waehrung) == ("gleich", "EUR")
    assert (t["107"].grund, t["107"].differenz) == ("waehrung", None)


def test_strategien():
    s = oa_vergleich(OA, LEGS, EXECS, PAARE).strategien
    assert [z.strategie for z in s] == ["B", "E", "F", "A", "G", "D"]
    a = s[3]
    assert (a.anzahl, a.gleich, a.abweichend, a.offen, a.fehlt, a.waehrung_unklar) == (
        3, 1, 1, 0, 1, 0)
    assert (a.summe_oa, a.summe_ib, a.differenz) == (D("298.72"), D("208.72"), D("-90.00"))
    b = s[0]
    assert (b.anzahl, b.abweichend, b.offen) == (2, 1, 1)
    assert (b.summe_oa, b.summe_ib, b.differenz) == (D("12406.46"), D("-406.26"), D("-12812.72"))
    d = s[5]
    assert (d.gleich, d.waehrung_unklar, d.differenz) == (1, 1, D("0.00"))


def test_leer():
    e = oa_vergleich([], [], {}, [])
    assert (e.trades, e.strategien) == ([], [])


def test_verrechnet_und_gering():
    e = oa_vergleich(OA, LEGS, EXECS, PAARE)
    t = _je_nr(e)
    assert (t["108"].grund, t["108"].differenz) == ("verrechnet", D("600.00"))
    assert (t["109"].grund, t["109"].differenz) == ("verrechnet", D("-600.00"))
    assert (t["110"].grund, t["110"].differenz) == ("gering", D("0.10"))
    s = {z.strategie: z for z in e.strategien}
    assert (s["E"].verrechnet, s["E"].abweichend, s["E"].differenz) == (1, 0, D("600.00"))
    assert (s["G"].gering, s["G"].abweichend) == (1, 0)
