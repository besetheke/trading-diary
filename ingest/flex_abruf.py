"""Abruf eines Flex-Statements über den Flex Web Service (AP-02a2k).

Umsetzung des Vertrags aus ``auftraege/AP-02a2.md`` (Abnahmebasis:
``tests/test_flex_abruf.py``). Das Protokoll (Version 3) hat zwei Schritte:

1. ``GET <basis>/SendRequest?t=<Token>&q=<Query-ID>&v=3`` liefert
   ``<FlexStatementResponse>`` mit ``Status``, ``ReferenceCode`` und ``Url``.
2. ``GET <Url>?t=<Token>&q=<ReferenceCode>&v=3`` liefert das Statement
   (``<FlexQueryResponse>``) — oder, solange es erzeugt wird, ``ErrorCode``
   1019; dann wartet der Abruf und holt erneut.

Grundsätze:

- **Der Token ist ein Geheimnis.** Er steht nur in den URLs der Anfragen —
  nie in einer Fehlermeldung, Ausgabe oder Datei. Transportfehler werden zu
  ``AbrufFehler`` mit nur dem Typnamen der Ausnahme; der Körper einer
  unerwarteten Antwort wird nie ausgegeben (er kann Kontodaten enthalten).
- **Kein Netzzugriff in den Tests.** ``abrufen`` nimmt Transport und
  Wartefunktion entgegen; die Vorgaben sind ``standard_transport`` (hier im
  Modul, bei jedem Aufruf nachgeschlagen) und ``time.sleep``.
- **Das Statement bleibt draußen.** ``statement_speichern`` legt es nur
  außerhalb des Projektverzeichnisses ab (Ausnahme ``fixtures/golden/``),
  über eine Zwischendatei und ``os.replace`` — es bleibt nie ein Rest.

Nur Standardbibliothek (``urllib.request``, ``xml.etree.ElementTree``,
``hashlib``). Die Antworten stammen von IBKR, nicht von Dritten; die
Dateigröße bleibt klein (Entscheidung im Vertrag).
"""

import hashlib
import os
import pathlib
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime

# Standard-Endpunkt des Flex Web Service (Vertrag).
BASIS_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"

# Wurzel des Repositories — Statements mit Kontodaten gehören nicht darunter.
PROJEKTWURZEL = pathlib.Path(__file__).resolve().parents[1]

# Zeitgrenze je Anfrage (Vertrag: 60 s) und fester User-Agent statt der
# Python-Vorgabe.
ABRUF_ZEITGRENZE_S = 60
USER_AGENT = "trading-journal/0.1 (Flex Web Service v3)"

# Eingaben werden geprüft, bevor etwas gesendet wird (Vertrag) — so kann kein
# Wert die URL selbst verändern.
TOKEN_MUSTER = re.compile(r"[A-Za-z0-9]+")
QUERY_MUSTER = re.compile(r"[0-9]+")

# ``ErrorCode`` 1019: Statement wird noch erzeugt — warten und neu holen.
IN_ARBEIT_CODE = "1019"


class AbrufFehler(Exception):
    """Fehler beim Abruf — ohne Token, ohne Antwortkörper."""


def standard_transport(url: str) -> bytes:
    """GET mit Zeitgrenze und festem User-Agent (nur Standardbibliothek)."""
    anfrage = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(anfrage, timeout=ABRUF_ZEITGRENZE_S) as antwort:
        return antwort.read()


def ziel_pruefen(ziel: pathlib.Path | str) -> None:
    """Lehnt Ziele im Projektverzeichnis ab — vor jedem Anlegen (Vertrag).

    Statements enthalten Kontodaten. Nur ``fixtures/golden/`` bleibt erlaubt:
    Dort liegen die vergoldeten Abnahmedaten, schreibgeschützt.
    """
    aufgeloest = pathlib.Path(ziel).resolve()
    try:
        relativ = aufgeloest.relative_to(PROJEKTWURZEL)
    except ValueError:
        return  # außerhalb des Projekts: erlaubt
    if list(relativ.parts[:2]) == ["fixtures", "golden"]:
        return
    raise ValueError(
        f"Ziel {aufgeloest} liegt im Projektverzeichnis — Statements "
        "gehören außerhalb des Repositories"
    )


def statement_speichern(
    xml: bytes, ziel: pathlib.Path | str, *, jetzt: datetime | None = None
) -> pathlib.Path:
    """Speichert das Statement und liefert den Pfad (Vertrag).

    Name: ``flex_<JJJJMMTT>_<erste 8 Zeichen SHA-256>.xml``. Gibt es im Ziel
    schon eine Datei mit demselben Inhalt (gleiche Kurzprüfsumme im Namen),
    wird sie zurückgegeben und nichts geschrieben. Geschrieben wird über
    eine Zwischendatei und ``os.replace`` — ein Abbruch hinterlässt keinen
    Rest und nie ein halbes Statement.
    """
    ziel_pfad = pathlib.Path(ziel)
    ziel_pruefen(ziel_pfad)
    kurz = hashlib.sha256(xml).hexdigest()[:8]
    zeit = jetzt if jetzt is not None else datetime.now()
    ziel_pfad.mkdir(parents=True, exist_ok=True)
    endung = f"_{kurz}.xml"
    for vorhandene in ziel_pfad.glob(f"flex_*{endung}"):
        return vorhandene
    name = f"flex_{zeit:%Y%m%d}_{kurz}.xml"
    zwischen = ziel_pfad / (name + ".teil")
    zwischen.write_bytes(xml)
    os.replace(zwischen, ziel_pfad / name)
    return ziel_pfad / name


