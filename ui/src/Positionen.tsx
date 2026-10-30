import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fehlerText, holeAktienEinkauf, holeAuswertung, holeDepot, holeFilterwerte, holeKetten, holeOaStand } from './api'
import type {
  AktieEinkauf,
  Auswertung,
  Depot,
  Filterwerte,
  Kette,
  KettenFilter,
  KettenListe,
  OaStand,
  Richtung,
  Sortierspalte,
} from './api'
import { betrag, datumDe, mengeDe, zeit, zeitDe } from './format'
import Betrag from './Betrag'
import FilterAuswertung from './FilterAuswertung'
import { useZeitraum } from './zeitraum'
import ErgebnisBegriffe from './ErgebnisBegriffe'

// Wunsch des Nutzers (11.10.2026): Vorgabe 200 Zeilen, Auswahl 50 bis 500.
const LIMITS = [50, 100, 200, 500]
const VORGABE_LIMIT = 200

// Rückfallwerte, falls GET /filterwerte (AP-07fw) nicht antwortet: Werte aus dem
// Datenbankschema (CHECK instruments.asset_class) und aus dem Wiederhersteller
// (chains.endzustand) — die Oberfläche erfindet keine. Sonst gelten die
// Auswahllisten der API.
const ANLAGEKLASSEN = ['OPT', 'FOP', 'FUT', 'STK', 'CASH']
const ENDZUSTAENDE = ['Offen', 'Geschlossen', 'Verfall', 'Assigned']

// AP-08s: Spalten der Positionsliste. Die Eröffnung steht zuerst — Datum und
// Uhrzeit in einer Zeile —, danach Basiswert, Klasse, Seite, Ende (ebenso in
// einer Zeile), Rolls, Endzustand, OA-Strategie und die abgeleiteten Werte.
// Sortiert wird ausschließlich die API (AP-07s): „sortierbar" heißt, der Kopf
// schickt sortierung/richtung mit; der erste Klick wählt die natürliche
// Richtung (neueste zuerst bei Zeit und Rolls, A bis Z bei Text), jeder
// weitere Klick kehrt um.
type SpaltenId =
  | 'eroeffnet_am'
  | 'underlying'
  | 'strikes_aktuell'
  | 'verfall_aktuell'
  | 'asset_class'
  | 'seite'
  | 'menge'
  | 'beendet_am'
  | 'anzahl_rolls'
  | 'endzustand'
  | 'oa_strategie'
  | 'eroeffnungspreis'
  | 'schlusspreis'
  | 'struktur_summe_netto'
  | 'unrealisiert_eur'
  | 'praemie_offen_eur'
  | 'praemie_aktuell_eur'
  | 'waehrung'

interface Spalte {
  titel: string
  sortierbar: boolean
  ersteRichtung?: Richtung
  // Erklärung im Tooltip des Spaltenkopfs (bei sortierbaren Spalten).
  hinweis?: string
}

const SPALTEN: Record<SpaltenId, Spalte> = {
  eroeffnet_am: { titel: 'Eröffnung', sortierbar: true, ersteRichtung: 'desc' },
  underlying: { titel: 'Basiswert', sortierbar: true, ersteRichtung: 'asc' },
  // AP-21: Strikes und Verfall des jüngsten Glieds (Rolls ändern sie), je Seite zusammengestellt.
  strikes_aktuell: { titel: 'Strikes', sortierbar: false, hinweis: 'Strikes des jüngsten Glieds der Kette' },
  verfall_aktuell: { titel: 'Verfall', sortierbar: false, hinweis: 'Verfall des jüngsten Glieds der Kette' },
  asset_class: { titel: 'Klasse', sortierbar: true, ersteRichtung: 'asc' },
  seite: { titel: 'Seite', sortierbar: true, ersteRichtung: 'asc' },
  // Kontrakte bzw. Stück der Eröffnung. Wie die Preise je Seite zusammengestellt,
  // nicht sortierbar (AP-07s).
  menge: { titel: 'Anzahl', sortierbar: false },
  beendet_am: { titel: 'Ende', sortierbar: true, ersteRichtung: 'desc' },
  anzahl_rolls: {
    titel: 'Rolls (belegt)',
    sortierbar: true,
    ersteRichtung: 'desc',
    hinweis:
      'Nur Rolls, die eine gemeinsame Order belegt. Ein Roll in getrennten Orders ist ein Vorschlag und zählt nicht.',
  },
  endzustand: { titel: 'Endzustand', sortierbar: true, ersteRichtung: 'asc' },
  oa_strategie: { titel: 'OA-Strategie', sortierbar: true, ersteRichtung: 'asc' },
  // Preise, Ergebnis und Währung sind je Seite zusammengestellt — nicht
  // sortierbar (AP-07s): Eine Sortierung nur über die aktuelle Seite wäre
  // irreführend; der Kopf sagt das im title.
  eroeffnungspreis: { titel: 'Preis auf', sortierbar: false },
  schlusspreis: { titel: 'Preis zu', sortierbar: false },
  struktur_summe_netto: { titel: 'Ergebnis netto¹', sortierbar: false },
  // AP-07ku: offene Legs zu IBs letztem Marktwert gegen den Einstand, EUR.
  unrealisiert_eur: { titel: 'Unrealisiert²', sortierbar: false },
  // AP-06sf: Prämienwert der offenen Position in EUR, Verkäufersicht.
  praemie_offen_eur: {
    titel: 'Prämie offen³',
    sortierbar: false,
  },
  praemie_aktuell_eur: {
    titel: 'Prämie aktuell³',
    sortierbar: false,
  },
  waehrung: { titel: 'Währung', sortierbar: false },
}

const ALLE_SPALTEN = Object.keys(SPALTEN) as SpaltenId[]
const STANDARD_SPALTEN: SpaltenId[] = [...ALLE_SPALTEN]
const ZAHL_SPALTEN: SpaltenId[] = [
  'menge',
  'anzahl_rolls',
  'eroeffnungspreis',
  'schlusspreis',
  'struktur_summe_netto',
  'unrealisiert_eur',
  'praemie_offen_eur',
  'praemie_aktuell_eur',
]
const NICHT_SORTIERBAR_TITEL =
  'Nicht sortierbar — der Wert gilt nur für die angezeigte Seite'

