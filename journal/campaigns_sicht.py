"""Sichtbarkeit offener Campaign-Kandidaten (AP-05sk, Plan §6 / AP-05).

Zählt, wie viele Kandidaten aus ``engine.campaigns.campaign_kandidaten()``
noch keine gemeinsame Kampagnen-Klassifikation haben — reine Anzeige, kein
Schreiben: Unklassifizierte Kandidaten bleiben sichtbar; sie werden nicht
still als ``independent`` einsortiert (AP-05, Abnahme).

Ein Kandidat gilt als entschieden, wenn beide Ketten bereits derselben
``campaign_id`` zugeordnet sind (``campaign_links``) — unabhängig vom
``beziehungstyp``. Wie diese Zeilen in die Tabelle gekommen sind, ist hier
gleichgültig (OF-54 ist offen); gelesen wird nur, was bereits steht.
"""

from collections.abc import Iterable, Mapping

from engine.campaigns import CampaignKandidat


def offene_kandidaten_zaehlen(
    kandidaten: Iterable[CampaignKandidat],
    kampagnen_je_chain_id: Mapping[int, set[int]],
    chain_id_je_objekt: Mapping[int, int],
) -> int:
    """Anzahl der Kandidaten ohne gemeinsame Kampagne (Vertrag
    ``auftraege/AP-05s.md``) — reine Funktion (Regel 6), kein DB-Zugriff.

    Die Ketten eines Kandidaten werden über Python-Objektidentität
    aufgelöst (wie ``journal.oa_persistenz``): ``kandidat.kette_a``/
    ``kandidat.kette_b`` sind dieselben Objekte, die auch in
    ``kette_je_schluessel`` stehen, keine Kopien. Fehlt eine Kette in
    ``chain_id_je_objekt`` (sollte nicht vorkommen), zählt sie als „keine
    Kampagne" — offen, nicht Abbruch.
    """
    offen = 0
    for kandidat in kandidaten:
        kampagnen = [
            kampagnen_je_chain_id.get(chain_id_je_objekt.get(id(kette)), set())
            for kette in (kandidat.kette_a, kandidat.kette_b)
        ]
        # Nicht leerer Schnitt heißt entschieden (gemeinsame Kampagne).
        if not kampagnen[0] & kampagnen[1]:
            offen += 1
    return offen
