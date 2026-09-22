---
titel: Abnahmebasis fuer die Positionsliste (AP-08l)
modell: stark
status: fertig
abhaengig_von: AP-07l
aendert_tests: ja
---

# AP-08lv · Abnahmebasis für die Positionsliste

Vorbereitungspaket nach Plan §11.2, Schritt 1. **Es implementiert nichts.**
Die Umsetzung ist AP-08l (günstiges Modell).

Fachliche Grundlage: Plan §6, AP-08 in der zweigeteilten Fassung — die
Positionsliste und die Detailansicht werden vor AP-06 gezogen.

## Die Entscheidung, die dieses Paket prägt

**Die erste Fassung kommt ohne Frontend-Testwerkzeug** (Nutzer,
22.09.2026). Vitest gegen Playwright wird später verglichen, wenn die
Oberfläche eigene Logik trägt, die zu prüfen sich lohnt. Heute wäre sie vor
allem Gerüst, und ein zweites Testökosystem kostet mehr, als es hier sichert.

**Daraus folgt ein ungewöhnlicher Zuschnitt, und er wird hier offen
benannt:**

- Maschinell geprüft wird **die Naht** zwischen API und gebautem Frontend.
  Sie liegt in Python (`tests/test_api_statisch.py`) und ist die Stelle, an
  der ein Fehler still bliebe: Eine Oberfläche, die eine API-Route
  verschluckt, fällt beim Durchklicken nicht auf — aber später in jeder
  zweiten Anfrage.
- Die Oberfläche selbst wird **im Browser begutachtet**, durch das starke
  Modell vor der Übergabe und danach durch den Nutzer. Das ist kein
  Testersatz, und es wird auch nicht als solcher ausgegeben.
- **Deshalb bleibt die Oberfläche dünn.** Je weniger eigene Logik sie
  trägt, desto weniger fehlt der fehlende Test. Alles, was rechnet,
  sortiert oder filtert, gehört in die API — sie ist geprüft.

## Ausdrücklich freigegebene Änderungen

Nur diese, keine weiteren.

- **Neue Testdatei** `tests/test_api_statisch.py` — acht Testfunktionen, springt
  still ab, solange FastAPI oder `api/app.py` fehlen.
- **`.gitignore`**: `node_modules/` und `ui/dist/`.
- Kein bestehender Test, kein bestehendes Fixture wird angefasst.

## Vertrag an die Umsetzung (AP-08l)

### Naht zur API — hier prüfen die Tests

1. **`erzeuge_app(db_pfad, *, ui_verzeichnis=None)`.** Ist das Verzeichnis
   angegeben und vorhanden, liefert die Anwendung `index.html` unter `/`
   und die Dateien darunter (`assets/…`) aus. Ohne Angabe sucht sie
   `ui/dist` neben dem Projektverzeichnis; fehlt es, bleibt es dabei.
2. **Rückfall auf `index.html`** für jeden unbekannten Weg, der keine
   API-Route ist. Eine Einzelseitenanwendung führt ihre Wege selbst; ohne
   Rückfall sind tiefe Verweise wertlos.
3. **Die API geht vor.** Weder `/ketten` noch `/openapi.json` dürfen im
   Rückfall landen, und ein fehlerhafter API-Aufruf (`/ketten/abc`) bleibt
   **422**, ein unbekannter Bezeichner **404**. Wer hier zurückfällt,
   verwandelt jede kaputte Anfrage in eine leere Seite statt in eine
   Meldung.
4. **Ohne gebaute Oberfläche bleibt die API nutzbar**, und `/` sagt, was
   fehlt (404 mit einem Hinweis, der `ui` oder `build` nennt) — der
   Normalzustand auf einem frisch geklonten Rechner.
5. **Kein Ausbruch aus dem Bauverzeichnis.** Pfade wie `/../pyproject.toml`
   liefern niemals eine Projektdatei, auch wenn das Journal lokal läuft.

### Die Oberfläche

6. **`ui/`** als Vite-Projekt mit React und TypeScript (Plan §3). Recharts
   wird **nicht** eingebunden — es gibt noch nichts zu zeichnen (AP-06).
   Abhängigkeiten sparsam; `react-router-dom` ist zugelassen, weil tiefe
   Verweise auf eine Position gebraucht werden.
