// Abrufe der Lese-API (AP-07l). Alles Fachliche bleibt Zeichenkette, wie die
// API liefert: Geld, Mengen, Strikes und Preise werden hier nie in Zahlen
// umgewandelt — JavaScript-Zahlen sind Gleitkommazahlen, und genau deren
// Genauigkeitsverlust vermeidet die API (AP-08lv, Vertrag 8).

export interface Kette {
  chain_id: number
  natur_schluessel: string
  underlying: string
  asset_class: string
  seite: string | null
  eroeffnet_am: string
  beendet_am: string | null
  anzahl_rolls: number
  endzustand: string | null
  anzahl_glieder: number
  // AP-07pv, P8 / AP-08fp: Prämie des ersten bzw. letzten Glieds, wie die API
  // liefert — Zeichenkette oder leer; offen heißt ohne Schlusspreis.
  eroeffnungspreis: string | null
  schlusspreis: string | null
  struktur_summe_netto: string | null
  waehrung: string | null
  waehrungen: string[]
  sicht: string
  // AP-13x: OA-Strategie/-Status/-Erkennung der Kette (AP-13wk) — reine
  // Anzeige, Text oder leer; keine Interpretation.
  oa_strategie: string | null
  oa_status: string | null
  oa_erkennung: string | null
}

export interface Struktur {
  structure_id: number
  natur_schluessel: string
  asset_class: string
  typ: string
  underlying: string
  expiry: string | null
  short_strike: string | null
  long_strike: string | null
  breite: string | null
  menge: string
  eroeffnet_am: string
  geschlossen_am: string | null
  dte_bei_eroeffnung: number | null
  status: string | null
  erkennung: string
  // AP-07pv, P7 / AP-08fp: Prämien je Kontrakt; offen heißt ohne Schlusspreis.
  eroeffnungspreis: string | null
  schlusspreis: string | null
  brutto_pnl: string | null
  kommission: string | null
  netto_pnl: string | null
  waehrung: string
  sicht: string
  // AP-13x: OA-Strategie/-Status/-Erkennung der Struktur (AP-13wk).
  oa_strategie: string | null
  oa_status: string | null
  oa_erkennung: string | null
}

export interface Kettenglied {
  sequenz: number
  verknuepfungstyp: string
  erkennung: string
  struktur: Struktur
}

export interface KetteDetail extends Kette {
  glieder: Kettenglied[]
}

export interface Leg {
  leg_id: number
  conid: number
  open_exec_id: string
  close_exec_id: string | null
  menge: string
  matching_methode: string
  offen_ja_nein: boolean
  basis_ungeklaert: boolean
  brutto_pnl: string | null
  kommission_gesamt: string | null
}

export interface StrukturDetail extends Struktur {
  legs: Leg[]
}

export interface Ausfuehrung {
  exec_id: string
  rolle: string
  conid: number
  symbol: string
  side: string
  menge: string
  preis: string
  waehrung: string
  kommission: string | null
  handelszeit: string
  ereignistyp: string
  exec_batch: string | null
  oa_trade: string | null
}

export interface KettenListe {
  gesamt: number
  treffer: Kette[]
}

export class ApiFehler extends Error {
  readonly status: number

  constructor(status: number, text: string) {
    super(`HTTP ${status} — ${text}`)
    this.status = status
  }
}

export function fehlerText(ursache: unknown): string {
  if (ursache instanceof ApiFehler) {
    return `Die API meldet ${ursache.status}: ${ursache.message}`
  }
  if (ursache instanceof Error) return ursache.message
  return String(ursache)
}

async function hole(pfad: string): Promise<unknown> {
  let antwort: Response
  try {
    antwort = await fetch(pfad, { headers: { Accept: 'application/json' } })
  } catch (ursache) {
    throw new Error(
      `Die API unter ${pfad.split('?')[0]} antwortet nicht — läuft der Server?`,
      { cause: ursache },
    )
  }
  if (!antwort.ok) {
    let text = antwort.statusText
    try {
      const inhalt = (await antwort.json()) as { detail?: unknown }
      if (typeof inhalt.detail === 'string') text = inhalt.detail
    } catch {
      /* Fehlertext bleibt bei der Statuszeile */
    }
    throw new ApiFehler(antwort.status, text)
  }
  return antwort.json()
}

export interface KettenAbfrage {
  basiswert?: string
  anlageklasse?: string
  endzustand?: string
  min_rolls?: number
  max_rolls?: number
  limit: number
  offset: number
}

export function holeKetten(abfrage: KettenAbfrage): Promise<KettenListe> {
  const zusaetze = new URLSearchParams()
  if (abfrage.basiswert) zusaetze.set('basiswert', abfrage.basiswert)
  if (abfrage.anlageklasse) zusaetze.set('anlageklasse', abfrage.anlageklasse)
  if (abfrage.endzustand) zusaetze.set('endzustand', abfrage.endzustand)
  if (abfrage.min_rolls !== undefined) zusaetze.set('min_rolls', String(abfrage.min_rolls))
  if (abfrage.max_rolls !== undefined) zusaetze.set('max_rolls', String(abfrage.max_rolls))
  zusaetze.set('limit', String(abfrage.limit))
  zusaetze.set('offset', String(abfrage.offset))
  return hole(`/ketten?${zusaetze.toString()}`) as Promise<KettenListe>
}

export function holeKette(chainId: number): Promise<KetteDetail> {
  return hole(`/ketten/${chainId}`) as Promise<KetteDetail>
}

export function holeStruktur(structureId: number): Promise<StrukturDetail> {
  return hole(`/strukturen/${structureId}`) as Promise<StrukturDetail>
}

export function holeAusfuehrungen(structureId: number): Promise<Ausfuehrung[]> {
  return hole(`/strukturen/${structureId}/ausfuehrungen`) as Promise<Ausfuehrung[]>
}
