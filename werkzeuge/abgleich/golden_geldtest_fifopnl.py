"""Geldtest je schließender Ausführung gegen IBs ``fifoPnlRealized`` (OF-24).

Vergleicht das eigene, echte Matching (``engine.matching.bilde_legs()``,
Kommission addiert, mit ``executions.buchungskurs`` in EUR umgerechnet) mit
IBs ``fifoPnlRealized`` je Ausführung (roh am ``Trade``-Element) — bewusst
NICHT gegen die periodenaggregierten ``FIFOPerformanceSummaryInBase``-Werte,
die über die neun sich überlappenden Golden-Exporte hinweg nicht
deduplizierbar wären (gemessen: dieselbe conid trägt in überlappenden
Perioden unterschiedliche Summen — die Sektion ist periodenspezifisch, nicht
kumulativ). Der Vergleich je Ausführung braucht das nicht: jede Ausführung
kommt über ``exec_id`` genau einmal vor.

Regeln (CLAUDE.md, Regel 2): ausgegeben werden ausschließlich Zählwerte,
Prozentangaben, relative Größenordnungen und Pseudonyme — keine Beträge,
Titel, conids oder Kontonummern.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_geldtest_fifopnl.py``
"""

import contextlib
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402

from engine.matching import bilde_legs  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
DATEIEN = sorted(GOLDEN.glob("U8443617_*.xml"))

TOLERANZ = Decimal("0.02")


def ib_fifo_pnl_je_trade() -> tuple[dict[str, Decimal], int]:
    """``fifoPnlRealized`` je ``tradeID`` — **nur aus modellfreien Exporten**.

    IB schaltet alle Felder zum realisierten Ergebnis ab, sobald ein Modell
    einbezogen ist (OF-21): In den Exporten mit ``model="Independent"`` steht
    an jeder Zeile ``fifoPnlRealized="0"``. Gemessen 17.09.2026: 14.009
    ``tradeID``s kommen in beiden Varianten vor, und **in jedem einzelnen
    Fall** steht die 0 im Modell-Export und der echte Wert im modellfreien.
    Eine Deduplizierung nach „erste Datei gewinnt" nimmt daher massenhaft
    Nullen als Referenz und erzeugt Scheinabweichungen (Trefferquote 63,9 %
    statt 93,2 %).

    Zeilen mit gesetztem ``model`` werden deshalb übergangen. Eine
    Ausführung, die es nur dort gibt, hat keine Referenz und wird nicht
    verglichen — das ist ehrlicher, als sie gegen eine abgeschaltete 0 zu
    stellen. Rückgabe: Werte und die Zahl der übergangenen Modellzeilen.
    """
    werte: dict[str, Decimal] = {}
    uebergangen = 0
    for datei in DATEIEN:
        root = ET.parse(datei).getroot()
        for el in root.iter("Trade"):
            tid = el.attrib.get("tradeID")
            wert = el.attrib.get("fifoPnlRealized")
            if not tid or wert in (None, ""):
                continue
            if (el.attrib.get("model") or "").strip():
                uebergangen += 1
                continue
            with contextlib.suppress(InvalidOperation):
                werte.setdefault(tid, Decimal(wert))
    return werte, uebergangen


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

    eigen_je_exec: dict[str, Decimal] = defaultdict(Decimal)
    for leg in geschlossene:
        if leg.conid in betroffene_conids:
            continue
        eigen_je_exec[leg.close_exec_id] += leg.brutto_pnl + leg.kommission_gesamt

    ib_pnl, modellzeilen_uebergangen = ib_fifo_pnl_je_trade()

    exec_conid = {r["exec_id"]: r["conid"] for r in exec_rows}
    exec_asset_class = {
        r["exec_id"]: instruments.get(r["conid"], {}).get("asset_class") for r in exec_rows
    }
    exec_ereignistyp = {r["exec_id"]: r["ereignistyp"] for r in exec_rows}
    conids_mit_zuteilung = {
        r["conid"] for r in exec_rows if r["ereignistyp"] in ("assignment", "exercise")
    }
    underlyings_mit_zuteilung = {
        instruments.get(c, {}).get("underlying") for c in conids_mit_zuteilung
    }

    treffer = 0
    fehltreffer = 0
    ohne_referenz = 0
    kombi_treffer: dict[str, int] = defaultdict(int)
    kombi_fehltreffer: dict[str, int] = defaultdict(int)

    for exec_id, eigen_lokal in eigen_je_exec.items():
        ib_wert = ib_pnl.get(exec_id)
        if ib_wert is None:
            ohne_referenz += 1
            continue
        klasse = exec_asset_class.get(exec_id, "?")
        typ = exec_ereignistyp.get(exec_id, "?")
        underlying = instruments.get(exec_conid.get(exec_id), {}).get("underlying")
        beruehrt = underlying in underlyings_mit_zuteilung
        schluessel = f"{klasse}/{typ}/zuteilung_am_underlying={beruehrt}"
        if abs(eigen_lokal - ib_wert) <= TOLERANZ:
            treffer += 1
            kombi_treffer[schluessel] += 1
        else:
            fehltreffer += 1
            kombi_fehltreffer[schluessel] += 1

    vergleichbar = treffer + fehltreffer
    print(f"übergangene Modellzeilen (fifoPnlRealized abgeschaltet, OF-21): "
          f"{modellzeilen_uebergangen}")
    print(f"schließende Ausführungen ohne Referenzwert: {ohne_referenz}")
    print(f"vergleichbare Ausführungen: {vergleichbar}")
    print(f"  Treffer (±0.02 Lokalwährung, Brutto+Kommission): {treffer} "
          f"({treffer / vergleichbar * 100:.1f} %)" if vergleichbar else "  keine")
    print("  je Anlageklasse/Ereignistyp/Zuteilung-am-Underlying "
          "(nur Gruppen mit >=20 Ausführungen):")
    for schluessel in sorted(set(kombi_treffer) | set(kombi_fehltreffer)):
        t, f = kombi_treffer[schluessel], kombi_fehltreffer[schluessel]
        if t + f >= 20:
            print(f"    {schluessel}: {t}/{t + f} ({t / (t + f) * 100:.1f} %)")


if __name__ == "__main__":
    main()