def _text(wurzel: ET.Element, name: str) -> str:
    """Text eines Kindelements — leer, wenn es fehlt."""
    kind = wurzel.find(name)
    return "" if kind is None or kind.text is None else kind.text.strip()


def _als_baum(antwort: bytes, schritt: str) -> ET.Element:
    """Parst die Antwort; kein XML wird zu „unbekannte Antwort“ — ohne Körper."""
    try:
        return ET.fromstring(antwort)
    except ET.ParseError as fehler:
        raise AbrufFehler(f"unbekannte Antwort beim {schritt} (kein XML)") from fehler


def _anfordern(transport: Callable[[str], bytes], url: str) -> bytes:
    """Ein Anfrageversuch; Ausnahmen werden zu AbrufFehler — nur der Typname.

    Die Meldung der ursprünglichen Ausnahme kann den Token (Bestandteil der
    URL) oder die Antwort enthalten und wird bewusst weggeworfen.
    """
    try:
        return transport(url)
    except Exception as ausnahme:
        raise AbrufFehler(f"Transportfehler: {type(ausnahme).__name__}") from ausnahme


def _fehlermeldung(wurzel: ET.Element) -> AbrufFehler:
    """Fehler der Gegenstelle mit Code und Text — endgültig, ohne Wiederholung."""
    code = _text(wurzel, "ErrorCode") or _text(wurzel, "Status")
    return AbrufFehler(f"Gegenstelle meldet Fehler {code}: {_text(wurzel, 'ErrorMessage')}")


def abrufen(
    token: str,
    query_id: str,
    *,
    transport: Callable[[str], bytes] | None = None,
    warten: Callable[[float], None] = time.sleep,
    wartezeit_s: float = 10.0,
    max_versuche: int = 12,
    basis_url: str | None = None,
) -> bytes:
    """Holt das Statement als Bytes (Protokoll Version 3, Vertrag AP-02a2).

    Eingaben werden geprüft, bevor etwas gesendet wird. ``ErrorCode`` 1019
    wartet und holt erneut — höchstens ``max_versuche`` Abrufe, danach
    „nicht rechtzeitig“. Jeder andere Fehler der Gegenstelle ist endgültig.
    """
    if not TOKEN_MUSTER.fullmatch(token or ""):
        raise AbrufFehler("Ungültiger Token: nur Buchstaben und Ziffern (FLEX_TOKEN)")
    if not QUERY_MUSTER.fullmatch(query_id or ""):
        raise AbrufFehler("Ungültige Query-ID: nur Ziffern (--query-id, FLEX_QUERY_ID)")
    if transport is None:
        transport = standard_transport
    basis = (basis_url if basis_url is not None else BASIS_URL).rstrip("/")

    send_url = f"{basis}/SendRequest?t={token}&q={query_id}&v=3"
    senden = _als_baum(_anfordern(transport, send_url), "Senden")
    if senden.tag != "FlexStatementResponse":
        raise AbrufFehler(f"unbekannte Antwort beim Senden (Wurzelelement {senden.tag})")
    if _text(senden, "Status") != "Success":
        raise _fehlermeldung(senden)
    reference = _text(senden, "ReferenceCode")
    if not reference:
        raise AbrufFehler("unbekannte Antwort beim Senden (kein ReferenceCode)")
    hole_url = _text(senden, "Url") or f"{basis}/GetStatement"
    hole_url = f"{hole_url}?t={token}&q={reference}&v=3"

    for versuch in range(1, max_versuche + 1):
        antwort = _anfordern(transport, hole_url)
        baum = _als_baum(antwort, "Holen")
        if baum.tag == "FlexQueryResponse":
            return antwort  # das Statement selbst, unverändert
        if baum.tag != "FlexStatementResponse":
            raise AbrufFehler(f"unbekannte Antwort beim Holen (Wurzelelement {baum.tag})")
        if _text(baum, "ErrorCode") == IN_ARBEIT_CODE:
            if versuch < max_versuche:
                warten(wartezeit_s)
                continue
            raise AbrufFehler(
                f"Statement wurde nicht rechtzeitig erzeugt: {max_versuche} Abrufe, "
                f"Wartezeit {wartezeit_s} s"
            )
        raise _fehlermeldung(baum)
    raise AbrufFehler("unbekannte Antwort beim Holen")  # unreachable