function istSortierbareSpalte(wert: string | null): wert is Sortierspalte {
  return (
    wert !== null && ALLE_SPALTEN.some((id) => id === wert && SPALTEN[id].sortierbar)
  )
}

// AP-08s, Punkt 3: Auswahl und Reihenfolge der Spalten stehen im Browser.
// Fehlt der Speicher oder ist der Inhalt unlesbar oder ungültig, gilt die
// Vorgabe — vollständig oder gar nicht, nichts wird still repariert.
// AP-07ku: v3 kennt die Spalte „Unrealisiert“. Eine unter v2 gespeicherte Wahl
// wird übernommen und um die neue Spalte ergänzt (nach „Ergebnis netto“).
// AP-06sf: v4 kennt „Prämie offen/aktuell“; eine v3-Wahl wird um beide ergänzt.
const SPALTEN_SCHLUESSEL = 'positionen.spalten.v4'

function leseSpalten(): SpaltenId[] | null {
  try {
    let roh = window.localStorage.getItem(SPALTEN_SCHLUESSEL)
    if (roh === null) {
      const alt =
        window.localStorage.getItem('positionen.spalten.v3') ??
        window.localStorage.getItem('positionen.spalten.v2')
      if (alt === null) return null
      const liste = JSON.parse(alt) as string[]
      if (Array.isArray(liste) && !liste.includes('unrealisiert_eur')) {
        const nach = liste.indexOf('struktur_summe_netto')
        liste.splice(nach >= 0 ? nach + 1 : liste.length, 0, 'unrealisiert_eur')
      }
      if (Array.isArray(liste) && !liste.includes('praemie_offen_eur')) {
        const nach = liste.indexOf('unrealisiert_eur')
        liste.splice(nach >= 0 ? nach + 1 : liste.length, 0, 'praemie_offen_eur', 'praemie_aktuell_eur')
      }
      roh = JSON.stringify(liste)
    }
    const geparst: unknown = JSON.parse(roh)
    if (!Array.isArray(geparst) || geparst.length === 0) return null
    if (!geparst.every((eintrag) => ALLE_SPALTEN.includes(eintrag as SpaltenId))) {
      return null
    }
    if (new Set(geparst).size !== geparst.length) return null
    return geparst as SpaltenId[]
  } catch {
    return null
  }
}

// AP-08g2b: alle Filter der Liste. Sie stehen in der Adresse (Lesezeichen,
// Neuladen) unter den Namen der API; der Entwurf hält die Eingaben, bis
// „Anwenden" sie dorthin schreibt.
interface Entwurf {
  basiswert: string
  anlageklasse: string
  waehrung: string
  strategie: string
  seite: string
  endzustand: string
  eroeffnetAb: string
  eroeffnetBis: string
  geschlossenAb: string
  geschlossenBis: string
  minRolls: string
  maxRolls: string
}

const LEERER_ENTWURF: Entwurf = {
  basiswert: '',
  anlageklasse: '',
  waehrung: '',
  strategie: '',
  seite: '',
  endzustand: '',
  eroeffnetAb: '',
  eroeffnetBis: '',
  geschlossenAb: '',
  geschlossenBis: '',
  minRolls: '',
  maxRolls: '',
}

const FILTER_PARAMETER: [keyof Entwurf, string][] = [
  ['basiswert', 'basiswert'],
  ['anlageklasse', 'anlageklasse'],
  ['waehrung', 'waehrung'],
  ['strategie', 'strategie'],
  ['seite', 'seite'],
  ['endzustand', 'endzustand'],
  ['eroeffnetAb', 'eroeffnet_ab'],
  ['eroeffnetBis', 'eroeffnet_bis'],
  ['geschlossenAb', 'geschlossen_ab'],
  ['geschlossenBis', 'geschlossen_bis'],
  ['minRolls', 'min_rolls'],
  ['maxRolls', 'max_rolls'],
]

// AP-07fm: Diese Filter erlauben mehrere Werte. Im Entwurf stehen sie als
// ein Text mit Trennzeichen (Basiswert: frei mit Komma getippt), in der
// Adresse und an der API als wiederholter Parameter.
const MEHRFACH: (keyof Entwurf)[] = [
  'basiswert',
  'anlageklasse',
  'waehrung',
  'strategie',
  'seite',
  'endzustand',
]
const TRENNER = '\u001f'

function werteListe(wert: string): string[] {
  return wert
    .split(/[,\u001f]/)
    .map((eins) => eins.trim())
    .filter((eins) => eins !== '')
}

function entwurfAusAdresse(suche: URLSearchParams): Entwurf {
  const entwurf = { ...LEERER_ENTWURF }
  for (const [schluessel, parameter] of FILTER_PARAMETER) {
    if (MEHRFACH.includes(schluessel)) {
      entwurf[schluessel] = suche
        .getAll(parameter)
        .join(schluessel === 'basiswert' ? ', ' : TRENNER)
    } else {
      entwurf[schluessel] = suche.get(parameter) ?? ''
    }
  }
  return entwurf
}

function mehrfachOderUndefined(wert: string): string[] | undefined {
  const werte = werteListe(wert)
  return werte.length > 0 ? werte : undefined
}

function rollsOderUndefined(wert: string): number | undefined {
  const zahl = Number.parseInt(wert, 10)
  return Number.isNaN(zahl) || zahl < 0 ? undefined : zahl
}

function filterAusEntwurf(entwurf: Entwurf): KettenFilter {
  return {
    basiswert: mehrfachOderUndefined(entwurf.basiswert),
    anlageklasse: mehrfachOderUndefined(entwurf.anlageklasse),
    waehrung: mehrfachOderUndefined(entwurf.waehrung),
    strategie: mehrfachOderUndefined(entwurf.strategie),
    seite: mehrfachOderUndefined(entwurf.seite),
    endzustand: mehrfachOderUndefined(entwurf.endzustand),
    eroeffnet_ab: entwurf.eroeffnetAb || undefined,
    eroeffnet_bis: entwurf.eroeffnetBis || undefined,
    geschlossen_ab: entwurf.geschlossenAb || undefined,
    geschlossen_bis: entwurf.geschlossenBis || undefined,
    min_rolls: rollsOderUndefined(entwurf.minRolls),
    max_rolls: rollsOderUndefined(entwurf.maxRolls),
  }
}

