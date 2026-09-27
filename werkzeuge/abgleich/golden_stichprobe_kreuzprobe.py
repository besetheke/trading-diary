"""AP-04: Kreuzprobe der Stichprobe gegen die heutigen Rollkandidaten.

Dritte der drei AP-04-Abnahmeprüfungen (Plan §6): „geprüft wird, dass
[Kandidaten] vollständig angeboten werden — kein bestätigter Roll der
Stichprobe fehlt in der Kandidatenliste."

`fixtures/golden/Stichprobe_Ketten_v2.xlsx` wurde **vor** AP-04k erzeugt,
als Rolls über das Zeitfenster noch automatisch verkettet wurden (nicht als
Kandidaten vorgeschlagen). Die Urteile des Nutzers bleiben gültig — sie
beurteilen, ob ein Link zwischen zwei Structures ein echter Roll war oder
nicht, unabhängig davon, wie die Engine ihn zum Zeitpunkt der Durchsicht
dargestellt hat. Block A (Strukturbildung) ist von AP-04k unberührt; dieses
Skript löst deshalb jede geurteilte Zeile über Basiswert und exakten
Eröffnungszeitpunkt zu ihrer **Structure** auf (stabil, unabhängig vom
Kettenmodell) und prüft, ob der bestätigte Link heute unter
``bilde_chains().kandidaten`` erscheint.

Zwei Herkünfte bestätigter Rolls:

- **Heuristik-Block, Urteil „richtig":** Der Link war schon in der alten
  Kette heuristisch verknüpft und vom Nutzer bestätigt — er muss heute als
  Kandidat auftauchen.
- **Gegenprobe, Urteil „falsch":** „falsch" heißt hier (siehe Anleitung in
  der Stichprobe-Datei): die Engine hatte **nicht** verkettet, obwohl es
  ein echter Roll war — auch dieser Link muss heute als Kandidat auftauchen.

Regel 2: nur Zählwerte und Pseudonyme (gesalzener Hash der Stichproben-Nr,
nicht der `conid`). Liest ausschließlich, schreibt nichts.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe werkzeuge\\abgleich\\golden_stichprobe_kreuzprobe.py``
"""

import sys
from collections import Counter
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import golden_bestandsabgleich_of23 as _bestandsabgleich  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from pseudonym import pseudonym  # noqa: E402

from engine.chains import KANDIDATENFENSTER, _rolls_verketten, bilde_chains  # noqa: E402
from engine.matching import bilde_legs  # noqa: E402
from engine.structures import bilde_structures  # noqa: E402

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
STICHPROBE = GOLDEN / "Stichprobe_Ketten_v2.xlsx"


def _urteil(wert) -> str:
    text = "" if wert is None else str(wert).strip().lower()
    if text.startswith("richtig") or text == "true":
        return "richtig"
    if text.startswith("falsch") or text == "false":
        return "falsch"
    if text.startswith("unklar"):
        return "unklar"
    return text


def _stichprobe_lesen() -> dict:
    blatt = load_workbook(STICHPROBE, data_only=True)["Stichprobe"]
    zeilen = list(blatt.iter_rows(values_only=True))
    kopf = None
    for index, zeile in enumerate(zeilen):
        if zeile and zeile[0] == "Nr":
            kopf = {name: position for position, name in enumerate(zeile) if name}
            start = index + 1
            break
    if kopf is None:
        raise ValueError("Kopfzeile 'Nr' nicht gefunden — Stichprobe-Format geändert?")
    nr_je_zeile: dict = {}
    for zeile in zeilen[start:]:
        if not zeile or zeile[kopf["Nr"]] is None:
            continue
        nr_je_zeile.setdefault(zeile[kopf["Nr"]], []).append(zeile)
    return kopf, nr_je_zeile


