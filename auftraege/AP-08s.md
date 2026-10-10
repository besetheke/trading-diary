---
titel: Positionsliste — Zeit zuerst, sortierbare und wählbare Spalten, schmalere Zeilen
modell: guenstig
status: fertig
abhaengig_von: AP-07sk, AP-08j2
aendert_tests: nein
---

# AP-08s · Positionsliste nach der Rückmeldung des Nutzers

Rückmeldung (09.10.2026): „Bei der Positionssicht bin ich gewöhnt, mit der
ersten Spalte ein Datum und eine Uhrzeit zu haben, nicht den Ticker. Die
Spalten und die Sortierung müssen möglich sein. Datum und Uhrzeit in eine
Zeile. Zeilen eher schmaler." Das ist die einzige Änderung am Aussehen vor
dem MVP; das übrige Facelift folgt in einer eigenen Sitzung.

Voraussetzung: AP-07sk (Sortierung in der API) und AP-08j2 sind eingespielt.
Wie bei AP-08j gibt es **keine Tests für die Oberfläche** (Entscheidung
22.09.2026); sie bleibt dünn: sortiert wird nur durch die API.

## Zu bauen (in `ui/src`)

1. **Erste Spalte „Eröffnung":** Datum und Uhrzeit **in einer Zeile**
   (`JJJJ-MM-TT HH:MM`, ohne Sekunden und ohne Umbruch; die volle Zeit im
   `title`). Danach Basiswert, Klasse, Seite, Ende (ebenso in einer Zeile),
   Rolls, Endzustand, OA-Strategie, Preis auf, Preis zu, Ergebnis netto,
   Währung. Die Zeichenfolge wird nur geschnitten, nicht umgerechnet.
2. **Sortierung durch Klick auf die Spaltenköpfe** von Eröffnung, Ende,
   Basiswert, Klasse, Seite, Rolls, Endzustand und OA-Strategie: erster Klick
   `desc` bei Zeit-Spalten und Rolls, `asc` bei Text-Spalten; weiterer Klick
   kehrt um. Anzeige mit ▲ und ▼ am aktiven Kopf. Die Sortierung geht als
   `sortierung` und `richtung` an `GET /ketten` und steht in der Adresse
   (`useSearchParams`, wie die Filter), damit Neuladen und Lesezeichen sie
   erhalten; ein Wechsel setzt das Blättern auf die erste Seite zurück. Die
   übrigen Spalten (Preise, Ergebnis, Währung) sind nicht sortierbar — das
   zeigt sich daran, dass der Kopf nicht anklickbar ist (Hinweis im `title`).
   Vorgabe ohne Angabe: Eröffnung absteigend.
3. **Spaltenauswahl:** Ein Knopf „Spalten" öffnet eine Liste mit einem Kästchen
   je Spalte und je einem Knopf „nach oben"/„nach unten"; Auswahl und
   Reihenfolge werden im Browser gespeichert (`localStorage`, mit Rückfall auf
   die Vorgabe, wenn der Speicher fehlt oder unlesbar ist) und gelten
   beim nächsten Besuch. „Standard wiederherstellen" setzt zurück. Mindestens
   eine Spalte bleibt sichtbar. Die Spalte mit dem Verweis auf die Detailansicht
   ist die Eröffnung, solange sie sichtbar ist; sonst die erste sichtbare.
4. **Schmalere Zeilen:** weniger Innenabstand in Tabellenzellen der
   Positionsliste (etwa 0.15 rem senkrecht), Schriftgröße 0.9 rem,
   `white-space: nowrap` bei Zeit- und Zahlenspalten, kompakte Zeilenhöhe. Die
   Detailansicht bleibt unverändert.
5. **`api.ts`:** `KettenAbfrage` um `sortierung` und `richtung` erweitern.

## Grenzen

- Keine neue Abhängigkeit, kein Test-Werkzeug, keine Änderung an `api/`,
  `tests/`, `fixtures/`, `journal/`, `engine/`.
- Nichts berechnen, nichts clientseitig sortieren oder filtern.
- Geld bleibt Zeichenkette, die Sicht (Kontosicht) bleibt angezeigt.

## Abnahme

`npm run build` fehlerfrei; `pytest` grün (insbesondere
`tests/test_ui_routen.py` und `tests/test_api_statisch.py`); `ruff check .`
sauber. Begutachtung im Browser durch den Nutzer — kein Testersatz.
