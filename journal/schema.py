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
    # Pflichtfeld (CLAUDE.md, Regel 7); Wertebereich gemäß §5:
    # order_id / heuristik / manuell.
    Column("erkennung", Text, nullable=False),
    CheckConstraint(
        "erkennung IN ('order_id', 'heuristik', 'manuell')",
        name="ck_structures_erkennung",
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
    # Berichtswährung EUR (P4); die Umrechnung geschieht in der Analyseschicht
    # über fx_rates, das Ergebnis wird hier gespeichert.
    Column("netto_pnl_eur", ExactDecimal, nullable=True),
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
    CheckConstraint(
        "verknuepfungstyp IN ('open', 'roll', 'close', 'adjust')",
        name="ck_chain_links_verknuepfungstyp",
    ),
    CheckConstraint(
        "erkennung IN ('auto', 'heuristik', 'manuell')",
        name="ck_chain_links_erkennung",
    ),
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
)

campaign_overrides = Table(
    "campaign_overrides",
    metadata,
    Column("campaign_id", ForeignKey("campaigns.campaign_id"), primary_key=True),
    Column("chain_id", ForeignKey("chains.chain_id"), primary_key=True),
    Column("notiz", Text, nullable=True),
    Column("erstellt_am", DateTime, nullable=False),
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
# Aggregationsebene) legt AP-06 über eine Migration fest — dokumentiert in
# OFFENE_FRAGEN.md (OF-01).
metrics_daily = Table("metrics_daily", metadata, Column("id", Integer, primary_key=True))
metrics_by_chain = Table("metrics_by_chain", metadata, Column("id", Integer, primary_key=True))
metrics_by_campaign = Table(
    "metrics_by_campaign", metadata, Column("id", Integer, primary_key=True)
)
