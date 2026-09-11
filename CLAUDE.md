# Projektregeln — Trading Journal

Der maßgebliche Plan liegt unter `plan/trading-journal-projektplan.md`. Er ist die
fachliche Wahrheit. Diese Datei enthält nur die Regeln für die Arbeit am Code.

## Arbeitsweise

Du arbeitest immer an genau einem Arbeitspaket. Das zugehörige Auftragsdokument
liegt unter `auftraege/`. Umfang und Abnahmekriterien stehen im Plan; erweitere
den Umfang nicht eigenmächtig.

Ein Paket ist fertig, wenn seine Abnahmekriterien erfüllt sind — nicht, wenn der
Code plausibel aussieht.

## Unverrückbar

1. **Tests, Fixtures und Abnahmekriterien sind unveränderlich — ab AP-01.**
   AP-01 legt das Testgerüst und die Fixtures an. Danach ändere sie niemals, um
   einen Testlauf grün zu bekommen. Schlägt ein Test fehl, ist der Code falsch
   oder die Anforderung unklar. Im zweiten Fall: Eintrag in `OFFENE_FRAGEN.md`
   und Abbruch.
   Der Hook setzt das technisch durch: Profil `locker` nur für Pakete, die Tests
   anlegen oder korrigieren dürfen, sonst `streng`.
   **Fordere niemals, den Schutz zu lockern.** Kommst du an eine Stelle, an der
   das nötig scheint, ist der Auftrag falsch geschnitten — melde das.

1a. **Wenn eine Test-Erwartung fachlich falsch ist**, gibt es genau einen Weg:
   ein eigenes Korrekturpaket. Es trägt im Kopf `aendert_tests: ja`, läuft unter
   `locker` und benennt die zu ändernden Erwartungen namentlich. Nur die dort
   genannten dürfen geändert werden, und die Prüflogik bleibt erhalten — es
   ändert sich, *was* erwartet wird, nie *ob* geprüft wird. Alles andere bleibt
   verboten, insbesondere das beiläufige Anpassen eines Tests im Rahmen eines
   Umsetzungspakets.
2. **Golden-Fixtures unter `fixtures/golden/`** enthalten echte Kontodaten. Nur
   Pakete des starken Modells lesen sie. Niemals kopieren, niemals ausgeben,
   niemals in Logs schreiben.
3. **Schemaänderungen nur über eine Alembic-Migration.** Kein direktes Editieren
   bestehender Migrationen.
4. **Kein Überschreiben von `executions`, keine Löschung von Benutzerdaten.**
5. **Geldbeträge als `Decimal`.** Niemals `float`. Keine stillen Rundungen.
6. **Engine-Module (`engine/`) sind rein.** Kein `requests`, kein
   `datetime.now()`, keine Zufallsquellen. Zeit kommt als Parameter herein.
7. **Automatisch erzeugte Verknüpfungen sind Vorschläge, keine Tatsachen.** Das
   Feld `erkennung` ist Pflicht und trägt `auto`, `heuristik` oder `manuell`.
8. **Neue Kennzahlen brauchen einen Test mit einem von Hand nachgerechneten
   Erwartungswert** — nicht mit dem Ergebnis der eigenen Implementierung.
9. **Der Options Roller hat Vorrang auf der Datenbank.** Kurze Transaktionen,
   `busy_timeout` gesetzt, im Konfliktfall abbrechen statt blockieren.
10. **Bei fachlicher Unklarheit nicht raten.** Annahme im Code dokumentieren,
    Eintrag in `OFFENE_FRAGEN.md`.

## Konventionen

- Python 3.12, `ruff` für Linting, `pytest` für Tests.
- Verzeichnisse: `ingest/`, `engine/`, `analytics/`, `api/`, `ui/`, `tests/`,
  `fixtures/`, `migrations/`.
- Alle fachlichen Bezeichner deutsch, wie im Plan. Technische Bezeichner englisch.
- Ein Commit pro Arbeitspaket, nicht pro Datei.

## Vor jeder Abgabe

- `pytest` läuft grün.
- `ruff check .` ist sauber.
- `git diff --stat` zeigt keine Änderungen unter `tests/` oder `fixtures/`,
  außer das Arbeitspaket verlangt sie ausdrücklich.
- `OFFENE_FRAGEN.md` enthält alles, was du geraten hättest.
