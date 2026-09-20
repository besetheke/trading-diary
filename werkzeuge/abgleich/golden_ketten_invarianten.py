"""Invarianten-Prüfung für die Kettenbildung (AP-04, Plan §6, „Invarianten,
gesamter Bestand" — die zweite der drei Abnahmeprüfungen neben dem
OA-Abgleich und der Stichprobe für den Nicht-OA-Teil).

Prüft `engine.chains.bilde_chains()` gegen die gesamte Golden-Historie auf
vier Eigenschaften, die für JEDE Kette gelten müssen, unabhängig davon, ob
sie über OA-Referenz, `exec_batch`-Roll, Zeitfenster-Roll oder gar nicht
verkettet wurde:

1. Keine Structure liegt in mehr als einer Kette.
2. Nur das letzte Glied einer Kette darf offen sein — jedes vorangehende
   Glied ist geschlossen (sonst wäre die Kette an der falschen Stelle
   fortgesetzt worden).
3. Jede Rollverknüpfung (zwei aufeinanderfolgende Glieder) hat dieselbe
   Basiswert — eine schließende und eine eröffnende Seite auf demselben
   Underlying.
4. Die Summe des Ketten-Ergebnisses (über alle vollständig geschlossenen
   Ketten) entspricht der Summe der Struktur-Ergebnisse derselben Structures
   — es geht nichts verloren und nichts entsteht doppelt beim Verketten.

Regel 2: nur Zählwerte und Prozentangaben, keine Beträge, Titel oder
`conid`s.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_ketten_invarianten.py``
"""

import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402

from engine.chains import bilde_chains  # noqa: E402
from engine.matching import bilde_legs  # noqa: E402
from engine.structures import bilde_structures  # noqa: E402


def main() -> None:
    exec_rows, instruments, corporate_actions, _open = _bestandsabgleich.sammeln()
    massnahmen, _uebersprungen, _ohne_instr = _bestandsabgleich.kapitalmassnahmen_ableiten(
        corporate_actions, instruments
    )
    matching_ergebnis = bilde_legs(exec_rows, instruments, massnahmen)

    legs = [
        {
            "conid": leg.conid,
            "open_exec_id": leg.open_exec_id,
            "close_exec_id": leg.close_exec_id,
            "menge": leg.menge,
            "offen_ja_nein": leg.offen_ja_nein,
            "brutto_pnl": leg.brutto_pnl,
            "kommission_gesamt": leg.kommission_gesamt,
        }
        for leg in matching_ergebnis.legs
    ]

    struktur_ergebnis = bilde_structures(legs, exec_rows, instruments)
    ketten_ergebnis = bilde_chains(struktur_ergebnis, legs, exec_rows, instruments)

    print(f"Structures: {len(struktur_ergebnis.structures)}")
    print(f"Chains: {len(ketten_ergebnis.chains)}")
    print()

    # 1. Keine Structure in mehr als einer Kette.
    gesehen: Counter = Counter()
    for chain in ketten_ergebnis.chains:
        for glied in chain.glieder:
            gesehen[glied.structure.leg_schluessel] += 1
    mehrfach = sum(1 for anzahl in gesehen.values() if anzahl > 1)
    print(f"1) Structures in mehr als einer Kette: {mehrfach} von {len(gesehen)}")

    # 2. Nur das letzte Glied darf offen sein.
    verletzt_reihenfolge = 0
    for chain in ketten_ergebnis.chains:
        for glied in chain.glieder[:-1]:
            if glied.structure.status != "geschlossen":
                verletzt_reihenfolge += 1
    print(f"2) Ketten mit offenem Nicht-Schlussglied: {verletzt_reihenfolge} "
          f"von {len(ketten_ergebnis.chains)}")

    # 3. Jede Rollverknüpfung: gleicher Basiswert beidseitig.
    verletzt_underlying = 0
    rollverknuepfungen = 0
    for chain in ketten_ergebnis.chains:
        for a, b in zip(chain.glieder, chain.glieder[1:], strict=False):
            rollverknuepfungen += 1
            if a.structure.underlying != b.structure.underlying:
                verletzt_underlying += 1
    print(f"3) Rollverknüpfungen mit unterschiedlichem Underlying: "
          f"{verletzt_underlying} von {rollverknuepfungen}")

    # 4. Chain.brutto_pnl == unabhängig aus der rohen Structure-Liste
    #    aufsummiertes Ergebnis derselben Glieder — schützt gegen Verlust
    #    oder Doppelzählung einer Structure beim Verketten.
    struktur_je_schluessel = {
        s.leg_schluessel: s for s in struktur_ergebnis.structures
    }
    abweichende_ketten = 0
    gepruefte_ketten = 0
    TOLERANZ = Decimal("0.01")
    for chain in ketten_ergebnis.chains:
        if chain.brutto_pnl is None:
            continue
        gepruefte_ketten += 1
        kontrollsumme = Decimal(0)
        for glied in chain.glieder:
            original = struktur_je_schluessel.get(glied.structure.leg_schluessel)
            wert = original.brutto_pnl if original is not None else glied.structure.brutto_pnl
            if wert is not None:
                kontrollsumme += wert
        if abs(chain.brutto_pnl - kontrollsumme) > TOLERANZ:
            abweichende_ketten += 1
    print(f"4) Ketten mit abweichender Ergebnissumme: {abweichende_ketten} "
          f"von {gepruefte_ketten} geprüften (vollständig geschlossenen)")

    print()
    alle_bestanden = (
        mehrfach == 0
        and verletzt_reihenfolge == 0
        and verletzt_underlying == 0
        and abweichende_ketten == 0
    )
    print("Alle vier Invarianten erfüllt." if alle_bestanden else "MINDESTENS EINE INVARIANTE VERLETZT.")


if __name__ == "__main__":
    main()
