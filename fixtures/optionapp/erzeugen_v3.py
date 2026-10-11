"""Erzeugt die OptionApp-Fixtures für AP-13r3 (Exportformat der neuen OA-Version).

Eigenes Skript, damit die übrigen Fixtures unverändert bleiben. Alle Werte frei
erfunden; Aufbau wie der Export „AllTrades_…xlsx" (Oktober 2026): eigene Spalte
`Id`, `Name` ohne Klammernummer, Zeiten als Datum, `Profit (USD)` als Zahl,
leeres `Stops` für „kein Stop". Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe fixtures\\optionapp\\erzeugen_v3.py``
"""

from datetime import datetime
from pathlib import Path

from erzeugen import schreiben
from openpyxl import Workbook

ZIEL = Path(__file__).resolve().parent

KOPF_V3 = [
    "Id", "Entry Time", "Strategy", "Name", "Entry Cond.", "Strikes", "Quantity",
    "Open", "Close", "Stops", "Profit (USD)", "Return on Risk (%)", "Risk (USD)",
    "Commission (USD)", "Entry Slip. (USD)", "Exit Slip. (USD)", "Long P&L (USD)",
    "Duration (min)", "DTE", "Close Time", "Status", "Currency", "Profit (orig.)",
    "Commission (orig.)", "FX open (orig. per USD)", "FX close (orig. per USD)",
]


def zeile_v3(nr, entry, strategie, name, strikes, menge, offen, schluss, stop, profit,
             schluss_zeit, status):
    return [nr, entry, strategie, name, "Bedingung", strikes, menge, offen, schluss, stop,
            profit, 10.0, 500.0, 0.76, 0.01, None, -2.0, 279, 0, schluss_zeit, status, "USD",
            profit, 0.76, 1.0, None]


V3 = [
    # 7001: verfallen, kein Stop (leer), Name mit nachgestelltem Leerzeichen
    zeile_v3(7001, datetime(2026, 9, 3, 11, 20, 44), "XSP: IF7 ", "IF7 ",
             "-1xP774 (260903) / 1xC780 (260903)", "1/1", -1.45, 0, None, 144.24,
             datetime(2026, 9, 3, 16, 0, 0), "EXPIRED"),
    # 7002: geschlossen, Stop 1.5 als Zahl
    zeile_v3(7002, datetime(2026, 9, 4, 12, 2, 24), "XSP: IF7", "IF7",
             "-1xP772 (260904) / 1xC779 (260904)", "1/1", -1.19, -0.14, 1.5, 104.24,
             datetime(2026, 9, 4, 15, 0, 0), "CLOSED"),
    # 7003: läuft noch, Legs in Restlaufzeitform
    zeile_v3(7003, datetime(2026, 10, 9, 11, 0, 0), "SPY: 30DTE Strangle", "Strangle",
             "-1xP716-26DTE / -1xC812-26DTE", "1/1", -3.2, None, None, 0.0, None,
             "RUNNING"),
]

# Derselbe Trade 7001 im bisherigen Format (AP-13): Name mit Klammernummer und
# doppeltem Leerzeichen, Strich für „kein Stop", Profit als deutscher Text.
ALT_7001 = [
    "2026/09/03 11:20:44", "XSP: IF7", "IF7  [7001]",
    "-1xP774 (260903) / 1xC780 (260903)", "1/1", -1.45, 0, "-", "144,24 $",
    "2026/09/03 16:00:00", "EXPIRED",
]

# 7001 mit abweichendem Schlusskurs (wie Trade 5213 der echten Daten) plus ein
# neuer Trade 7004.
ABWEICHEND = [
    zeile_v3(7001, datetime(2026, 9, 3, 11, 20, 44), "XSP: IF7", "IF7",
             "-1xP774 (260903) / 1xC780 (260903)", "1/1", -1.45, -0.70, None, 144.24,
             datetime(2026, 9, 3, 16, 0, 0), "EXPIRED"),
    zeile_v3(7004, datetime(2026, 9, 8, 11, 20, 37), "XSP: IF7", "IF7",
             "-1xP770 (260908) / 1xC777 (260908)", "2/2", -1.3, -2.65, None, -271.52,
             datetime(2026, 9, 8, 16, 0, 0), "EXPIRED"),
]


def schreiben_v3(name: str, zeilen: list[list]) -> None:
    mappe = Workbook()
    blatt = mappe.active
    blatt.title = "Trades"
    blatt.append(KOPF_V3)
    for zeile in zeilen:
        blatt.append(zeile)
    mappe.save(ZIEL / name)
    print(f"{name}: {len(zeilen)} Zeilen")


if __name__ == "__main__":
    schreiben_v3("oa_v3.xlsx", V3)
    schreiben("oa_v3_alt_7001.xlsx", [ALT_7001])
    schreiben_v3("oa_v3_abweichend.xlsx", ABWEICHEND)
