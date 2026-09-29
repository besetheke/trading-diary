---
titel: Menge fehlte im Fingerabdruck des OA-Abgleichs (AP-13v/AP-13k)
modell: stark
status: fertig
abhaengig_von: AP-13v
aendert_tests: ja
---

# AP-13vk · Menge in der Fingerabdruck-Absicherung ergänzt

Korrekturpaket nach CLAUDE.md, Regel 1a. Es läuft unter `locker`, weil es
`tests/test_oa_abgleich.py` erweitert.

## Der Befund

Plan §6.1 definiert die Fingerabdruck-Absicherung als „Entry Time
sekundengenau plus die vollständige Leg-Spezifikation aus `Strikes`
(**Richtung, Menge**, Typ, Strike, Expiry je Leg)". `auftraege/AP-13v.md`
— von mir selbst geschrieben — hat beim Zuschnitt die Menge vergessen:
`OALegSignatur` hatte nur `right`/`strike`/`expiry`/`richtung`. Ohne Menge
hätte ein Ratio-Spread (z. B. 1×2) mit falscher Stückzahl je Leg
fälschlich als Fingerabdruck-Treffer gegolten — der Vertrag war
unvollständig, nicht die Umsetzung; `engine/oa_abgleich.py` (AP-13k) war
vertragstreu zum lückenhaften Vertrag.

Gefunden bei der Vorbereitung der Persistenz-Anbindung, vor deren Zuschnitt
— `oa_erkennung` (auto/heuristik) sollte nicht auf einer unvollständigen
Prüfung dauerhaft in die Datenbank geschrieben werden.

## Die Korrektur

- `engine/oa_abgleich.py`: `OALegSignatur` bekommt das Feld `menge:
  Decimal`; `_LegSignatur`, `_eigene_legs()` und der Referenzvergleich in
  `oa_abgleich()` nehmen die Menge in die Signatur auf. Modul-Docstring
  entsprechend präzisiert.
- `tests/test_oa_abgleich.py`: `_oa_leg()` bekommt den Parameter `menge`
  (Default `"1"`, passend zu den bestehenden Fixtures — kein bestehender
  Aufruf musste geändert werden, nur die Signatur erweitert). Neuer Test
  `test_abweichende_menge_bleibt_zugeordnet_aber_heuristik` — Menge 2 im
  Export gegen 1 in der Kette bei sonst identischer Spezifikation ergibt
  `fingerabdruck_treffer=False`, `erkennung="heuristik"`.

Die Prüflogik ändert sich in ihrer Absicht nicht: Der Fingerabdruck ist
weiterhin reine Absicherung, verwirft nie eine Zuordnung, nur die Menge
der geprüften Merkmale wächst um genau das im Plan bereits geforderte
Feld.

## Abnahme

- `tests/test_oa_abgleich.py`: 7 von 7 grün (vorher 6).
- Gesamte Suite grün, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `engine/oa_abgleich.py` und
  `tests/test_oa_abgleich.py`.
