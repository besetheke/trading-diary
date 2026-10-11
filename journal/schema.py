"""Schemadefinition nach §5 des Projektplans (SQLAlchemy Core).

Gliederung wie im Plan:
- Rohdaten: nie verändert, jederzeit neu importierbar (P1).
- Abgeleitet: jederzeit neu berechenbar (rebuild).
- Benutzerdaten: überleben jeden Rebuild.
- Materialisiert: Cache, verwerfbar.

Geldbeträge, Preise, Mengen und Multiplikatoren laufen durchgängig über
``ExactDecimal`` (CLAUDE.md, Regel 5) — niemals über float, keine stillen
Rundungen. ``erkennung`` ist auf den Verknüpfungstabellen Pflichtfeld und
trägt nur die im Plan vorgesehenen Werte (CLAUDE.md, Regel 7).

Aufzählungswerte sind als CHECK-Constraints am Schema gehängt: unbekannte
Werte führen zu einem Fehler statt zu stillem Verwerfen (Abnahme AP-02).
"""

import decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Table,
    Text,
    UniqueConstraint,
    types,
)

# Explizite Namen für alle Constraints — erst damit sind spätere
# Alembic-Migrationen (Autogenerate) deterministisch.
NAMENSKONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMENSKONVENTION)


class ExactDecimal(types.TypeDecorator):
    """Decimal verlustfrei in TEXT — SQLite hat keinen echten Dezimaltyp.

    Bewusst nicht ``sa.Numeric``: das landet auf SQLite über float und rundet
    damit still. Bind und Result gehen ausschließlich über Decimal; ein float
    wird beim Schreiben abgewiesen statt still umgeformt.
    """

    impl = types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, decimal.Decimal):
            raise TypeError(
                "Beträge sind als decimal.Decimal zu übergeben, "
                f"erhalten: {type(value).__name__} ({value!r})"
            )
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decimal.Decimal(value)


# ---------------------------------------------------------------------------
# Rohdaten (nie verändert)
# ---------------------------------------------------------------------------

import_runs = Table(
    "import_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    # flex / legacy_pdf / legacy_csv
    Column("quelle", Text, nullable=False),
    # Idempotenz: gleicher Dateiinhalt wird nicht doppelt importiert (AP-02)
    Column("datei_hash", Text, nullable=False, index=True),
    Column("importiert_am", DateTime, nullable=False),
    Column("zeitraum_von", Date, nullable=True),
    Column("zeitraum_bis", Date, nullable=True),
    # A = Flex-XML mit Order-IDs, B = strukturierter Auszug, C = PDF-extrahiert
    Column("qualitaetsstufe", Text, nullable=False),
    # False, sobald der Export Modell-Attribute trägt: IB nullt dann jedes
    # Realized-P&L-Feld (OF-21, OF-24). Jeder Vergleich muss die Werte eines
    # solchen Laufs verweigern — als Datenfeld, nicht als Notiz (Plan §5).
    Column("realized_pnl_verfuegbar", Boolean, nullable=False, server_default="1"),
    Column("zeilen_gesamt", Integer, nullable=False),
    Column("zeilen_neu", Integer, nullable=False),
    CheckConstraint(
        "qualitaetsstufe IN ('A', 'B', 'C')",
        name="ck_import_runs_qualitaetsstufe",
    ),
)

executions = Table(
    "executions",
    metadata,
    # Brokerseitige Ausführungs-ID: das Flex-Feld ``tradeID``, gleichbedeutend
    # mit der Spalte ``Transaction ID`` im TDP-Export (§5, gemessen: 175 von
    # 175 Treffern im Überschneidungszeitraum, null gegen ``transactionID``).
    # Der quellenübergreifende Schlüssel, §5 — der Namensgleichklang mit dem
    # Flex-Feld ``transactionID`` ist irreführend (OF-10).
    Column("exec_id", Text, primary_key=True),
    # Das Flex-Feld ``transactionID``, sekundär: dient der Abstimmung mit dem
    # Broker, taugt aber nicht als Brücke zum Altbestand (§5). Bewusst ohne
    # Eindeutigkeitszwang — die Spalte ist Beleg, nicht Schlüssel.
    Column("transaction_id", Text, nullable=True, index=True),
    Column("konto", Text, nullable=False),
    Column("conid", BigInteger, nullable=False, index=True),
    Column("symbol", Text, nullable=False),
    Column("sec_type", Text, nullable=True),
    Column("expiry", Date, nullable=True),
    Column("strike", ExactDecimal, nullable=True),
    Column("right", Text, nullable=True),
    Column("side", Text, nullable=False),
    Column("menge", ExactDecimal, nullable=False),
    Column("preis", ExactDecimal, nullable=False),
    Column("waehrung", Text, nullable=False),
    Column("multiplikator", ExactDecimal, nullable=True),
    Column("kommission", ExactDecimal, nullable=True),
    Column("kommission_waehrung", Text, nullable=True),
    Column("handelszeit", DateTime, nullable=False),
    # ib_exec_id: erste zwei Segmente bilden den exec_batch —
    # Gruppierungsschlüssel für Combo-Legs (§6.1).
    Column("ib_exec_id", Text, nullable=True, index=True),
    Column("exec_batch", Text, nullable=True, index=True),
    # Gruppiert nur Teilfills desselben Kontrakts, niemals Combo-Legs (§6.1).
    Column("ib_order_id", Text, nullable=True, index=True),
    # Rohwert der Quelle; strukturiert bei OptionApp, sonst Werkzeugnamen.
    Column("order_reference", Text, nullable=True),
    # Opake OptionApp-Kennungen (§6.1): oa_trade trägt die Verknüpfung zum
    # OA-Export, die übrigen werden nicht semantisch ausgewertet.
    Column("oa_trade", Text, nullable=True, index=True),
    Column("oa_leg", Text, nullable=True),
    Column("oa_rolle", Text, nullable=True),
    Column("oa_order", Text, nullable=True),
    Column("boerse", Text, nullable=True),
    # P7: Ereignisse sind keine Trades. Jede Zeile trägt einen Typ.
    Column("ereignistyp", Text, nullable=False),
    # Rohwert der Quelle, z. B. Ep / Ex / A / P.
    Column("ereignis_code", Text, nullable=True),
    # Trade.closePrice: der Kurs, zu dem Zuteilung oder Ausübung abgerechnet
    # wird — der Barausgleich steht hier, nicht im tradePrice (OF-25, AP-02k
    # Regel 6). Leer bei gewöhnlichen Ausführungen.
    Column("schlusskurs", ExactDecimal, nullable=True),
    # Trade.fxRateToBase: der Kurs, zu dem IB die Ausführung in die
    # Basiswährung bucht — Grundlage des IB-vergleichbaren Geldtests
    # (OF-23, OF-29). Nullable: kein Standardwert, falls die Quelle es
    # ausnahmsweise nicht liefert.
    Column("buchungskurs", ExactDecimal, nullable=True),
    Column("roh_json", Text, nullable=False),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("qualitaetsstufe", Text, nullable=False),
    CheckConstraint(
        # 'unbekannt' trägt der Ereigniscode P, der keinem der vier Typen aus
        # §1.4 zugeordnet werden kann (OF-07). P7 bleibt gewahrt: Strukturen
        # entstehen nur aus ereignistyp = 'trade'.
        "ereignistyp IN ('trade', 'expiry', 'exercise', 'assignment', 'unbekannt')",
        name="ck_executions_ereignistyp",
    ),
    CheckConstraint(
        "qualitaetsstufe IN ('A', 'B', 'C')",
        name="ck_executions_qualitaetsstufe",
    ),
)

