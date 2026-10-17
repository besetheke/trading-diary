# ruff: noqa: E501
"""Überleitung der Steuer-Aufbereitung zu IBs Realized P/L (AP-10c, Nachtrag 17.10.2026).

Frage des Nutzers: „Warum liegt die Station so weit neben dem Activity Statement?“ Antwort je Zuflussjahr, rein
rechnerisch aus Zahlen, die schon vorliegen — nichts wird neu bewertet:

- **IB** (``fifoPnlRealized × fxRateToBase`` je Ausführung, Klassen Aktien / Optionen / Futures u. a.).
- **Verschobene Prämien:** IB schiebt die Prämie einer zugeteilten Option in den Einstand der Aktie (die Option
  bucht 0); die Station lässt sie als Stillhalterprämie stehen. Gemessen als Differenz IB − Station je
  Schließungsausführung von Aktienbeinen, deren Eröffnung oder Schließung eine Zuteilung/Ausübung war.
- **Offene Prämien:** Prämien offener Short-Positionen zählen in der Station im Zuflussjahr, bei IB nicht.
- **Rest:** alles Übrige (Zuflussjahr statt Schließungsjahr, Kommission, Kurs, Rundung) — als Rest ausgewiesen, nicht
  weiter aufgeschlüsselt.

Rein: keine Datenbank, keine Uhr.
"""

from collections import defaultdict
from decimal import Decimal

from analytics.steuer_zufluss import (
    TOPF_AKTIEN,
    TOPF_STILLHALTER,
    TOPF_TERMIN,
    SteuerZuflussErgebnis,
)

_NULL = Decimal("0")
KLASSE_AKTIEN = "STK"
KLASSE_OPTIONEN = "OPT"
# Futures und Futures-Optionen stehen bei IB getrennt, in der Station bei den Termingeschäften.
KLASSEN_FUTURES = ("FUT", "FOP")


def ib_ueberleitung(
    ergebnis: SteuerZuflussErgebnis,
    ib_zeilen: list[dict],
    lieferung_exec_ids: frozenset[str],
    offene_leg_ids: frozenset[int],
) -> dict[int, dict]:
    """Je Jahr die Überleitung IB → Station.

    ``ib_zeilen``: ``exec_id``, ``jahr``, ``klasse`` (STK/OPT/FUT/FOP/…), ``eur`` (IB-Gewinn der Ausführung in EUR).
    ``lieferung_exec_ids``: Schließungsausführungen von Aktienbeinen, deren Eröffnung oder Schließung eine
    Zuteilung/Ausübung war. ``offene_leg_ids``: Legs ohne Schließung.
    """
    jahre: dict[int, dict] = defaultdict(
        lambda: {
            "ib_aktien": _NULL, "ib_optionen": _NULL, "ib_futures": _NULL,
            "station_aktien": _NULL, "station_stillhalter": _NULL, "station_termin": _NULL,
            "verschobene_praemien": _NULL, "offene_praemien": _NULL,
        }
    )
    # Station je Schließungsausführung (Aktien) — ETF-Beine stehen in den offenen Regeln, zählen hier mit
    station_je_exec: dict[str, Decimal] = defaultdict(lambda: _NULL)
    for s in ergebnis.stroeme:
        j = jahre[s.jahr]
        if s.topf == TOPF_AKTIEN:
            j["station_aktien"] += s.betrag_eur
            if s.exec_id:
                station_je_exec[s.exec_id] += s.betrag_eur
        elif s.topf == TOPF_STILLHALTER:
            j["station_stillhalter"] += s.betrag_eur
            if s.vorgang == "stillhalterpraemie" and s.leg_id in offene_leg_ids:
                j["offene_praemien"] += s.betrag_eur
        elif s.topf == TOPF_TERMIN:
            j["station_termin"] += s.betrag_eur
    for r in ergebnis.regeln_offen:
        if r.art != "etf_investmentsteuer":
            continue
        for d in r.details:
            jahr = int(d["geschlossen"][:4])
            jahre[jahr]["station_aktien"] += d["ergebnis_eur"]
            if d.get("exec_id"):
                station_je_exec[d["exec_id"]] += d["ergebnis_eur"]

    for z in ib_zeilen:
        j = jahre[z["jahr"]]
        if z["klasse"] == KLASSE_AKTIEN:
            j["ib_aktien"] += z["eur"]
            if z["exec_id"] in lieferung_exec_ids:
                j["verschobene_praemien"] += z["eur"] - station_je_exec.get(z["exec_id"], _NULL)
        elif z["klasse"] == KLASSE_OPTIONEN:
            j["ib_optionen"] += z["eur"]
        elif z["klasse"] in KLASSEN_FUTURES:
            j["ib_futures"] += z["eur"]

    ergebnis_je_jahr = {}
    for jahr, j in sorted(jahre.items()):
        ib_opt_fut = j["ib_optionen"] + j["ib_futures"]
        station_opt = j["station_stillhalter"] + j["station_termin"]
        rest_aktien = j["station_aktien"] - (j["ib_aktien"] - j["verschobene_praemien"])
        rest_optionen = station_opt - (ib_opt_fut + j["verschobene_praemien"] + j["offene_praemien"])
        ergebnis_je_jahr[jahr] = {
            **j,
            "ib_optionen_futures": ib_opt_fut,
            "station_optionen": station_opt,
            "rest_aktien": rest_aktien,
            "rest_optionen": rest_optionen,
        }
    return ergebnis_je_jahr


