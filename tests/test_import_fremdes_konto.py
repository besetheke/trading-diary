# ruff: noqa: E501
"""Import lehnt ein fremdes Konto ab, bevor etwas geschrieben wird (Einzelkonto-Grenze, R04).

Welt: Die Datenbank kennt das Konto U8000001 (eine importierte Ausführung). Eine Datei des Paper-Kontos DU9999999 wird
abgelehnt, die Datenbank bleibt unverändert; eine weitere Datei desselben Kontos U8000001 wird weiter importiert;
in einer leeren Datenbank gilt die erste Datei als das Konto der Datenbank.
"""
import pytest
from sqlalchemy import text

from ingest.flex import import_flex_file
from journal.db import create_db_engine


def datei(tmp_path, name, konto, trade_id, transaction_id):
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<FlexQueryResponse queryname="Activity" type="Statement">
  <FlexStatements count="1">
    <FlexStatement accountId="{konto}" fromDate="20260601" toDate="20260630" period="Test" whenGenerated="20260701;031500">
      <Trades>
        <Trade levelOfDetail="EXECUTION" tradeID="{trade_id}" transactionID="{transaction_id}" ibExecID="0099.0001.01.01"
               ibOrderID="5599999" orderReference="" conid="500001" symbol="CORPX" underlyingSymbol="CORPX"
               assetCategory="STK" buySell="BUY" quantity="1" tradePrice="1.00" proceeds="0.00" ibCommission="-1.00"
               ibCommissionCurrency="USD" currency="USD" fxRateToBase="1.0000" netCash="0.00"
               dateTime="20260601;120000" orderTime="" exchange="MEMX" notes="" openCloseIndicator="O" />
      </Trades>
      <OpenPositions></OpenPositions><CashTransactions></CashTransactions><CorporateActions></CorporateActions>
      <Transfers></Transfers><SecuritiesInfo></SecuritiesInfo>
    </FlexStatement>
  </FlexStatements>
</FlexQueryResponse>
"""
    ziel = tmp_path / name
    ziel.write_text(xml, encoding="utf-8")
    return ziel


def konten(db):
    with create_db_engine(db).connect() as v:
        return sorted(r[0] for r in v.execute(text("SELECT DISTINCT konto FROM executions")))


def zeilen(db):
    with create_db_engine(db).connect() as v:
        return v.execute(text("SELECT COUNT(*) FROM executions")).scalar()


def test_fremdes_konto_wird_vor_dem_schreiben_abgelehnt(migrated_db, tmp_path):
    import_flex_file(migrated_db, datei(tmp_path, "a.xml", "U8000001", "1001", "7001"))
    assert konten(migrated_db) == ["U8000001"] and zeilen(migrated_db) == 1
    with pytest.raises(ValueError, match="DU9999999 gehört nicht zu dieser Datenbank"):
        import_flex_file(migrated_db, datei(tmp_path, "paper.xml", "DU9999999", "2001", "8001"))
    assert konten(migrated_db) == ["U8000001"] and zeilen(migrated_db) == 1       # nichts geschrieben


def test_gleiches_konto_wird_weiter_importiert(migrated_db, tmp_path):
    import_flex_file(migrated_db, datei(tmp_path, "a.xml", "U8000001", "1001", "7001"))
    import_flex_file(migrated_db, datei(tmp_path, "b.xml", "U8000001", "1002", "7002"))
    assert konten(migrated_db) == ["U8000001"] and zeilen(migrated_db) == 2


def test_leere_datenbank_nimmt_das_erste_konto(migrated_db, tmp_path):
    import_flex_file(migrated_db, datei(tmp_path, "paper.xml", "DU9999999", "2001", "8001"))
    assert konten(migrated_db) == ["DU9999999"]
