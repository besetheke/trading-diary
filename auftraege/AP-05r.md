---
titel: Abnahmebasis Kandidatenregeln nach der Praxis des Nutzers (AP-05, Teil 1)
modell: stark
status: fertig
abhaengig_von: AP-05v, AP-05k
aendert_tests: ja
---

# AP-05r · Abnahmebasis: IC- und Financing-Kandidaten nach der Praxis

Vorbereitungspaket nach Plan §11.2. **Es implementiert nichts**; die
Umsetzung ist AP-05rk (günstiges Modell). Neue Testdatei
`tests/test_campaigns_regeln.py` (10 Tests), `tests/test_campaigns.py` bleibt
unverändert und muss grün bleiben.

## Grund (Nutzerangaben 08.10.2026, OF-71)

Der Nutzer hält Spreads auf beiden Seiten oft dauerhaft und rollt sie einzeln,
wochenweise (DAX: freitags, etwa 7 DTE). Die Gegenfinanzierung setzt er meist
innerhalb weniger Minuten auf; zugleich rollt oder setzt er zu Beginn häufig
**beide** Seiten neu auf, auch nach einem Take Profit, alles in wenigen
Minuten. Daraus folgen drei Änderungen an `engine.campaigns`.

## Regeln

1. **IC-Kandidat über irgendein Glied.** Zwei Ketten (gleicher Basiswert,
   Gegenseiten) sind ein IC-Kandidat, wenn es je Kette ein Glied gibt, die
   dieselbe (nicht leere) Expiry tragen und zeitlich überlappen. Glied-
   Intervall: `structure.eroeffnet_am` bis `structure.geschlossen_am`
   (offen = unbegrenzt). Das ersetzt den Vergleich der *letzten* Glieder.
2. **Doppel-Roll ist kein Financing.** Ist die Gegenseite-Kette B die
   Fortsetzung oder der Wiedereinstieg der eigenen Seite — es gibt eine
   andere Kette C mit demselben Basiswert und derselben Seite wie B, die
   `0 <= B.eroeffnet_am - C.beendet_am <= 15 Minuten` endete —, wird das
   Paar nicht als Financing angeboten. Benannter Modulwert
   `DOPPEL_ROLL_FENSTER = timedelta(minutes=15)`, einschließlich der Grenze.
3. **Ranggrößen.** `CampaignKandidat` bekommt `abstand` und `ueberlappung`
   (beide `timedelta | None`, Standard `None`):
   - `abstand`: bei `ic` der Betrag des Unterschieds der beiden Ketten-
     Eröffnungen; bei `financing` der Betrag zwischen dem frühesten Roll
     der Bestandskette und der Eröffnung der Gegenseite.
   - `ueberlappung`: gemeinsame Zeit der beiden Ketten (vom späteren
     Beginn bis zum früheren Ende, mindestens 0); `None`, wenn beide Ketten
     offen sind (unbegrenzt).
   Die Ausgabereihenfolge bleibt (Typ, Naturschlüssel A, Naturschlüssel B);
   sortiert wird erst in der Durchsicht (AP-05d).

## Wirkung am Echtbestand (Wegwerf-Umsetzung, Kopie, nur Zählwerte)

IC-Kandidaten 3.237 → 4.308 (davon Überlappung über 7 Tage: 400 → 1.065, 1 bis
7 Tage: 402 → 766); Financing 518 → 451 (67 Doppel-Rolls). Die Zunahme bei den
IC liegt fast vollständig in den langen Überlappungen — den dauerhaften
Doppelseiten, um die es dem Nutzer geht.

## Abnahme

`tests/test_campaigns_regeln.py` und `tests/test_campaigns.py` und
`tests/test_campaigns_sicht.py` grün, `ruff check .` sauber. Gegen die
Wegwerf-Umsetzung geprüft: 24 von 24 grün; ohne sie schlagen 7 der 10 neuen
Tests fehl.