strategies = Table(
    "strategies",
    metadata,
    # Sprechende Konvention (§1.3): stabil, nie umbenannt — nur neu angelegt
    # und alt gesetzt.
    Column("strategy_id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    # optionapp / roller / diskretionaer
    Column("quelle", Text, nullable=False),
    Column("aktiv_ab", Date, nullable=True),
    Column("aktiv_bis", Date, nullable=True),
    Column("beschreibung", Text, nullable=True),
    Column("backtest_referenz", Text, nullable=True),
    CheckConstraint(
        "quelle IN ('optionapp', 'roller', 'diskretionaer')",
        name="ck_strategies_quelle",
    ),
)

# Zuteilung ist ein Kettenübergang, kein neuer Trade (§1.4).
assignment_links = Table(
    "assignment_links",
    metadata,
    Column("option_exec_id", ForeignKey("executions.exec_id"), primary_key=True),
    Column("stock_exec_id", ForeignKey("executions.exec_id"), primary_key=True),
    # Pflichtfeld: auto / heuristik / manuell (CLAUDE.md, Regel 7)
    Column("erkennung", Text, nullable=False),
    Column("bestaetigt_am", DateTime, nullable=True),
    CheckConstraint(
        "erkennung IN ('auto', 'heuristik', 'manuell')",
        name="ck_assignment_links_erkennung",
    ),
)

instruments = Table(
    "instruments",
    metadata,
    Column("conid", BigInteger, primary_key=True),
    Column("symbol", Text, nullable=False),
    Column("underlying", Text, nullable=True),
    # OPT / FOP / FUT / STK / CASH — Filterdimension in jeder Auswertung,
    # Grundlage der steuerlichen Trennung (§1.1).
    Column("asset_class", Text, nullable=False),
    Column("expiry", Date, nullable=True),
    Column("strike", ExactDecimal, nullable=True),
    Column("right", Text, nullable=True),
    Column("multiplikator", ExactDecimal, nullable=True),
    # Berichtsgröße, geht nicht in den P&L ein (OF-14): der Punktwert eines
    # Futures steht in ``multiplikator``. Ein echter Tickwert — der Wert der
    # kleinsten Preisbewegung — wäre ohne Tickgröße nicht umrechenbar.
    Column("tickwert", ExactDecimal, nullable=True),
    Column("waehrung", Text, nullable=True),
    # Periodenende der Quelldatei, aus der dieser Stand stammt (§6.2,
    # „Reihenfolgeunabhängigkeit des Imports"): nur eine jüngere Quelle
    # überschreibt, eine ältere ergänzt nur Leerstellen. Leer heißt
    # „Periode unbekannt" und verliert damit gegen jede datierte Quelle.
    Column("quell_periodenende", Date, nullable=True),
    # SecurityInfo.settlementPolicyMethod: entscheidet bei Zuteilung und
    # Ausübung zwischen Lieferung des Basiswerts und Barausgleich (OF-25,
    # AP-02k Regel 6). Leer, wenn die Quelle nichts liefert — das Matching
    # (AP-03) bricht dann bei einer betroffenen Zeile ab.
    Column("abwicklungsart", Text, nullable=True),
    # Zugang einer Kapitalmaßnahme (OF-23): der Lieferumfang ist nach einer
    # Optionsanpassung nicht mehr standardisiert — Strikes und Multiplikatoren
    # dürfen die Analytik dann nicht mit gewöhnlichen Kontrakten vergleichen.
    Column("angepasst", Boolean, nullable=False, server_default="0"),
    CheckConstraint(
        "asset_class IN ('OPT', 'FOP', 'FUT', 'STK', 'CASH')",
        name="ck_instruments_asset_class",
    ),
    CheckConstraint(
        "abwicklungsart IN ('lieferung', 'barausgleich')",
        name="ck_instruments_abwicklungsart",
    ),
)

corporate_actions = Table(
    "corporate_actions",
    metadata,
    Column("id", Integer, primary_key=True),
    # Gruppiert Abgang und Zugang derselben Maßnahme (IBs actionID, OF-23):
    # IB bucht eine Kapitalmaßnahme nicht als Faktor auf derselben conid,
    # sondern als Abgang auf der alten und Zugang auf einer neuen — gemessen
    # an allen 10 Maßnahmen der Golden-Exporte, ausnahmslos.
    Column("aktion_id", Text, nullable=False, index=True),
    Column("konto", Text, nullable=False),
    # Rohwert der Quelle (z. B. FS, RS, TO, TC, FI, DI) — die Typen aus der
    # Vor-OF-23-Fassung (Split/Reverse/Merger/Spinoff) waren nicht gemessen,
    # sondern geraten; kein CHECK, bis eine echte Taxonomie vorliegt.
    Column("typ", Text, nullable=False),
    Column("stichtag", Date, nullable=False),
    # NULL bei reinem Zugang (z. B. DI) — keine abgebende Seite.
    Column("alter_conid", BigInteger, nullable=True, index=True),
    Column("alte_menge", ExactDecimal, nullable=True),
    Column("neuer_conid", BigInteger, nullable=False, index=True),
    Column("neue_menge", ExactDecimal, nullable=False),
    # IBs Kostenangabe für den Zugang (costBasis), falls geliefert — nur bei
    # reinem Zugang relevant. Fehlt sie, bleibt das Lot 'basis_ungeklaert'
    # (legs.basis_ungeklaert) statt stillschweigend mit Kosten 0 zu öffnen.
    Column("kosten_neu", ExactDecimal, nullable=True),
    Column("roh_json", Text, nullable=True),
)

# ---------------------------------------------------------------------------
# Flex-Sektionen (Rohdaten, AP-02)
#
# Die Sektionen aus §6.2 werden beim Flex-Import mitgelesen und jede in ihre
# eigene Tabelle gestellt — Rohdaten im Sinne von P1, jede Zeile trägt das
# vollständige Attributbild in ``roh_json``. Die Spalten daneben sind die
# unmittelbar benötigten Felder; alles Weitere bleibt im JSON erschlossen.
# Die fachliche Verdichtung (z. B. CorporateActions → corporate_actions,
# SecuritiesInfo → instruments) gehört den Folgpaketen, nicht dem Import.
#
# Keine Dubletten über Importläufe hinweg (Abnahme AP-02, OF-09): Jede Zeile
# trägt Konto und Quellschlüssel, das Paar ist eindeutig. Der Quellschlüssel
# ist die ``transactionID`` der Quelle, wo sie vorhanden ist, sonst ein
# Inhalts-Hash mit laufender Nummer je Datei — zwei inhaltsgleiche Buchungen
# derselben Datei bleiben so zwei Zeilen. Eine schon vorhandene Zeile wird
# nicht überschrieben; ``import_run_id`` nennt den Lauf, der sie zuerst sah.
# ---------------------------------------------------------------------------

flex_open_positions = Table(
    "flex_open_positions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    Column("quell_schluessel", Text, nullable=False),
    # Bestand zum Stichtag: reportDate der Zeile, sonst toDate des Statements.
    Column("stichtag", Date, nullable=False),
    Column("conid", BigInteger, nullable=False, index=True),
    Column("symbol", Text, nullable=False),
    Column("asset_class", Text, nullable=False),
    # Bestandsabgleich an den Periodengrenzen (§6.2): Kostenbasis und
    # unrealisiertes Ergebnis sind die beiden Abgleichswerte.
    Column("menge", ExactDecimal, nullable=False),
    Column("kostenbasis_preis", ExactDecimal, nullable=True),
    Column("fifo_pnl_unrealisiert", ExactDecimal, nullable=True),
    Column("waehrung", Text, nullable=False),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint("konto", "quell_schluessel", name="uq_flex_open_positions_quell_schluessel"),
)

flex_cash_transactions = Table(
    "flex_cash_transactions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    Column("quell_schluessel", Text, nullable=False),
    Column("datum", DateTime, nullable=False),
    # Zinsen, Quellensteuer, Dividenden, Gebühren, Einzahlungen (§6.1)
    Column("typ", Text, nullable=False),
    Column("betrag", ExactDecimal, nullable=False),
    Column("waehrung", Text, nullable=False),
    Column("beschreibung", Text, nullable=True),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint(
        "konto", "quell_schluessel", name="uq_flex_cash_transactions_quell_schluessel"
    ),
)

# AP-02n: Kontowert und Überleitung (OF-77). Je Abschnitt einige Kernspalten,
# der vollständige Rohsatz in roh_json. Schlüssel wie bei den übrigen
# Flex-Sektionen (konto, quell_schluessel): Bewegungsdaten, die erste Quelle
# gewinnt, nichts wird überschrieben.

flex_nav_tage = Table(
    "flex_nav_tage",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    # nav:<reportDate> — ein Kontowert je Konto und Tag.
    Column("quell_schluessel", Text, nullable=False),
    Column("datum", Date, nullable=False, index=True),
    Column("waehrung", Text, nullable=False),   # Basiswährung (EUR)
    Column("cash", ExactDecimal, nullable=True),
    Column("aktien", ExactDecimal, nullable=True),
    Column("optionen", ExactDecimal, nullable=True),
    Column("rohstoffe", ExactDecimal, nullable=True),  # IB: commodities (Futures)
    Column("fonds", ExactDecimal, nullable=True),
    Column("anleihen", ExactDecimal, nullable=True),
    Column("dividenden_abgrenzung", ExactDecimal, nullable=True),
    Column("zins_abgrenzung", ExactDecimal, nullable=True),
    Column("gesamt", ExactDecimal, nullable=False),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint("konto", "quell_schluessel", name="uq_flex_nav_tage_quell_schluessel"),
)

flex_change_in_nav = Table(
    "flex_change_in_nav",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    # cinav:<fromDate>|<toDate> — eine Überleitung je Statementzeitraum.
    Column("quell_schluessel", Text, nullable=False),
    Column("von", Date, nullable=False),
    Column("bis", Date, nullable=False),
    Column("waehrung", Text, nullable=False),
    Column("anfangswert", ExactDecimal, nullable=False),
    Column("endwert", ExactDecimal, nullable=False),
    Column("realisiert", ExactDecimal, nullable=True),
    Column("veraenderung_unrealisiert", ExactDecimal, nullable=True),
    Column("marktbewertung", ExactDecimal, nullable=True),     # IB: mtm
    Column("ein_auszahlungen", ExactDecimal, nullable=True),
    Column("dividenden", ExactDecimal, nullable=True),
    Column("zinsen", ExactDecimal, nullable=True),
    Column("kommissionen", ExactDecimal, nullable=True),
    Column("waehrungseffekt", ExactDecimal, nullable=True),    # IB: fxTranslation
    Column("twr", ExactDecimal, nullable=True),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint("konto", "quell_schluessel", name="uq_flex_change_in_nav_quell_schluessel"),
)

flex_cash_report = Table(
    "flex_cash_report",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    # cash:<fromDate>|<toDate>|<currency>|<levelOfDetail>
    Column("quell_schluessel", Text, nullable=False),
    Column("von", Date, nullable=False),
    Column("bis", Date, nullable=False),
    Column("waehrung", Text, nullable=False),
    Column("ebene", Text, nullable=True),                       # IB: levelOfDetail
    Column("anfangsbestand", ExactDecimal, nullable=True),
    Column("endbestand", ExactDecimal, nullable=True),
    Column("ein_auszahlungen", ExactDecimal, nullable=True),
    Column("kommissionen", ExactDecimal, nullable=True),
    Column("dividenden", ExactDecimal, nullable=True),
    Column("zinsen", ExactDecimal, nullable=True),              # IB: brokerInterest
    Column("waehrungseffekt", ExactDecimal, nullable=True),     # IB: fxTranslationGainLoss
    Column("roh_json", Text, nullable=False),
    UniqueConstraint("konto", "quell_schluessel", name="uq_flex_cash_report_quell_schluessel"),
)

# AP-02p: IBs realisiertes Ergebnis je Ausführung (``fifoPnlRealized``, netto nach
# Kommission, in Positionswährung) mit IBs Kurs in die Basiswährung. Eigene
# Tabelle, weil ``executions`` nie überschrieben wird (Regel 4) und die erste
# Quelle gewinnt: Eine ältere Abfrage ohne dieses Feld ließ es dort für immer
# leer (OF-78, 11.949 Zeilen). Hier wird der Wert aufgenommen, sobald irgendeine
# Datei ihn liefert; ``0`` ist ein Wert (eröffnende Zeile), „nicht geliefert"
# erzeugt keine Zeile.
flex_ib_realized = Table(
    "flex_ib_realized",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    # trade:<tradeID> — eine Zeile je Ausführung und Konto.
    Column("quell_schluessel", Text, nullable=False),
    Column("exec_id", Text, nullable=False, index=True),
    Column("handelstag", Date, nullable=False, index=True),
    Column("conid", BigInteger, nullable=False),
    Column("waehrung", Text, nullable=False),
    Column("fifo_pnl_realized", ExactDecimal, nullable=False),
    Column("fx_rate_to_base", ExactDecimal, nullable=True),
    UniqueConstraint("konto", "quell_schluessel", name="uq_flex_ib_realized_quell_schluessel"),
)

flex_corporate_actions = Table(
    "flex_corporate_actions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    Column("quell_schluessel", Text, nullable=False),
    Column("conid", BigInteger, nullable=True, index=True),
    # Rohwert der Quelle (z. B. SSplit); die fachliche Zuordnung auf die
    # Typen aus corporate_actions macht AP-03.
    Column("typ", Text, nullable=False),
    Column("datum", DateTime, nullable=False),
    Column("beschreibung", Text, nullable=True),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint(
        "konto", "quell_schluessel", name="uq_flex_corporate_actions_quell_schluessel"
    ),
)

flex_transfers = Table(
    "flex_transfers",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("konto", Text, nullable=False),
    Column("quell_schluessel", Text, nullable=False),
    Column("conid", BigInteger, nullable=True, index=True),
    Column("typ", Text, nullable=False),
    Column("datum", DateTime, nullable=False),
    Column("beschreibung", Text, nullable=True),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint("konto", "quell_schluessel", name="uq_flex_transfers_quell_schluessel"),
)

# Stammdaten: conid ist der natürliche Schlüssel. Überschrieben wird nur aus
# einer jüngeren Quelle — maßgeblich ist das Periodenende der Quelldatei, nicht
# die Importreihenfolge (§6.2, AP-02a; Details in OF-09).
flex_securities_info = Table(
    "flex_securities_info",
    metadata,
    Column("conid", BigInteger, primary_key=True),
    Column("symbol", Text, nullable=False),
    Column("underlying", Text, nullable=True),
    Column("asset_class", Text, nullable=False),
    Column("expiry", Date, nullable=True),
    Column("strike", ExactDecimal, nullable=True),
    Column("right", Text, nullable=True),
    Column("multiplikator", ExactDecimal, nullable=True),
    Column("waehrung", Text, nullable=True),
    Column("roh_json", Text, nullable=False),
    # Wie bei ``instruments``: Periodenende der Quelldatei (§6.2).
    Column("quell_periodenende", Date, nullable=True),
)

# ---------------------------------------------------------------------------
# Abgeleitet (jederzeit neu berechenbar)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# OptionApp-Trade-Export (AP-13, Rohdaten)
# ---------------------------------------------------------------------------

# Der Export ist eine XLSX-Datei mit einem Arbeitsblatt `Trades` und elf
# Spalten; Format und Fallstricke stehen in
# `auftraege/AP-13-anhang-oa-format.md`. Die Tabellen halten den Rohbestand,
# die Verknüpfung mit den Ketten macht AP-04/AP-13 (starkes Modell).
optionapp_trades = Table(
    "optionapp_trades",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    # Klammernummer am Ende von `Name` — der einzige Verknüpfungsschlüssel
    # (§6.1); läuft gegen executions.oa_trade.
    Column("oa_trade", Text, nullable=False, index=True),
    # Zeitstempel im dritten Format (JJJJ/MM/TT hh:mm:ss), Zeitzone ungeprüft:
    # ausdrücklich NICHT zum Abgleich verwenden (Anhang, Punkt 4).
    Column("entry_zeit", DateTime, nullable=False),
    Column("schluss_zeit", DateTime, nullable=True),
    Column("strategie", Text, nullable=False),
    # Freier, vom Nutzer gepflegter Text — trägt keinen Schlüssel.
    Column("name_roh", Text, nullable=False),
    Column("strikes_roh", Text, nullable=False),
    # `Quantity` ist ein Verhältnis n/m; beide Zahlen getrennt, weil ihre
    # Gleichheit nicht vorausgesetzt werden darf.
    Column("menge_zaehler", ExactDecimal, nullable=False),
    Column("menge_nenner", ExactDecimal, nullable=False),
    Column("offen_preis", ExactDecimal, nullable=True),
    Column("schluss_preis", ExactDecimal, nullable=True),
    # `-` heißt „kein Stop" und ist etwas anderes als `0`: Rohwert bleibt
    # erhalten, der Zahlwert ist NULL, wenn kein Stop gesetzt war.
    Column("stop_roh", Text, nullable=False),
    Column("stop_wert", ExactDecimal, nullable=True),
    # `Profit` steht als Text im deutschen Format mit Währungszeichen.
    Column("profit", ExactDecimal, nullable=False),
    Column("profit_waehrung", Text, nullable=True),
    Column("status", Text, nullable=False),
    Column("roh_json", Text, nullable=False),
    UniqueConstraint("oa_trade", name="uq_optionapp_trades_oa_trade"),
)

optionapp_legs = Table(
    "optionapp_legs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "optionapp_trade_id",
        ForeignKey("optionapp_trades.id"),
        nullable=False,
        index=True,
    ),
    # Reihenfolge innerhalb der Spalte `Strikes` — die Grammatik ist
    # positionsbehaftet, zwei bis vier Legs je Trade.
    Column("position", Integer, nullable=False),
    # +1 long, -1 short (führendes Minus in der Leg-Grammatik).
    Column("richtung", Integer, nullable=False),
    Column("menge", ExactDecimal, nullable=False),
    # Rohwert der Quelle: 'C' oder 'P'.
    Column("right", Text, nullable=False),
    Column("strike", ExactDecimal, nullable=False),
    Column("expiry", Date, nullable=False),
    Column("roh", Text, nullable=False),
    UniqueConstraint(
        "optionapp_trade_id", "position", name="uq_optionapp_legs_position"
    ),
    CheckConstraint("richtung IN (-1, 1)", name="ck_optionapp_legs_richtung"),
    CheckConstraint("\"right\" IN ('C', 'P')", name="ck_optionapp_legs_right"),
)

