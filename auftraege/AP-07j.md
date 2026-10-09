---
titel: Abnahmebasis Journal-Endpunkte der API (Notizen, Tags, Tagesjournal)
modell: stark
status: fertig
abhaengig_von: AP-07l
aendert_tests: ja
---

# AP-07j · Abnahmebasis: Journal-Endpunkte (AP-07 Rest, erster Teil)

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die Umsetzung
ist AP-07jk (günstiges Modell). Neue Testdatei `tests/test_api_journal.py`
(28 Tests); `tests/test_api_lesen.py` bleibt unverändert und muss grün bleiben.

Plan AP-07 Rest: „Write-Endpunkte für Journal, Tags …"; Tabellen
`journal_entries`, `tags`, `entity_tags` (Benutzerdaten, überleben jeden
Rebuild). Anlass: Der Nutzer möchte zuerst das tägliche Journal mit den
Basisfunktionen stabil nutzen (MVP); das Ausfüllen der Kandidatenlisten
(AP-04d, AP-05d) wird zurückgestellt.

## Entscheidungen (vom Nutzer freigegeben, 09.10.2026)

- **Bereiche.** `scope_typ` ist `chain`, `structure`, `campaign` (jeweils
  numerische ID als Text; die Kette/Struktur muss in der **Kontosicht**
  existieren, die Kampagne in `campaigns`) oder `tag` — der **Handelstag**,
  `scope_id` = ISO-Datum `JJJJ-MM-TT`. Der Handelstag braucht kein vorhandenes
  Objekt: das ist das tägliche Journal. Ketten-IDs bleiben über Rebuilds stabil,
  deshalb überleben die Einträge.
- **Schalter statt Aufweichung der Lese-API.** `erzeuge_app(db_pfad, *,
  ui_verzeichnis=None, mit_journal=False)`: Ohne `mit_journal` bleibt das
  OpenAPI-Schema ausschließlich lesend (`test_openapi_kennt_nur_lesende_
  methoden` in `tests/test_api_lesen.py` bleibt gültig). Mit `mit_journal=True`
  kommen die Journal-Routen dazu; das Modulobjekt `app` (Start der
  Anwendung) wird mit `mit_journal=True` erzeugt. Die Journal-Routen werden
  **vor** der Rückfall-Route der Oberfläche eingehängt.
- **Löschen.** `DELETE` entfernt eine Notiz auf ausdrücklichen Wunsch des
  Nutzers. Das ist eine Handlung des Nutzers an seinen eigenen Daten und
  berührt weder Roh- noch abgeleitete Tabellen (Regel 4). Tags werden nie
  gelöscht, nur Zuordnungen; ein unbenutzter Tag bleibt mit Anzahl 0.
- **Text bleibt unverändert** (Leerzeichen und Zeilenumbrüche), muss aber
  mindestens ein Zeichen außer Leerraum enthalten, sonst 422.
- **Tags** sind Namen. Beim Ersetzen werden Namen getrimmt, leere Namen sind
  422, gleiche Namen (ohne Beachtung der Schreibweise) zählen einmal, ein
  bereits vorhandener Tag gilt mit **seiner** Schreibweise. Ausgabe
  alphabetisch ohne Beachtung der Schreibweise.

## Endpunkte (verbindlich)

| Methode und Pfad | Wirkung |
|---|---|
| `GET /journal/{scope_typ}/{scope_id}` | `JournalAntwort`: `scope_typ`, `scope_id`, `notizen` (neueste zuerst, bei Gleichstand größere `id` zuerst), `tags` |
| `POST /journal/{scope_typ}/{scope_id}/notizen` | Body `{"text": …}`, 201, `NotizAntwort` (`id`, `scope_typ`, `scope_id`, `text`, `erstellt_am`, `geaendert_am` = null) |
| `PUT /journal/notizen/{notiz_id}` | Body `{"text": …}`, setzt `text` und `geaendert_am`, `erstellt_am` bleibt; 404 bei unbekannter Notiz |
| `DELETE /journal/notizen/{notiz_id}` | 204, 404 bei unbekannter Notiz |
| `PUT /journal/{scope_typ}/{scope_id}/tags` | Body `{"tags": [...]}` ersetzt die Zuordnung, Antwort `JournalAntwort` |
| `GET /tags` | Liste `{"name", "anzahl"}` aller Tags, alphabetisch; `anzahl` = Zuordnungen |

Fehler: unbekannter `scope_typ`, nicht numerische ID, ungültiges Datum, leerer
Text/Tagname, fehlender Body → 422; Kette/Struktur/Kampagne nicht vorhanden →
404. Bei jedem Fehler wird nichts geschrieben. Zeitstempel kommen vom Server
(`datetime.now()` ist hier erlaubt, die API ist nicht Teil von `engine/`).

## Grenzen

Kein Schreibzugriff auf andere Tabellen als `journal_entries`, `tags`,
`entity_tags`; kein Anhang (`attachments`), keine Overrides, keine
Kampagnen-Klassifikation (folgen mit AP-07 Rest). Keine Authentifizierung
(lokales Einbenutzer-Tool, E4).

## Abnahme

`tests/test_api_journal.py` und alle bisherigen API-Tests grün, `ruff check .`
sauber. Gegen eine Wegwerf-Umsetzung geprüft: 61 von 61 grün (33 bestehende,
28 neue); ohne Umsetzung 27 Fehler (`mit_journal` unbekannt), der Test der
rein lesenden Standard-API bleibt grün.