def kap_ib_varianten(ib_zeilen: list[dict], jahre: dict[int, dict]) -> dict[int, dict]:
    """Variante B der KAP-Vorschau: **IBs Realized P/L** (wie im Activity Statement) — realisiert beim Schließen,
    die Prämie einer zugeteilten Option liegt im Einstand der Aktie, offene Positionen fehlen. Gewinne und Verluste
    je IB-Ausführung (IB selbst weist sie je Lot aus; je Ausführung ist eine Näherung). Dividenden, Habenzinsen und
    Quellensteuer stammen unverändert aus der Station (``jahre`` von ``SteuerZuflussErgebnis.jahre()``)."""
    from analytics.steuer_zufluss import TOPF_DIVIDENDEN, TOPF_ZINSEN, kap_block

    ib: dict[int, dict[str, Decimal]] = defaultdict(
        lambda: {"stk_g": _NULL, "stk_v": _NULL, "opt_g": _NULL, "opt_v": _NULL}
    )
    for z in ib_zeilen:
        if z["klasse"] == KLASSE_AKTIEN:
            k = "stk_g" if z["eur"] >= _NULL else "stk_v"
        elif z["klasse"] == KLASSE_OPTIONEN or z["klasse"] in KLASSEN_FUTURES:
            k = "opt_g" if z["eur"] >= _NULL else "opt_v"
        else:
            continue
        ib[z["jahr"]][k] += z["eur"]
    ergebnis = {}
    for jahr in sorted(set(ib) | set(jahre)):
        w = ib[jahr]
        t = jahre.get(jahr, {"toepfe": {}, "quellensteuer": {"vorlaeufig_anrechenbar": _NULL}})
        ergebnis[jahr] = kap_block(
            jahr, "ib", "IB-Methode (Realized P/L)",
            "Wie das Activity Statement: realisiert beim Schließen, Prämie zugeteilter Optionen im Einstand der Aktie, "
            "offene Positionen nicht enthalten.",
            {
                "Aktien (IB)": w["stk_g"] + w["stk_v"],
                "Optionen und Futures (IB)": w["opt_g"] + w["opt_v"],
                "Dividenden": t["toepfe"].get(TOPF_DIVIDENDEN, {}).get("saldo", _NULL),
                "Habenzinsen": t["toepfe"].get(TOPF_ZINSEN, {}).get("saldo", _NULL),
            },
            w["stk_g"], -w["opt_v"], -w["stk_v"], t["quellensteuer"]["vorlaeufig_anrechenbar"],
        )
    return ergebnis
