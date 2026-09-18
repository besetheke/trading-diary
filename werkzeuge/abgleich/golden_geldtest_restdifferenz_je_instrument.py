"""Restdifferenz des Geldtests je Instrument, pseudonymisiert (OF-24, Plan §4).

Erzeugt `auftraege/AP-03-restdifferenz-je-instrument.csv` — die bezifferte
Schuld, die AP-04 mit `assignment_links` und der Prämienspeicherung auf null
bringen muss, je Pseudonym statt nur in der Summe. Eine Summe je Jahr und
Währung kann auch dann auf null gehen, wenn sich Fehler über Instrumente
hinweg aufheben; das soll die Bezifferung ausschließen.

Das Pseudonym ist ein gesalzener Hash der `conid` (siehe `pseudonym.py`) —
stabil über Läufe hinweg, aber ohne das lokale Salz nicht auf die echte
`conid` zurückrechenbar (Regel 2). Grundlage ist derselbe Vergleich wie in
`golden_geldtest_fifopnl.py` (Brutto plus Kommission gegen IBs
`fifoPnlRealized`, Toleranz 0,02 Lokalwährung), hier aber je Instrument statt
aggregiert.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_geldtest_restdifferenz_je_instrument.py``
"""

import csv
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402
import golden_geldtest_fifopnl as _geldtest  # noqa: E402
from pseudonym import pseudonym  # noqa: E402

from engine.matching import bilde_legs  # noqa: E402

ZIEL = Path(__file__).resolve().parents[2] / "auftraege" / "AP-03-restdifferenz-je-instrument.csv"
TOLERANZ = Decimal("0.02")


def _kategorie(satz, instrument) -> str:
    if instrument.get("asset_class") == "STK":
        return "praemie_aktienseite"
    if satz["ereignistyp"] in ("assignment", "exercise"):
        return "praemie_optionsseite"
    return "zuordnung"


def main() -> None:
    exec_rows, instruments, corporate_actions, _ = _bestandsabgleich.sammeln()
    massnahmen, _, _ = _bestandsabgleich.kapitalmassnahmen_ableiten(
        corporate_actions, instruments
    )
    betroffene_conids = {
        c for k in massnahmen for c in (k["alter_conid"], k["neuer_conid"]) if c is not None
    }
    ergebnis = bilde_legs(exec_rows, instruments, massnahmen)
    geschlossene = [leg for leg in ergebnis.legs if not leg.offen_ja_nein]
    ib_pnl, _ = _geldtest.ib_fifo_pnl_je_trade()
    exec_je_id = {r["exec_id"]: r for r in exec_rows}

    legs_je_exec: dict[str, list] = defaultdict(list)
    for leg in geschlossene:
        if leg.conid not in betroffene_conids:
            legs_je_exec[leg.close_exec_id].append(leg)

    zellen: dict[tuple[str, int, str], Decimal] = defaultdict(Decimal)
    waehrung_je_pseudonym: dict[str, str] = {}
    for exec_id, legs in legs_je_exec.items():
        satz = exec_je_id.get(exec_id)
        if satz is None or exec_id not in ib_pnl:
            continue
        instrument = instruments.get(satz["conid"], {})
        eigen = sum((leg.brutto_pnl + leg.kommission_gesamt for leg in legs), Decimal(0))
        differenz = eigen - ib_pnl[exec_id]
        if abs(differenz) <= TOLERANZ:
            continue
        kategorie = _kategorie(satz, instrument)
        jahr = satz["handelszeit"].year
        pseud = pseudonym(satz["conid"])
        waehrung_je_pseudonym[pseud] = instrument.get("waehrung") or "?"
        zellen[(pseud, jahr, kategorie)] += differenz

    zeilen = sorted({(pseud, jahr) for (pseud, jahr, _k) in zellen})
    with open(ZIEL, "w", newline="", encoding="utf-8") as datei:
        schreiber = csv.writer(datei)
        schreiber.writerow(
            [
                "pseudonym",
                "jahr",
                "waehrung",
                "praemie_aktienseite",
                "praemie_optionsseite",
                "zuordnung",
            ]
        )
        for pseud, jahr in zeilen:
            schreiber.writerow(
                [
                    pseud,
                    jahr,
                    waehrung_je_pseudonym[pseud],
                    zellen.get((pseud, jahr, "praemie_aktienseite"), Decimal(0)),
                    zellen.get((pseud, jahr, "praemie_optionsseite"), Decimal(0)),
                    zellen.get((pseud, jahr, "zuordnung"), Decimal(0)),
                ]
            )

    print(f"geschrieben: {ZIEL}")
    print(f"Zeilen (Pseudonym x Jahr): {len(zeilen)}")
    print(f"betroffene Instrumente: {len(waehrung_je_pseudonym)}")

    summe: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for (pseud, _jahr, kategorie), wert in zellen.items():
        summe[(kategorie, waehrung_je_pseudonym[pseud])] += wert
    print("Gegenprobe, Summe je Kategorie und Währung:")
    for (kategorie, waehrung), wert in sorted(summe.items()):
        print(f"  {kategorie} {waehrung}: {wert:.2f}")


if __name__ == "__main__":
    main()
