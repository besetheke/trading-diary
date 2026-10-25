# ruff: noqa: E501
"""Journal-Suche, Tag-Filter und Anhänge (AP-17g, Review M05).

Suche über Notiztexte und Tag-Namen mit Position (Kette, Struktur, Kampagne) als Trefferkontext; Filter nach Tags
(„alle dieser Tags“ oder „irgendeines“), Bereichsart und Anhängen; ohne Suchbegriff und Filter die zentrale Liste aller
markierten oder kommentierten Situationen. Anhänge: kontrollierte Ablage neben der Datenbank (``anhaenge/``), feste Typen und
Größen, **kein Löschen** (CLAUDE.md Regel 4: keine Löschung von Benutzerdaten). Die Bezüge laufen über die Bereichs-IDs der
Journal-Tabellen und überleben den Rebuild (AP-17d).
"""
import pathlib
import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, insert, select

from journal.schema import (
    attachments,
    campaigns,
    chains,
    entity_tags,
    journal_entries,
    structures,
    tags,
)

MAX_BYTES = 5 * 1024 * 1024
MAX_ANHAENGE_JE_BEREICH = 20
# Erlaubte Typen und die Dateiendung, unter der sie abgelegt werden (nichts Ausführbares).
ERLAUBTE_TYPEN = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp",
    "application/pdf": ".pdf", "text/plain": ".txt",
}
SNIPPET = 160


def _snippet(text: str, q: str) -> str:
    if not q:
        return text[:SNIPPET] + ("…" if len(text) > SNIPPET else "")
    i = text.lower().find(q)
    von = max(0, i - 50) if i >= 0 else 0
    return ("…" if von else "") + text[von:von + SNIPPET] + ("…" if von + SNIPPET < len(text) else "")


def _kontext(verbindung, bereiche: set[tuple[str, str]]) -> dict:
    """Beschriftung je Bereich: Basiswert, Art, Zeitraum — soweit die Position im Journal noch gefunden wird."""
    aus: dict[tuple[str, str], dict] = {}
    ketten_ids = [int(i) for t, i in bereiche if t == "chain" and i.isdigit()]
    if ketten_ids:
        for z in verbindung.execute(select(chains.c.chain_id, chains.c.underlying, chains.c.seite, chains.c.eroeffnet_am,
                                           chains.c.beendet_am, chains.c.oa_strategie, chains.c.sicht)
                                    .where(chains.c.chain_id.in_(ketten_ids))).mappings():
            aus[("chain", str(z["chain_id"]))] = {
                "text": f"Kette {z['chain_id']}: {z['underlying']} {z['seite'] or ''}".strip(),
                "von": str(z["eroeffnet_am"])[:10], "bis": None if z["beendet_am"] is None else str(z["beendet_am"])[:10],
                "strategie": z["oa_strategie"], "link": f"/positionen/{z['chain_id']}"}
    struktur_ids = [int(i) for t, i in bereiche if t == "structure" and i.isdigit()]
    if struktur_ids:
        for z in verbindung.execute(select(structures.c.structure_id, structures.c.underlying, structures.c.typ,
                                           structures.c.eroeffnet_am).where(structures.c.structure_id.in_(struktur_ids))).mappings():
            aus[("structure", str(z["structure_id"]))] = {
                "text": f"Struktur {z['structure_id']}: {z['underlying']} {z['typ']}", "von": str(z["eroeffnet_am"])[:10],
                "bis": None, "strategie": None, "link": None}
    kampagnen_ids = [int(i) for t, i in bereiche if t == "campaign" and i.isdigit()]
    if kampagnen_ids:
        for z in verbindung.execute(select(campaigns.c.campaign_id, campaigns.c.underlying, campaigns.c.eroeffnet_am)
                                    .where(campaigns.c.campaign_id.in_(kampagnen_ids))).mappings():
            aus[("campaign", str(z["campaign_id"]))] = {
                "text": f"Kampagne {z['campaign_id']}: {z['underlying']}", "von": str(z["eroeffnet_am"])[:10],
                "bis": None, "strategie": None, "link": "/kampagnenliste"}
    return aus


