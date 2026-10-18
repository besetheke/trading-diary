# ruff: noqa: E501
"""Konfiguration der Steuer-Aufbereitung nach Zufluss (AP-10c/10e, Regeln R7, R10, R12 aus AP-10b).

Alles, was eine fachliche Entscheidung ist und sich ändern kann, steht **hier an einer Stelle**: welches Datumsfeld
je Vorgangsart Steuerdatum und Kursdatum ist, welche Quellensteuer-Obergrenze je Land gilt, welche Zeilen der Anlage
KAP je Formularjahr, und auf welcher Grundlage jede Regel steht.

**Quellenhierarchie** (OF-99): 1. Gesetz, 2. BMF-Schreiben vom 14.05.2025, 3. amtlicher Vordruck 2025,
4. BFH-Rechtsprechung, 5. IB-Unterlagen nur zur Klärung des Sachverhalts. Eine Bestätigung durch den Steuerberater ist
eine fachliche Einschätzung, keine Rechtsgrundlage; verbindlich ist nur die Entscheidung des Finanzamts oder eines
Gerichts. Jede Regel trägt deshalb einen Marker: ``amtlich_belegt`` (Gesetz, BMF, Vordruck), ``aus_daten_belegt``
(der Sachverhalt folgt aus den Daten) oder ``vorsichtige_standardbehandlung`` (begründete Annahme, mit der
Erläuterung unter „Ergänzende Angaben zur Steuererklärung“, § 150 Abs. 7 AO, einzureichen).
"""

from dataclasses import dataclass, field, replace
from decimal import Decimal

QUELLENHIERARCHIE = (
    "Gesetz",
    "BMF-Schreiben vom 14.05.2025",
    "amtlicher Vordruck 2025",
    "BFH-Rechtsprechung",
    "IB-Unterlagen nur zur Klärung des Sachverhalts",
)
AMTLICH, AUS_DATEN, VORSICHTIG = "amtlich_belegt", "aus_daten_belegt", "vorsichtige_standardbehandlung"
MARKER = (AMTLICH, AUS_DATEN, VORSICHTIG)

