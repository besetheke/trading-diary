"""AP-04: OA-Abgleich — externe, engine-unabhängige Referenz für die
Kettenbildung (Plan §6, „Externe Referenz, OA-Teil").

Vergleicht für jede `oa_trade`-Nummer aus einem echten OptionApp-Export das
**erste** Kettenglied aus `engine.chains.bilde_chains()` gegen die
Leg-Zusammensetzung (Right/Strike/Expiry/Richtung) derselben Nummer im
Export. Die XLSX-Datei zeigt keine Roll-Historie — nur eine Momentaufnahme
je Trade —, und gemessen 19.09.2026 ist das die **Eröffnungs**-Momentaufnahme
(Vergleich gegen das erste Kettenglied trifft deutlich besser als gegen das
letzte), nicht der finale Zustand nach Rolls.

Regel 2: keine Kontodaten. `oa_trade`-Nummern werden ausschließlich
pseudonymisiert genannt; Strikes, Expiries und Beträge nie roh ausgegeben.

Aufruf aus dem Projektverzeichnis, mit dem Dateinamen des Exports:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_oa_abgleich.py <Dateiname.xlsx>``
"""

import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402
from pseudonym import pseudonym  # noqa: E402

from engine.chains import bilde_chains  # noqa: E402
from engine.matching import bilde_legs  # noqa: E402
from engine.structures import bilde_structures  # noqa: E402
from ingest.optionapp import _parse_datei  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
RICHTUNG_TEXT = {"BUY": "long", "SELL": "short"}


def _eigene_legs(structure, exec_je_id, instruments) -> set:
    sig = set()
    for schl in structure.leg_schluessel:
        oeffnung = exec_je_id.get(schl.open_exec_id)
        if oeffnung is None:
            continue
        instrument = instruments.get(oeffnung["conid"], {})
        sig.add(
            (
                instrument.get("right"),
                instrument.get("strike"),
                instrument.get("expiry"),
                RICHTUNG_TEXT.get(oeffnung["side"]),
            )
        )
    return sig


