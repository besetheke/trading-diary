"""Unrealisiertes Ergebnis offener Legs (AP-07fu).

Bewertet offene Legs mit IBs letztem Marktwert (``flex_open_positions``,
jüngster Stichtag) gegen den **Journal-Einstand** — passend zur realisierten
Rechnung des Journals (die Prämie einer Zuteilung steht dort schon im
realisierten Ergebnis, nicht im Einstand).

Je offenem Leg, in Positionswährung:

- Einstand = Vorzeichen (Kauf +, Verkauf −) × Preis ÷ Faktor × |Menge| ×
  Multiplikator − Kommission des Legs (Kommission ist negativ gebucht, erhöht
  also die Kosten). Faktor wie im Matching (Kapitalmaßnahmen, AP-03vz2).
- Wert = IBs Marktwert der conid × |Leg-Menge| ÷ |Menge der Position| (das Leg
  kann ein Teil der Position sein).
- Unrealisiert = Wert − Einstand, in EUR mit IBs Kurs der Bestandszeile.

Ohne Bestandszeile kein Wert — gezählt, nie still 0.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_NULL = Decimal("0")


@dataclass(frozen=True)
class Unrealisiert:
    stichtag: date | None
    eur: Decimal
    anzahl_legs: int     # bewertet
    ohne_kurs: int       # ohne Bestandszeile
    # AP-06sf: Prämienwert aus Sicht des Verkäufers (Credit positiv), EUR.
    # ``praemie_eur``: Prämie bei Eröffnung aller offenen Legs, ohne Kommission
    # — auch ohne Bestandszeile bekannt. ``aktuell_eur``: −Marktwert laut IB
    # der bewerteten Legs. Probe: praemie(bewertete) − aktuell − Kommission
    # = unrealisiert.
    praemie_eur: Decimal = _NULL
    aktuell_eur: Decimal = _NULL


def unrealisiert_auswertung(
    offene_legs: list[dict],
    exec_je_id: dict[str, dict],
    mult_je_conid: dict[int, Decimal],
    bestand_je_conid: dict[int, dict],
    stichtag: date | None,
) -> Unrealisiert:
    """Rein. ``offene_legs``: ``conid``, ``open_exec_id``, ``menge``,
    ``kommission_gesamt``, ``open_faktor``. ``bestand_je_conid``: conid →
    ``menge``, ``wert`` (positionValue), ``kurs`` (fxRateToBase)."""
    summe = praemie = aktuell = _NULL
    bewertet = ohne = 0
    for leg in offene_legs:
        b = bestand_je_conid.get(leg["conid"])
        a = exec_je_id[leg["open_exec_id"]]
        faktor = leg.get("open_faktor") or Decimal(1)
        menge = abs(leg["menge"])
        vorzeichen = 1 if a["side"] == "BUY" else -1
        preis = a["preis"] if faktor == 1 else a["preis"] / faktor
        # Der Prämienwert bei Eröffnung braucht keinen Bestand; der Kurs zur
        # Umrechnung kommt aus der Bestandszeile, sonst aus dem Buchungskurs
        # der Ausführung — fehlt beides, bleibt der Leg ohne Prämie.
        kurs = b["kurs"] if b is not None else a.get("buchungskurs")
        if kurs is not None:
            praemie -= vorzeichen * preis * menge * mult_je_conid[leg["conid"]] * kurs
        if b is None or b["menge"] == 0:
            ohne += 1
            continue
        einstand = vorzeichen * preis * menge * mult_je_conid[leg["conid"]] - (
            leg["kommission_gesamt"] or _NULL
        )
        wert = b["wert"] * menge / abs(b["menge"])
        summe += (wert - einstand) * b["kurs"]
        aktuell -= wert * b["kurs"]
        bewertet += 1
    return Unrealisiert(stichtag=stichtag, eur=summe, anzahl_legs=bewertet, ohne_kurs=ohne,
                        praemie_eur=praemie, aktuell_eur=aktuell)