legs = Table(
    "legs",
    metadata,
    Column("leg_id", Integer, primary_key=True),
    Column("conid", BigInteger, nullable=False, index=True),
    Column("open_exec_id", ForeignKey("executions.exec_id"), nullable=False, index=True),
    # Offene Legs haben keine Schließung.
    Column("close_exec_id", ForeignKey("executions.exec_id"), nullable=True, index=True),
    Column("menge", ExactDecimal, nullable=False),
    Column("matching_methode", Text, nullable=False),
    Column("brutto_pnl", ExactDecimal, nullable=True),
    Column("kommission_gesamt", ExactDecimal, nullable=True),
    Column("offen_ja_nein", Boolean, nullable=False),
    # Ein reiner Zugang aus einer Kapitalmaßnahme, für den IB keine
    # Kostenangabe liefert (OF-23): kein stiller Nullwert, sondern markiert —
    # eine Nullbasis erzeugte beim Verkauf einen Scheingewinn in voller Höhe.
    Column("basis_ungeklaert", Boolean, nullable=False, server_default="0"),
    # AP-03vz2: Faktor der Kapitalmaßnahmen an Eröffnungs- und Schließungsausführung
    # (neue ÷ alte Menge); 1 ohne Maßnahme. Die EUR-Analytik rechnet mit
    # Preis ÷ Faktor, weil ``menge`` in neuen Stücken steht, die Ausführung
    # noch in alten.
    Column("open_faktor", ExactDecimal, nullable=False, server_default="1"),
    Column("close_faktor", ExactDecimal, nullable=False, server_default="1"),
    # Entleerbar: nicht jede Leg landet in einer Struktur. Der P7-Vorfilter
    # schließt alles aus, was nicht per Trade eröffnet wurde (AP-04, Block A).
    Column("structure_id", ForeignKey("structures.structure_id"), nullable=True, index=True),
    # AP-04sw: Pflichtfeld in jeder abgeleiteten Tabelle (Plan §5, „Zwei
    # Sichten"). Dieselbe Ausführung erscheint mit eigener Zuordnung in
    # beiden Sichten — nie in einer Abfrage gemischt.
    Column("sicht", Text, nullable=False, server_default="konto"),
    CheckConstraint("sicht IN ('konto', 'kette')", name="ck_legs_sicht"),
)

