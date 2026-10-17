---
titel: Steuer — Anfangsbestände, Ersatzzahlungen/SYEP, USD-Konto (wartet auf Daten und Berater)
modell: stark
status: wartet
abhaengig_von: AP-10c
aendert_tests: nein
---

# AP-10d · Steuer — was erst mit Daten und Antworten geht

Dieses Paket ist **nicht beginnbar**, solange die Eingaben unten fehlen. Es steht hier, damit nichts verloren geht
und die Abhängigkeiten sichtbar sind. Vorgehen je Teil: erst Rückfrage beantworten, dann Auftrag schärfen.

## Teil 0 · Datenprüfung, parallel ab sofort (blockiert nichts)

Aus den vorhandenen Daten gezielte Listen **mit Buchungen und Beträgen** für den Steuerberater: Ersatzzahlungen je
Jahr, ETF-Anteile und -Lieferungen (9 Symbole), Buchungen um den Jahreswechsel, Quellensteuer-Überhang je Land,
Optionen mit Lieferung je Jahr. Nur Zählwerte und Summen im Bericht (CLAUDE.md Regel 2); die Einzelbuchungen für
den Berater erzeugt der Nutzer aus der Datenbank.

## Teil 1 · Steuerliche Anfangsbestände zum 01.01.2025

Benötigt für 2025: Anschaffungskosten und -daten der übernommenen **Aktien-, Options- und USD-Bestände**. Die
Datenbank beginnt 2022; was davor erworben wurde, hat nur den Einstand laut IB. **Eingabe vom Nutzer/Berater:**
Bestandsliste zum Stichtag mit Anschaffungsdatum und -kosten, dazu die festgestellten Verlustvorträge aus den
Bescheiden. Die **Eingabestruktur** liegt schon in AP-10b/c (R16); hier kommen die realen Werte. Das Paket gleicht sie mit den Beständen der Datenbank ab und listet Abweichungen; es **rechnet nichts
nach**. Das ist keine Neubearbeitung alter Erklärungen, sondern die Ausgangsbasis 2025.

## Teil 2 · Ersatzzahlungen und SYEP

Stand: 140 Ersatzzahlungen im Echtbestand (2023: 63 Buchungen, 2.656 EUR). Die Ursache einer Buchung (SYEP, Margin-
Leihe, verspätete Lieferung) steht in den Cash-Buchungen nicht. **Eingabe:** IB-Leihabschnitte (Securities
Lending/SYEP-Berichte) oder eine IB-Auskunft; möglicherweise eine erweiterte Flex-Query. Danach: Zuordnung je
Buchung (`ursache`), Einordnung nach Antwort des Beraters (§ 22 Nr. 3 oder § 20), Freigrenze auf der Summe. Die
laufende SYEP-Vergütung ist **getrennt** von Dividendenersatz einzuordnen (Vertragsgrundlage IBIE, Schedule 4).
Zahlungen von 2026 sind aufzuarbeiten, auch wenn SYEP abgeschaltet wird; Ersatzzahlungen anderer Ursache
verschwinden dadurch nicht.

## Teil 3 · USD-Konto und Kurseffekte

Stand: 22.678 USD Sollzinsen und 1.738 USD Habenzinsen — das USD-Konto war zeitweise im Minus, zeitweise im Plus.
**Zuerst klären (Berater):** Funktion und Verzinsungsstruktur des Kontos (Zahlungsverkehrskonto-Regel, verzinslich
oder nicht, Haltefrist/Freigrenze § 20 oder § 23). **Eingabe:** Verlauf des USD-Saldos (Cash-Report) und die
Vertragsbedingungen. Erst danach lohnt sich die Nachverfolgung jedes Zu- und Abflusses nach FIFO. IBs Forex-Zeile
wird **nicht ungeprüft** übernommen; Abgleich von Berechnungsmethode, erfassten Vorgängen und steuerlichen Regeln.

## Teil 4 · Formular 2026

KAP-Zeilen gelten für 2025. Für 2026 wird die Zeilentabelle erst nach Prüfung des amtlichen Vordrucks auf „geprüft“
gesetzt; die materiellen Regeln entsprechen dem derzeit geprüften Rechtsstand.

## Ausdrücklich nicht Teil dieses Pakets

- Steuerberatung, Verlustverrechnung, Ausfüllen der Anlagen KAP, SO oder AUS.
