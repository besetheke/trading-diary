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
    # Brokerseitige Ausführungs-ID (tradeID im Flex, Transaction ID im
    # TDP-Export) — der quellenübergreifende Schlüssel, §5.
    Column("exec_id", Text, primary_key=True),
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
    Column("roh_json", Text, nullable=False),
    Column("import_run_id", ForeignKey("import_runs.id"), nullable=False, index=True),
    Column("qualitaetsstufe", Text, nullable=False),
    CheckConstraint(
        "ereignistyp IN ('trade', 'expiry', 'exercise', 'assignment')",
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
    Column("tickwert", ExactDecimal, nullable=True),
    Column("waehrung", Text, nullable=True),
    CheckConstraint(
        "asset_class IN ('OPT', 'FOP', 'FUT', 'STK', 'CASH')",
        name="ck_instruments_asset_class",
    ),
)

corporate_actions = Table(
    "corporate_actions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("conid", BigInteger, nullable=False, index=True),
    # Split / Reverse / Merger / Spinoff
    Column("typ", Text, nullable=False),
    Column("stichtag", Date, nullable=False),
    Column("faktor", ExactDecimal, nullable=False),
    Column("roh_json", Text, nullable=True),
    CheckConstraint(
        "typ IN ('Split', 'Reverse', 'Merger', 'Spinoff')",
        name="ck_corporate_actions_typ",
    ),
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