structures = Table(
    "structures",
    metadata,
    Column("structure_id", Integer, primary_key=True),
    Column("asset_class", Text, nullable=False),
    # §1.3: jede Structure trägt eine Strategie-Kennung. Die Sammelkennung für
    # diskretionäre Trades ist E13/E14 und steht noch aus, deshalb zunächst
    # entleerbar.
    Column("strategy_id", ForeignKey("strategies.strategy_id"), nullable=True),
    # BCS / BPS / Vertical / Single / Stock / Future / Custom; OptionApp
    # handelt auch n-Leg-Gebilde (§6.1), deshalb keine Zwei-Leg-Annahme.
    Column("typ", Text, nullable=False),
    Column("underlying", Text, nullable=False),
    Column("expiry", Date, nullable=True),
    Column("short_strike", ExactDecimal, nullable=True),
    Column("long_strike", ExactDecimal, nullable=True),
    Column("breite", ExactDecimal, nullable=True),
    Column("menge", ExactDecimal, nullable=False),
    Column("eroeffnet_am", DateTime, nullable=False),
    Column("geschlossen_am", DateTime, nullable=True),
    Column("dte_bei_eroeffnung", Integer, nullable=True),
    Column("status", Text, nullable=True),
    Column("brutto_pnl", ExactDecimal, nullable=True),
    Column("kommission", ExactDecimal, nullable=True),
    Column("netto_pnl", ExactDecimal, nullable=True),
    Column("waehrung", Text, nullable=False),
    # Nettoprämie je Kontrakt, Verkauf positiv (AP-07p). An genau diesen
    # beiden Zahlen erkennt man einen Vorgang wieder und unterscheidet einen
    # Roll von einem Wiedereinstieg (OF-41). `schlusspreis` bleibt leer,
    # solange die Struktur offen ist.
    Column("eroeffnungspreis", ExactDecimal, nullable=True),
    Column("schlusspreis", ExactDecimal, nullable=True),
    # AP-13w: roh aus dem OA-Export, je Kette auf ihre Strukturen gespiegelt
    # (OA kennt keine feinere Ebene). `oa_status` überschreibt nie `status`
    # (Brokertatsache), sondern ergänzt ihn (§6, AP-13). `oa_erkennung` ist
    # das Pflichtfeld für die automatisch erzeugte Verknüpfung (Regel 7).
    Column("oa_strategie", Text, nullable=True),
    Column("oa_status", Text, nullable=True),
    Column("oa_erkennung", Text, nullable=True),
    # Pflichtfeld (CLAUDE.md, Regel 7); Wertebereich gemäß §5:
    # order_id / heuristik / manuell.
    Column("erkennung", Text, nullable=False),
    # Inhaltlicher Schlüssel, damit ein Rebuild abgleichen statt neu anlegen
    # kann: die aufsteigend sortierten `open_exec_id` der Legs, mit `|`
    # verbunden. Ohne ihn bekäme dieselbe Struktur bei jedem Lauf eine neue
    # Nummer, und die Fremdschlüssel in `chain_overrides` zeigten ins Leere
    # (AP-04v).
    Column("natur_schluessel", Text, nullable=False),
    # AP-04sw: wie an `legs` — jede Struktur existiert als zwei Zeilen, je
    # eine pro Sicht, mit demselben Naturschlüssel. Die Eindeutigkeit gilt
    # deshalb nur noch zusammen mit `sicht`.
    Column("sicht", Text, nullable=False, server_default="konto"),
    CheckConstraint(
        "erkennung IN ('order_id', 'heuristik', 'manuell')",
        name="ck_structures_erkennung",
    ),
    CheckConstraint(
        "oa_erkennung IN ('auto', 'heuristik')",
        name="ck_structures_oa_erkennung",
    ),
    CheckConstraint("sicht IN ('konto', 'kette')", name="ck_structures_sicht"),
    UniqueConstraint(
        "natur_schluessel", "sicht", name="uq_structures_natur_schluessel_sicht"
    ),
)