function zahlOderVorgabe(wert: string | null, vorgabe: number): number {
  const geparst = Number.parseInt(wert ?? '', 10)
  return Number.isNaN(geparst) ? vorgabe : geparst
}

// Eine Tabellenzelle je Spalte — reine Zeichenarbeit (Vertrag 8): Die
// Zeichenfolge wird nur geschnitten, nie umgerechnet.
function zelle(kette: Kette, id: SpaltenId, verweis: SpaltenId): JSX.Element {
  const istVerweis = id === verweis
  switch (id) {
    case 'eroeffnet_am':
      // Volle Zeit (mit Sekunden) im title, eine Zeile ohne Umbruch.
      return (
        <td className="zeit" title={zeit(kette.eroeffnet_am)}>
          {istVerweis ? (
            <Link to={`/positionen/${kette.chain_id}`}>{zeitDe(kette.eroeffnet_am)}</Link>
          ) : (
            zeitDe(kette.eroeffnet_am)
          )}
        </td>
      )
    case 'underlying':
      return istVerweis ? (
        <td>
          <Link to={`/positionen/${kette.chain_id}`}>{kette.underlying}</Link>
        </td>
      ) : (
        <td>{kette.underlying}</td>
      )
    case 'strikes_aktuell':
      return <td className="strikes">{kette.strikes_aktuell ?? '—'}</td>
    case 'verfall_aktuell':
      return <td>{kette.verfall_aktuell ? datumDe(kette.verfall_aktuell) : '—'}</td>
    case 'asset_class':
      return <td>{kette.asset_class}</td>
    case 'seite':
      return <td>{kette.seite ?? '—'}</td>
    // Kontrakte bzw. Stück der Eröffnung; der Rohwert steht im Tooltip.
    case 'menge':
      return (
        <td className="zahl" title={kette.menge ?? undefined}>
          {mengeDe(kette.menge)}
        </td>
      )
    case 'beendet_am':
      return (
        <td className="zeit" title={kette.beendet_am ? zeit(kette.beendet_am) : undefined}>
          {kette.beendet_am ? zeitDe(kette.beendet_am) : '—'}
        </td>
      )
    case 'anzahl_rolls':
      // AP-06se: In der Schrittansicht steht hier die Nummer des Glieds.
      return kette.schritt ? (
        <td className="zahl" title="Glied der Kette (1 = Eröffnung, danach jeweils ein Roll)">
          {kette.schritt} / {kette.schritte_gesamt}
        </td>
      ) : (
        <td className="zahl">{kette.anzahl_rolls}</td>
      )
    case 'endzustand':
      return <td>{kette.endzustand ?? '—'}</td>
    // AP-13x: OA-Strategie der Kette (AP-13wk), reines Durchreichen; leer
    // bleibt —. Status und Erkennung bleiben der Detailansicht vorbehalten.
    case 'oa_strategie':
      return <td>{kette.oa_strategie ?? '—'}</td>
    // AP-08f1: Preise ohne Farbe, deutsch über betrag() (zwei
    // Nachkommastellen, Komma, Tausenderpunkte) — der Rohwert bleibt im
    // title der Zelle. Das Ergebnis ist ein Geldbetrag und bekommt <Betrag>
    // mit Farbe und Tooltip.
    case 'eroeffnungspreis':
    case 'schlusspreis': {
      const voll = id === 'eroeffnungspreis' ? kette.eroeffnungspreis : kette.schlusspreis
      // Ein Schlusspreis von 0 bei Verfall oder Zuteilung ist richtig, aber ohne
      // Aussage über den Weg: Verfall (wertlos) oder Zuteilung (Aktie geliefert).
      // Der Rohwert bleibt im Tooltip; ein 0-Preis aus normalem Handel bleibt 0,00.
      const nullPreis = id === 'schlusspreis' && voll !== null && /^-?0(\.0+)?$/.test(voll)
      const marke =
        nullPreis && kette.endzustand === 'Verfall'
          ? 'Verfall'
          : nullPreis && kette.endzustand === 'Assigned'
            ? 'Zuteilung'
            : null
      return (
        <td className="zahl" title={voll === null ? undefined : marke ? `${marke} — Preis ${voll}` : voll}>
          {voll === null ? '—' : (marke ?? betrag(voll))}
        </td>
      )
    }
    case 'struktur_summe_netto':
      return (
        <td className="zahl">
          {kette.struktur_summe_netto === null && kette.realisiert_bisher ? (
            <span
              title="Bereits realisiert (geschlossene Rollschritte) — die Kette ist noch offen, das Gesamtergebnis steht erst am Ende fest"
            >
              <Betrag wert={kette.realisiert_bisher} waehrung={kette.waehrung ?? undefined} />
              <span className="nebenbei"> bisher</span>
            </span>
          ) : (
            <Betrag wert={kette.struktur_summe_netto} waehrung={kette.waehrung ?? undefined} />
          )}
        </td>
      )
    case 'unrealisiert_eur':
      return (
        <td
          className="zahl"
          title={
            kette.offene_legs_ohne_kurs > 0
              ? `${kette.offene_legs_ohne_kurs} offene(s) Leg(s) ohne Bestand laut IB — nicht bewertet`
              : undefined
          }
        >
          {kette.unrealisiert_eur === null ? (
            kette.offene_legs_ohne_kurs > 0 ? '?' : '—'
          ) : (
            <Betrag wert={kette.unrealisiert_eur} />
          )}
        </td>
      )
    case 'praemie_offen_eur':
    case 'praemie_aktuell_eur': {
      const wert = id === 'praemie_offen_eur' ? kette.praemie_offen_eur : kette.praemie_aktuell_eur
      return (
        <td
          className="zahl"
          title={
            id === 'praemie_offen_eur'
              ? 'Prämie der offenen Legs bei Eröffnung (Credit positiv), ohne Kommission'
              : 'Prämienwert der offenen Legs laut IBs letztem Marktwert (Credit positiv)'
          }
        >
          {wert === null || wert === undefined ? '—' : <Betrag wert={wert} />}
        </td>
      )
    }
    case 'waehrung':
      return (
        <td>
          {kette.waehrung ?? (
            <span title="Kette enthält mehrere Währungen — keine Summe möglich">
              {kette.waehrungen.join(' / ')}
            </span>
          )}
        </td>
      )
  }
}