def suche(verbindung, *, q: str | None = None, tags_filter: list[str] | None = None, modus: str = "alle",
          scope_typ: str | None = None, nur_mit_anhang: bool = False, limit: int = 200) -> list[dict]:
    """Trefferliste, neueste Aktivität zuerst. ``modus`` ``alle``: der Bereich trägt alle gesuchten Tags, ``irgendeines``: mindestens einen."""
    if modus not in ("alle", "irgendeines"):
        raise ValueError("modus muss 'alle' oder 'irgendeines' sein")
    q_norm = (q or "").strip().lower()
    gesucht = {t.strip().lower() for t in (tags_filter or []) if t.strip()}

    bereiche: dict[tuple[str, str], dict] = {}

    def bereich(typ: str, bid: str) -> dict:
        return bereiche.setdefault((typ, bid), {"notizen": [], "tags": [], "anhaenge": 0, "aktiv": ""})

    for z in verbindung.execute(select(journal_entries).order_by(journal_entries.c.erstellt_am.desc())).mappings():
        b = bereich(z["scope_typ"], z["scope_id"])
        b["notizen"].append({"id": z["id"], "text": z["text"], "erstellt_am": str(z["erstellt_am"])})
        b["aktiv"] = max(b["aktiv"], str(z["geaendert_am"] or z["erstellt_am"]))
    for z in verbindung.execute(select(entity_tags.c.scope_typ, entity_tags.c.scope_id, tags.c.name)
                                .join(tags, tags.c.id == entity_tags.c.tag_id)).all():
        bereich(z[0], z[1])["tags"].append(z[2])
    for z in verbindung.execute(select(attachments.c.scope_typ, attachments.c.scope_id, func.count(), func.max(attachments.c.erstellt_am))
                                .group_by(attachments.c.scope_typ, attachments.c.scope_id)).all():
        b = bereich(z[0], z[1])
        b["anhaenge"] = z[2]
        b["aktiv"] = max(b["aktiv"], str(z[3]))

    treffer = []
    for (typ, bid), b in bereiche.items():
        if scope_typ and typ != scope_typ:
            continue
        namen = {t.lower() for t in b["tags"]}
        if gesucht and not (gesucht <= namen if modus == "alle" else bool(gesucht & namen)):
            continue
        if nur_mit_anhang and not b["anhaenge"]:
            continue
        passende = [n for n in b["notizen"] if q_norm in n["text"].lower()] if q_norm else b["notizen"]
        if q_norm and not passende and not any(q_norm in t for t in namen):
            continue
        treffer.append({
            "scope_typ": typ, "scope_id": bid, "tags": sorted(b["tags"], key=str.lower), "anzahl_notizen": len(b["notizen"]),
            "anzahl_anhaenge": b["anhaenge"], "aktiv": b["aktiv"],
            "notizen": [{"id": n["id"], "snippet": _snippet(n["text"], q_norm), "erstellt_am": n["erstellt_am"]} for n in passende[:3]],
        })
    treffer.sort(key=lambda t: (t["aktiv"], t["scope_typ"], t["scope_id"]), reverse=True)
    treffer = treffer[:limit]
    kontexte = _kontext(verbindung, {(t["scope_typ"], t["scope_id"]) for t in treffer})
    for t in treffer:
        t["kontext"] = kontexte.get((t["scope_typ"], t["scope_id"]))
    return treffer


# ------------------------------------------------------------------------------------------------ Anhänge
def _sicherer_name(name: str, endung: str) -> str:
    stamm = re.sub(r"[^A-Za-z0-9._-]+", "_", pathlib.PurePath(name or "anhang").stem)[:60].strip("._") or "anhang"
    return stamm + endung


def anhang_speichern(verbindung, ordner: pathlib.Path, scope_typ: str, scope_id: str, name: str, mime: str, daten: bytes) -> dict:
    """Legt einen Anhang ab. Wirft ``ValueError`` mit der Begründung (Typ, Größe, Anzahl); Löschen gibt es nicht."""
    mime = (mime or "").split(";")[0].strip().lower()
    if mime not in ERLAUBTE_TYPEN:
        raise ValueError(f"Dateityp {mime or 'unbekannt'} nicht erlaubt (erlaubt: {', '.join(sorted(ERLAUBTE_TYPEN))})")
    if not daten:
        raise ValueError("Datei ist leer")
    if len(daten) > MAX_BYTES:
        raise ValueError(f"Datei größer als {MAX_BYTES // (1024 * 1024)} MB")
    vorhanden = verbindung.execute(select(func.count()).select_from(attachments).where(
        attachments.c.scope_typ == scope_typ, attachments.c.scope_id == scope_id)).scalar_one()
    if vorhanden >= MAX_ANHAENGE_JE_BEREICH:
        raise ValueError(f"höchstens {MAX_ANHAENGE_JE_BEREICH} Anhänge je Bereich")
    jetzt = datetime.now()
    anhang_id = verbindung.execute(insert(attachments).values(
        scope_typ=scope_typ, scope_id=scope_id, dateipfad="", mime=mime, erstellt_am=jetzt)).inserted_primary_key[0]
    relativ = pathlib.PurePosixPath("anhaenge") / f"{anhang_id}_{_sicherer_name(name, ERLAUBTE_TYPEN[mime])}"
    ziel = ordner / pathlib.Path(*relativ.parts)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(daten)
    verbindung.execute(attachments.update().where(attachments.c.id == anhang_id).values(dateipfad=str(relativ)))
    return {"id": anhang_id, "name": relativ.name.split("_", 1)[1], "mime": mime, "groesse": len(daten), "erstellt_am": str(jetzt)}


