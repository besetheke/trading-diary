---
titel: Lese-API ueber Ketten, Strukturen und Ausfuehrungen
modell: guenstig
status: fertig
abhaengig_von: AP-07lv
---

# AP-07l · Lese-API

Umsetzungspaket nach Plan §11.2, Schritt 2. Die Abnahmebasis liegt vor
(AP-07lv). **Tests und Fixtures sind tabu** — fällt ein Test, ist der Code
falsch.

Maßgeblich ist der Vertrag 1–17 in `auftraege/AP-07lv.md`. Lies ihn
vollständig, samt dem Abschnitt „Die vier Entscheidungen, die nicht beim
Umsetzer liegen".

## Worum es geht

Seit AP-04p schreibt `journal rebuild` Legs, Strukturen, Ketten und
Kettenglieder in die Datenbank. Bisher kommt niemand an sie heran außer
über SQL. Dieses Paket legt eine **lesende** FastAPI-Schicht darüber, auf
der die Positionsliste (AP-08l) aufsetzt.

Der Plan zog AP-07 ursprünglich hinter AP-06. Das ist aufgeteilt: Diese
Lese-Fassung kommt vorgezogen, weil die Daten schon da sind und keine
Kennzahl brauchen, um sichtbar zu sein.

## Zu bauen

- `api/app.py` mit `erzeuge_app(db_pfad)` und dem Modulobjekt `app`.
- Vier Endpunkte (Vertrag 4–7), alle `GET`.
- Die Antwortmodelle als Pydantic-Modelle (Vertrag 8–14).

Sonst nichts. `engine/`, `journal/`, Schema und Migrationen bleiben
unberührt.

## Die vier Stellen, an denen erfahrungsgemäß geraten wird

1. **Geld als Zeichenkette, nicht als Zahl** (Entscheidung 1, Vertrag 13).
   JSON kennt nur Gleitkommazahlen. `Decimal` als Zahl zu serialisieren
   heißt, den Wert durch `float` zu schicken — genau der stille
   Genauigkeitsverlust, den Regel 5 verbietet. Das betrifft auch Mengen,
   Strikes und Preise. Ein Pydantic-Feldtyp `str` mit einem Validator, der
   `Decimal` formatiert, ist der einfache Weg; `json_encoders` für
   `Decimal` ist der bequeme und liefert je nach Pydantic-Fassung doch
   Zahlen — prüfe, was wirklich im JSON steht.
2. **Leer bleibt leer** (Vertrag 13). Eine offene Struktur hat kein
   Ergebnis. Wird daraus `"0"` oder `"0.00"`, sieht sie aus wie ein
   Nullergebnis. Das ist ein Datenfehler, kein Darstellungsdetail.
3. **`seite` kann leer sein.** `Call`, `Put`, `n.a.` — oder nichts, bei
   einer Kette ohne Optionen. Übernimm den Wert aus der Spalte
   `chains.seite`, statt ihn abzuleiten.
4. **`gesamt` zählt vor der Begrenzung** (Vertrag 4). Ein `len()` auf das
   begrenzte Ergebnis liefert nie mehr als `limit`, und eine Oberfläche
   könnte nicht blättern. Das braucht eine eigene Zählabfrage.

## Grenzen

- **Nur lesen.** Keine `POST`/`PUT`/`DELETE`-Route — ein Test liest das
  OpenAPI-Schema und prüft genau das. Kein `rebuild` aus der API heraus.
- **Nichts rechnen** außer `struktur_summe_netto` (Entscheidung 4). Keine
  Kennzahlen, keine Umrechnung nach Euro, keine Quote, kein Durchschnitt.
- **Keine währungsübergreifende Summe** (Entscheidung 3).
- Keine Rollkandidaten — sie sind nicht gespeichert, und sie neu zu rechnen
  dauert über den ganzen Bestand Minuten.
- Keine Authentifizierung; das Journal läuft lokal (§4).
- **Regel 2:** Keine Datei unter `fixtures/golden/` lesen, kein Skript
  unter `werkzeuge/abgleich/` ausführen, und die API **nicht** gegen die
  echte Datenbank starten. Alle Tests arbeiten auf temporären Datenbanken
  mit erfundenen Daten.

## Abnahme

- `tests/test_api_lesen.py` — 19 Tests — vollständig grün.
- Alle übrigen Tests grün, `ruff check .` sauber.
- `git diff --stat` zeigt ausschließlich `api/` und `OFFENE_FRAGEN.md`.
  (`pyproject.toml` ist bereits vorbereitet: `fastapi` und `httpx` stehen
  drin.)