// Ein Auswahlfeld mit „alle". Fehlt die Liste (kein Wert im Bestand oder die API
// antwortet nicht), bleibt das Feld sichtbar, nur ohne Optionen. Ein in der
// Adresse stehender Wert, der nicht in der Liste ist, bleibt wählbar.
// AP-07fm: Mehrfachauswahl — eine aufklappbare Liste mit Häkchen. Ohne
// Häkchen gilt „alle“.
function Auswahl({
  titel,
  wert,
  optionen,
  aendere,
}: {
  titel: string
  wert: string
  optionen: string[]
  aendere: (wert: string) => void
}): JSX.Element {
  const gewaehlt = werteListe(wert)
  const alle = [...optionen, ...gewaehlt.filter((eins) => !optionen.includes(eins))]
  function umschalten(eins: string): void {
    const naechste = gewaehlt.includes(eins)
      ? gewaehlt.filter((x) => x !== eins)
      : [...gewaehlt, eins]
    aendere(naechste.join(TRENNER))
  }
  const anzeige =
    gewaehlt.length === 0
      ? 'alle'
      : gewaehlt.length <= 2
        ? gewaehlt.join(', ')
        : `${gewaehlt.length} gewählt`
  return (
    <div className="mehrfach">
      <span className="titel">{titel}</span>
      <details>
        <summary title={gewaehlt.join(', ') || 'alle'}>{anzeige}</summary>
        <div className="mehrfach-liste">
          {gewaehlt.length > 0 ? (
            <button type="button" className="leeren" onClick={() => aendere('')}>
              alle (Auswahl leeren)
            </button>
          ) : null}
          {alle.map((eins) => (
            <label key={eins}>
              <input
                type="checkbox"
                checked={gewaehlt.includes(eins)}
                onChange={() => umschalten(eins)}
              />
              {eins}
            </label>
          ))}
        </div>
      </details>
    </div>
  )
}

// Dichte der Tabellen (Nutzerwunsch 16.10.2026: alle Trades möglichst nah beieinander, ohne zu scrollen).
type Dichte = 'normal' | 'kompakt' | 'sehr'
const DICHTEN: [Dichte, string, string][] = [
  ['normal', 'Normal', 'Wie bisher'],
  ['kompakt', 'Kompakt', 'Kleinere Schrift, engere Zeilen, kein Umbruch'],
  ['sehr', 'Sehr kompakt', 'Kleinste Schrift, Zeilen ohne Abstand'],
]
const DICHTE_SCHLUESSEL = 'positionen-dichte'
const FILTER_SCHLUESSEL = 'positionen-filter-offen'

function leseFilterOffen(): boolean {
  try {
    return window.localStorage.getItem(FILTER_SCHLUESSEL) !== 'zu'
  } catch {
    return true
  }
}

function leseDichte(): Dichte {
  try {
    const wert = window.localStorage.getItem(DICHTE_SCHLUESSEL)
    return wert === 'normal' || wert === 'sehr' || wert === 'kompakt' ? wert : 'kompakt'
  } catch {
    return 'kompakt'
  }
}

