---
titel: Preise in Positionsliste und Detailansicht
modell: guenstig
status: fertig
abhaengig_von: AP-07p
---

# AP-08fp · Preise in der Oberfläche

Korrektur-/Erweiterungspaket, kein Vorbereitungspaket nötig: Die Felder
existieren bereits in der API (AP-07p), nur die Oberfläche kennt sie noch
nicht. **Tests und Fixtures sind tabu.** Kein neuer Frontend-Test — die
Oberfläche bleibt bewusst ohne eigenes Testwerkzeug (AP-08lv), Abnahme
läuft über Augenschein wie bei AP-08l/AP-08lk.

Anlass: „Die Übersichtsliste hat z. B. keine Preise. Ich möchte wenig
klicken und direkt viel Informationen." (Nutzer, 22.09.2026, siehe
`auftraege/AP-08f.md`). Das ist der erste, sofort umsetzbare Ausschnitt
aus dieser Anforderung — der Teil, der keine neue Rechnung braucht,
sondern nur bereits vorhandene API-Felder zeigt.

## Der Befund

`api/app.py` liefert seit AP-07p an Struktur **und** Kette je
`eroeffnungspreis` und `schlusspreis` (Zeichenkette oder leer). Die
TypeScript-Typen in `ui/src/api.ts` kennen beide Felder noch nicht — sie
kommen zwar im JSON an, werden aber nirgends angezeigt.

## Vertrag

1. **`ui/src/api.ts`:** Ergänze `eroeffnungspreis: string | null` und
   `schlusspreis: string | null` in den Interfaces `Kette` und `Struktur`.
2. **`ui/src/Positionen.tsx`:** Zwei neue Spalten in der Tabelle, „Preis
   auf" und „Preis zu", mit den Werten aus `kette.eroeffnungspreis` und
   `kette.schlusspreis`. Platzierung: neben den bestehenden Geldspalten,
   vor „Ergebnis netto".
3. **`ui/src/PositionDetail.tsx`:** Dieselben zwei Felder ergänzend zu
   Brutto/Kommission/Netto in der Strukturkarte — der Preis, zu dem
   eröffnet bzw. geschlossen wurde, gehört fachlich neben das Ergebnis.
4. **Dieselbe Kürzung wie bei „Ergebnis netto"** (AP-08lk, Punkt 2, vom
   Nutzer freigegeben): In der **Liste** zwei Nachkommastellen über
   `aufZweiNachkommastellen()`, voller Wert im `title`. In der
   **Detailansicht** unverändert genau — dort ist die Genauigkeit der
   Zweck, das gilt für die neuen Felder genauso wie für die bestehenden.
5. **Leer bleibt leer.** Eine offene Struktur/Kette hat keinen
   Schlusspreis — `—`, keine `"0.00"` (Vertrag 8, AP-08lv; dieselbe Regel,
   die für Geldbeträge durchweg gilt).
6. **Geld bleibt Zeichenkette** (Vertrag 8, unverändert). Kein
   `parseFloat`, kein `Number()`, kein `toFixed` — auch nicht für die
   neuen Felder. `aufZweiNachkommastellen()` aus `format.ts` ist reine
   Zeichenarbeit, benutze sie, erfinde nichts Neues.

## Wo du abschreiben sollst

Die Spalte „Ergebnis netto" in `Positionen.tsx` und das Feld
`struktur_summe_netto` zeigen bereits exakt das Muster, das für die neuen
Spalten gilt — Kürzung, `title` mit vollem Wert, `—` bei `null`. Kopiere
das Muster für die zwei neuen Spalten, statt es neu zu erfinden.

## Grenzen

- Keine neue Berechnung — beide Felder kommen unverändert aus der API.
- Kein Frontend-Testwerkzeug einführen.
- **Regel 2:** Starte die Oberfläche nicht gegen `journal.db`, sondern
  gegen eine Datenbank mit erfundenen Daten.

## Abnahme

- `ruff check .` sauber, gesamte Python-Testsuite grün (unverändert, da
  keine Python-Datei angefasst wird).
- `npm run build` läuft durch.
- **Du siehst dir beide Ansichten selbst an** (`npm run dev` gegen die API
  mit erfundenen Daten) und berichtest, was du siehst: Preise in Liste und
  Detailansicht, Kürzung mit Tooltip in der Liste, volle Genauigkeit im
  Detail, `—` bei offenen Positionen ohne Schlusspreis.
- `git diff --stat` zeigt ausschließlich `ui/src/api.ts`,
  `ui/src/Positionen.tsx`, `ui/src/PositionDetail.tsx`.
