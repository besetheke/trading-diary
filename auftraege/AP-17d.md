---
titel: Notizen, Tags und Anhänge überleben den Rebuild (R02)
modell: stark
status: fertig
abhaengig_von: AP-17
aendert_tests: nein
---

# AP-17d · Journalbezüge bei geändertem Naturschlüssel (Review R02)

**Befund (18.10.2026, geprüft):** Der Naturschlüssel einer Struktur besteht aus den eröffnenden Ausführungen (`E1`, nach einem
nachgelieferten Teilfill `E1|E2`). Die bisherige Kette/Struktur entfiel beim Rebuild, ihre Notizen, Tags und Anhänge blieben mit der alten
Nummer zurück und waren über die Oberfläche nicht mehr erreichbar (404). Gesichert waren nur Overrides und Kampagnen.

## Regel (Zwischenstufe aus dem Review: Weiterführung statt dauerhafter Identität)

Vor dem Löschen einer Kette oder Struktur sucht der Rebuild ihre **Fortsetzung**: einen neuen Schlüssel (ohne Vorgänger), dessen
Ausführungen eine **echte Obermenge** der alten sind.

- **Genau eine Fortsetzung:** `journal_entries`, `attachments` und `entity_tags` wandern auf sie (hat sie den Tag schon, fällt der alte weg).
- **Mehrere mögliche Fortsetzungen:** nichts wird verschoben, der Fall wird als „uneindeutig“ gezählt.
- **Keine Fortsetzung:** Bezüge bleiben stehen, gezählt als „verwaist“. Nie still verloren.

Die Zählwerte stehen im `RebuildErgebnis` (`journal_bezuege_umgehaengt/_uneindeutig/_verwaist`) und in der CLI-Zeile `Rebuild …`
(nur wenn sie nicht 0 sind). Wirksam für Ketten und Strukturen, beide Sichten.

## Tests

`tests/test_rebuild_journal_bezuege.py`: End-zu-End (E1 → E1|E2 über den echten Rebuild, Notiz, Tag und Anhang erreichbar),
Zuordnung (eindeutig, uneindeutig, ohne Nachfolger, keine Obermenge, Tag schon vorhanden, Strukturen, ohne Bezüge).

## Nicht Teil dieses Pakets

Eine dauerhafte Identität der fachlichen Position (spätere Stufe); sichtbare Zuordnungsprüfung für „uneindeutig/verwaist“ in der Oberfläche
(M04); Geänderte Heuristik und Zusammenführung durch Roll-Override (nicht eigens getestet).
