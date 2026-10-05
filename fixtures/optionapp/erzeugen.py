"""Erzeugt die synthetischen OptionApp-Fixtures für AP-13.

Die acht XLSX-Dateien sind Binärdateien; dieses Skript hält nachvollziehbar
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

# Noch nicht geschlossene Trades: `Close` und `Close Time` tragen den Strich,
# nie nur eine der beiden Spalten (AP-13pl, OF-37). Je eine Zeile für die drei
# im Bestand beobachteten Status. `[3003]` trägt zusätzlich einen gesetzten
# Stop, damit belegt ist, dass der Strich in `Close` die übrigen Spalten nicht
# mitreißt.
LAUFEND = [
    [
        "2026/01/12 10:05:00",
        "SPX: IC",
        "Abgebrochen [3001]",
        "-1xP5000 (260220) / 1xP4950 (260220)",
        "1/1",
        2.4,
        "-",
        "-",
        "0,00 $",
        "-",
        "CANCELED",
    ],
    [
        "2026/01/20 14:30:00",
        "QQQ: DC14/28",
        "Laeuft noch [3002]",
        "-1xC520 (260306) / 1xC530 (260306)",
        "2/2",
        1.75,
        "-",
        "-",
        "0,00 $",
        "-",
        "RUNNING",
    ],
    [
        "2026/08/04 09:45:00",
        "XSP: IF7",
        "Teilweise gestoppt [3003]",
        "-1xP600 (260918) / 1xP590 (260918) / -1xC640 (260918)",
        "3/3",
        3.6,
        "-",
        "14.4",
        "-125,00 $",
        "-",
        "PARTIALLY STOPPED",
    ],
]

# Nie oder noch nicht ausgeführte Trades und die zweite Exportvariante
# (AP-13pm, OF-40). Nachgebildet nach gemessenen Formen, Werte frei erfunden:
# - `CANCELED`: `Open`, `Close`, `Close Time`, `Stops` tragen den Strich,
#   `Strikes` einen Abbruchgrund oder nichts, `Profit` die Zahl 0.
# - `RUNNING`: geplante Legs mit Restlaufzeit (`-7DTE`) statt Verfallsdatum.
# - Ausgeführter Trade der Januarvariante: `Profit` als Zahl ohne
#   Währungszeichen, `Stops` leer.
# - Vier-Leg-Trade mit zwei Stops in einer Zelle, zeilengetrennt.
NICHT_AUSGEFUEHRT = [
    [
        "2026/01/05 10:00:00",
        "SPX: IC",
        "Nicht ausgeloest [4001]",
        "Entry condition not met",
        "1/1",
        "-",
        "-",
        "-",
        0,
        "-",
        "CANCELED",
    ],
    [
        "2026/01/05 10:05:00",
        "SPX: IC",
        "Ohne Angabe [4002]",
        None,
        "1/1",
        "-",
        "-",
        "-",
        0,
        "-",
        "CANCELED",
    ],
    [
        "2026/01/06 09:35:00",
        "SPX: DD 5/7",
        "Wartet [4003]",
        "-1xP5000-7DTE / 1xP4950-7DTE",
        "1/1",
        2.1,
        "-",
        "-",
        0.0,
        "-",
        "RUNNING",
    ],
    [
        "2026/01/07 11:20:00",
        "QQQ: DC14/28",
        "Januarformat [4004]",
        "-1xC520 (260220) / 1xC530 (260220)",
        "1/1",
        1.9,
        0.75,
        None,
        7.72,
        "2026/01/30 15:45:00",
        "CLOSED",
    ],
    [
        "2026/08/10 10:10:00",
        "SPX: IC",
        "Zwei Stops [4005]",
        "-1xP5100 (260918) / 1xP5050 (260918) / -1xC5700 (260918) / 1xC5750 (260918)",
        "1/1",
        3.4,
        "-",
        "-14.4\n-12.1",
        "-212,00 $",
        "-",
        "PARTIALLY STOPPED",
    ],
]

# Ein ausgeführter Trade mit Freitext in `Strikes`: Die Lockerung gilt nur für
# nicht ausgeführte Trades; hier bleibt es ein Defekt der Quelle.
FREITEXT_AUSGEFUEHRT = [
    [
        "2026/01/07 11:20:00",
        "QQQ: DC14/28",
        "Freitext bei geschlossenem Trade [4101]",
        "Entry condition not met",
        "1/1",
        1.9,
        0.75,
        "-",
        "-100,00 $",
        "2026/01/30 15:45:00",
        "CLOSED",
    ],
]

# Mehrere Stops, einer davon unlesbar: Jede Zeile muss für sich Vertrag 3
# genügen.
MEHRSTOP_DEFEKT = [
    [
        "2026/08/10 10:10:00",
        "SPX: IC",
        "Kaputter Zweitstop [4201]",
        "-1xP5100 (260918) / 1xP5050 (260918) / -1xC5700 (260918) / 1xC5750 (260918)",
        "1/1",
        3.4,
        "-",
        "-14.4\nabc",
        "-212,00 $",
        "-",
        "PARTIALLY STOPPED",
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

# Eurex-Produktcode vor dem Recht (AP-13pn, OF-66): `-1xODAP P23000 (260918)`.
# Gemessen im Gesamtexport 2026 (DAX-Trades der OptionApp), Werte frei erfunden.
# `[5003]` mischt je Leg mit und ohne Code: Der Code ist je Leg optional.
PRODUKTCODE = [
    [
        "2026/08/20 09:40:00",
        "DAX: BPS",
        "BPS D25/20 14DTE [5001]",
        "-1xODAP P23000 (260918) / 1xODAP P22900 (260918)",
        "1/1",
        14.5,
        2.5,
        "-",
        "1.200,00 $",
        "2026/09/18 17:30:00",
        "CLOSED",
    ],
    [
        "2026/08/21 10:05:00",
        "DAX: BCS",
        "BCS D25/20 14DTE [5002]",
        "-2xODAC C24500 (260918) / 2xODAC C24600 (260918)",
        "2/2",
        9.0,
        1.0,
        "-",
        "-340,00 $",
        "2026/09/18 17:30:00",
        "EXPIRED",
    ],
    [
        "2026/08/24 09:55:00",
        "DAX: BPS",
        "Gemischt [5003]",
        "-1xODAP P23000 (260918) / 1xP22900 (260918)",
        "1/1",
        13.0,
        3.0,
        "-",
        "500,00 $",
        "2026/09/18 17:30:00",
        "CLOSED",
    ],
]

# Produktcode mit unbekanntem Recht: Der Code lockert nur die Grammatik, nicht
# `C|P` — weiterhin ein Defekt der Quelle (Gegenprobe zu `PRODUKTCODE`).
PRODUKTCODE_DEFEKT_RECHT = [
    [
        "2026/08/20 09:40:00",
        "DAX: BPS",
        "Kaputtes Recht [5101]",
        "-1xODAP Z23000 (260918) / 1xODAP P22900 (260918)",
        "1/1",
        14.5,
        2.5,
        "-",
        "100,00 $",
        "2026/09/18 17:30:00",
        "CLOSED",
    ],
]

# Produktcode in Kleinbuchstaben: kein Eurex-Code, weiterhin ein Defekt.
PRODUKTCODE_DEFEKT_KLEIN = [
    [
        "2026/08/20 09:40:00",
        "DAX: BPS",
        "Kleingeschrieben [5201]",
        "-1xodap P23000 (260918) / 1xodap P22900 (260918)",
        "1/1",
        14.5,
        2.5,
        "-",
        "100,00 $",
        "2026/09/18 17:30:00",
        "CLOSED",
    ],
]

# Ein Trade mit nur einem Leg (AP-13pp, OF-67): gemessen im Gesamtexport 2026
# (ein ausgefuehrter SPX-Trade unter 1.383), Werte frei erfunden. Die
# Untergrenze "zwei Legs" des Anhangs war eine Beobachtung, keine Regel.
EIN_LEG = [
    [
        "2026/08/25 10:20:00",
        "SPX: Single",
        "Einzelleg [5301]",
        "-1xP5400 (260918)",
        "1/1",
        6.5,
        1.5,
        "-",
        "500,00 $",
        "2026/09/18 22:00:00",
        "CLOSED",
    ],
]

# Fuenf Legs: Die Obergrenze vier bleibt (Gegenprobe zu EIN_LEG).
FUENF_LEGS = [
    [
        "2026/08/25 10:20:00",
        "SPX: IC",
        "Zu viele Legs [5401]",
        "-1xP5400 (260918) / 1xP5350 (260918) / -1xC5800 (260918) / 1xC5850 (260918) / 1xP5300 (260918)",
        "1/1",
        6.5,
        1.5,
        "-",
        "500,00 $",
        "2026/09/18 22:00:00",
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
    schreiben("oa_laufend.xlsx", LAUFEND)
    schreiben("oa_nicht_ausgefuehrt.xlsx", NICHT_AUSGEFUEHRT)
    schreiben("oa_freitext_ausgefuehrt.xlsx", FREITEXT_AUSGEFUEHRT)
    schreiben("oa_mehrstop_defekt.xlsx", MEHRSTOP_DEFEKT)
    schreiben("oa_grammatik_defekt.xlsx", GRAMMATIK_DEFEKT)
    schreiben("oa_ohne_klammernummer.xlsx", OHNE_NUMMER)
    schreiben("oa_doppelte_nummer.xlsx", DOPPELTE_NUMMER)
    schreiben("oa_produktcode.xlsx", PRODUKTCODE)
    schreiben("oa_produktcode_defekt_recht.xlsx", PRODUKTCODE_DEFEKT_RECHT)
    schreiben("oa_produktcode_defekt_klein.xlsx", PRODUKTCODE_DEFEKT_KLEIN)
    schreiben("oa_ein_leg.xlsx", EIN_LEG)
    schreiben("oa_fuenf_legs_defekt.xlsx", FUENF_LEGS)
