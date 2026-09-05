"""ExactDecimal: verlustfreier Roundtrip über TEXT-Storage (CLAUDE.md, Regel 5).

SQLite hat keinen Dezimaltyp; der übliche Weg über sa.Numeric läuft auf
SQLite zwangsläufig durch float und rundet still. Diese Tests halten die
Ersatzlösung fest: Beträge sind exakt, Speicherung ist TEXT, floats werden
beim Schreiben abgewiesen.

Die Erwartungswerte sind von Hand gewählt — unter anderem Werte, die ein
float-Umweg zwangsläufig verfälschen würde.
"""

import decimal
from datetime import date

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import StatementError

from journal.db import create_db_engine
from journal.schema import fx_rates

# 20 signifikante Stellen bzw. 19 Nachkommastellen liegen jenseits der
# float64-Auflösung (~15-17 Stellen); ein float-Umweg wäre hier falsch.
ROUNDTRIP_WERTE = [
    decimal.Decimal("19.99"),
    decimal.Decimal("0.1"),
    decimal.Decimal("-0.005"),
    decimal.Decimal("98765432109876.54321"),
    decimal.Decimal("0.0000000000000000001"),
]


def _lese_kurse(db_pfad, waehrung):
    engine = create_db_engine(db_pfad)
    with engine.connect() as verbindung:
        return verbindung.execute(
            select(fx_rates.c.kurs_eur).where(fx_rates.c.waehrung == waehrung)
        ).scalar_one()


def test_exact_decimal_roundtrip_is_lossless(migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        for i, wert in enumerate(ROUNDTRIP_WERTE):
            verbindung.execute(
                insert(fx_rates).values(
                    datum=date(2026, 9, 5),
                    waehrung=f"X{i}",
                    kurs_eur=wert,
                    quelle="test",
                )
            )
    for i, wert in enumerate(ROUNDTRIP_WERTE):
        geladen = _lese_kurse(migrated_db, f"X{i}")
        assert isinstance(geladen, decimal.Decimal), (
            f"Ergebnis ist kein Decimal, sondern {type(geladen).__name__}"
        )
        assert geladen == wert


def test_exact_decimal_is_stored_as_text_in_sqlite(migrated_db):
    engine = create_db_engine(migrated_db)
    with engine.begin() as verbindung:
        verbindung.execute(
            insert(fx_rates).values(
                datum=date(2026, 9, 5),
                waehrung="TXT",
                kurs_eur=decimal.Decimal("123.45"),
                quelle="test",
            )
        )
    with engine.connect() as verbindung:
        speichertyp = verbindung.execute(
            text("SELECT typeof(kurs_eur) FROM fx_rates WHERE waehrung = 'TXT'")
        ).scalar_one()
    assert speichertyp == "text", "Beträge dürfen nicht in float-affinen Spalten liegen"


def test_exact_decimal_rejects_float_at_bind_time(migrated_db):
    engine = create_db_engine(migrated_db)
    # SQLAlchemy hüllt den Bind-Fehler in StatementError; die Ursache
    # muss unser TypeError sein, kein stiller float-Umweg.
    with engine.begin() as verbindung, pytest.raises(StatementError) as fehler:
        verbindung.execute(
            insert(fx_rates).values(
                datum=date(2026, 9, 5),
                waehrung="FLT",
                kurs_eur=123.45,  # absichtlich float
                quelle="test",
            )
        )
    assert isinstance(fehler.value.orig, TypeError)
