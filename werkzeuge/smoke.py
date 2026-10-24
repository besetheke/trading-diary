# ruff: noqa: E501
"""Smoke-Test der Oberfläche (AP-17g, Review M08): jede Seite und jeder API-Weg, den die Oberfläche aufruft, antwortet.

Liest aus dem Quellcode der Oberfläche (``ui/src/main.tsx`` und ``ui/src/api.ts``), welche Seiten (Routen) und welche
lesenden API-Wege es gibt, und ruft sie gegen einen laufenden Server oder eine Test-Anwendung auf. Er fängt Fehler wie R11
(ein Weg fehlt im Proxy oder in der API) automatisch ab: ein Weg, der nicht mit 200 antwortet, ist ein Befund.

Aufruf gegen einen laufenden Server (z. B. nach dem Deploy)::

    python werkzeuge/smoke.py http://127.0.0.1:8000

Rückgabewert 0 nur, wenn alles antwortet. Ohne Browser: geprüft wird Erreichbarkeit und Antwortcode, nicht die Darstellung.
"""
import pathlib
import re
import sys
from collections.abc import Callable

WURZEL = pathlib.Path(__file__).resolve().parents[1]


def seiten() -> list[str]:
    """Seiten ohne Parameter aus den Routen von ui/src/main.tsx (ohne Platzhalter und Sammelroute)."""
    text = (WURZEL / "ui" / "src" / "main.tsx").read_text(encoding="utf-8")
    pfade = re.findall(r'<Route path="(/[^"*:]*)"', text)
    return sorted({p for p in pfade if not p.endswith("/")} | {"/"})


def api_wege() -> list[str]:
    """Lesende API-Wege (GET) aus ui/src/api.ts: der statische Anfang jedes ``hole(...)``-Aufrufs."""
    text = (WURZEL / "ui" / "src" / "api.ts").read_text(encoding="utf-8")
    wege = re.findall(r"""hole\(\s*[`'"](/[a-z0-9\-/]+)""", text)
    return sorted({w for w in wege if not w.endswith("/")})


# Wege mit Pflichtparametern bekommen harmlose Standardwerte (sonst antwortet die API zu Recht mit 422).
PFLICHTPARAMETER = {
    "/kalender": "?monat=2026-10",
    "/backtests/paare": "?oo_strategie=smoke&oa_strategie=smoke",
}


# Ein Weg, der ein bestimmtes Objekt verlangt, antwortet für ein Objekt, das es nicht gibt, zu Recht mit 404.
ERLAUBTE_STATUS = {"/backtests/paare": {200, 404}}


def smoke(hole_status: Callable[[str], int]) -> list[tuple[str, int]]:
    """Ruft alle Seiten und API-Wege auf und gibt die Abweichungen zurück: (Pfad, Statuscode); leer = alles in Ordnung."""
    return [(pfad, status) for pfad in seiten() + api_wege()
            if (status := hole_status(pfad + PFLICHTPARAMETER.get(pfad, ""))) not in ERLAUBTE_STATUS.get(pfad, {200})]


def main(argv: list[str] | None = None) -> int:
    import urllib.error
    import urllib.request

    basis = (argv or sys.argv[1:] or ["http://127.0.0.1:8000"])[0].rstrip("/")

    def status(pfad: str) -> int:
        try:
            with urllib.request.urlopen(basis + pfad, timeout=60) as antwort:
                return antwort.status
        except urllib.error.HTTPError as fehler:
            return fehler.code
        except Exception:  # noqa: BLE001 — nicht erreichbar zählt als Befund
            return 0

    abweichungen = smoke(status)
    gesamt = len(seiten()) + len(api_wege())
    print(f"Smoke-Test {basis}: {gesamt - len(abweichungen)} von {gesamt} Wegen antworten mit 200")
    for pfad, code in abweichungen:
        print(f"  BEFUND {pfad}: {code or 'nicht erreichbar'}", file=sys.stderr)
    return 0 if not abweichungen else 1


if __name__ == "__main__":
    sys.exit(main())
