---
titel: Flex-Import Kontowert (NAV je Tag), Change in NAV, Cash Report
modell: stark
status: fertig
abhaengig_von: AP-02, OF-77
aendert_tests: ja
---

# AP-02n · Kontowert aus Flex

Anlass: OF-77/OF-78 — die realisierte Kapitalkurve weicht vom Depotwert ab;
der Nutzer will realisiert **und** unrealisiert sehen. Die Flex-Query wurde
am 10.10.2026 um „Net Asset Value (NAV) in Base", „Change in NAV" (Option
„Realized & Unrealized") und „Cash Report" (Currency Breakout) erweitert,
Zeitraum des Nachtlaufs auf 30 Tage verkürzt (365 Tage wurden vom Web-Service
nicht rechtzeitig erzeugt). Historie 2022–2026 als Jahresexporte importiert.

Vorbereitung und Umsetzung in einem (starkes Modell). Neue Fixtures
`fixtures/flex/activity_nav.xml`, `activity_nav_overlap.xml` (frei erfunden),
neue Testdatei `tests/test_ingest_flex_nav.py` (8). Bestehende Tests
unverändert.

## Entscheidungen

- **N1 Drei Rohdatentabellen** nach dem Muster der übrigen Flex-Sektionen:
  Kernspalten + vollständiger Rohsatz, Schlüssel `(konto, quell_schluessel)`.
  - `flex_nav_tage` — `nav:<Datum>`; Cash, Aktien, Optionen, Rohstoffe,
    Fonds, Anleihen, Abgrenzungen, Gesamt (Pflicht).
  - `flex_change_in_nav` — `cinav:<von>|<bis>`; Anfangs-/Endwert (Pflicht),
    realisiert, Veränderung unrealisiert, Marktbewertung, Ein-/Auszahlungen,
    Dividenden, Zinsen, Kommissionen, Währungseffekt, TWR.
  - `flex_cash_report` — `cash:<von>|<bis>|<Währung>|<Ebene>`; jede Ebene wird
    gespeichert (die Ebene steht im Schlüssel).
- **N2 Erste Quelle gewinnt.** Überlappende Dateien überschreiben nichts
  (wie alle Bewegungsdaten des Imports).
- **N3 Leer bleibt leer** — kein stilles 0 für fehlende Teilwerte.
- **N4 Pflichtfelder fehlen oder unlesbar → `ValueError`**, die Datei wird
  nicht geschrieben (Parse vor Schreiben, wie bisher).

## Echtlauf (10.10.2026)

Migration `aacd88fb9269`; Jahresexporte 2022–2026 importiert: 1.182
Handelstage NAV (2022-03-31 bis 2026-10-09, keine Lücke über 5 Tage), 5
Change-in-NAV-Zeiträume, 19 Cash-Report-Zeilen; 112 neue Ausführungen aus
2026, Rebuild danach. **Change in NAV liefert in allen Exporten nur Anfangs-,
Endwert und TWR** — die Einzelposten bleiben leer (siehe OF-78).