def _referenz_legs(trade_inhalt) -> set:
    return {
        (leg["right"], leg["strike"], leg["expiry"], "long" if leg["richtung"] == 1 else "short")
        for leg in trade_inhalt.legs
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("Aufruf: golden_oa_abgleich.py <OA-Exportdatei.xlsx> (in fixtures/golden/)")
        raise SystemExit(1)
    datei = GOLDEN / sys.argv[1]

    try:
        oa_inhalt = _parse_datei(datei)
    except ValueError as fehler:
        # Regel 2 gilt auch für Fehlermeldungen: Die Parsermeldung nennt
        # Tradenummer und Zellwert. Ausgegeben wird nur das betroffene Feld.
        feld = re.search(r"'([A-Za-z ]+)'", str(fehler))
        print(f"Parser bricht ab, Feld: {feld.group(1) if feld else 'unbekannt'} "
              f"(Einzelheiten nur über das Messskript, nie roh)")
        raise SystemExit(2) from None
    # Trades ohne ausgeführte Legs (`CANCELED`, `RUNNING` mit geplanten
    # DTE-Legs, OF-40) können keiner Kette entsprechen — sie haben nie eine
    # Ausführung erzeugt. Sie gehören nicht in den Nenner, sondern eigens
    # ausgewiesen; sonst sieht ein Export voller abgebrochener Trades wie ein
    # Abgleichsfehler aus.
    ohne_legs = [t for t in oa_inhalt.trades if not t.legs]
    oa_je_trade = {t.felder["oa_trade"]: t for t in oa_inhalt.trades if t.legs}
    print(f"OA-Referenz: {len(oa_inhalt.trades)} Trades, davon {len(ohne_legs)} ohne "
          f"ausgeführte Legs (Status: "
          f"{', '.join(f'{s}×{n}' for s, n in sorted(Counter(t.felder['status'] for t in ohne_legs).items()))}"
          f") — verglichen werden {len(oa_je_trade)}")

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

    # Verglichen wird die **früheste Struktur mit dieser OA-Nummer**, nicht das
    # erste Glied der Kette. Beides fällt meist zusammen, aber nicht immer: Eine
    # OA-Struktur kann als Fortsetzung an einer fremden Kette hängen, deren Kopf
    # dann gar keine OA-Nummer trägt. Am Kettenkopf zu suchen meldete solche
    # Fälle fälschlich als „ohne passende Kette" (gemessen: einmal im August).
    struktur_je_oa_trade: dict[str, object] = {}
    for struktur in struktur_ergebnis.structures:
        if not struktur.oa_trade:
            continue
        bisher = struktur_je_oa_trade.get(struktur.oa_trade)
        if bisher is None or struktur.eroeffnet_am < bisher.eroeffnet_am:
            struktur_je_oa_trade[struktur.oa_trade] = struktur

    ketten_je_oa_trade: dict[str, set] = {}
    for chain in ketten_ergebnis.chains:
        for glied in chain.glieder:
            if glied.structure.oa_trade:
                ketten_je_oa_trade.setdefault(glied.structure.oa_trade, set()).add(id(chain))

    mehrfach = sum(1 for v in ketten_je_oa_trade.values() if len(v) > 1)
    print(f"oa_trade-Werte, deren Strukturen in mehreren Ketten liegen: {mehrfach}")

    # OF-36: Eröffnungen, die der FIFO-Abgleich (pro conid, kontoweit) als
    # Schließung einer Gegenposition eines ANDEREN OA-Trades verbraucht hat.
    # Diese Beine gibt es auf Brokerebene nicht; OA führt sie je Trade weiter.
    exec_als_schliessung = {
        leg.close_exec_id: leg for leg in matching_ergebnis.legs if leg.close_exec_id
    }

    def _kontoweit_verrechnet(oa_trade, fehlende_sig, eroeffnung_zeit) -> bool:
        for sig in fehlende_sig:
            kandidaten = [
                r for r in exec_rows
                if r.get("oa_trade") == oa_trade and r["ereignistyp"] == "trade"
                and (
                    instruments.get(r["conid"], {}).get("right"),
                    instruments.get(r["conid"], {}).get("strike"),
                    instruments.get(r["conid"], {}).get("expiry"),
                    RICHTUNG_TEXT.get(r["side"]),
                ) == sig
            ]
            if not kandidaten:
                return False
            naechste = min(
                kandidaten, key=lambda r: abs((r["handelszeit"] - eroeffnung_zeit).total_seconds())
            )
            geschlossen = exec_als_schliessung.get(naechste["exec_id"])
            if geschlossen is None:
                return False
            gegen = exec_je_id[geschlossen.open_exec_id].get("oa_trade")
            if not gegen or gegen == oa_trade:
                return False
        return True

    fehlend = 0
    exakt = 0
    verrechnet = 0
    abweichend_pseudonyme = []
    delta_verteilung = Counter()

    for oa_trade in sorted(oa_je_trade, key=int):
        referenz = oa_je_trade[oa_trade]
        eigene = struktur_je_oa_trade.get(oa_trade)
        if eigene is None:
            fehlend += 1
            abweichend_pseudonyme.append(pseudonym(int(oa_trade), praefix="T"))
            continue
        ref_sig = _referenz_legs(referenz)
        eig_sig = _eigene_legs(eigene, exec_je_id, instruments)
        if ref_sig == eig_sig:
            exakt += 1
        elif not (eig_sig - ref_sig) and _kontoweit_verrechnet(
            oa_trade, ref_sig - eig_sig, referenz.felder["entry_zeit"]
        ):
            verrechnet += 1
        else:
            delta_verteilung[len(ref_sig) - len(eig_sig)] += 1
            abweichend_pseudonyme.append(pseudonym(int(oa_trade), praefix="T"))

    gesamt = len(oa_je_trade)
    print(f"\nOhne eigene Struktur: {fehlend} von {gesamt}")
    print(f"Früheste Struktur mit dieser OA-Nummer stimmt exakt mit der Referenz "
          f"überein: {exakt} von {gesamt} ({exakt / gesamt * 100:.1f} %)")
    print(f"Abweichung durch kontoweite Verrechnung mit einem anderen OA-Trade (OF-36): "
          f"{verrechnet} von {gesamt}")
    print(f"Unerklärt: {len(abweichend_pseudonyme)} von {gesamt}")
    if delta_verteilung:
        print(f"Differenz Anzahl Legs (Referenz minus Eigen) bei Unerklärten: "
              f"{dict(delta_verteilung)}")
    if abweichend_pseudonyme:
        print(f"Pseudonyme ohne Erklärung: {', '.join(abweichend_pseudonyme)}")


if __name__ == "__main__":
    main()
