# ruff: noqa: E501
"""Echtgeld-Reife des Options Rollers (Nutzer 21.10.2026): messbare Kriterien aus dem Roller-Status.

Schwellen sind Annahmen (OF-104) und stehen als Modulwerte hier. Gemessen wird nur, was der Status des Rollers hergibt;
alles andere ist eine manuelle Abnahme (``MANUELL``) und wird in der Oberfläche vom Nutzer abgehakt. Das Ergebnis ist eine
Entscheidungshilfe, keine Freigabe: der Schritt auf Echtgeld bleibt eine Entscheidung des Nutzers.
"""
from datetime import date, datetime

MIN_LIVE_TAGE = 5          # Datenquelle durchgehend live seit mindestens so vielen Kalendertagen
MIN_ROLLS = 10             # vollständige Rolls (geschlossene und offene Ketten zusammen)
MIN_GESCHLOSSENE_KETTEN = 30
MAX_ANGEHALTENE_KETTEN = 0
MAX_WAISEN_MELDUNGEN = 0   # Meldungen „Bestand ohne Kette“ im Meldungsspeicher

def _zaehlt(name: str) -> bool:
    """Für Echtgeld zählen nur Strategien mit Laufzeit über einen Tag (Nutzer 23.10.2026): 0DTE-Ketten verzerren
    Rolls und Ketten, weil sie nie gerollt werden und täglich in großer Zahl entstehen."""
    return "0DTE" not in name


MANUELL = (
    ("neustart_order", "Dienstneustart mitten in einer laufenden Order getestet (kein Waisen-Bestand, keine doppelte Order)"),
    ("not_aus", "Not-Aus (Automatik aus) wirkt auch während eines Tagesprogramms"),
    ("bcs_ursache", "Ursache der nicht füllenden Call-Spreads (0DTE) verstanden und behoben oder bewusst ausgeschlossen"),
    ("restore", "Wiederherstellung aus der Sicherung einmal in einer temporären Datenbank geprobt (M08)"),
    ("live_modus", "Live-Modus mit harten Grenzen gebaut: 1 Kontrakt, feste Strategieliste, Tageslimit, Kontoprüfung"),
    ("fill_qualitaet", "Fill-Qualität (Fill gegen Mittelkurs) über mehrere Wochen mit Live-Daten beurteilt"),
)


def _kriterium(kid: str, text: str, ist, soll: str, ok: bool | None) -> dict:
    return {"id": kid, "text": text, "ist": ist, "soll": soll, "ok": ok, "automatisch": True}


def bewerte(status: dict | None, heute: date) -> dict:
    """``status``: Antwort des Roller-Dienstes (``strategie``-Teil) oder ``None``, wenn nicht erreichbar."""
    s = (status or {}).get("strategie") if status and "strategie" in status else status
    if not s:
        return {"erreichbar": False, "kriterien": [], "manuell": [{"id": k, "text": t} for k, t in MANUELL],
                "automatisch_erfuellt": False}
    daten = s.get("daten") or {}
    art, seit = daten.get("art"), daten.get("seit")
    try:
        tage = (heute - datetime.fromisoformat(seit).date()).days if seit else None
    except (TypeError, ValueError):
        tage = None
    statistik = {n: z for n, z in (s.get("statistik") or {}).items() if _zaehlt(n)}
    ketten_zaehlt = [k for k in s.get("ketten") or [] if _zaehlt(str(k.get("strategie", "")))]
    geschlossen = sum(int(z.get("n", 0)) for z in statistik.values())
    rolls = sum(int(z.get("rolls_summe", 0)) for z in statistik.values()) + sum(
        int(k.get("rolls", 0)) for k in ketten_zaehlt)
    angehalten = sum(1 for k in s.get("ketten") or [] if k.get("status") == "pruefen")    # jede angehaltene Kette zählt
    waisen = sum(1 for m in s.get("meldungen") or [] if "Bestand ohne Kette" in str(m))

    kriterien = [
        _kriterium("live_daten", f"Datenquelle live, durchgehend seit mindestens {MIN_LIVE_TAGE} Tagen",
                   f"{art or 'unbekannt'}" + (f", seit {tage} Tagen" if tage is not None and art == "live" else ""),
                   f"live seit ≥ {MIN_LIVE_TAGE} Tagen", art == "live" and tage is not None and tage >= MIN_LIVE_TAGE),
        _kriterium("rolls", "Vollständige Rolls ohne Auffälligkeit (ohne 0DTE)", rolls, f"≥ {MIN_ROLLS}", rolls >= MIN_ROLLS),
        _kriterium("ketten", "Geschlossene Ketten (ohne 0DTE)", geschlossen, f"≥ {MIN_GESCHLOSSENE_KETTEN}",
                   geschlossen >= MIN_GESCHLOSSENE_KETTEN),
        _kriterium("angehalten", "Angehaltene Ketten (Bestand passt nicht zur Kette)", angehalten,
                   f"≤ {MAX_ANGEHALTENE_KETTEN}", angehalten <= MAX_ANGEHALTENE_KETTEN),
        _kriterium("waisen", "Meldungen „Bestand ohne Kette“", waisen, f"≤ {MAX_WAISEN_MELDUNGEN}",
                   waisen <= MAX_WAISEN_MELDUNGEN),
    ]
    return {
        "erreichbar": True,
        "kriterien": kriterien,
        "manuell": [{"id": k, "text": t} for k, t in MANUELL],
        "automatisch_erfuellt": all(k["ok"] for k in kriterien),
    }
