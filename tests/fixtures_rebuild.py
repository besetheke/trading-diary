"""Frei erfundene Ausführungen für die Abnahmetests der Persistenz (AP-04v).

Kein Golden, kein XML: Python-Literale, damit im Test nachlesbar bleibt, was
erwartet wird. Drei voneinander unabhängige Vorgänge auf drei Basiswerten:

- **DAX** — eine Put-Vertikale, in **einer** Order gerollt (gemeinsamer
  ``exec_batch``). Ergibt zwei Strukturen mit ``erkennung = 'order_id'`` in
  einer Kette, deren Rollverknüpfung ``auto`` trägt: die Order-Nummer belegt
  den Roll.
- **ESTX50** — dieselbe Bewegung ohne ``exec_batch``, in **zwei** Orders zwei
  Minuten auseinander. Ergibt zwei Strukturen mit ``erkennung = 'heuristik'``
  in einer Kette, deren Rollverknüpfung ``heuristik`` trägt: hier schließt nur
  zeitliche Nähe.
- **IDX9** — zwei Aktientranchen, die nach Plan §6 (Block B, Regel 4) nie
  automatisch verkettet werden. Sie sind die Vorlage für den Override-Test.

Die Beträge sind so gewählt, dass sich das Ergebnis im Kopf nachrechnen lässt
(Regel 8) — siehe ``tests/test_rebuild.py``.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import insert

from journal.db import create_db_engine
from journal.schema import executions, import_runs, instruments

# ---------------------------------------------------------------------------
# Instrumente
# ---------------------------------------------------------------------------

INSTRUMENTE = [
    # DAX: Put-Vertikale September, gerollt in den Oktober.
    dict(conid=601, symbol="DAX  260918P19000", underlying="DAX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("19000"), right="P",
         multiplikator=Decimal("5"), waehrung="EUR"),
    dict(conid=602, symbol="DAX  260918P18900", underlying="DAX", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("18900"), right="P",
         multiplikator=Decimal("5"), waehrung="EUR"),
    dict(conid=701, symbol="DAX  261016P18800", underlying="DAX", asset_class="OPT",
         expiry=date(2026, 10, 16), strike=Decimal("18800"), right="P",
         multiplikator=Decimal("5"), waehrung="EUR"),
    dict(conid=702, symbol="DAX  261016P18700", underlying="DAX", asset_class="OPT",
         expiry=date(2026, 10, 16), strike=Decimal("18700"), right="P",
         multiplikator=Decimal("5"), waehrung="EUR"),
    # ESTX50: dieselbe Bewegung, aber ohne exec_batch.
    dict(conid=801, symbol="ESTX50 260918P4900", underlying="ESTX50", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("4900"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
    dict(conid=802, symbol="ESTX50 260918P4850", underlying="ESTX50", asset_class="OPT",
         expiry=date(2026, 9, 18), strike=Decimal("4850"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
    dict(conid=803, symbol="ESTX50 261016P4800", underlying="ESTX50", asset_class="OPT",
         expiry=date(2026, 10, 16), strike=Decimal("4800"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
    dict(conid=804, symbol="ESTX50 261016P4750", underlying="ESTX50", asset_class="OPT",
         expiry=date(2026, 10, 16), strike=Decimal("4750"), right="P",
         multiplikator=Decimal("10"), waehrung="EUR"),
    # Aktie: zwei Tranchen, nie automatisch verkettet.
    dict(conid=901, symbol="IDX9", underlying="IDX9", asset_class="STK",
         expiry=None, strike=None, right=None,
         multiplikator=Decimal("1"), waehrung="USD"),
]

# ---------------------------------------------------------------------------
# Ausführungen
# ---------------------------------------------------------------------------

_DAX = [
    # Eröffnung der Vertikale, eine Order.
    dict(exec_id="E1", conid=601, side="SELL", preis=Decimal("100.00"),
         handelszeit=datetime(2026, 9, 1, 10, 0, 0), exec_batch="3.1"),
    dict(exec_id="E2", conid=602, side="BUY", preis=Decimal("60.00"),
         handelszeit=datetime(2026, 9, 1, 10, 0, 0), exec_batch="3.1"),
    # Roll: dieselbe Combo-Order schließt September und eröffnet Oktober.
    dict(exec_id="E3", conid=601, side="BUY", preis=Decimal("40.00"),
         handelszeit=datetime(2026, 9, 15, 15, 0, 0), exec_batch="3.9"),
    dict(exec_id="E4", conid=602, side="SELL", preis=Decimal("20.00"),
         handelszeit=datetime(2026, 9, 15, 15, 0, 0), exec_batch="3.9"),
    dict(exec_id="E5", conid=701, side="SELL", preis=Decimal("90.00"),
         handelszeit=datetime(2026, 9, 15, 15, 0, 0), exec_batch="3.9"),
    dict(exec_id="E6", conid=702, side="BUY", preis=Decimal("55.00"),
         handelszeit=datetime(2026, 9, 15, 15, 0, 0), exec_batch="3.9"),
]

_ESTX50 = [
    dict(exec_id="Z1", conid=801, side="SELL", preis=Decimal("30.00"),
         handelszeit=datetime(2026, 9, 2, 11, 0, 0)),
    dict(exec_id="Z2", conid=802, side="BUY", preis=Decimal("18.00"),
         handelszeit=datetime(2026, 9, 2, 11, 1, 0)),
    dict(exec_id="Z3", conid=801, side="BUY", preis=Decimal("12.00"),
         handelszeit=datetime(2026, 9, 16, 15, 0, 0)),
    dict(exec_id="Z4", conid=802, side="SELL", preis=Decimal("6.00"),
         handelszeit=datetime(2026, 9, 16, 15, 0, 0)),
    # Zwei Minuten später, eigene Order: der Roll ist hier nur erschlossen.
    dict(exec_id="Z5", conid=803, side="SELL", preis=Decimal("28.00"),
         handelszeit=datetime(2026, 9, 16, 15, 2, 0)),
    dict(exec_id="Z6", conid=804, side="BUY", preis=Decimal("17.00"),
         handelszeit=datetime(2026, 9, 16, 15, 2, 0)),
]

_AKTIE = [
    dict(exec_id="A1", conid=901, side="BUY", menge=Decimal("100"),
         preis=Decimal("50.00"), waehrung="USD",
         handelszeit=datetime(2026, 3, 2, 10, 0, 0)),
    dict(exec_id="A2", conid=901, side="BUY", menge=Decimal("100"),
         preis=Decimal("55.00"), waehrung="USD",
         handelszeit=datetime(2026, 5, 4, 10, 0, 0)),
]

AUSFUEHRUNGEN = _DAX + _ESTX50 + _AKTIE

_VORGABEN = dict(
    konto="U1234567",
    menge=Decimal("1"),
    waehrung="EUR",
    kommission=Decimal("-2.00"),
    kommission_waehrung="EUR",
    ereignistyp="trade",
    roh_json="{}",
    qualitaetsstufe="A",
)


def befuelle(db_pfad, ausfuehrungen=None, instrumente_=None) -> None:
    """Schreibt Instrumente und Ausführungen in eine migrierte Datenbank.

    Ohne Argumente den vollständigen Bestand; sonst genau das Übergebene —
    für Tests, die einen Teilbestand oder einen Sonderfall brauchen.
    """
    engine = create_db_engine(db_pfad)
    with engine.begin() as verbindung:
        for satz in instrumente_ if instrumente_ is not None else INSTRUMENTE:
            verbindung.execute(insert(instruments).values(**satz))

        lauf = verbindung.execute(
            insert(import_runs).values(
                quelle="flex",
                datei_hash="rebuild-fixture",
                importiert_am=datetime(2026, 9, 20, 6, 0, 0),
                qualitaetsstufe="A",
                zeilen_gesamt=0,
                zeilen_neu=0,
            )
        ).inserted_primary_key[0]

        symbol_je_conid = {
            satz["conid"]: satz["symbol"]
            for satz in (instrumente_ if instrumente_ is not None else INSTRUMENTE)
        }
        for satz in ausfuehrungen if ausfuehrungen is not None else AUSFUEHRUNGEN:
            werte = dict(_VORGABEN)
            werte.update(satz)
            werte.setdefault("symbol", symbol_je_conid[satz["conid"]])
            werte["import_run_id"] = lauf
            verbindung.execute(insert(executions).values(**werte))
