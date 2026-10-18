# ruff: noqa: E501
"""Momentum Lab starten und beenden (Station, Schalter „Momentum Suite“).

Momentum Lab ist ein eigenes Projekt (Streamlit auf 127.0.0.1:8501). Das Journal startet es über dessen
eigenen versteckten Starter und beendet es über den Prozess, der den Port hält — und nur, wenn dieser Prozess
nachweislich Momentum Lab ist (Kommandozeile enthält ``momentum_lab`` und ``app.py``). Ein fremdes Programm
auf dem Port wird nie beendet. Nur Windows; der Ordner des Projekts kommt aus ``MOMENTUM_LAB_ORDNER``,
sonst ``momentum-lab`` neben diesem Projekt.
"""

import os
import pathlib
import re
import subprocess

PORT = 8501
_KEIN_FENSTER = 0x08000000      # CREATE_NO_WINDOW
_ABGELOEST = 0x00000200         # CREATE_NEW_PROCESS_GROUP (DETACHED_PROCESS beendet den Starter sofort und stumm)


def lab_ordner() -> pathlib.Path:
    vorgabe = os.environ.get("MOMENTUM_LAB_ORDNER")
    return pathlib.Path(vorgabe) if vorgabe else pathlib.Path(__file__).resolve().parents[2] / "momentum-lab"


def pid_am_port(netstat_text: str, port: int = PORT) -> int | None:
    """PID des Prozesses, der ``port`` auf 127.0.0.1/0.0.0.0/[::] abhört (aus der Ausgabe von ``netstat -ano``)."""
    muster = re.compile(rf"^\s*TCP\s+\S+:{port}\s+\S+\s+(?:LISTENING|ABH\S*)\s+(\d+)\s*$", re.IGNORECASE)
    for zeile in netstat_text.splitlines():
        treffer = muster.match(zeile)
        if treffer:
            return int(treffer.group(1))
    return None


def ist_momentum_lab(kommandozeile: str) -> bool:
    text = (kommandozeile or "").lower().replace("/", "\\")
    return "momentum_lab" in text and "app.py" in text


def _ausgabe(befehl: list[str]) -> str:
    return subprocess.run(befehl, capture_output=True, text=True, timeout=20,
                          creationflags=_KEIN_FENSTER, errors="replace").stdout


def _kommandozeile(pid: int) -> str:
    return _ausgabe(["powershell", "-NoProfile", "-Command",
                     f"(Get-CimInstance Win32_Process -Filter 'ProcessId={pid}').CommandLine"]).strip()


def _starter_pids(mindestalter_s: int = 0) -> list[int]:
    """PIDs der versteckten Starter-Skripte von Momentum Lab (älter als ``mindestalter_s``).

    Der Starter überwacht den Server. Endet der Server (Stopp von außen), zeigt der Starter einen
    Fehlerdialog in seinem unsichtbaren Fenster und hält dabei die Sperre — jeder weitere Start
    scheiterte danach stumm. Deshalb werden Starter beim Stopp und vor einem Start mit beendet."""
    text = _ausgabe(["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_Process -Filter \"Name='powershell.exe'\" | "
                     "Where-Object { $_.CommandLine -like '*start_momentum_lab_hidden*' -and "
                     f"(New-TimeSpan -Start $_.CreationDate).TotalSeconds -ge {mindestalter_s} }} | "
                     "ForEach-Object { $_.ProcessId }"])
    return [int(z.strip()) for z in text.splitlines() if z.strip().isdigit()]


def _starter_beenden(mindestalter_s: int = 0) -> None:
    try:
        pids = _starter_pids(mindestalter_s)
    except Exception:       # Aufräumen ist nur ein Zusatz; der eigentliche Stopp/Start darf daran nicht scheitern
        return
    for pid in pids:
        _ausgabe(["taskkill", "/PID", str(pid), "/T", "/F"])


def laeuft() -> bool:
    return pid_am_port(_ausgabe(["netstat", "-ano", "-p", "tcp"])) is not None


def starten_mit_aufraeumen() -> tuple[bool, str]:
    """Wie ``starten``, räumt vorher hängengebliebene Starter (älter als 90 s) ab, falls Lab nicht läuft."""
    if not laeuft():
        _starter_beenden(mindestalter_s=90)
    return starten()


def starten() -> tuple[bool, str]:
    """Startet Momentum Lab ohne Fenster und ohne Browser. Läuft es schon, geschieht nichts."""
    if laeuft():
        return True, "Momentum Lab läuft bereits."
    skript = lab_ordner() / "tools" / "start_momentum_lab_hidden.ps1"
    if not skript.is_file():
        return False, f"Starter nicht gefunden: {skript} (Ordner über MOMENTUM_LAB_ORDNER festlegen)."
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(skript), "-NoBrowser"],
        creationflags=_KEIN_FENSTER | _ABGELOEST, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(lab_ordner()))
    return True, "Momentum Lab wird gestartet (dauert einige Sekunden)."


def beenden() -> tuple[bool, str]:
    """Beendet Momentum Lab samt Unterprozessen — nur wenn der Port-Halter wirklich Momentum Lab ist."""
    pid = pid_am_port(_ausgabe(["netstat", "-ano", "-p", "tcp"]))
    if pid is None:
        _starter_beenden()
        return True, "Momentum Lab läuft nicht."
    if not ist_momentum_lab(_kommandozeile(pid)):
        return False, f"Port {PORT} gehört einem anderen Programm (PID {pid}) — nicht beendet."
    _starter_beenden()          # zuerst den Starter, sonst bleibt er mit Fehlerdialog und Sperre stehen
    _ausgabe(["taskkill", "/PID", str(pid), "/T", "/F"])
    return True, "Momentum Lab wurde beendet."
