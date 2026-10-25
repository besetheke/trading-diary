# ruff: noqa: E501
"""Datenqualität als Arbeitsliste (AP-17g, Review M04).

Eine einheitliche Liste statt verstreuter Hinweise: je Punkt Art, Schwere, Anzahl, Betrag, Zeitraum, betroffene Objekte und
Lösungsweg. Der Betriebsstatus unterscheidet **letzten erfolgreichen Abruf**, **letzten erfolgreichen Import** und **letzten
erfolgreichen Rebuild** und zeigt einen Fehlschlag oder Teilerfolg (``betriebslaeufe``) — das Importdatum allein beweist keinen
Neuaufbau. Jeder Punkt trägt seinen Zeitraum: alte fachliche Fragen blockieren neue, unabhängige Zeiträume nicht pauschal.
Nur lesend.
"""
import pathlib
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from journal.db import create_db_engine
from journal.schema import (
    betriebslaeufe,
    chains,
    executions,
    import_runs,
    instruments,
    legs,
    strategie_zuordnungen,
)

ABRUF_ALT_TAGE = 2          # ab so vielen Tagen ohne erfolgreichen Abruf: Warnung
LOG_HINWEIS = r"%USERPROFILE%\.trading-journal\logs\nachtlauf-<Datum>.log"


def _punkt(pid: str, art: str, titel: str, schwere: str, *, anzahl: int | None = None, betrag: str | None = None,
           von=None, bis=None, betroffen: list | None = None, loesung: str = "", link: str | None = None) -> dict:
    return {"id": pid, "art": art, "titel": titel, "schwere": schwere, "anzahl": anzahl, "betrag": betrag,
            "von": None if von is None else str(von)[:10], "bis": None if bis is None else str(bis)[:10],
            "betroffen": betroffen or [], "loesung": loesung, "link": link}


def _laeufe(verbindung) -> tuple[dict, bool]:
    """Jüngster und jüngster erfolgreicher Lauf je Art; zweiter Wert: Tabelle ``betriebslaeufe`` vorhanden (sonst Migration offen)."""
    aus = {}
    tabelle_da = True
    for art in ("abruf", "import", "rebuild"):
        try:
            letzte = verbindung.execute(select(betriebslaeufe).where(betriebslaeufe.c.art == art)
                                        .order_by(betriebslaeufe.c.beendet_am.desc(), betriebslaeufe.c.id.desc()).limit(1)).mappings().first()
            ok = verbindung.execute(select(func.max(betriebslaeufe.c.beendet_am)).where(
                betriebslaeufe.c.art == art, betriebslaeufe.c.ergebnis == "ok")).scalar()
        except OperationalError:
            letzte, ok, tabelle_da = None, None, False
        aus[art] = {"zuletzt_ok": None if ok is None else str(ok),
                    "zuletzt": None if letzte is None else {"zeit": str(letzte["beendet_am"]), "ergebnis": letzte["ergebnis"],
                                                            "meldung": letzte["meldung"]}}
    # Vor dem ersten protokollierten Lauf: der Import lässt sich aus import_runs ablesen, der Rebuild nicht.
    if aus["import"]["zuletzt_ok"] is None:
        zuletzt = verbindung.execute(select(func.max(import_runs.c.importiert_am)).where(import_runs.c.quelle == "flex")).scalar()
        if zuletzt is not None:
            aus["import"]["zuletzt_ok"] = str(zuletzt)
            aus["import"]["herkunft"] = "import_runs (vor der Protokollierung)"
    return aus, tabelle_da