// Aktien im Depot (Nutzerwunsch 16.10.2026): Die Positionsliste zeigt Ketten von Geschäften. Aktien stehen dort
// nur, soweit sie aus Zuteilungen stammen (Teil einer Options-Kette, Seite „n.a.“) oder als eigene Aktienkette.
// Dieser Block zeigt deshalb den Aktienbestand laut IB (Flex-Bestand, letzter Stichtag, wie die Seite „Depot“),
// gefiltert nach Basiswert, Währung und Anlageklasse der Leiste. Gefiltert nach Endzustand/Datum wird nicht:
// der Bestand ist immer „offen“ zum Stichtag.
function AktienImDepot({ filter, dichte }: { filter: Entwurf; dichte: Dichte }): JSX.Element | null {
  const [depot, setzeDepot] = useState<Depot | null>(null)
  const [einkauf, setzeEinkauf] = useState<Record<number, AktieEinkauf>>({})
  useEffect(() => {
    holeDepot()
      .then(setzeDepot)
      .catch(() => setzeDepot(null))
    holeAktienEinkauf()
      .then((e) => setzeEinkauf(Object.fromEntries(e.aktien.map((a) => [a.conid, a]))))
      .catch(() => setzeEinkauf({}))
  }, [])
  if (depot === null) return null
  const basiswerte = werteListe(filter.basiswert).map((x) => x.toUpperCase())
  const waehrungen = werteListe(filter.waehrung).map((x) => x.toUpperCase())
  const klassen = werteListe(filter.anlageklasse).map((x) => x.toUpperCase())
  if (klassen.length > 0 && !klassen.includes('STK')) return null
  const aktien = depot.positionen.filter(
    (p) =>
      p.anlageklasse === 'STK' &&
      (basiswerte.length === 0 || basiswerte.includes(p.basiswert.toUpperCase())) &&
      (waehrungen.length === 0 || waehrungen.includes(p.waehrung.toUpperCase())),
  )
  if (aktien.length === 0) return null
  return (
    <details className="aktien-im-depot" open>
      <summary>
        <strong>Aktien im Depot ({aktien.length})</strong> — Bestand laut IB, Stand {datumDe(depot.stichtag)}
      </summary>
      <p className="hinweis">
        Aktien aus Zuteilungen gehören im Journal zur Options-Kette (Zeile mit Seite „n.a.“); hier steht der
        tatsächliche Bestand. <strong>Einkauf</strong> = Preis der Kauf- oder Zuteilungsausführung (bei Zuteilung der
        Strike). <strong>IB-Einstand</strong> = IBs Kostenbasis, schon um die Optionsprämien gekürzt (IB bucht eine
        zugeteilte Option mit 0 und schiebt die Prämie in den Einstand der Aktie). Die Summen der Ketten-Liste
        enthalten diese Tabelle nicht. Mehr auf der Seite <Link to="/bestand">Depot</Link>.
      </p>
      <table className={`positionen dichte-${dichte}`}>
        <thead>
          <tr>
            <th>Basiswert</th>
            <th className="zahl">Menge</th>
            <th className="zahl" title="Gewichteter Durchschnitt der Kauf- und Zuteilungspreise der offenen Aktien-Legs im Journal">Einkauf Ø</th>
            <th className="zahl" title="IBs Kostenbasis: schon um Optionsprämien gekürzt">IB-Einstand</th>
            <th className="zahl" title="Einkauf minus IB-Einstand: die Prämien je Aktie, die IB in den Einstand schiebt">Prämien/Aktie</th>
            <th className="zahl">Kurs</th>
            <th className="zahl">Marktwert</th>
            <th className="zahl" title="Kurs gegen IB-Einstand (IBs Zahl)">Unrealisiert (IB)</th>
            <th className="zahl" title="Kurs gegen den tatsächlichen Einkaufspreis, ohne Prämien">Unrealisiert (Einkauf)</th>
            <th>Währung</th>
          </tr>
        </thead>
        <tbody>
          {aktien.map((p) => (
            <tr key={p.conid}>
              <td>
                <Link to={`/?anlageklasse=OPT&basiswert=${encodeURIComponent(p.basiswert)}`} title="Optionen und Ketten dieses Basiswerts">
                  {p.basiswert}
                </Link>
              </td>
              <td className="zahl">{mengeDe(p.menge)}</td>
              <td className="zahl" title={einkauf[p.conid] ? `Journal: ${einkauf[p.conid].menge_journal} Stück, davon ${(Number(einkauf[p.conid].anteil_zuteilung) * 100).toFixed(0)} % aus Zuteilung` : "Kein offener Aktien-Leg im Journal"}>
                {einkauf[p.conid] ? betrag(einkauf[p.conid].einkaufskurs) : '—'}
              </td>
              <td className="zahl">{betrag(p.einstandskurs)}</td>
              <td className="zahl">{einkauf[p.conid] ? betrag(einkauf[p.conid].praemien_je_aktie) : '—'}</td>
              <td className="zahl">{betrag(p.kurs)}</td>
              <td className="zahl">{betrag(p.marktwert)}</td>
              <td className="zahl">
                <Betrag wert={p.unrealisiert} waehrung={p.waehrung} />
              </td>
              <td className="zahl">
                {einkauf[p.conid] ? <Betrag wert={einkauf[p.conid].unrealisiert_einkauf} waehrung={p.waehrung} /> : '—'}
              </td>
              <td>{p.waehrung}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

export default function Positionen(): JSX.Element {
  const [suche, setzeSuche] = useSearchParams()
  // AP-08z: Der globale Zeitraum aus dem Wähler im Kopf (AP-08f2) steuert
  // auch diese Liste — die API liefert die im Zeitraum aktiven Ketten
  // (AP-07f, Z3); der Browser filtert nichts selbst.
  const [zeitraum] = useZeitraum()
  // Die Filter der Adresse; als Text, damit Effekte nur bei echter Änderung
  // neu laden.
  const filterText = JSON.stringify(entwurfAusAdresse(suche))
  const limit = Math.min(Math.max(zahlOderVorgabe(suche.get('limit'), VORGABE_LIMIT), 1), 500)
  const offset = Math.max(zahlOderVorgabe(suche.get('offset'), 0), 0)

  // AP-08s: Die Sortierung steht in der Adresse — Neuladen und Lesezeichen
  // erhalten sie. Ungültiges darin wird nicht durchgereicht (die API
  // antwortete 422); es gilt die Vorgabe: Eröffnung absteigend (AP-07s).
  const sortierungParam = suche.get('sortierung')
  const richtungParam = suche.get('richtung')
  const sortierung: Sortierspalte = istSortierbareSpalte(sortierungParam)
    ? sortierungParam
    : 'eroeffnet_am'
  const richtung: Richtung =
    richtungParam === 'asc' || richtungParam === 'desc' ? richtungParam : 'desc'

  // AP-06se: Schrittansicht — jedes Kettenglied als eigene Zeile, um eine
  // Strategie gezielt mit OptionApp zu vergleichen. Steht in der Adresse.
  const ansicht: 'ketten' | 'schritte' =
    suche.get('ansicht') === 'schritte' ? 'schritte' : 'ketten'

  const [filterOffen, setzeFilterOffen] = useState<boolean>(() => leseFilterOffen())
  function filterUmschalten(offen: boolean): void {
    setzeFilterOffen(offen)
    try {
      window.localStorage.setItem(FILTER_SCHLUESSEL, offen ? 'offen' : 'zu')
    } catch {
      /* Speicher fehlt — die Wahl gilt dann nur für diese Sitzung. */
    }
  }
  const [dichte, setzeDichteZustand] = useState<Dichte>(() => leseDichte())
  function setzeDichte(wert: Dichte): void {
    setzeDichteZustand(wert)
    try {
      window.localStorage.setItem(DICHTE_SCHLUESSEL, wert)
    } catch {
      /* Speicher fehlt — die Wahl gilt dann nur für diese Sitzung. */
    }
  }
  const [entwurf, setzeEntwurf] = useState<Entwurf>(() => entwurfAusAdresse(suche))
  const [liste, setzeListe] = useState<KettenListe | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  // AP-08g2b: wählbare Werte (AP-07fw) und Auswertung der Auswahl (AP-07f).
  const [werte, setzeWerte] = useState<Filterwerte | null>(null)
  const [oaStand, setzeOaStand] = useState<OaStand | null>(null)
  const [auswertung, setzeAuswertung] = useState<Auswertung | null>(null)
  const [auswertungFehler, setzeAuswertungFehler] = useState<string | null>(null)

  useEffect(() => {
    // Ohne Auswahllisten bleibt die Leiste benutzbar (Rückfallwerte, Freitext).
    holeFilterwerte()
      .then(setzeWerte)
      .catch(() => setzeWerte(null))
    // AP-13r2: Hinweis zur Strategie — nur Information, ohne Antwort kein Hinweis.
    holeOaStand()
      .then(setzeOaStand)
      .catch(() => setzeOaStand(null))
  }, [])

  // AP-08s, Punkt 3: Auswahl und Reihenfolge der sichtbaren Spalten.
  const [sichtbare, setzeSichtbare] = useState<SpaltenId[]>(
    () => leseSpalten() ?? STANDARD_SPALTEN,
  )

  // Die Wahl gilt auch beim nächsten Besuch. Fehlt der Speicher, gilt sie
  // still nur für diese Sitzung — die Ansicht bricht darüber nicht.
  useEffect(() => {
    try {
      window.localStorage.setItem(SPALTEN_SCHLUESSEL, JSON.stringify(sichtbare))
    } catch {
      /* Speicher fehlt oder ist voll — nichts weiter zu tun. */
    }
  }, [sichtbare])

  // Der Verweis auf die Detailansicht hängt an der Eröffnung, solange sie
  // sichtbar ist; sonst an der ersten sichtbaren Spalte (AP-08s, Punkt 3).
  const verweisSpalte: SpaltenId = sichtbare.includes('eroeffnet_am')
    ? 'eroeffnet_am'
    : sichtbare[0]
  const versteckte = ALLE_SPALTEN.filter((id) => !sichtbare.includes(id))

  useEffect(() => {
    let abgebrochen = false
    setzeListe(null)
    setzeFehler(null)
    holeKetten({
      ...filterAusEntwurf(JSON.parse(filterText) as Entwurf),
      sortierung,
      richtung,
      von: zeitraum.von,
      bis: zeitraum.bis,
      limit,
      offset,
      ansicht,
    })
      .then((ergebnis) => {
        if (!abgebrochen) setzeListe(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [filterText, limit, offset, sortierung, richtung, zeitraum.von, zeitraum.bis, ansicht])

  // AP-08g2b: Verlauf und Ergebnis für dieselbe Auswahl. Der Zeitraum gilt
  // hier am Schließungstag (AP-07f, Z2); Blättern und Sortieren ändern die
  // Auswertung nicht.
  useEffect(() => {
    let abgebrochen = false
    setzeAuswertung(null)
    setzeAuswertungFehler(null)
    holeAuswertung(
      filterAusEntwurf(JSON.parse(filterText) as Entwurf),
      zeitraum.von,
      zeitraum.bis,
    )
      .then((ergebnis) => {
        if (!abgebrochen) setzeAuswertung(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeAuswertungFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [filterText, zeitraum.von, zeitraum.bis])

  // AP-08z: Ein anderer Zeitraum beginnt beim Blättern wieder vorn. Der
  // Wähler löscht den Blätterstand schon selbst (zeitraum.ts); das hier
  // sichert auch Adressen, die von außen kommen (Zurück-Taste, Verweise).
  const vorigerZeitraum = useRef(`${zeitraum.von ?? ''}|${zeitraum.bis ?? ''}`)
  useEffect(() => {
    const jetzt = `${zeitraum.von ?? ''}|${zeitraum.bis ?? ''}`
    if (jetzt === vorigerZeitraum.current) return
    vorigerZeitraum.current = jetzt
    const naechste = new URLSearchParams(suche)
    naechste.delete('offset')
    setzeSuche(naechste)
  }, [zeitraum.von, zeitraum.bis, suche, setzeSuche])

  function anwenden(ereignis: FormEvent): void {
    ereignis.preventDefault()
    const naechste = new URLSearchParams()
    for (const [schluessel, parameter] of FILTER_PARAMETER) {
      const wert = entwurf[schluessel].trim()
      if (MEHRFACH.includes(schluessel)) {
        for (const eins of werteListe(wert)) naechste.append(parameter, eins)
      } else if (schluessel === 'minRolls' || schluessel === 'maxRolls') {
        const zahl = rollsOderUndefined(wert)
        if (zahl !== undefined) naechste.set(parameter, String(zahl))
      } else if (wert) {
        naechste.set(parameter, wert)
      }
    }
    // Die Sortierung gehört zur Ansicht — sie bleibt beim Anwenden der
    // Filter erhalten (AP-08s); limit und offset fallen auf die Vorgabe
    // zurück.
    if (sortierung !== 'eroeffnet_am' || richtung !== 'desc') {
      naechste.set('sortierung', sortierung)
      naechste.set('richtung', richtung)
    }
    // AP-08z: Der globale Zeitraum gehört zum Kopf, nicht zur Filterleiste
    // — von/bis wandern aus der aktuellen Adresse in die neue.
    if (zeitraum.von) naechste.set('von', zeitraum.von)
    if (zeitraum.bis) naechste.set('bis', zeitraum.bis)
    if (ansicht === 'schritte') naechste.set('ansicht', 'schritte')
    setzeSuche(naechste) // limit und offset fallen auf die Vorgabe zurück
  }

  function zuruecksetzen(): void {
    setzeEntwurf({ ...LEERER_ENTWURF })
    // AP-08z: Zurücksetzen räumt nur die Filter der Liste — der globale
    // Zeitraum bleibt gewählt und in der Adresse.
    const naechste = new URLSearchParams()
    if (zeitraum.von) naechste.set('von', zeitraum.von)
    if (zeitraum.bis) naechste.set('bis', zeitraum.bis)
    if (ansicht === 'schritte') naechste.set('ansicht', 'schritte')
    setzeSuche(naechste)
  }

  function ansichtWaehlen(neu: 'ketten' | 'schritte'): void {
    const naechste = new URLSearchParams(suche)
    if (neu === 'schritte') naechste.set('ansicht', 'schritte')
    else naechste.delete('ansicht')
    naechste.delete('offset')
    setzeSuche(naechste)
  }

  function blaettern(schritt: number): void {
    const naechste = new URLSearchParams(suche)
    naechste.set('limit', String(limit))
    naechste.set('offset', String(Math.max(offset + schritt, 0)))
    setzeSuche(naechste)
  }

  function jeSeite(wert: string): void {
    const naechste = new URLSearchParams(suche)
    naechste.set('limit', wert)
    naechste.delete('offset')
    setzeSuche(naechste)
  }

  // AP-08s: Klick auf den Spaltenkopf — die Sortierung geht als sortierung
  // und richtung an GET /ketten (AP-07sk) und steht in der Adresse; ein
  // Wechsel setzt das Blättern auf die erste Seite zurück.
  function sortiereNach(id: SpaltenId): void {
    const spalte = SPALTEN[id]
    if (!spalte.sortierbar) return
    const naechste = new URLSearchParams(suche)
    naechste.set('sortierung', id)
    if (sortierung === id) {
      naechste.set('richtung', richtung === 'asc' ? 'desc' : 'asc')
    } else {
      naechste.set('richtung', spalte.ersteRichtung ?? 'asc')
    }
    naechste.delete('offset')
    setzeSuche(naechste)
  }

  // AP-08s, Punkt 3: Spaltenauswahl — mindestens eine Spalte bleibt sichtbar.
  function spalteUmschalten(id: SpaltenId): void {
    if (sichtbare.includes(id)) {
      if (sichtbare.length === 1) return
      setzeSichtbare(sichtbare.filter((eine) => eine !== id))
    } else {
      // Wieder eingeblendet wird an der Standardposition — sonst hinge die
      // Spalte ohne erkennbaren Grund am Ende.
      setzeSichtbare(
        [...sichtbare, id].sort(
          (a, b) => STANDARD_SPALTEN.indexOf(a) - STANDARD_SPALTEN.indexOf(b),
        ),
      )
    }
  }

  function spalteVerschieben(id: SpaltenId, schritt: number): void {
    const von = sichtbare.indexOf(id)
    const nach = von + schritt
    if (von < 0 || nach < 0 || nach >= sichtbare.length) return
    const naechste = [...sichtbare]
    ;[naechste[von], naechste[nach]] = [naechste[nach], naechste[von]]
    setzeSichtbare(naechste)
  }

  return (
    <section>
      <h2>Positionen</h2>
      <ErgebnisBegriffe />
      <details
        className="filterbereich"
        open={filterOffen}
        onToggle={(e) => filterUmschalten((e.currentTarget as HTMLDetailsElement).open)}
      >
        <summary>
          Filter
          {(() => {
            const aktiv = Object.values(entwurfAusAdresse(suche)).filter((w) => typeof w === 'string' && w !== '').length
            return aktiv > 0 ? ` (${aktiv} aktiv)` : ' (keine aktiv)'
          })()}
        </summary>
      <form className="filter" onSubmit={anwenden}>
        <label>
          Basiswert
          <input
            list="filter-basiswerte"
            value={entwurf.basiswert}
            onChange={(e) => setzeEntwurf({ ...entwurf, basiswert: e.target.value })}
            placeholder="z. B. DAX, ESTX50"
          />
          <datalist id="filter-basiswerte">
            {(werte?.basiswerte ?? []).map((wert) => (
              <option key={wert} value={wert} />
            ))}
          </datalist>
        </label>
        <Auswahl
          titel="Anlageklasse"
          wert={entwurf.anlageklasse}
          optionen={werte?.anlageklassen ?? ANLAGEKLASSEN}
          aendere={(wert) => setzeEntwurf({ ...entwurf, anlageklasse: wert })}
        />
        <Auswahl
          titel="Währung"
          wert={entwurf.waehrung}
          optionen={werte?.waehrungen ?? []}
          aendere={(wert) => setzeEntwurf({ ...entwurf, waehrung: wert })}
        />
        <Auswahl
          titel="Strategie"
          wert={entwurf.strategie}
          optionen={werte?.strategien ?? []}
          aendere={(wert) => setzeEntwurf({ ...entwurf, strategie: wert })}
        />
        <Auswahl
          titel="Seite"
          wert={entwurf.seite}
          optionen={werte?.seiten ?? []}
          aendere={(wert) => setzeEntwurf({ ...entwurf, seite: wert })}
        />
        <Auswahl
          titel="Endzustand"
          wert={entwurf.endzustand}
          optionen={werte?.endzustaende ?? ENDZUSTAENDE}
          aendere={(wert) => setzeEntwurf({ ...entwurf, endzustand: wert })}
        />
        <div className="zeilenumbruch" aria-hidden="true" />
        <label>
          Eröffnet von
          <input
            type="date"
            value={entwurf.eroeffnetAb}
            onChange={(e) => setzeEntwurf({ ...entwurf, eroeffnetAb: e.target.value })}
          />
        </label>
        <label>
          bis
          <input
            type="date"
            value={entwurf.eroeffnetBis}
            onChange={(e) => setzeEntwurf({ ...entwurf, eroeffnetBis: e.target.value })}
          />
        </label>
        <label>
          Geschlossen von
          <input
            type="date"
            value={entwurf.geschlossenAb}
            onChange={(e) => setzeEntwurf({ ...entwurf, geschlossenAb: e.target.value })}
          />
        </label>
        <label>
          bis
          <input
            type="date"
            value={entwurf.geschlossenBis}
            onChange={(e) => setzeEntwurf({ ...entwurf, geschlossenBis: e.target.value })}
          />
        </label>
        <label className="schmal">
          Rolls von
          <input
            type="number"
            min={0}
            value={entwurf.minRolls}
            onChange={(e) => setzeEntwurf({ ...entwurf, minRolls: e.target.value })}
          />
        </label>
        <label className="schmal">
          bis
          <input
            type="number"
            min={0}
            value={entwurf.maxRolls}
            onChange={(e) => setzeEntwurf({ ...entwurf, maxRolls: e.target.value })}
          />
        </label>
        <button type="submit">Anwenden</button>
        <button type="button" onClick={zuruecksetzen}>
          Zurücksetzen
        </button>
      </form>
      </details>
      {oaStand !== null && oaStand.ohne_export > 0 ? (
        <p className="sicht">
          Strategien stammen aus dem OptionApp-Export
          {oaStand.export_bis ? ` (Stand ${datumDe(oaStand.export_bis)})` : ''}:{' '}
          {oaStand.ohne_export} OA-Trade(s) seit {datumDe(oaStand.ohne_export_ab)} sind noch
          ohne Strategie. Neuen Export in den OA-Ordner legen — der nächste Abruf liest ihn ein.
        </p>
      ) : null}

      {/* AP-08g2b: Verlauf und Ergebnis der Auswahl (GET /auswertung). */}
      <FilterAuswertung
        auswertung={auswertung}
        fehler={auswertungFehler}
        mitZeitraum={zeitraum.von !== null || zeitraum.bis !== null}
      />

      {/* AP-08s: Spaltenauswahl — ein Kästchen je Spalte, Reihenfolge über
          die Pfeile, im Browser gespeichert (mit Rückfall auf die Vorgabe);
          „Standard wiederherstellen" setzt zurück. Die Liste zeigt die
          sichtbaren Spalten in ihrer Reihenfolge und darunter die
          ausgeblendeten. */}
      <details className="spaltenwahl">
        <summary>Spalten</summary>
        <ul>
          {sichtbare.map((id, stelle) => (
            <li key={id}>
              <label>
                <input
                  type="checkbox"
                  checked
                  disabled={sichtbare.length === 1}
                  onChange={() => spalteUmschalten(id)}
                />{' '}
                {SPALTEN[id].titel}
              </label>
              <button
                type="button"
                aria-label={`${SPALTEN[id].titel} nach oben`}
                disabled={stelle === 0}
                onClick={() => spalteVerschieben(id, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`${SPALTEN[id].titel} nach unten`}
                disabled={stelle === sichtbare.length - 1}
                onClick={() => spalteVerschieben(id, 1)}
              >
                ↓
              </button>
            </li>
          ))}
          {versteckte.map((id) => (
            <li key={id} className="aus">
              <label>
                <input type="checkbox" onChange={() => spalteUmschalten(id)} />{' '}
                {SPALTEN[id].titel}
              </label>
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => setzeSichtbare([...STANDARD_SPALTEN])}>
          Standard wiederherstellen
        </button>
      </details>

      {/* AP-08z: Der gewählte Zeitraum steht über der Tabelle; was „aktiv"
          heißt, sagt die Klammer. Ohne Zeitraum keine Zeile. */}
      {zeitraum.von !== null || zeitraum.bis !== null ? (
        <p className="sicht">
          Aktiv im Zeitraum: {datumDe(zeitraum.von)} – {datumDe(zeitraum.bis)} (eröffnet bis
          zum Ende und offen oder beendet ab dem Anfang)
        </p>
      ) : null}

      {fehler ? (
        <section className="fehler">
          <h3>Die Liste konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      ) : liste === null ? (
        <p className="laedt">Lade Positionen …</p>
      ) : liste.gesamt === 0 ? (
        <section className="hinweis">
          <p>
            {zeitraum.von !== null || zeitraum.bis !== null
              ? 'Keine Positionen in diesem Zeitraum aktiv.'
              : 'Keine Positionen für diese Filter.'}
          </p>
          <p>Filter zurücksetzen oder andere Werte versuchen.</p>
        </section>
      ) : (
        <>
          <AktienImDepot filter={entwurfAusAdresse(suche)} dichte={dichte} />
          <div className="diagramm-wahl" role="group" aria-label="Dichte der Tabellen">
            {DICHTEN.map(([wert, name, hinweis]) => (
              <button
                key={wert}
                type="button"
                aria-pressed={dichte === wert}
                title={hinweis}
                onClick={() => setzeDichte(wert)}
              >
                {name}
              </button>
            ))}
          </div>
          <div className="diagramm-wahl" role="group" aria-label="Ansicht der Liste">
            <button
              type="button"
              aria-pressed={ansicht === 'ketten'}
              title="Eine Zeile je Kette, Rolls zusammen"
              onClick={() => ansichtWaehlen('ketten')}
            >
              Ketten (Rolls zusammen)
            </button>
            <button
              type="button"
              aria-pressed={ansicht === 'schritte'}
              title="Eine Zeile je Kettenglied — so zählt OptionApp seine Trades. Die Filter wirken auf die Kette; die Auswertung oben bleibt die der Ketten."
              onClick={() => ansichtWaehlen('schritte')}
            >
              Schritte einzeln (wie OA)
            </button>
          </div>
          <table className={`positionen dichte-${dichte}`}>
            <thead>
              <tr>
                {sichtbare.map((id) => {
                  const spalte = SPALTEN[id]
                  const aktiv = spalte.sortierbar && sortierung === id
                  return (
                    <th
                      key={id}
                      className={ZAHL_SPALTEN.includes(id) ? 'zahl' : undefined}
                      aria-sort={
                        aktiv ? (richtung === 'asc' ? 'ascending' : 'descending') : undefined
                      }
                      title={spalte.sortierbar ? spalte.hinweis : NICHT_SORTIERBAR_TITEL}
                    >
                      {spalte.sortierbar ? (
                        <button type="button" className="sortierer" onClick={() => sortiereNach(id)}>
                          {spalte.titel}
                          {aktiv ? (richtung === 'asc' ? ' ▲' : ' ▼') : ''}
                        </button>
                      ) : (
                        spalte.titel
                      )}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {liste.treffer.map((kette) => (
                <tr key={`${kette.chain_id}-${kette.schritt ?? 0}`}>
                  {sichtbare.map((id) => zelle(kette, id, verweisSpalte))}
                </tr>
              ))}
            </tbody>
          </table>
          <footer className="blaettern">
            <button type="button" disabled={offset === 0} onClick={() => blaettern(-limit)}>
              Zurück
            </button>
            <p>
              Treffer {offset + 1}–{Math.min(offset + limit, liste.gesamt)} von{' '}
              {liste.gesamt}
            </p>
            <button
              type="button"
              disabled={offset + limit >= liste.gesamt}
              onClick={() => blaettern(limit)}
            >
              Weiter
            </button>
            <label>
              je Seite
              <select value={String(limit)} onChange={(e) => jeSeite(e.target.value)}>
                {LIMITS.map((wert) => (
                  <option key={wert} value={wert}>
                    {wert}
                  </option>
                ))}
              </select>
            </label>
          </footer>
          <p className="sicht fussnote">
            ¹ Kontosicht, Summe der Strukturergebnisse — der genaue Wert steht
            im Tooltip der Zelle. Keine Umrechnung, nichts gerechnet. „Anzahl“:
            Kontrakte bzw. Stück der Eröffnung. „Preis zu“: bei Verfall und Zuteilung
            steht der Weg statt 0,00. „Rolls (belegt)“ zählt nur Rolls, die eine
            gemeinsame Order belegt; Rolls in getrennten Orders sind Vorschläge.
            <br />² Nur offene Positionen: IBs letzter Marktwert gegen den Einstand des
            Journals, in EUR (Stand des letzten Berichts). „?“: offene Legs ohne Bestand laut IB.
            <br />³ Nur offene Positionen, in EUR, aus Verkäufersicht (Credit positiv):
            „Prämie offen“ = Prämie der offenen Legs bei Eröffnung (ohne Kommission),
            „Prämie aktuell“ = Prämienwert laut IBs letztem Marktwert. Offen − aktuell
            − Kommission = Unrealisiert. In der Schrittansicht steht der Wert am offenen Glied.
          </p>
        </>
      )}
    </section>
  )
}
