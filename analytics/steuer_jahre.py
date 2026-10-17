# ruff: noqa: E501
"""Jahresübersicht der steuerlichen Aufbereitung (Seite „Steuer“, 17.10.2026).

Fasst das Ergebnis von ``analytics.steuer`` (Töpfe je Jahr/Währung, EUR über den Buchungskurs der
Schließung — OF-59) mit den Erträgen aus ``analytics.cashflows`` (EUR) je Zuflussjahr zusammen. Rein.
Keine Steuerberatung und **keine Verlustverrechnung**: die Zahlen sind die Aufbereitung für den
Steuerberater; wie sie verrechnet und in die Anlage KAP übertragen werden, entscheidet der.
"""

from decimal import Decimal

from analytics.steuer import TOPF_AKTIEN, TOPF_TERMIN, SteuerErgebnis

# Cash-Kategorien (analytics.cashflows), die steuerlich neben den Töpfen stehen. Kommissionen und
# Barausgleich stecken schon in den Töpfen, Ein-/Auszahlungen sind kein Ertrag.
ERTRAGS_KATEGORIEN = (
    "dividenden",
    "quellensteuer",
    "zinsen_erhalten",
    "zinsen_gezahlt",
    "gebuehren",
    "kommissionsanpassungen",
    "sonstige",
)

_NULL = Decimal("0")


def jahres_uebersicht(
    ergebnis: SteuerErgebnis,
    cash_monate: list[tuple[str, str, Decimal]],
    lieferung_close_ids: frozenset[str] = frozenset(),
) -> dict[int, dict]:
    """Je Zuflussjahr: Summe der Töpfe in EUR, Zahl der Legs, fehlende Kurse und Erträge je Kategorie.

    ``cash_monate``: (Monat ``JJJJ-MM``, Kategorie, Summe EUR) wie ``cashflow_bericht`` sie liefert.
    ``lieferung_close_ids``: Schließungen von Optionen, die mit Lieferung endeten (Zuteilung/Ausübung
    mit Aktien). Ihre Prämie steht in den Termingeschäften, die Aktie trägt den Gegenposten im
    Aktien-Topf; ``praemie_lieferung_eur`` nennt sie je Jahr (Frage an den Steuerberater, OF-91).
    """
    jahre: dict[int, dict] = {}

    def jahr(j: int) -> dict:
        return jahre.setdefault(
            j,
            {
                "aktien_eur": _NULL,
                "termin_eur": _NULL,
                "aktien_legs": 0,
                "termin_legs": 0,
                "eur_kurs_fehlt": 0,
                "ungeklaert": 0,
                "praemie_lieferung_eur": _NULL,
                "ertraege": {k: _NULL for k in ERTRAGS_KATEGORIEN},
            },
        )

    for t in ergebnis.toepfe:
        z = jahr(t.jahr)
        if t.topf == TOPF_AKTIEN:
            z["aktien_eur"] += t.netto_eur_ib
            z["aktien_legs"] += t.anzahl_legs
        elif t.topf == TOPF_TERMIN:
            z["termin_eur"] += t.netto_eur_ib
            z["termin_legs"] += t.anzahl_legs
        z["eur_kurs_fehlt"] += t.eur_kurs_fehlt
    for d in ergebnis.details:
        if d.topf == TOPF_TERMIN and d.close_exec_id in lieferung_close_ids and d.netto_eur_ib is not None:
            jahr(d.jahr)["praemie_lieferung_eur"] += d.netto_eur_ib
    for u in ergebnis.ungeklaert:
        jahr(u.jahr)["ungeklaert"] += 1
    for monat, kategorie, summe in cash_monate:
        if kategorie in ERTRAGS_KATEGORIEN:
            jahr(int(monat[:4]))["ertraege"][kategorie] += summe
    return dict(sorted(jahre.items()))