def main() -> None:
    kopf, nr_zeilen = _stichprobe_lesen()

    exec_rows, instruments, corporate_actions, _offen = _bestandsabgleich.sammeln()
    massnahmen, _u, _o = _bestandsabgleich.kapitalmassnahmen_ableiten(
        corporate_actions, instruments
    )
    matching = bilde_legs(exec_rows, instruments, massnahmen)
    legs = [
        {
            "conid": leg.conid, "open_exec_id": leg.open_exec_id,
            "close_exec_id": leg.close_exec_id, "menge": leg.menge,
            "offen_ja_nein": leg.offen_ja_nein, "brutto_pnl": leg.brutto_pnl,
            "kommission_gesamt": leg.kommission_gesamt,
        }
        for leg in matching.legs
    ]
    struktur_ergebnis = bilde_structures(legs, exec_rows, instruments)
    strukturen = list(struktur_ergebnis.structures)
    ketten_ergebnis = bilde_chains(struktur_ergebnis, legs, exec_rows, instruments)

    je_underlying_zeit: dict = {}
    for struktur in strukturen:
        je_underlying_zeit.setdefault(
            (struktur.underlying, struktur.eroeffnet_am), []
        ).append(struktur)

    def _struktur(basiswert, eroeffnet):
        treffer = je_underlying_zeit.get((basiswert, eroeffnet), [])
        return treffer[0] if len(treffer) == 1 else None

    kandidaten_paare = {
        (id(k.schliessende), id(k.eroeffnende)) for k in ketten_ergebnis.kandidaten
    }

    ergebnisse = Counter()
    fehlende_pseudonyme = []
    unaufloesbar_pseudonyme = []

    for nr, zeilen in nr_zeilen.items():
        block = zeilen[0][kopf["Block"]]
        pseudo = pseudonym(int(nr), praefix="N")

        if block in ("Heuristik", "Belegt"):
            if block != "Heuristik" or _urteil(zeilen[0][kopf["Urteil"]]) != "richtig":
                continue
            geordnet = sorted(zeilen, key=lambda z: z[kopf["Glied"]])
            aufgeloest = []
            eindeutig = True
            for zeile in geordnet:
                struktur = _struktur(zeile[kopf["Basiswert"]], zeile[kopf["Eröffnet"]])
                if struktur is None:
                    eindeutig = False
                    break
                aufgeloest.append((struktur, zeile[kopf["Erkennung / Grund"]]))
            if not eindeutig:
                ergebnisse["nicht eindeutig auflösbar"] += 1
                unaufloesbar_pseudonyme.append(pseudo)
                continue
            for i in range(len(aufgeloest) - 1):
                schliessende, _ = aufgeloest[i]
                eroeffnende, erkennung_dort = aufgeloest[i + 1]
                if erkennung_dort != "heuristik":
                    continue
                ergebnisse["bestätigte Rolls geprüft"] += 1
                if (id(schliessende), id(eroeffnende)) in kandidaten_paare:
                    ergebnisse["... als Kandidat gefunden"] += 1
                else:
                    ergebnisse["... FEHLT als Kandidat"] += 1
                    fehlende_pseudonyme.append(pseudo)

        elif block == "Gegenprobe":
            alt_zeile = next(z for z in zeilen if z[kopf["Glied"]] == "alt")
            neu_zeile = next(z for z in zeilen if z[kopf["Glied"]] == "neu")
            if _urteil(alt_zeile[kopf["Urteil"]]) != "falsch":
                continue
            alt = _struktur(alt_zeile[kopf["Basiswert"]], alt_zeile[kopf["Eröffnet"]])
            neu = _struktur(neu_zeile[kopf["Basiswert"]], neu_zeile[kopf["Eröffnet"]])
            if alt is None or neu is None:
                ergebnisse["nicht eindeutig auflösbar"] += 1
                unaufloesbar_pseudonyme.append(pseudo)
                continue
            ergebnisse["bestätigte Rolls geprüft"] += 1
            if (id(alt), id(neu)) in kandidaten_paare:
                ergebnisse["... als Kandidat gefunden"] += 1
            else:
                ergebnisse["... FEHLT als Kandidat"] += 1
                fehlende_pseudonyme.append(pseudo)

    print("Kreuzprobe: bestätigte Rolls aus der Stichprobe gegen die heutige "
          "Kandidatenliste (engine.chains.rollkandidaten, nach AP-04k)")
    for schluessel, wert in ergebnisse.most_common():
        print(f"  {schluessel}: {wert}")
    if unaufloesbar_pseudonyme:
        print(f"  nicht auflösbare Nummern (Pseudonyme): {unaufloesbar_pseudonyme}")
    if fehlende_pseudonyme:
        print(f"  fehlende Nummern (Pseudonyme): {fehlende_pseudonyme}")

        # Ursachendiagnose nur für fehlende Fälle: welche Ausschlussregel aus
        # rollkandidaten() greift? Nur Kategorien, keine Rohwerte.
        fortsetzung = _rolls_verketten(strukturen)
        fortgesetzt = {id(strukturen[von]) for von in fortsetzung}
        gruende = Counter()
        for _nr, zeilen in nr_zeilen.items():
            if zeilen[0][kopf["Block"]] != "Gegenprobe":
                continue
            alt_zeile = next(z for z in zeilen if z[kopf["Glied"]] == "alt")
            neu_zeile = next(z for z in zeilen if z[kopf["Glied"]] == "neu")
            if _urteil(alt_zeile[kopf["Urteil"]]) != "falsch":
                continue
            alt = _struktur(alt_zeile[kopf["Basiswert"]], alt_zeile[kopf["Eröffnet"]])
            neu = _struktur(neu_zeile[kopf["Basiswert"]], neu_zeile[kopf["Eröffnet"]])
            if alt is None or neu is None or (id(alt), id(neu)) in kandidaten_paare:
                continue
            if id(alt) in fortgesetzt:
                gruende["alt bereits per exec_batch fortgesetzt (ausgeschlossen, OF-50)"] += 1
            elif alt.status != "geschlossen":
                gruende["alt nicht als geschlossen erkannt"] += 1
            else:
                abstand = neu.eroeffnet_am - alt.geschlossen_am
                if abstand < timedelta(0) or abstand > KANDIDATENFENSTER:
                    gruende["Abstand außerhalb des Kandidatenfensters"] += 1
                elif neu.rechte != alt.rechte:
                    gruende["unterschiedliche Rechte"] += 1
                else:
                    gruende["keine bekannte Ausschlussregel — bitte prüfen"] += 1
        print("  Ursachen der fehlenden Kandidaten:")
        for schluessel, wert in gruende.most_common():
            print(f"    {schluessel}: {wert}")


if __name__ == "__main__":
    main()
