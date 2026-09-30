"""AP-13: Nachweis der Abnahme — `engine.oa_abgleich.oa_abgleich()` gegen
einen echten OptionApp-Export (Plan §6, AP-13: „mindestens 95 % der
OA-Trades eindeutig einer Kette zugeordnet ... Abweichungen zwischen
OA-Ergebnis und eigener Berechnung sind erklärbar").

Baut Legs/Strukturen/Ketten im Speicher aus dem echten Flex-Bestand (wie
`golden_oa_abgleich.py`), parst den echten OA-Export und ruft die
Produktionsfunktion `engine.oa_abgleich.oa_abgleich()` auf — dieselbe
Funktion, die `journal/oa_persistenz.py` gegen die echte Datenbank
aufruft, hier nur gegen Golden-Daten gemessen statt gegen `journal.db`
geschrieben.

Regel 2: keine Kontodaten. `oa_trade`-Nummern werden ausschließlich
pseudonymisiert genannt; Strikes, Expiries, Prämien und Ergebnisse nie roh
ausgegeben — Abweichungen nur als Bucket (erklärt/unerklärt), nie als
Betrag.

Aufruf aus dem Projektverzeichnis, mit dem Dateinamen des Exports:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_oa_abgleich_verknuepfung.py <Datei.xlsx>``
"""

import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402
from pseudonym import pseudonym  # noqa: E402

from engine.chains import bilde_chains  # noqa: E402
from engine.matching import bilde_legs  # noqa: E402
from engine.oa_abgleich import OALegSignatur, OATradeEintrag, oa_abgleich  # noqa: E402
from engine.structures import bilde_structures  # noqa: E402
from ingest.optionapp import _parse_datei  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
# Typische Kommission je Leg in der Golden-Historie (grob, nur zur
# Grössenordnung einer „durch Kommission erklärbaren" Abweichung) — kein
# echter Betrag aus den Daten, eine Toleranzbreite.
KOMMISSIONS_TOLERANZ = Decimal("5.00")


def _oa_trade_eintrag(trade_inhalt) -> OATradeEintrag:
    legs = tuple(
        OALegSignatur(
            right=leg["right"], strike=leg["strike"], expiry=leg["expiry"],
            richtung=leg["richtung"], menge=leg["menge"],
        )
        for leg in trade_inhalt.legs
    )
    felder = trade_inhalt.felder
    return OATradeEintrag(
        oa_trade=felder["oa_trade"], legs=legs, profit=felder["profit"],
        strategie=felder["strategie"], status=felder["status"],
    )


def main() -> None:
    if len(sys.argv) != 2:
        print("Aufruf: golden_oa_abgleich_verknuepfung.py <OA-Exportdatei.xlsx> "
              "(in fixtures/golden/)")
        raise SystemExit(1)
    datei = GOLDEN / sys.argv[1]

    try:
        oa_inhalt = _parse_datei(datei)
    except ValueError as fehler:
        feld = re.search(r"'([A-Za-z ]+)'", str(fehler))
        print(f"Parser bricht ab, Feld: {feld.group(1) if feld else 'unbekannt'} "
              f"(Einzelheiten nur über das Messskript, nie roh)")
        raise SystemExit(2) from None

    ohne_legs = [t for t in oa_inhalt.trades if not t.legs]
    oa_trades = [_oa_trade_eintrag(t) for t in oa_inhalt.trades if t.legs]
    print(f"OA-Referenz: {len(oa_inhalt.trades)} Trades, davon {len(ohne_legs)} ohne "
          f"ausgeführte Legs (Status: "
          f"{', '.join(f'{s}×{n}' for s, n in sorted(Counter(t.felder['status'] for t in ohne_legs).items()))}"
          f") — verglichen werden {len(oa_trades)}")

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
    exec_je_id = {r["exec_id"]: r for r in exec_rows}

    ergebnis = oa_abgleich(oa_trades, ketten_ergebnis.chains, exec_je_id, instruments)

    gesamt = len(oa_trades)
    zugeordnet = len(ergebnis.zuordnungen)
    auto = sum(1 for z in ergebnis.zuordnungen if z.erkennung == "auto")
    heuristik = zugeordnet - auto
    abdeckung_pct = (ergebnis.abdeckung * 100) if gesamt else Decimal(0)

    print(f"\nEindeutig zugeordnet: {zugeordnet} von {gesamt} ({abdeckung_pct:.1f} %) "
          f"— davon {auto} mit bestätigtem Fingerabdruck (auto), {heuristik} mit "
          f"abweichendem (heuristik)")

    fehler_je_grund = Counter(f.grund for f in ergebnis.fehler)
    print(f"Fehlerliste: {len(ergebnis.fehler)} von {gesamt} "
          f"({dict(fehler_je_grund) if fehler_je_grund else 'keine'})")
    if ergebnis.fehler:
        pseudonyme = ", ".join(
            pseudonym(int(f.oa_trade), praefix="T") for f in sorted(ergebnis.fehler,
                                                                      key=lambda f: f.oa_trade)
        )
        print(f"Pseudonyme ohne Kette: {pseudonyme}")

    if heuristik:
        pseudonyme = ", ".join(
            pseudonym(int(z.oa_trade), praefix="T")
            for z in sorted(ergebnis.zuordnungen, key=lambda z: z.oa_trade)
            if z.erkennung == "heuristik"
        )
        print(f"Pseudonyme mit abweichendem Fingerabdruck: {pseudonyme}")

    # Ergebnisabgleich: nur wo die Kette geschlossen ist. `abweichung`
    # vergleicht bereits Netto gegen Netto (AP-13vk2/OF-56 — OAs Profit ist
    # kommissionsbereinigt). Ein kleiner Rest gilt als „im Toleranzband"
    # (Rundung, Restdifferenzen) — grob, Regel-2-konform (kein echter
    # Betrag wird ausgegeben).
    vergleichbar = [z for z in ergebnis.zuordnungen if z.abweichung is not None]
    exakt = sum(1 for z in vergleichbar if z.abweichung == 0)
    im_toleranzband = sum(
        1 for z in vergleichbar if z.abweichung != 0 and abs(z.abweichung) <= KOMMISSIONS_TOLERANZ
    )
    unerklaert = [z for z in vergleichbar if abs(z.abweichung) > KOMMISSIONS_TOLERANZ]
    print(f"\nErgebnisabgleich (nur geschlossene Ketten): {len(vergleichbar)} vergleichbar")
    print(f"  exakt gleich: {exakt}")
    print(f"  Abweichung im Kommissions-Toleranzband (<= {KOMMISSIONS_TOLERANZ}): "
          f"{im_toleranzband}")
    print(f"  Abweichung darüber, unerklärt: {len(unerklaert)}")
    if unerklaert:
        pseudonyme = ", ".join(
            pseudonym(int(z.oa_trade), praefix="T")
            for z in sorted(unerklaert, key=lambda z: z.oa_trade)
        )
        print(f"  Pseudonyme, unerklärte Ergebnisabweichung: {pseudonyme}")


if __name__ == "__main__":
    main()