chains = Table(
    "chains",
    metadata,
    Column("chain_id", Integer, primary_key=True),
    Column("underlying", Text, nullable=False),
    Column("asset_class", Text, nullable=False),
    # Call / Put / n.a.
    Column("seite", Text, nullable=True),
    Column("eroeffnet_am", DateTime, nullable=False),
    Column("beendet_am", DateTime, nullable=True),
    # Roll-Anzahl ist Kennzahl und Filter, nie Eintrittskriterium (§1).
    Column("anzahl_rolls", Integer, nullable=False),
    # Verfall / Geschlossen / Assigned / Offen
    Column("endzustand", Text, nullable=True),
    # Berichtswährung EUR (P4) — bleibt dauerhaft leer (AP-06, Entscheidung
    # E2): Der Rebuild setzt die Spalte bei jedem Lauf auf None, die
    # EUR-Materialisierung liegt in metrics_by_chain
    # (netto_eur_wirtschaftlich / netto_eur_ib).
    Column("netto_pnl_eur", ExactDecimal, nullable=True),
    # Wie bei `structures`: der Naturschlüssel der eröffnenden Struktur, mit
    # `k:` davor. Rolls hängen hinten an, der Kettenanfang bleibt derselbe —
    # deshalb überlebt die `chain_id` einen Rebuild (AP-04v).
    Column("natur_schluessel", Text, nullable=False),
    # AP-13w: wie an `structures` — roh aus dem OA-Export, `oa_erkennung`
    # ist das Pflichtfeld der automatisch erzeugten Verknüpfung (Regel 7).
    Column("oa_strategie", Text, nullable=True),
    Column("oa_status", Text, nullable=True),
    Column("oa_erkennung", Text, nullable=True),
    # AP-04sw: wie an `structures` — Eindeutigkeit nur noch je Sicht.
    Column("sicht", Text, nullable=False, server_default="konto"),
    CheckConstraint(
        "oa_erkennung IN ('auto', 'heuristik')",
        name="ck_chains_oa_erkennung",
    ),
    CheckConstraint("sicht IN ('konto', 'kette')", name="ck_chains_sicht"),
    UniqueConstraint("natur_schluessel", "sicht", name="uq_chains_natur_schluessel_sicht"),
)