# Regeln und ihre Grundlage (Anzeige auf der Seite und im CSV-Kopf). Rechtsquellen: nicht von mir geprüft (OF-99).
REGELN = (
    {"id": "stillhalterpraemie_zufluss", "marker": AMTLICH,
     "text": "Stillhalterprämie im Zuflussjahr, auch bei offener Position",
     "quelle": "§ 11, § 20 Abs. 1 Nr. 11 EStG; BMF 14.05.2025"},
    {"id": "rueckkauf_negativer_kapitalertrag", "marker": AMTLICH,
     "text": "Rückkaufprämie und Kosten im Zahlungszeitpunkt: negativer Kapitalertrag, im Saldo (Zeile 19) und als "
             "enthaltener Verlust (Zeile 22)",
     "quelle": "BMF 14.05.2025, Rn. 25"},
    {"id": "barausgleich_termingeschaeft", "marker": AMTLICH,
     "text": "Barausgleich bei Indexoptionen als Termingeschäftsverlust bzw. -gewinn",
     "quelle": "§ 20 Abs. 2 EStG; BMF 14.05.2025"},
    {"id": "aktie_zum_strike", "marker": AMTLICH,
     "text": "Zugeteilte oder gelieferte Aktie zum Strike; Stillhalterprämie bleibt separat; gekaufte Option bei "
             "Lieferung in den Anschaffungskosten (Call) bzw. im Veräußerungsergebnis (Put)",
     "quelle": "BMF 14.05.2025, Rn. 22, 29"},
    {"id": "waehrung_je_zahlungsstrom", "marker": AMTLICH,
     "text": "Anschaffung und Veräußerung getrennt zum jeweils maßgeblichen Kurs (nicht Netto zum Schlusskurs)",
     "quelle": "§ 20 Abs. 4 EStG; BMF 14.05.2025, Rn. 85"},
    {"id": "kursquelle_ib", "marker": VORSICHTIG,
     "text": "Kursquelle IB (fxRateToBase je Ausführung, gehört zum Handelstag); wo die Regel den Abrechnungstag "
             "verlangt, steht kursdatum_abweichend",
     "quelle": "IB-Unterlagen (Sachverhalt); Abweichung ein bis zwei Tage"},
    {"id": "datum_abrechnungstag", "marker": VORSICHTIG,
     "text": "Zufluss bzw. Zahlung von Prämie, Rückkauf und Barausgleich nach dem Abrechnungstag (settleDateTarget)",
     "quelle": "§ 11 EStG; Sachverhalt aus IB-Daten"},
    {"id": "verlusttoepfe", "marker": AMTLICH,
     "text": "Aktienverluste nur mit Aktiengewinnen; übrige Kapitalverluste ohne die frühere 20.000-€-Grenze; "
             "die Seite verrechnet nicht",
     "quelle": "§ 20 Abs. 6 EStG"},
    {"id": "quellensteuer_obergrenze", "marker": AMTLICH,
     "text": "Quellensteuer: vorläufig anrechenbar höchstens der DBA-Satz auf die Bruttodividende (USA 15 %)",
     "quelle": "§ 32d Abs. 5 EStG; DBA"},
    {"id": "ersatzzahlung_so", "marker": VORSICHTIG,
     "text": "Ersatzzahlungen (PIL, abzüglich Stornos) und laufende SYEP-Vergütung: Anlage SO, § 22 Nr. 3 EStG, "
             "getrennt ausgewiesen; Freigrenze 256 € für alle Einkünfte dieser Kategorie zusammen",
     "quelle": "§ 22 Nr. 3 EStG; BT-Drs. 18/8739 S. 89 f.; Sachverhalt aus den IB-Daten"},
    {"id": "pil_belastung_nicht_saldiert", "marker": VORSICHTIG,
     "text": "Gezahlte Kompensation aus einem Leerverkauf (negative PIL ohne Storno) nicht gegen die empfangenen "
             "Ersatzzahlungen saldiert und nicht als abzugsfähig angesetzt",
     "quelle": "vorsichtige Behandlung; Sachverhalt aus den IB-Daten"},
    {"id": "pil_quellensteuer_nicht_kap41", "marker": VORSICHTIG,
     "text": "Quellensteuer auf Ersatzzahlungen nicht in Zeile 41, gesondert zu prüfen (Anlage AUS bzw. Erstattung)",
     "quelle": "vorsichtige Behandlung"},
    {"id": "sollzinsen_nicht_abziehbar", "marker": AMTLICH,
     "text": "Sollzinsen und Marktdatengebühren nicht abziehbar; Kommissionen als Transaktionskosten",
     "quelle": "§ 20 Abs. 9 EStG"},
    {"id": "etf_ausgesondert", "marker": VORSICHTIG,
     "text": "ETF/ETN/ETP-Anteile nicht im Aktien-Topf (Investmentsteuerrecht), nicht berechnet",
     "quelle": "InvStG; Sachverhalt aus den IB-Daten"},
    {"id": "deutsche_emittenten_zeile_18", "marker": AUS_DATEN,
     "text": "Aktien deutscher Emittenten (ISIN DE, ohne deutschen Steuerabzug): Ergebnis in Zeile 18 statt 19; Zeile 20 "
             "unverändert",
     "quelle": "§ 34d EStG; Emittent aus der ISIN"},
    {"id": "kap_zeilen_formular", "marker": AMTLICH,
     "text": "Zeilen der Anlage KAP 2025 laut amtlichem Vordruck; 2026 vorsichtshalber wie 2025",
     "quelle": "amtlicher Vordruck 2025 (2026 liegt nicht vor)"},
)

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
    "inl_kapitalertraege_saldo": 18,
    "ausl_kapitalertraege_saldo": 19,
    "aktiengewinne": 20,
    "verluste_ohne_aktien": 22,
    "aktienverluste": 23,
    "anrechenbare_quellensteuer": 41,
}
KAP_ZEILEN = {
    2025: {"status": AMTLICH, "zeilen": _ZEILEN_2025},
    2026: {"status": VORSICHTIG, "zeilen": _ZEILEN_2025},
}


@dataclass(frozen=True)
class Konfig:
    regeln: dict = field(default_factory=lambda: {k: dict(v) for k, v in _STANDARD_REGELN.items()})
    laender_saetze: dict = field(default_factory=lambda: dict(_STANDARD_SAETZE))
    kursquelle: str = KURSQUELLE_IB
    kursdatum_feld: str = KURSDATUM_FELD_IB
    pruefstatus: str = "regelweise"  # Marker je Regel, siehe ``REGELN``
    # Behandlung gezahlter Rückkaufprämien in Zeile 22: ``True`` = zusätzlich zum Saldo als enthaltener Verlust
    # (BMF 14.05.2025, Rn. 25, Standard); ``False`` = nur im Saldo. Die Vorschau zeigt immer beide Werte.
    rueckkauf_als_verlust: bool = True

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
        return {"status": VORSICHTIG, "zeilen": dict(_ZEILEN_2025)}
    return {"status": eintrag["status"], "zeilen": dict(eintrag["zeilen"])}
