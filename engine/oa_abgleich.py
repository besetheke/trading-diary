"""Importierte OA-Trades gegen bereits gebildete Ketten halten (AP-13k, Plan
§6, AP-13 zweiter Teil — „Verknüpfung und Ergebnisabgleich").

Verknüpft jeden OA-Trade über seine Klammernummer (``oa_trade``) mit den
Ketten aus ``engine.chains.bilde_chains()`` und gleicht das Ergebnis ab:
OA-``profit`` gegen ``chain.brutto_pnl``, nur solange die Kette geschlossen
ist. Die Zuordnung ist ein Nachweis/eine Auswertung, keine Schreiboperation
— nichts davon wird persistiert; die Übernahme von ``Strategy``/``Status``
in die Persistenz ist ein eigenes, noch nicht geschriebenes Paket.

Der Fingerabdruck vergleicht **nur** die Leg-Spezifikation (Right/Strike/
Expiry/Richtung als Menge), nicht die Entry Time: Das OA-Format ist ein
drittes neben TDP und Flex, seine Zeitzone ist ungeprüft (Anhang zum
OA-Format, Punkt 4). Die Klammernummer bleibt der alleinige Primärschlüssel
(§6.1, „Entschieden"); der Fingerabdruck ist nur Absicherung — eine
Abweichung verwirft die Zuordnung nicht, sondern markiert sie als
``erkennung="heuristik"`` statt ``"auto"`` (CLAUDE.md Regel 7; OF-53).

Rein im Sinne von CLAUDE.md Regel 6: keine Datenbank, keine Uhrzeit, kein
Zufall. ``zuordnungen`` und ``fehler`` sind deterministisch nach
``oa_trade`` sortiert; ``abdeckung`` bleibt ungerundet — Prozent und
Nachkommastellen sind Sache des Aufrufers.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from engine.chains import Chain
from engine.structures import Structure

# Richtung der eröffnenden Ausführung als Vorzeichen — dieselbe Bedeutung wie
# optionapp_legs.richtung (+1 long, −1 short) und damit direkt vergleichbar
# mit OALegSignatur.richtung. Nicht aufgeführte Seiten landen als None in der
# Signatur und lassen den Fingerabdruck anschlagen (heuristik), statt die
# Zuordnung still zu verwerfen (Regel 7).
RICHTUNG = {"BUY": 1, "SELL": -1}

# Mengen-Signatur eines Legs: (right, strike, expiry, richtung). None-Werte
# sind möglich, wenn Ausführung oder Instrument fehlen — sie machen den
# Vergleich unleidlich, aber nicht falsch (Regel 7: markieren, nicht werfen).
_LegSignatur = tuple[str | None, Decimal | None, date | None, int | None]


@dataclass(frozen=True)
class OALegSignatur:
    """Leg-Spezifikation eines OA-Trades, wie der Export sie liefert."""

    right: str  # 'C' / 'P'
    strike: Decimal
    expiry: date
    richtung: int  # +1 long, -1 short (wie optionapp_legs.richtung)


@dataclass(frozen=True)
class OATradeEintrag:
    """Ein importierter OA-Trade — unverändert durchgereicht, keine
    Interpretation von ``strategie``/``status`` (das ist Persistenzsache
    eines späteren Pakets)."""

    oa_trade: str
    legs: tuple[OALegSignatur, ...]
    profit: Decimal
    strategie: str
    status: str


@dataclass(frozen=True)
class OAZuordnung:
    """Eine bestehende Verknüpfung zwischen OA-Trade und Kette.

    ``erkennung`` ist ``"auto"``, wenn der Fingerabdruck bestätigt hat, und
    ``"heuristik"``, wenn er abweicht (Regel 7: die Nummer bleibt
    Primärschlüssel, die Zuordnung bleibt bestehen). ``ergebnis_eigen`` ist
    ``chain.brutto_pnl`` — ``None``, solange die Kette offen ist; dann ist
    auch ``abweichung`` ``None``.
    """

    oa_trade: str
    chain: Chain
    fingerabdruck_treffer: bool
    erkennung: str  # auto / heuristik (Regel 7)
    ergebnis_oa: Decimal
    ergebnis_eigen: Decimal | None
    abweichung: Decimal | None  # ergebnis_oa - ergebnis_eigen
    strategie: str
    status: str


@dataclass(frozen=True)
class OAFehler:
    """Ein OA-Trade ohne eindeutige Kette — nie stillschweigend verworfen
    (Abnahmekriterium des Plans)."""

    oa_trade: str
    grund: str  # 'keine_kette' / 'mehrdeutig'


@dataclass(frozen=True)
class OAAbgleichErgebnis:
    """Gesamtergebnis des Abgleichs.

    ``abdeckung`` ist der Anteil der OA-Trades mit genau einer gefundenen
    Kette — unabhängig vom Fingerabdruck-Status, denn die Zuordnung bleibt
    auch bei ``heuristik`` bestehen. Ungerundet; Grundlage der 95-%-Abnahme.
    """

    zuordnungen: tuple[OAZuordnung, ...]
    fehler: tuple[OAFehler, ...]
    abdeckung: Decimal


def _eigene_legs(
    structure: Structure,
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
) -> set[_LegSignatur]:
    """Leg-Signatur einer Structure — Muster aus
    ``werkzeuge/abgleich/golden_oa_abgleich.py._eigene_legs()``, hier als
    Produktionscode; keine Abhängigkeit dorthin, nur das Muster."""
    sig: set[_LegSignatur] = set()
    for schl in structure.leg_schluessel:
        oeffnung = executions.get(schl.open_exec_id)
        if oeffnung is None:
            continue
        instrument = instruments.get(oeffnung["conid"], {})
        sig.add(
            (
                instrument.get("right"),
                instrument.get("strike"),
                instrument.get("expiry"),
                RICHTUNG.get(oeffnung["side"]),
            )
        )
    return sig


def oa_abgleich(
    oa_trades: Iterable[OATradeEintrag],
    chains: Iterable[Chain],
    executions: Mapping[str, Mapping],
    instruments: Mapping[int, Mapping],
) -> OAAbgleichErgebnis:
    """OA-Trades gegen Ketten verknüpfen und Ergebnisse vergleichen (Vertrag
    ``auftraege/AP-13v.md``, Abschnitt „Ablauf").

    Chains ganz ohne ``oa_trade`` (DAX, ESTX50, Futures, diskretionäre Werte)
    werden ausgelassen und sind kein Fehlerfall. Leere OA-Trade-Menge ergibt
    ``Decimal(0)`` statt einer Division durch Null — eine leere Auswertung
    darf nicht als volle Abdeckung durchgehen.
    """
    # 1/2: Ketten je oa_trade-Nummer sammeln — über alle Glieder, denn
    # OA-Rolls tragen dieselbe Nummer über mehrere Glieder (mehrere
    # oa_order-Werte, AP-04k „0a"); pro Chain und Nummer genau einmal, sonst
    # wäre eine normale Roll-Kette fälschlich „mehrdeutig".
    chain_je_oa_trade: dict[str, list[Chain]] = {}
    for chain in chains:
        nummern = {g.structure.oa_trade for g in chain.glieder if g.structure.oa_trade}
        for nummer in sorted(nummern):
            chain_je_oa_trade.setdefault(nummer, []).append(chain)

    trades = list(oa_trades)
    zuordnungen: list[OAZuordnung] = []
    fehler: list[OAFehler] = []
    for trade in trades:
        # 3: Nachschlag — leer, eindeutig oder mehrdeutig; niemals still
        # wählen.
        treffer = chain_je_oa_trade.get(trade.oa_trade, [])
        if not treffer:
            fehler.append(OAFehler(oa_trade=trade.oa_trade, grund="keine_kette"))
            continue
        if len(treffer) > 1:
            fehler.append(OAFehler(oa_trade=trade.oa_trade, grund="mehrdeutig"))
            continue
        chain = treffer[0]

        # 4: Fingerabdruck — erstes Kettenglied (Eröffnungs-Momentaufnahme,
        # der Export zeigt keine Roll-Historie), Leg-Spezifikation als
        # Menge, ohne Entry Time (OF-53).
        eigene = _eigene_legs(chain.glieder[0].structure, executions, instruments)
        referenz: set[tuple[str, Decimal, date, int]] = {
            (leg.right, leg.strike, leg.expiry, leg.richtung) for leg in trade.legs
        }
        treffer_fp = eigene == referenz

        # 5: Ergebnisabgleich, nur wenn die Kette geschlossen ist.
        ergebnis_eigen = chain.brutto_pnl
        abweichung = (
            trade.profit - ergebnis_eigen if ergebnis_eigen is not None else None
        )
        zuordnungen.append(
            OAZuordnung(
                oa_trade=trade.oa_trade,
                chain=chain,
                fingerabdruck_treffer=treffer_fp,
                erkennung="auto" if treffer_fp else "heuristik",
                ergebnis_oa=trade.profit,
                ergebnis_eigen=ergebnis_eigen,
                abweichung=abweichung,
                strategie=trade.strategie,
                status=trade.status,
            )
        )

    zuordnungen.sort(key=lambda z: z.oa_trade)
    fehler.sort(key=lambda f: f.oa_trade)
    # 6: ungerundet; Darstellung (Prozent, Nachkommastellen) beim Aufrufer.
    abdeckung = (
        Decimal(len(zuordnungen)) / Decimal(len(trades)) if trades else Decimal(0)
    )
    return OAAbgleichErgebnis(
        zuordnungen=tuple(zuordnungen), fehler=tuple(fehler), abdeckung=abdeckung
    )

