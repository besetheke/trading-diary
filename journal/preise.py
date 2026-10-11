"""Die Nettoprämie je Kontrakt — eine Rechnung statt dreier (AP-07p).

Vor diesem Paket rechneten ``journal/durchsicht.py`` und
``werkzeuge/abgleich/golden_ketten_stichprobe.py`` dieselbe Größe, jede für
sich; die Lese-API wäre die dritte Kopie geworden. Hier steht sie einmal:
``journal/rebuild.py`` schreibt mit ihr ``structures.eroeffnungspreis`` und
``structures.schlusspreis``, ``journal/durchsicht.py`` ruft sie für seine
Kandidatendatei auf. Das Abgleichswerkzeug unter ``werkzeuge/abgleich/``
zieht das starke Modell nach (AP-07pv, P5).

Verbindlich ist der Vertrag P1–P8 aus ``auftraege/AP-07pv.md``; die Nummern
in den Kommentaren folgen ihm.
"""

from decimal import ROUND_HALF_UP, Decimal

# Vertrag P3: ausdrücklich acht Nachkommastellen. Die Ausführungspreise des
# echten Bestands tragen bis zu acht Stellen; nur die Division durch die
# Strukturmenge kann einen Rest lassen — und das auch nur bei ungleichen
# Beinmengen. Ohne festgelegte Tiefe schnitte ``Decimal`` still bei 28
# signifikanten Stellen ab, eine Rundung ohne Namen (Regel 5).
ACHT_STELLEN = Decimal("0.00000001")


def nettopraemie(struktur, *, schliessung: bool, bestand, leg_je_schluessel) -> Decimal:
    """Nettoprämie je Kontrakt (Vertrag P1): je Leg Menge der **Leg** × Preis
    der zugehörigen Ausführung, Verkauf positiv, Kauf negativ; die Summe über
    alle Legs geteilt durch die Menge der Struktur. ``schliessung=True``
    nimmt die schließenden Ausführungen („Preis zu“), sonst die eröffnenden
    („Preis auf“).

    Die Menge der Leg, nicht die der Ausführung — eine Ausführung kann
    mehrere Legs bedienen, ihre Menge zählte doppelt (AP-04pk).
    """
    summe = Decimal(0)
    for schluessel in struktur.leg_schluessel:
        leg = leg_je_schluessel[(schluessel.open_exec_id, schluessel.close_exec_id)]
        exec_id = schluessel.close_exec_id if schliessung else schluessel.open_exec_id
        if exec_id is None:
            raise ValueError(
                f"Struktur {_schluessel(struktur)} hat ein Leg ohne "
                f"{'Schließung' if schliessung else 'Eröffnung'} — keine "
                "Nettoprämie berechenbar (Vertrag P1)"
            )
        ausfuehrung = bestand.exec_je_id[exec_id]
        vorzeichen = 1 if ausfuehrung["side"] == "SELL" else -1
        # AP-03vz2: ``leg.menge`` steht nach einer Kapitalmaßnahme in neuen
        # Stücken, der Ausführungspreis noch in alten — Preis ÷ Faktor.
        faktor = leg.close_faktor if schliessung else leg.open_faktor
        preis = ausfuehrung["preis"] if faktor == 1 else ausfuehrung["preis"] / faktor
        summe += vorzeichen * leg.menge * preis
    if not struktur.menge:
        raise ValueError(
            f"Struktur {_schluessel(struktur)} hat Menge 0 — die "
            "Nettoprämie je Kontrakt wäre nicht teilbar (Vertrag P1)"
        )
    return (summe / struktur.menge).quantize(ACHT_STELLEN, rounding=ROUND_HALF_UP)


def praemie_als_text(wert: Decimal | None) -> str | None:
    """Prämie als Zeichenkette nach Vertrag P3: höchstens acht
    Nachkommastellen, überzählige Nullen entfallen, aber **mindestens zwei**
    bleiben stehen. Aus 40 wird ``"40.00"``, aus −20 ``"-20.00"``, aus 26/3
    ``"8.66666667"``.

    Leer bleibt leer — nie ``"0"``, nie ``None`` als Zahl (AP-07lv,
    Vertrag 13). Ein negatives Null wird zu ``"0.00"``.
    """
    if wert is None:
        return None
    if wert == 0:
        wert = wert.copy_abs()  # aus −0 wird 0 — kein „−0.00“
    ganze, _, nachkomma = format(wert, "f").partition(".")
    nachkomma = nachkomma.rstrip("0")
    if len(nachkomma) < 2:
        nachkomma = nachkomma.ljust(2, "0")
    return f"{ganze}.{nachkomma}"


def _schluessel(struktur) -> str:
    """Naturschlüssel der Struktur wie ``journal.rebuild._struktur_schluessel``
    (AP-04v, Vertrag 7) — hier lokal wiederholt, weil ``journal.rebuild``
    seinerseits dieses Modul braucht und ein Import beide im Kreis schließen
    würde."""
    return "|".join(sorted(schluessel.open_exec_id for schluessel in struktur.leg_schluessel))
