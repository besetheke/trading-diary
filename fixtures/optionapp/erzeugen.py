"""Erzeugt die synthetischen OptionApp-Fixtures für AP-13.

Die vier XLSX-Dateien sind Binärdateien; dieses Skript hält nachvollziehbar
fest, was in ihnen steht. Alle Werte sind frei erfunden — der Anhang
`auftraege/AP-13-anhang-oa-format.md` liefert nur Struktur und Grammatik,
keine Kontodaten.

Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe fixtures\\optionapp\\erzeugen.py``
"""

from pathlib import Path

from openpyxl import Workbook

ZIEL = Path(__file__).resolve().parent

KOPF = [
    "Entry Time",
    "Strategy",
    "Name",
    "Strikes",
    "Quantity",
    "Open",
    "Close",
    "Stops",
    "Profit",
    "Close Time",
    "Status",
]

# Der Regelfall: zwei, drei und vier Legs, `Stops` einmal `-` und einmal `0`,
# `Profit` negativ und positiv, dazu ein noch offener Trade ohne `Close`.
STANDARD = [
    [
        "2026/08/17 09:57:19",
        "QQQ: DC14/28",
        "Standardfall [1001]",
        "-1xC751 (260831) / 1xC761 (260831) / -1xP717 (260918) / 1xP707 (260918)",
        "1/1",
        11.49,
        4.2,
        "-",
        "-1.234,56 $",
        "2026/08/28 16:05:00",
        "CLOSED",
    ],
    [
        "2026/08/03 10:15:00",
        "SPX: IC",
        "mit (Klammer) im Text [1002]",
        "-2xP5100 (260904) / 2xP5000 (260904)",
        "2/2",
        3.05,
        0.0,
        "0",
        "610,00 $",
        "2026/09/04 22:00:00",
        "EXPIRED",
    ],
    [
        "2026/07/20 15:30:00",
        "SPX: DD 5/7",
        "Drei Legs [1003]",
        "1xC5400 (260724) / -2xC5450 (260724) / 1xP5300 (260724)",
        "3/3",
        2.5,
        1.25,
        "-14.4",
        "-375,50 $",
        "2026/07/24 21:00:00",
        "PARTIALLY STOPPED",
    ],
    [
        "2026/09/10 09:31:00",
        "XSP: IF7",
        "Noch offen [1004]",
        "-1xP612.5 (261016) / 1xP602.5 (261016)",
        "1/1",
        1.8,
        None,
        "-",
        "0,00 $",
        None,
        "UNMANAGED",
    ],
]

# Eine Zelle, die der Grammatik nicht folgt: `Z` ist weder Call noch Put.
GRAMMATIK_DEFEKT = [
    [
        "2026/08/17 09:57:19",
        "QQQ: DC14/28",
        "Kaputte Grammatik [1101]",
        "-1xZ751 (260831) / 1xC761 (260831)",
        "1/1",
        11.49,
        4.2,
        "-",
        "-100,00 $",
        "2026/08/28 16:05:00",
        "CLOSED",
    ],
]

# `Name` ohne Klammernummer — ohne Schlüssel ist der Trade nicht verknüpfbar.
OHNE_NUMMER = [
    [
        "2026/08/17 09:57:19",
        "QQQ: DC14/28",
        "ohne Nummer",
        "-1xC751 (260831) / 1xC761 (260831)",
        "1/1",
        11.49,
        4.2,
        "-",
        "-100,00 $",
        "2026/08/28 16:05:00",
        "CLOSED",
    ],
]

# Dieselbe Nummer zweimal, aber mit abweichendem Inhalt.
DOPPELTE_NUMMER = [
    [
        "2026/08/17 09:57:19",
        "QQQ: DC14/28",
        "Erster Stand [2001]",
        "-1xC751 (260831) / 1xC761 (260831)",
        "1/1",
        11.49,
        4.2,
        "-",
        "-100,00 $",
        "2026/08/28 16:05:00",
        "CLOSED",
    ],
    [
        "2026/08/17 09:57:19",
        "QQQ: DC14/28",
        "Zweiter Stand [2001]",
        "-1xC751 (260831) / 1xC761 (260831)",
        "1/1",
        11.49,
        4.2,
        "-",
        "-999,00 $",
        "2026/08/28 16:05:00",
        "CLOSED",
    ],
]


def schreiben(name: str, zeilen: list[list]) -> None:
    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Trades"
    blatt.append(KOPF)
    for zeile in zeilen:
        blatt.append(zeile)
    mappe.save(ZIEL / name)
    print(f"{name}: {len(zeilen)} Zeilen")


if __name__ == "__main__":
    schreiben("oa_standard.xlsx", STANDARD)
    schreiben("oa_grammatik_defekt.xlsx", GRAMMATIK_DEFEKT)
    schreiben("oa_ohne_klammernummer.xlsx", OHNE_NUMMER)
    schreiben("oa_doppelte_nummer.xlsx", DOPPELTE_NUMMER)