def anhaenge_liste(verbindung, ordner: pathlib.Path, scope_typ: str, scope_id: str) -> list[dict]:
    zeilen = verbindung.execute(select(attachments).where(attachments.c.scope_typ == scope_typ, attachments.c.scope_id == scope_id)
                                .order_by(attachments.c.erstellt_am.desc(), attachments.c.id.desc())).mappings().all()
    aus = []
    for z in zeilen:
        datei = _aufloesen(ordner, z["dateipfad"])
        aus.append({"id": z["id"], "name": pathlib.PurePath(z["dateipfad"]).name.split("_", 1)[-1], "mime": z["mime"],
                    "groesse": datei.stat().st_size if datei is not None and datei.is_file() else None,
                    "erstellt_am": str(z["erstellt_am"])})
    return aus


def _aufloesen(ordner: pathlib.Path, relativ: str) -> pathlib.Path | None:
    """Datei zum gespeicherten Pfad — nur innerhalb des Anhang-Ordners (kein Ausbrechen über ``..``)."""
    if not relativ:
        return None
    basis = (ordner / "anhaenge").resolve()
    datei = (ordner / relativ).resolve()
    return datei if basis in datei.parents else None


def anhang_datei(verbindung, ordner: pathlib.Path, anhang_id: int) -> tuple[pathlib.Path, str] | None:
    z = verbindung.execute(select(attachments).where(attachments.c.id == anhang_id)).mappings().first()
    if z is None:
        return None
    datei = _aufloesen(ordner, z["dateipfad"])
    if datei is None or not datei.is_file() or z["mime"] not in ERLAUBTE_TYPEN:
        return None
    return datei, z["mime"]


def registriere(applikation, engine, anhang_ordner: pathlib.Path, pruefe_station_aufruf, journal_bereich_pruefen) -> None:
    """Hängt die Wege für Suche und Anhänge an die Anwendung (nur mit Journal; die Prüffunktionen kommen von ``api.app``)."""
    @applikation.get("/journal-suche")
    def journal_suchen(
        q: str | None = None,
        tags: Annotated[list[str] | None, Query()] = None,
        modus: Literal["alle", "irgendeines"] = "alle",
        scope_typ: str | None = None,
        mit_anhang: bool = False,
    ) -> list[dict]:
        """Suche über Notiztexte und Tags (M05): Treffer mit Position als Kontext; ``tags`` je Tag ein Parameter,
        ``modus`` alle/irgendeines; ohne Suchbegriff und Filter die zentrale Liste aller markierten Situationen."""
        with engine.connect() as verbindung:
            return suche(verbindung, q=q, tags_filter=tags, modus=modus, scope_typ=scope_typ,
                                       nur_mit_anhang=mit_anhang)

    @applikation.get("/journal/{scope_typ}/{scope_id}/anhaenge")
    def anhaenge_lesen(scope_typ: str, scope_id: str) -> list[dict]:
        """Anhänge eines Bereichs (Name, Typ, Größe), neueste zuerst."""
        with engine.connect() as verbindung:
            journal_bereich_pruefen(verbindung, scope_typ, scope_id)
            return anhaenge_liste(verbindung, anhang_ordner, scope_typ, scope_id)

    @applikation.post("/journal/{scope_typ}/{scope_id}/anhaenge", status_code=201)
    async def anhang_anlegen(scope_typ: str, scope_id: str, request: Request, name: str = "anhang") -> dict:
        """Neuer Anhang: der Dateiinhalt ist der Körper der Anfrage, der Typ der Kopf ``Content-Type`` (png, jpeg, gif,
        webp, pdf, txt; höchstens 5 MB, 20 je Bereich). Nur aus der Station; Löschen gibt es nicht."""
        pruefe_station_aufruf(request)
        laenge = request.headers.get("content-length", "")
        if laenge.isdigit() and int(laenge) > MAX_BYTES:
            raise HTTPException(status_code=413, detail="Datei zu groß (höchstens 5 MB)")
        daten = bytearray()
        async for stueck in request.stream():
            daten += stueck
            if len(daten) > MAX_BYTES:
                raise HTTPException(status_code=413, detail="Datei zu groß (höchstens 5 MB)")
        with engine.begin() as verbindung:
            journal_bereich_pruefen(verbindung, scope_typ, scope_id)
            try:
                return anhang_speichern(
                    verbindung, anhang_ordner, scope_typ, scope_id, name,
                    request.headers.get("content-type", ""), bytes(daten))
            except ValueError as fehler:
                raise HTTPException(status_code=422, detail=str(fehler)) from fehler

    @applikation.get("/anhang/{anhang_id}")
    def anhang_holen(anhang_id: int) -> FileResponse:
        """Die Datei eines Anhangs, nur innerhalb des Anhang-Ordners; nie als ausführbarer Inhalt."""
        with engine.connect() as verbindung:
            gefunden = anhang_datei(verbindung, anhang_ordner, anhang_id)
        if gefunden is None:
            raise HTTPException(status_code=404, detail="Anhang nicht gefunden")
        datei, mime = gefunden
        return FileResponse(datei, media_type=mime, headers={"X-Content-Type-Options": "nosniff",
                                                             "Content-Disposition": "inline"})