chain_links = Table(
    "chain_links",
    metadata,
    Column("chain_id", ForeignKey("chains.chain_id"), primary_key=True),
    Column("structure_id", ForeignKey("structures.structure_id"), primary_key=True, index=True),
    Column("sequenz", Integer, nullable=False),
    # open / roll / close / adjust
    Column("verknuepfungstyp", Text, nullable=False),
    Column("erkennung", Text, nullable=False),
    # AP-04sw: Pflichtfeld wie an den anderen drei abgeleiteten Tabellen.
    Column("sicht", Text, nullable=False, server_default="konto"),
    CheckConstraint(
        "verknuepfungstyp IN ('open', 'roll', 'close', 'adjust')",
        name="ck_chain_links_verknuepfungstyp",
    ),
    CheckConstraint(
        "erkennung IN ('auto', 'heuristik', 'manuell')",
        name="ck_chain_links_erkennung",
    ),
    CheckConstraint("sicht IN ('konto', 'kette')", name="ck_chain_links_sicht"),
)

campaigns = Table(
    "campaigns",
    metadata,
    Column("campaign_id", Integer, primary_key=True),
    Column("underlying", Text, nullable=False),
    Column("eroeffnet_am", DateTime, nullable=False),
    Column("beendet_am", DateTime, nullable=True),
    Column("netto_pnl_eur", ExactDecimal, nullable=True),
)

