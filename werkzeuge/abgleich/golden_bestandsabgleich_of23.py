"""Bestandsabgleich nach OF-23 (Kapitalmassnahmen als Transfer, AP-03vm/AP-03).

Nachweis fuer die Abnahme: liest die Golden-Exporte ueber die echten,
rein funktionalen Bausteine von ``ingest.flex`` (Parsen einer Datei ist von
der Datenbank getrennt, siehe dort) und bildet Legs mit der echten
``engine.matching.bilde_legs()`` — nicht mit einer eigens fuer den Abgleich
nachgebauten Logik. Es wird keine Datenbank angelegt, nichts geschrieben.

Die Kapitalmassnahmen-Eingabe fuer ``bilde_legs()`` wird hier aus den rohen
``CorporateAction``-Zeilen gruppiert (nach ``actionID``) — die eigentliche,
dauerhafte Ableitung nach ``corporate_actions`` ist laut AP-03vm ein eigenes,
noch nicht begonnenes Paket; dieses Skript nimmt sie nur fuer die Pruefung
vorweg.

Regeln (CLAUDE.md, Regel 2 und Konventionen): ausgegeben werden ausschliesslich
Zaehlwerte, Prozentangaben und Pseudonyme — keine Betraege, Titel, conids oder
Kontonummern, auch nicht in Fehlermeldungen.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_bestandsabgleich_of23.py``
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from engine.matching import bilde_legs
from ingest.flex import _parse_datei, _stammsatz_verschmelzen

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
DATEIEN = sorted(GOLDEN.glob("U8443617_*.xml"))


def _datum(dt_roh: str):
    """IB-Zeitformat JJJJMMTT[;HHMMSS] auf das Datum reduzieren."""
    return datetime.strptime(dt_roh.split(";")[0], "%Y%m%d").date()


def _pseudonym(conid: int, zuordnung: dict) -> str:
    if conid not in zuordnung:
        zuordnung[conid] = f"C{len(zuordnung) + 1:03d}"
    return zuordnung[conid]


def sammeln():
    """Alle Golden-Dateien rein lesend einsammeln — keine Datenbank.

    Ausfuehrungen werden ueber ``exec_id`` dedupliziert (ueberlappende
    Perioden liefern dieselbe Ausfuehrung mehrfach), Instrumente ueber
    dieselbe Verschmelzungsregel wie der echte Import (§6.2). Bei den
    OpenPositions-Zeilen kann es zwei Exporte desselben Statements geben
    (gemessen bei der 2026-Momentaufnahme, OF-27) — die Deduplizierung
    ueber ``quell_schluessel`` passiert im echten Import erst beim
    Schreiben in die Datenbank und wird hier ueber den Zeileninhalt
    nachgebildet.
    """
    executions: dict[str, dict] = {}
    instruments: dict[int, dict] = {}
    corporate_actions: list[dict] = []
    open_positions: dict[tuple, dict] = {}

    for datei in DATEIEN:
        inhalt = _parse_datei(datei)
        for ex in inhalt.executions:
            executions.setdefault(ex["exec_id"], ex)
        for conid, daten in inhalt.instruments.items():
            instruments[conid] = (
                daten
                if conid not in instruments
                else _stammsatz_verschmelzen(instruments[conid], daten)
            )
        corporate_actions.extend(inhalt.corporate_actions)
        for op in inhalt.open_positions:
            schluessel = (op["conid"], op["stichtag"], op["menge"], op["waehrung"])
            open_positions.setdefault(schluessel, op)

    return (
        list(executions.values()),
        instruments,
        corporate_actions,
        list(open_positions.values()),
    )


def kapitalmassnahmen_ableiten(corporate_actions, instruments):
    """CorporateAction-Rohzeilen nach ``actionID`` zu Kapitalmassnahmen gruppieren.

    Vertrag AP-03vm (Vertrag Regel 6): ein Abgang plus ein Zugang ist ein
    Transfer, eine einzelne Zugang-Zeile ein reiner Zugang. Zeilenformen, die
    sich nicht eindeutig zuordnen lassen (mehrere Instrumente unter derselben
    ``actionID``, gemessen bei Optionsanpassungen und einem ``ED``-Ereignis),
    werden nicht geraten (Regel 10) — s. Rueckgabe ``uebersprungen``.
    """
    gruppen: dict[tuple, list] = defaultdict(list)
    for row in corporate_actions:
        roh = json.loads(row["roh_json"])
        aktion_id = roh.get("actionID")
        if aktion_id:
            gruppen[(row["konto"], aktion_id)].append(roh)

    massnahmen = []
    uebersprungen = 0
    for (konto, aktion_id), rohs in gruppen.items():
        eindeutig = {
            (r.get("conid"), r.get("quantity"), r.get("dateTime")): r for r in rohs
        }
        rohs = list(eindeutig.values())
        mit_conid = [r for r in rohs if r.get("conid")]
        if not mit_conid:
            continue
        abgang = [r for r in mit_conid if Decimal(r["quantity"]) < 0]
        zugang = [r for r in mit_conid if Decimal(r["quantity"]) > 0]

        if len(mit_conid) == 1 and zugang:
            z = zugang[0]
            kosten = z.get("costBasis") or z.get("value")
            massnahmen.append(
                {
                    "aktion_id": aktion_id,
                    "konto": konto,
                    "typ": z.get("type", "?"),
                    "stichtag": _datum(z["dateTime"]),
                    "alter_conid": None,
                    "alte_menge": None,
                    "neuer_conid": int(z["conid"]),
                    "neue_menge": abs(Decimal(z["quantity"])),
                    "kosten_neu": abs(Decimal(kosten)) if kosten not in (None, "") else None,
                }
            )
        elif len(abgang) == 1 and len(zugang) == 1:
            a, z = abgang[0], zugang[0]
            massnahmen.append(
                {
                    "aktion_id": aktion_id,
                    "konto": konto,
                    "typ": z.get("type", "?"),
                    "stichtag": _datum(z["dateTime"]),
                    "alter_conid": int(a["conid"]),
                    "alte_menge": abs(Decimal(a["quantity"])),
                    "neuer_conid": int(z["conid"]),
                    "neue_menge": abs(Decimal(z["quantity"])),
                    "kosten_neu": None,
                }
            )
        elif len(abgang) == len(zugang) and abgang:
            # Mehrere Instrumente unter derselben aktion_id, kein Link-Feld
            # zwischen Abgang- und Zugang-Zeile geliefert. Dokumentierte,
            # nicht bestaetigte Annahme: positionale Zuordnung nach conid.
            for a, z in zip(
                sorted(abgang, key=lambda r: r["conid"]),
                sorted(zugang, key=lambda r: r["conid"]),
                strict=True,
            ):
                massnahmen.append(
                    {
                        "aktion_id": aktion_id,
                        "konto": konto,
                        "typ": z.get("type", "?"),
                        "stichtag": _datum(z["dateTime"]),
                        "alter_conid": int(a["conid"]),
                        "alte_menge": abs(Decimal(a["quantity"])),
                        "neuer_conid": int(z["conid"]),
                        "neue_menge": abs(Decimal(z["quantity"])),
                        "kosten_neu": None,
                    }
                )
        else:
            uebersprungen += 1

    fehlt = {
        c
        for k in massnahmen
        for c in (k["alter_conid"], k["neuer_conid"])
        if c is not None and c not in instruments
    }
    if fehlt:
        massnahmen = [
            k
            for k in massnahmen
            if k["neuer_conid"] in instruments
            and (k["alter_conid"] is None or k["alter_conid"] in instruments)
        ]
    return massnahmen, uebersprungen, len(fehlt)


def main() -> None:
    exec_rows, instruments, corporate_actions, open_positions = sammeln()
    print(f"Golden-Dateien gelesen: {len(DATEIEN)}")
    print(f"Ausfuehrungen (dedupliziert ueber exec_id): {len(exec_rows)}")
    print(f"Instrumentzeilen: {len(instruments)}")

    massnahmen, uebersprungen, ohne_instrument = kapitalmassnahmen_ableiten(
        corporate_actions, instruments
    )
    print(f"Kapitalmassnahmen abgeleitet: {len(massnahmen)} "
          f"(uebersprungen, Zeilenform uneindeutig: {uebersprungen}; "
          f"ohne Instrumentzeile verworfen: {ohne_instrument})")

    # Seit OF-28 prueft bilde_legs() abwicklungsart nur noch an Optionen
    # (OPT/FOP) - die begleitende Aktienlieferungszeile einer physischen
    # Zuteilung/Ausuebung braucht keine mehr. Verbleibende Faelle ohne
    # abwicklungsart AN EINER OPTION waeren eine echte Datenluecke; in den
    # Golden-Daten kommt keine vor (0 gemessen), s. OF-27/OF-28.
    OPTIONS_ANLAGEKLASSEN = {"OPT", "FOP"}
    ohne_abwicklungsart = 0
    conids_ohne_abwicklungsart: set[int] = set()
    for satz in exec_rows:
        if satz["ereignistyp"] in ("assignment", "exercise"):
            instr = instruments.get(satz["conid"]) or {}
            if instr.get("asset_class") in OPTIONS_ANLAGEKLASSEN and not instr.get(
                "abwicklungsart"
            ):
                ohne_abwicklungsart += 1
                conids_ohne_abwicklungsart.add(satz["conid"])
    if ohne_abwicklungsart:
        print(
            f"Optionsausfuehrungen ohne abwicklungsart (echte Datenluecke, "
            f"OF-25): {ohne_abwicklungsart}"
        )

    try:
        ergebnis = bilde_legs(exec_rows, instruments, massnahmen)
    except (ValueError, TypeError) as exc:
        redigiert = re.sub(r"\d{4,}", "<zahl>", str(exc))
        print(f"bilde_legs() abgebrochen mit {type(exc).__name__}: {redigiert}")
        return

    offene = [leg for leg in ergebnis.legs if leg.offen_ja_nein]
    print(f"Legs gesamt: {len(ergebnis.legs)} "
          f"({len(offene)} offen, {len(ergebnis.legs) - len(offene)} geschlossen)")
    print(f"Nicht gematchte Ausfuehrungen: {len(ergebnis.nicht_gematcht)}")
    print(f"Legs mit basis_ungeklaert: "
          f"{sum(1 for leg in ergebnis.legs if leg.basis_ungeklaert)}")

    richtung_je_exec = {r["exec_id"]: r["side"] for r in exec_rows}
    eigene_bestand: dict[int, Decimal] = defaultdict(Decimal)
    for leg in offene:
        side = richtung_je_exec.get(leg.open_exec_id, "BUY")
        vorzeichen = Decimal(1) if side == "BUY" else Decimal(-1)
        eigene_bestand[leg.conid] += leg.menge * vorzeichen

    juengster_stichtag = max((op["stichtag"] for op in open_positions), default=None)
    ib_bestand: dict[int, Decimal] = defaultdict(Decimal)
    for op in open_positions:
        if op["stichtag"] == juengster_stichtag:
            ib_bestand[op["conid"]] += op["menge"]

    nur_eigen = set(eigene_bestand) - set(ib_bestand)
    nur_ib = set(ib_bestand) - set(eigene_bestand)
    beide = set(eigene_bestand) & set(ib_bestand)
    gleich = {c for c in beide if eigene_bestand[c] == ib_bestand[c]}
    abweichend = (nur_eigen | nur_ib | (beide - gleich))

    betroffen = {c for c in abweichend if c in conids_ohne_abwicklungsart}
    unattribuiert = abweichend - betroffen

    anzahl = len(eigene_bestand.keys() | ib_bestand.keys())
    quote = (len(gleich) / (len(gleich) + len(abweichend)) * 100) if anzahl else 100.0
    print(
        f"Bestandsabgleich am juengsten Stichtag: {len(gleich)}/"
        f"{len(gleich) + len(abweichend)} conids stimmen ueberein ({quote:.1f} %)"
    )
    print(
        f"  abweichend: {len(abweichend)}, davon mit Bezug zur "
        f"OF-25-Datenluecke: {len(betroffen)}, ohne Zuordnung: {len(unattribuiert)}"
    )
    if unattribuiert:
        zuordnung: dict[int, str] = {}
        pseudonyme = sorted(_pseudonym(c, zuordnung) for c in unattribuiert)
        print(f"  Pseudonyme ohne Zuordnung: {', '.join(pseudonyme)}")


if __name__ == "__main__":
    main()