7. **Zwei Ansichten, mehr nicht:**
   - **Positionsliste** (`/`): eine Zeile je Kette mit Basiswert,
     Anlageklasse, Seite, Eröffnung, Ende, Roll-Anzahl, Endzustand,
     Ergebnissumme und Währung. Filter für Basiswert, Anlageklasse,
     Roll-Anzahl und Endzustand; Blättern über `limit`/`offset` mit der
     Gesamtzahl aus der API.
   - **Detailansicht** (`/positionen/<chain_id>`): die Glieder der Kette in
     ihrer Reihenfolge als Zeitstrahl, je mit Verknüpfungsart und
     **Erkennungsart**, darunter aufklappbar die Legs und die Ausführungen
     (Drilldown, P3).
8. **Geld wird angezeigt, nicht gerechnet.** Die API liefert Beträge als
   Zeichenketten, und sie bleiben es. **Kein `parseFloat`, kein `Number()`
   auf ein Geldfeld** — JavaScript-Zahlen sind Gleitkommazahlen, und damit
   wäre der Genauigkeitsverlust, den die API gerade vermeidet, im letzten
   Meter doch da. Ausrichten und Gruppieren ja, umrechnen nein.
9. **Jede Zahl nennt ihre Währung und ihre Sicht** (Plan §5, Zwei
   Sichten). Die Lese-API liefert ausschließlich die Kontosicht; die
   Oberfläche schreibt das sichtbar hin, nicht ins Kleingedruckte. Sobald
   es zwei Sichten gibt, muss der Unterschied ins Auge fallen.
10. **Keine Summen über Positionen.** Es gibt keine Umrechnung nach Euro
    (AP-06); eine Spaltensumme über mehrere Währungen wäre falsch. Auch
    keine Trefferquote, kein Durchschnitt, keine Kennzahl.
11. **Leere und langsame Zustände gehören dazu:** kein Treffer, Ladezustand,
    und eine Fehlermeldung, wenn die API nicht antwortet — keine leere
    Seite, die wie ein leeres Konto aussieht.
12. **Kein eigener Zustand über die Anzeige hinaus.** Filter und Blättern
    stehen in der Adresszeile, damit ein Stand teilbar und nach dem Neuladen
    derselbe ist. Nichts wird im Browser gespeichert.
13. **Entwicklung über `npm run dev` mit Weiterleitung** an die API auf
    `localhost:8000`; im Betrieb wird gebaut und statisch ausgeliefert
    (Plan §3 — kein Node-Server während der Handelszeiten).

## Abnahme

**Maschinell:**

- `tests/test_api_statisch.py` — acht Testfunktionen, zehn Fälle (der Ausbruchstest ist dreifach parametriert) — grün.
- Alle übrigen Tests grün, `ruff check .` sauber.
- `npm run build` läuft durch und erzeugt `ui/dist/index.html`.
- `git diff --stat` zeigt `api/app.py`, `ui/`, `.gitignore` und
  `OFFENE_FRAGEN.md` — kein `tests/`, kein `journal/`, kein `engine/`.

**Durch Augenschein — und als solcher benannt:**

- Die Oberfläche wird mit `npm run dev` gegen die API gestartet und
  durchgeklickt: Liste, Filter, Blättern, Detailansicht, Drilldown, tiefer
  Verweis nach Neuladen, leerer Treffer, gestoppte API.
- **Der Umsetzer prüft das selbst und berichtet, was er gesehen hat** —
  nicht, was er erwartet. Ohne diesen Durchgang ist das Paket nicht fertig.
- Geldbeträge stehen so da, wie die API sie liefert; Stichprobe gegen die
  Rohantwort.

## Ausdrücklich nicht Teil dieses Pakets

Kein Dashboard, keine Kampagnen, kein Kalender, kein Journal-Editor (alles
AP-08 nach AP-06). Keine Durchsicht der Rollkandidaten — sie sind nicht
gespeichert, und woher sie schnell genug kommen, ist offen (Plan §6,
Block B, Regel 2). Keine Schreibfunktion. Keine Kennzahl. Kein
Frontend-Testwerkzeug: Vitest gegen Playwright wird später verglichen, in
einem eigenen Paket.