campaign_links = Table(
    "campaign_links",
    metadata,
    Column("campaign_id", ForeignKey("campaigns.campaign_id"), primary_key=True),
    Column("chain_id", ForeignKey("chains.chain_id"), primary_key=True, index=True),
    # ic_leg / financing / contract_roll / independent
    Column("beziehungstyp", Text, nullable=False),
    Column("erkennung", Text, nullable=False),
    Column("bestaetigt_am", DateTime, nullable=True),
    CheckConstraint(
        "beziehungstyp IN ('ic_leg', 'financing', 'contract_roll', 'independent')",
        name="ck_campaign_links_beziehungstyp",
    ),
    CheckConstraint(
        "erkennung IN ('auto', 'heuristik', 'manuell')",
        name="ck_campaign_links_erkennung",
    ),
)

# ---------------------------------------------------------------------------
# Benutzerdaten (überleben jeden Rebuild)
# ---------------------------------------------------------------------------

journal_entries = Table(
    "journal_entries",
    metadata,
    Column("id", Integer, primary_key=True),
    # campaign / chain / structure / tag — polymorph, deshalb kein FK.
    Column("scope_typ", Text, nullable=False),
    Column("scope_id", Text, nullable=False),
    Column("text", Text, nullable=False),
    Column("erstellt_am", DateTime, nullable=False),
    Column("geaendert_am", DateTime, nullable=True),
    CheckConstraint(
        "scope_typ IN ('campaign', 'chain', 'structure', 'tag')",
        name="ck_journal_entries_scope_typ",
    ),
)

tags = Table(
    "tags",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", Text, nullable=False, unique=True),
)

entity_tags = Table(
    "entity_tags",
    metadata,
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
    Column("scope_typ", Text, primary_key=True),
    Column("scope_id", Text, primary_key=True),
    CheckConstraint(
        "scope_typ IN ('campaign', 'chain', 'structure', 'tag')",
        name="ck_entity_tags_scope_typ",
    ),
)

