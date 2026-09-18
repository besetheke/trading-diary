"""Stabile Pseudonyme für `conid`s in Abgleichsausgaben (Regel 2).

Ein gesalzener Hash statt einer laufenden Nummer je Skriptlauf: dieselbe
`conid` ergibt über verschiedene Läufe und verschiedene Skripte hinweg
dasselbe Pseudonym, ohne dass die `conid` selbst irgendwo im Repository
steht. Das Salz liegt bei den Golden-Fixtures, also außerhalb des
Repositorys (``fixtures/golden/`` ist gitignored) — ohne das Salz lässt sich
ein Pseudonym nicht auf die echte `conid` zurückrechnen.

Wird das Salz nicht gefunden, erzeugt dieses Modul eines und schreibt es neu
— das ist beabsichtigt: Pseudonyme aus einem Lauf ohne vorhandenes Salz sind
nicht mit denen eines späteren Laufs vergleichbar, aber das betrifft nur die
lokale Maschine, nie das Repository.
"""

import hashlib
import secrets
from pathlib import Path

SALZ_DATEI = Path(__file__).resolve().parents[2] / "fixtures" / "golden" / ".pseudonym_salz"


def _salz() -> bytes:
    if SALZ_DATEI.is_file():
        return SALZ_DATEI.read_bytes()
    salz = secrets.token_bytes(32)
    SALZ_DATEI.write_bytes(salz)
    return salz


def pseudonym(conid: int, praefix: str = "I") -> str:
    """Stabiles Pseudonym für eine `conid`, z. B. `I-3F7A2C91`."""
    digest = hashlib.sha256(_salz() + str(conid).encode("ascii")).hexdigest()
    return f"{praefix}-{digest[:8].upper()}"