def arbeitsliste(db_pfad: str | pathlib.Path, heute: date | None = None, *, mit_abgleich: bool = True) -> dict:
    """Betriebsstatus und Arbeitsliste, die schwersten Punkte zuerst. ``heute`` kommt vom Aufrufer (keine Uhr im Kern)."""
    heute = heute or date.today()
    engine = create_db_engine(db_pfad)
    punkte: list[dict] = []
    with engine.connect() as v:
        laeufe, tabelle_da = _laeufe(v)
        if not tabelle_da:
            punkte.append(_punkt("schema-veraltet", "betrieb", "Datenbank nicht auf dem neuesten Stand: die Tabelle der Betriebsläufe fehlt", "warnung",
                                 loesung="`alembic upgrade head` ausführen (das Deploy tut das); bis dahin fehlen Abruf-/Rebuild-Zeiten und Fehlschläge."))

        # 1. Fehlschläge und Teilerfolge: der jüngste Lauf einer Art ist schlechter als der letzte Erfolg
        namen = {"abruf": "Abruf", "import": "Import", "rebuild": "Neuaufbau (Rebuild)"}
        for art, info in laeufe.items():
            z = info["zuletzt"]
            if z and z["ergebnis"] in ("fehler", "teilweise") and (info["zuletzt_ok"] is None or z["zeit"] > info["zuletzt_ok"]):
                punkte.append(_punkt(
                    f"lauf-{art}", "betrieb", f"{namen[art]} {'fehlgeschlagen' if z['ergebnis'] == 'fehler' else 'nur teilweise erfolgreich'}: {z['meldung'] or 'ohne Meldung'}",
                    "fehler" if z["ergebnis"] == "fehler" else "warnung", von=z["zeit"], bis=z["zeit"],
                    loesung=f"Ursache im Protokoll ({LOG_HINWEIS}) suchen und beheben, danach `journal abrufen --rebuild` bzw. `journal rebuild` erneut starten."))

        # 2. Abruf zu alt
        referenz = laeufe["abruf"]["zuletzt_ok"] or laeufe["import"]["zuletzt_ok"]
        if referenz is None:
            punkte.append(_punkt("abruf-nie", "betrieb", "Noch kein Abruf oder Import protokolliert", "hinweis",
                                 loesung="`journal abrufen --rebuild` oder `journal import <datei>` ausführen."))
        else:
            alter = (heute - datetime.fromisoformat(referenz).date()).days
            if alter >= ABRUF_ALT_TAGE:
                punkte.append(_punkt("abruf-alt", "betrieb", f"Letzter erfolgreicher Abruf/Import vor {alter} Tagen", "warnung",
                                     von=referenz, bis=referenz,
                                     loesung="Nachtlauf in der Aufgabenplanung prüfen (nachtlauf.cmd), Flex-Token und Zugang kontrollieren."))

        # 3. Neuaufbau älter als der letzte Import
        rb, im = laeufe["rebuild"]["zuletzt_ok"], laeufe["import"]["zuletzt_ok"]
        if im and rb is None:
            punkte.append(_punkt("rebuild-nie", "betrieb", "Neuaufbau noch nie protokolliert: die abgeleiteten Tabellen sind vom Import-Stand unbelegt", "hinweis",
                                 loesung="`journal rebuild` ausführen (der Nachtlauf tut das mit `--rebuild`)."))
        elif im and rb and rb < im:
            punkte.append(_punkt("rebuild-alt", "betrieb", "Der letzte erfolgreiche Neuaufbau ist älter als der letzte Import", "warnung",
                                 von=rb, bis=im, loesung="`journal rebuild` ausführen; sonst fehlen neue Ausführungen in Ketten und Kennzahlen."))

        # 4. Nicht strukturierte Legs
        n, von, bis = v.execute(
            select(func.count(), func.min(executions.c.handelszeit), func.max(executions.c.handelszeit))
            .select_from(legs.join(executions, executions.c.exec_id == legs.c.open_exec_id))
            .where(legs.c.sicht == "konto", legs.c.structure_id.is_(None))).one()
        if n:
            ids = [str(i) for (i,) in v.execute(select(legs.c.leg_id).where(legs.c.sicht == "konto", legs.c.structure_id.is_(None))
                                                .order_by(legs.c.leg_id.desc()).limit(10))]
            punkte.append(_punkt("legs-ohne-struktur", "zuordnung", "Legs ohne Struktur (z. B. Eröffnung durch Zuteilung oder Ausübung)", "warnung",
                                 anzahl=n, von=von, bis=bis, betroffen=[f"Leg {i}" for i in ids],
                                 loesung="Zuordnung in der Positionsliste prüfen; Einordnung als Kettenübergang ist Sache der Kettenbildung (AP-04)."))

        # 5. Kapitalmaßnahmen ohne Kostenangabe
        n, von, bis = v.execute(
            select(func.count(), func.min(executions.c.handelszeit), func.max(executions.c.handelszeit))
            .select_from(legs.join(executions, executions.c.exec_id == legs.c.open_exec_id))
            .where(legs.c.sicht == "konto", legs.c.basis_ungeklaert.is_(True))).one()
        if n:
            symbole = [s for (s,) in v.execute(
                select(func.distinct(instruments.c.symbol)).select_from(legs.join(instruments, instruments.c.conid == legs.c.conid))
                .where(legs.c.sicht == "konto", legs.c.basis_ungeklaert.is_(True)).limit(10))]
            punkte.append(_punkt("basis-ungeklaert", "kapitalmassnahme", "Zugang aus Kapitalmaßnahme ohne Kostenangabe (Einstandswert ungeklärt)", "fehler",
                                 anzahl=n, von=von, bis=bis, betroffen=symbole,
                                 loesung="Kosten laut Broker nachtragen bzw. Kapitalmaßnahme klären (OFFENE_FRAGEN OF-23); bis dahin keine Ergebnisaussage für diese Titel."))

        # 6. Fehlende Wechselkurse
        n, von, bis = v.execute(
            select(func.count(), func.min(executions.c.handelszeit), func.max(executions.c.handelszeit))
            .where(executions.c.buchungskurs.is_(None), executions.c.waehrung != "EUR")).one()
        if n:
            punkte.append(_punkt("kurs-fehlt", "kurs", "Ausführungen in Fremdwährung ohne Wechselkurs (fxRateToBase)", "fehler", anzahl=n, von=von, bis=bis,
                                 loesung="Flex-Abfrage prüfen: das Feld fxRateToBase muss aktiviert sein (Flex-Query-Anleitung); danach erneut abrufen."))

        # 6b. Manuelle Strategiezuordnungen: Widerspruch zu OA und Zuordnungen ohne Kette
        try:
            konflikte = v.execute(select(strategie_zuordnungen.c.natur_schluessel, strategie_zuordnungen.c.strategie,
                                         strategie_zuordnungen.c.konflikt_oa).where(
                strategie_zuordnungen.c.zurueckgenommen_am.is_(None), strategie_zuordnungen.c.konflikt_oa.is_not(None))).all()
            if konflikte:
                punkte.append(_punkt("strategie-widerspruch", "zuordnung", "Manuelle Strategie widerspricht OA", "hinweis", anzahl=len(konflikte),
                                     betroffen=[f"{nk}: manuell {s}, OA {o}" for nk, s, o in konflikte[:5]],
                                     loesung="Die manuelle Zuordnung gilt (Regel des Nutzers). Prüfen, ob sie noch stimmt; sonst auf der Positionsseite zurücknehmen."))
            vorhanden = {nk for (nk,) in v.execute(select(chains.c.natur_schluessel).where(chains.c.sicht == "konto"))}
            aktiv = [nk for (nk,) in v.execute(select(strategie_zuordnungen.c.natur_schluessel).where(strategie_zuordnungen.c.zurueckgenommen_am.is_(None)))]
            verwaist = [nk for nk in aktiv if nk not in vorhanden]
            if verwaist:
                punkte.append(_punkt("strategie-verwaist", "zuordnung", "Manuelle Strategiezuordnung ohne Kette (Kette hat sich verändert)", "warnung",
                                     anzahl=len(verwaist), betroffen=verwaist[:5],
                                     loesung="Die Zuordnung bleibt gespeichert. Kette in der Positionsliste suchen und die Strategie neu setzen."))
        except OperationalError:
            pass        # Tabelle noch nicht migriert (siehe Punkt „schema-veraltet“)

    # 7. offene Rollkandidaten (liest selbst)
    try:
        from journal.rebuild import offene_rollkandidaten
        kandidaten = offene_rollkandidaten(db_pfad)
        if kandidaten:
            punkte.append(_punkt("rollkandidaten", "zuordnung", "Offene Rollkandidaten ohne Entscheidung", "hinweis", anzahl=kandidaten,
                                 loesung="Auf der Seite „Rollkandidaten“ bestätigen oder ablehnen.", link="/rolls"))
    except Exception:  # noqa: BLE001 — eine einzelne Prüfung darf die Liste nie verhindern
        pass

    # 8. Abgleichsreste gegen IBs realisierte Werte
    if mit_abgleich:
        try:
            from analytics.ib_abgleich import ib_abgleich_bericht
            ab = ib_abgleich_bericht(db_pfad)
            if ab.zeilen_abweichend:
                top = sorted(ab.einzelreste, key=lambda r: abs(r.eur), reverse=True)[:5]
                punkte.append(_punkt("abgleich-reste", "abgleich", "Abgleich mit IBs realisierten Werten: Zeilen mit Rest", "hinweis",
                                     anzahl=ab.zeilen_abweichend, betrag=str(sum((abs(r.eur) for r in ab.einzelreste), Decimal(0))),
                                     betroffen=[f"{r.gruppe} ({r.waehrung}): {r.eur} EUR" for r in top],
                                     loesung="Seite „Abgleich“ ansehen; Reste aus der Einstandsmethode von IB (Prämien im Einstand) sind erklärt, andere prüfen."))
        except Exception:  # noqa: BLE001
            pass

    rang = {"fehler": 0, "warnung": 1, "hinweis": 2}
    punkte.sort(key=lambda p: (rang[p["schwere"]], p["id"]))
    status = "fehler" if any(p["schwere"] == "fehler" for p in punkte) else "warnung" if any(p["schwere"] == "warnung" for p in punkte) else "ok"
    return {"stand": str(heute), "status": status, "laeufe": laeufe, "punkte": punkte}
