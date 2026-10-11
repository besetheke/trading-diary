"""Erzeugt die OptionApp-Fixtures für AP-13r2 (Fortschreibung laufender Trades).

Eigenes Skript, damit die Dateien aus ``erzeugen.py`` unverändert bleiben.
Alle Werte frei erfunden. Aufruf aus dem Projektverzeichnis:
``.venv\\Scripts\\python.exe fixtures\\optionapp\\erzeugen_fortschreibung.py``

Stand 1 (älterer Export): 6001 läuft noch, 6002 ist geschlossen.
Stand 2 (neuerer Export): 6001 ist verfallen (Profit 174,24 $), 6002
unverändert, 6003 neu.
Strategie anders: 6001 läuft — aber unter einer anderen Strategie.
"""

from erzeugen import schreiben

LAUFEND_6001 = [
    "2026/03/02 11:20:44",
    "XSP: IF7",
    "IF7 [6001]",
    "-1xP520 (260306) / 1xC530 (260306)",
    "1/1",
    -1.75,
    "-",
    "-",
    "0,00 $",
    "-",
    "RUNNING",
]
FERTIG_6001 = [
    "2026/03/02 11:20:44",
    "XSP: IF7",
    "IF7 [6001]",
    "-1xP520 (260306) / 1xC530 (260306)",
    "1/1",
    -1.75,
    0,
    "-",
    "174,24 $",
    "2026/03/06 16:00:00",
    "EXPIRED",
]
GESCHLOSSEN_6002 = [
    "2026/03/03 12:00:00",
    "XSP: IF7",
    "IF7 [6002]",
    "-1xP521 (260306) / 1xC531 (260306)",
    "1/1",
    -1.10,
    -0.60,
    "-",
    "48,48 $",
    "2026/03/05 15:00:00",
    "CLOSED",
]
NEU_6003 = [
    "2026/03/09 11:20:00",
    "XSP: IF7",
    "IF7 [6003]",
    "-1xP522 (260313) / 1xC532 (260313)",
    "1/1",
    -1.20,
    0,
    "-",
    "118,48 $",
    "2026/03/13 16:00:00",
    "EXPIRED",
]
ANDERE_STRATEGIE_6001 = [
    "2026/03/02 11:20:44",
    "SPX: IC",
    "IF7 [6001]",
    "-1xP520 (260306) / 1xC530 (260306)",
    "1/1",
    -1.75,
    0,
    "-",
    "174,24 $",
    "2026/03/06 16:00:00",
    "EXPIRED",
]

if __name__ == "__main__":
    schreiben("oa_fortschreibung_1.xlsx", [LAUFEND_6001, GESCHLOSSEN_6002])
    schreiben("oa_fortschreibung_2.xlsx", [FERTIG_6001, GESCHLOSSEN_6002, NEU_6003])
    schreiben(
        "oa_fortschreibung_andere_strategie.xlsx", [ANDERE_STRATEGIE_6001, NEU_6003]
    )