attachments = Table(
    "attachments",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scope_typ", Text, nullable=False),
    Column("scope_id", Text, nullable=False),
    Column("dateipfad", Text, nullable=False),
    Column("mime", Text, nullable=True),
    Column("erstellt_am", DateTime, nullable=False),
    CheckConstraint(
        "scope_typ IN ('campaign', 'chain', 'structure', 'tag')",
        name="ck_attachments_scope_typ",
    ),
)

# Annahme, dokumentiert in OFFENE_FRAGEN.md (OF-02): Overrides spiegeln die
# manuell festgelegte Zuordnung von Struktur zu Kette beziehungsweise Kette
# zu Kampagne und sind die Grundlage, aus der der Rebuild die Erkennung
# korrigiert (AP-04).
chain_overrides = Table(
    "chain_overrides",
    metadata,
    Column("chain_id", ForeignKey("chains.chain_id"), primary_key=True),
    Column("structure_id", ForeignKey("structures.structure_id"), primary_key=True),
    Column("notiz", Text, nullable=True),
    Column("erstellt_am", DateTime, nullable=False),
    # Ablehnungen sind ebenso Benutzerdaten wie Bestätigungen (Plan §6,
    # Block B, Regel 2): Ohne sie erscheint jeder abgelehnte Rollkandidat
    # beim nächsten `rebuild` erneut. `abgelehnt` heißt „diese Struktur
    # setzt jene Kette NICHT fort".
    Column("urteil", Text, nullable=False, server_default="bestaetigt"),
    CheckConstraint(
        "urteil IN ('bestaetigt', 'abgelehnt')",
        name="ck_chain_overrides_urteil",
    ),
)

campaign_overrides = Table(
    "campaign_overrides",
    metadata,
    Column("campaign_id", ForeignKey("campaigns.campaign_id"), primary_key=True),
    Column("chain_id", ForeignKey("chains.chain_id"), primary_key=True),
    Column("notiz", Text, nullable=True),
    Column("erstellt_am", DateTime, nullable=False),
)

# AP-05d: Die Ablehnung eines Campaign-Kandidaten ist ebenso eine Entscheidung
# des Nutzers wie die Bestätigung (Plan §6, Block B, Regel 2) — ohne sie erschiene
# jedes abgelehnte Paar bei der nächsten Durchsicht erneut. `chain_id_a` ist die
# früher eröffnete bzw. bei `financing` die Bestandskette (wie
# `CampaignKandidat.kette_a`); die IDs sind Kontosicht-Ketten.
campaign_ablehnungen = Table(
    "campaign_ablehnungen",
    metadata,
    Column("chain_id_a", ForeignKey("chains.chain_id"), primary_key=True),
    Column("chain_id_b", ForeignKey("chains.chain_id"), primary_key=True),
    # ic / financing
    Column("typ", Text, nullable=False, primary_key=True),
    Column("notiz", Text, nullable=True),
    Column("erstellt_am", DateTime, nullable=False),
    CheckConstraint("typ IN ('ic', 'financing')", name="ck_campaign_ablehnungen_typ"),
)

# Brücke zum Options Roller (§4.1): Absicht (Roller) gegen Ergebnis (Journal).
roller_link = Table(
    "roller_link",
    metadata,
    Column("roller_chain_id", Text, primary_key=True),
    Column("journal_chain_id", ForeignKey("chains.chain_id"), primary_key=True),
    Column("zugeordnet_am", DateTime, nullable=False),
    Column("methode", Text, nullable=False),
)

fx_rates = Table(
    "fx_rates",
    metadata,
    Column("datum", Date, primary_key=True),
    Column("waehrung", Text, primary_key=True),
    Column("kurs_eur", ExactDecimal, nullable=False),
    Column("quelle", Text, nullable=False),
)

# ---------------------------------------------------------------------------
# Materialisiert (Cache, verwerfbar)
# ---------------------------------------------------------------------------

# Stellvertreter: der Plan nennt nur die Namen. Die eigentliche Form (Spalten,
# Aggregationsebene) legen die Tranchen von AP-06 über Migrationen fest —
# dokumentiert in OFFENE_FRAGEN.md (OF-01).
metrics_daily = Table("metrics_daily", metadata, Column("id", Integer, primary_key=True))

# AP-06 E2: EUR-Materialisierung je Kette (Cache, verwerfbar). Vollständig neu
# geschrieben von `journal kennzahlen` (Regel 11), nie vom Rebuild. chain_id
# ist je Sicht eindeutig: Ketten beider Sichten tragen eigene chain_id, jede
# Kette genau eine Zeile. NULL nur nach Regel 11 (offen oder Kursmangel).
# ON DELETE CASCADE (Löschverhalten, OF-01): Verschwindet eine Kette im
# Rebuild, fällt die Cache-Zeile mit ihr — sonst könnte der Rebuild Ketten
# nicht mehr löschen, sobald einmal Kennzahlen gelaufen ist (journal/db.py
# schaltet PRAGMA foreign_keys ein).
metrics_by_chain = Table(
    "metrics_by_chain",
    metadata,
    Column("id", Integer, primary_key=True),
    Column(
        "chain_id",
        ForeignKey("chains.chain_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    # Maßgebliche wirtschaftliche Sicht (Regel 3) …
    Column("netto_eur_wirtschaftlich", ExactDecimal, nullable=True),
    # … und die IB-vergleichbare (Regel 4); der Währungseffekt ist die
    # Differenz und wird nicht gespeichert.
    Column("netto_eur_ib", ExactDecimal, nullable=True),
)
metrics_by_campaign = Table(
    "metrics_by_campaign", metadata, Column("id", Integer, primary_key=True)
)
