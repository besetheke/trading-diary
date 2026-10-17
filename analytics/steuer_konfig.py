# ruff: noqa: E501
"""Konfiguration der Steuer-Aufbereitung nach Zufluss (AP-10c, Regeln R7, R10, R12 aus AP-10b).

Alles, was eine fachliche Entscheidung ist und sich ändern kann, steht **hier an einer Stelle**: welches Datumsfeld
je Vorgangsart Steuerdatum und Kursdatum ist, welche Quellensteuer-Obergrenze je Land gilt, welche Zeilen der Anlage
KAP je Formularjahr. Arbeitsstand des Steuerberaters (OF-92), vor Abnahme zu bestätigen — daher überall der
Prüfstatus ``ungeprueft``.
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal

KURSQUELLE_IB = "IB fxRateToBase je Ausführung"
# Der IB-Kurs ``fxRateToBase`` einer Ausführung gehört zum Handelstag (tradeDate), nicht zum Abrechnungstag.
KURSDATUM_FELD_IB = "tradeDate"

FELD_HANDEL = "tradeDate"
FELD_ABRECHNUNG = "settleDateTarget"
FELD_ZEIT = "dateTime"
FELDER = (FELD_HANDEL, FELD_ABRECHNUNG, FELD_ZEIT)

# Vorgangsart -> (Steuerdatum-Feld, gewünschtes Kursdatum-Feld). Prämie, Glattstellung und Barausgleich folgen dem
# tatsächlichen Zufluss bzw. der Zahlung (Abrechnung), Wertpapiergeschäfte dem Geschäftsabschluss (Handelstag).
VORGANGSARTEN = (
    "stillhalterpraemie",
    "glattstellung",
    "barausgleich",
    "termingeschaeft",
    "wertpapierkauf",
    "wertpapierverkauf",
    "dividende",
    "zins",
)

_STANDARD_REGELN = {
    "stillhalterpraemie": {"steuerdatum": FELD_ABRECHNUNG, "fx": FELD_ABRECHNUNG},
    "glattstellung": {"steuerdatum": FELD_ABRECHNUNG, "fx": FELD_ABRECHNUNG},
    "barausgleich": {"steuerdatum": FELD_ABRECHNUNG, "fx": FELD_ABRECHNUNG},
    "termingeschaeft": {"steuerdatum": FELD_HANDEL, "fx": FELD_HANDEL},
    "wertpapierkauf": {"steuerdatum": FELD_HANDEL, "fx": FELD_HANDEL},
    "wertpapierverkauf": {"steuerdatum": FELD_HANDEL, "fx": FELD_HANDEL},
    "dividende": {"steuerdatum": FELD_ABRECHNUNG, "fx": FELD_ABRECHNUNG},
    "zins": {"steuerdatum": FELD_ABRECHNUNG, "fx": FELD_ABRECHNUNG},
}

# Obergrenze der anrechenbaren Quellensteuer je Land (Anteil der Bruttodividende). Land ohne Eintrag: nicht berechnet.
# USA 15 % (DBA, W-8BEN). Weitere Länder erst nach Prüfung eintragen.
_STANDARD_SAETZE = {"US": Decimal("0.15")}

# Anlage KAP je Formularjahr: Posten -> Zeile. 2025 laut Antwort des Steuerberaters; 2026 ungeprüft (amtlicher
# Vordruck liegt noch nicht vor).
_ZEILEN_2025 = {
    "ausl_kapitalertraege_saldo": 19,
    "aktiengewinne": 20,
    "verluste_ohne_aktien": 22,
    "aktienverluste": 23,
    "anrechenbare_quellensteuer": 41,
}
KAP_ZEILEN = {
    2025: {"status": "laut_berater_antwort", "zeilen": _ZEILEN_2025},
    2026: {"status": "ungeprueft", "zeilen": _ZEILEN_2025},
}


@dataclass(frozen=True)
class Konfig:
    regeln: dict = field(default_factory=lambda: {k: dict(v) for k, v in _STANDARD_REGELN.items()})
    laender_saetze: dict = field(default_factory=lambda: dict(_STANDARD_SAETZE))
    kursquelle: str = KURSQUELLE_IB
    kursdatum_feld: str = KURSDATUM_FELD_IB
    pruefstatus: str = "ungeprueft"
    # Behandlung gezahlter Rückkaufprämien in Zeile 22: ``False`` = nur im Saldo der Stillhalter (Antwort des
    # Steuerberaters, „negative Einnahme“), ``True`` = zusätzlich als enthaltener Verlust (mögliche Verwaltungsauffassung,
    # Frage an den Steuerberater). Die Vorschau zeigt immer beide Werte.
    rueckkauf_als_verlust: bool = False

    def mit_regel(self, vorgang: str, *, steuerdatum: str | None = None, fx: str | None = None) -> "Konfig":
        """Kopie mit geänderter Regel für eine Vorgangsart (Tests, spätere Entscheidung des Steuerberaters)."""
        if vorgang not in self.regeln:
            raise KeyError(f"unbekannte Vorgangsart {vorgang!r}")
        neu = {k: dict(v) for k, v in self.regeln.items()}
        for schluessel, wert in (("steuerdatum", steuerdatum), ("fx", fx)):
            if wert is not None:
                if wert not in FELDER:
                    raise ValueError(f"unbekanntes Datumsfeld {wert!r}")
                neu[vorgang][schluessel] = wert
        return replace(self, regeln=neu)

    def alternative(self, vorgang: str) -> str:
        """Das jeweils andere Steuerdatum-Feld (Handel <-> Abrechnung), für die Betroffenheit."""
        return FELD_HANDEL if self.regeln[vorgang]["steuerdatum"] != FELD_HANDEL else FELD_ABRECHNUNG


STANDARD_KONFIG = Konfig()


def kap_zeilen(formularjahr: int) -> dict:
    """Zeilen der Anlage KAP des Formularjahrs samt Status; unbekannte Jahre gelten als ungeprüft."""
    eintrag = KAP_ZEILEN.get(formularjahr)
    if eintrag is None:
        return {"status": "ungeprueft", "zeilen": dict(_ZEILEN_2025)}
    return {"status": eintrag["status"], "zeilen": dict(eintrag["zeilen"])}
