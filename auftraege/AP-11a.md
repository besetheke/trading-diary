---
titel: Roller-Ketten über orderReference mit Journal-Ketten verknüpfen (AP-11, Teil 1)
modell: stark
status: fertig
abhaengig_von: AP-14f
aendert_tests: nein
---

# AP-11a · Roller → Journal über die orderReference

Der Roller (R3) kennzeichnet jede Order mit `orderRef = R3|<Kette>|<Strategie>`, z. B.
`R3|K002|T SPX: BPS D20 W25 7DTE`. IB liefert den Wert im Flex-Export als
`orderReference`; `executions.order_reference` trägt ihn roh (AP-02).

1. `journal/roller_verknuepfung.py` — `verknuepfe_roller(verbindung, jetzt)`: aus den
   Ausführungen mit `R3|…` folgen über `legs` → `chain_links` die Journal-Ketten; je
   Roller-Kette eine Zeile in `roller_link` (`methode = "auto: orderReference"`, ein Beleg
   nach Plan §E2, keine Vermutung). Kettensicht hat Vorrang vor der Kontosicht, damit nichts
   doppelt zählt. Idempotent, schreibt nur `roller_link`, überschreibt und löscht nichts.
2. `journal rebuild` (und `abrufen --rebuild`) ruft sie am Ende auf und nennt die Zählwerte
   („Roller: n neu verknüpft, m ohne Journal-Kette“). Fällt eine Journal-Kette beim Rebuild
   weg, werden nur die daraus abgeleiteten `roller_link`-Zeilen entfernt und neu erzeugt.
3. Roller-Ketten ohne Journal-Kette (Ausführung noch nicht im Flex-Export, z. B. am selben
   Tag) werden gezählt, nie verworfen; sie verknüpfen sich beim nächsten Nachtlauf.

Noch offen (Teil 2): Absicht (IC-Seite, Gegenfinanzierung) beim Aufsetzen mitschreiben und
in der Station anzeigen; Auswertung Absicht gegen Ergebnis über `roller_link`.

Test: `tests/test_roller_verknuepfung.py`. Am Echtbestand noch ohne Wirkung — die Roller-
Orders mit `R3|…` erscheinen erst nach dem nächsten Flex-Abruf, der sie enthält.
