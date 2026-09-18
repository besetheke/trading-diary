"""Vollständigkeitsprüfung: importierte Ausführungen gegen IBs Performance
Summary (Plan §4, „Monetär — zwei verschiedene Fragen, zwei verschiedene
Prüfungen").

Der Vergleich je Ausführung (`golden_geldtest_fifopnl.py`) ist eine
Genauigkeitsprüfung: Er deckt nur Ausführungen ab, die tatsächlich importiert
wurden. Ein vollständig fehlender Round Trip — Eröffnung und Schließung beide
nicht importiert — fiele dort nicht auf, weil es nichts zu vergleichen gäbe.

**Konstruktion, um die bekannte Prämiendifferenz (OF-24) nicht erneut zu
messen.** Ein direkter Vergleich des eigenen, an der Option realisierten
Ergebnisses gegen IBs Summary (die Prämie in der Aktienbasis führt) wäre von
genau der schon bezifferten, akzeptierten Differenz dominiert — nicht von
fehlenden Ausführungen. Deshalb wird **nicht** das eigene P&L-Ergebnis
verglichen, sondern **IBs eigener `fifoPnlRealized`-Wert je Ausführung**,
summiert über die Menge der **von uns importierten** Ausführungen, gegen IBs
eigene Summe in der Performance Summary. Stimmen beide überein, hat IB keine
Ausführung gezählt, die uns fehlt — unabhängig davon, ob unser Matching die
Prämie an der Option oder der Aktie realisiert.

**Fensterkaveat, gemessen 18.09.2026.** Die Performance Summary ist nur in
Exporten gefüllt, deren Trades kein `model`-Attribut tragen (OF-21) — von
neun Golden-Exporten sind das fünf, mit den Fenstern April–März (vier davon)
und Januar–September 2026 (das jüngste). **Keines davon ist ein
Kalenderjahr**; die kalenderjahrgleichen Exporte tragen durchweg
`model="Independent"` und liefern eine leere Performance Summary. Dieses
Skript vergleicht deshalb je verfügbarem Fenster, nicht je Kalenderjahr.

Regel 2: nur Zählwerte, Prozentangaben und Pseudonyme.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_geldtest_vollstaendigkeit.py``
"""

import contextlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402
import golden_geldtest_fifopnl as _geldtest  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
DATEIEN = sorted(GOLDEN.glob("U8443617_*.xml"))
TOLERANZ = Decimal("0.02")


def _datum(jjjjmmtt: str):
    from datetime import date

    return date(int(jjjjmmtt[:4]), int(jjjjmmtt[4:6]), int(jjjjmmtt[6:8]))


def modellfreie_fenster():
    """Je modellfreier Datei: (von, bis, {(conid, asset_class): totalRealizedPnl})."""
    fenster = []
    for datei in DATEIEN:
        root = ET.parse(datei).getroot()
        modelle = {t.attrib.get("model") or "" for t in root.iter("Trade")}
        if modelle != {""}:
            continue
        stmt = root.find(".//FlexStatement")
        von = _datum(stmt.attrib["fromDate"])
        bis = _datum(stmt.attrib["toDate"])
        werte: dict[tuple[int, str], Decimal] = defaultdict(Decimal)
        ohne_klasse = 0
        for summary in root.iter("FIFOPerformanceSummaryInBase"):
            for row in summary:
                conid = row.attrib.get("conid")
                klasse = row.attrib.get("assetCategory") or ""
                wert = row.attrib.get("totalRealizedPnl")
                if not conid or wert in (None, ""):
                    continue
                if not klasse:
                    ohne_klasse += 1
                    continue
                with contextlib.suppress(InvalidOperation):
                    werte[(int(conid), klasse)] += Decimal(wert)
        fenster.append((von, bis, werte, ohne_klasse))
    return fenster


def main() -> None:
    exec_rows, instruments, _corp, _open = _bestandsabgleich.sammeln()
    ib_pnl_lokal, _uebergangen = _geldtest.ib_fifo_pnl_je_trade()

    fenster = modellfreie_fenster()
    print(f"modellfreie Fenster mit Performance Summary: {len(fenster)}")
    print(f"importierte Ausführungen mit IB-Referenzwert: {len(ib_pnl_lokal)} von "
          f"{len(exec_rows)}")

    ohne_kurs = 0
    zeilen_gesamt = 0
    treffer_gesamt = 0

    for von, bis, ib_summary, ohne_klasse in fenster:
        eigene_menge_eur: dict[str, Decimal] = defaultdict(Decimal)
        for satz in exec_rows:
            exec_id = satz["exec_id"]
            if exec_id not in ib_pnl_lokal:
                continue
            if not (von <= satz["handelszeit"].date() <= bis):
                continue
            kurs = satz.get("buchungskurs")
            if kurs is None:
                ohne_kurs += 1
                continue
            klasse = instruments.get(satz["conid"], {}).get("asset_class") or "?"
            eigene_menge_eur[klasse] += ib_pnl_lokal[exec_id] * kurs

        ib_je_klasse: dict[str, Decimal] = defaultdict(Decimal)
        for (_conid, klasse), wert in ib_summary.items():
            ib_je_klasse[klasse] += wert

        print(f"\nFenster {von.isoformat()}–{bis.isoformat()} "
              f"(ohne Anlageklasse in IBs Summary: {ohne_klasse}):")
        for klasse in sorted(set(eigene_menge_eur) | set(ib_je_klasse)):
            eigen = eigene_menge_eur.get(klasse, Decimal(0))
            ib = ib_je_klasse.get(klasse, Decimal(0))
            diff = abs(eigen - ib)
            zeilen_gesamt += 1
            if diff <= TOLERANZ:
                treffer_gesamt += 1
                print(f"  {klasse}: exakt (±0,02 EUR)")
                continue
            if ib != 0:
                relativ = (diff / abs(ib) * 100).quantize(Decimal("0.1"))
                print(f"  {klasse}: Abweichung, relativ zu IB {relativ} %")
            else:
                print(f"  {klasse}: Abweichung, IB-Wert 0 (kein Bezugspunkt für %)")

    print(f"\nAusführungen ohne buchungskurs (übergangen): {ohne_kurs}")
    print(f"Fenster×Anlageklasse insgesamt: {zeilen_gesamt}, "
          f"davon exakt (±0,02 EUR): {treffer_gesamt}")


if __name__ == "__main__":
    main()
