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

// AP-08j: Senden für das Journal — dieselbe Fehlerbehandlung wie der Abruf:
// 404 und 422 werden mit dem Meldungstext der API sichtbar, nie verschluckt.
async function schicke(methode: string, pfad: string, koerper?: unknown): Promise<unknown> {
  let antwort: Response
  try {
    antwort = await fetch(pfad, {
      method: methode,
      headers:
        koerper === undefined
          ? { Accept: 'application/json' }
          : { Accept: 'application/json', 'Content-Type': 'application/json' },
      body: koerper === undefined ? undefined : JSON.stringify(koerper),
    })
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
  // 204 (Notiz gelöscht) hat keinen Körper.
  if (antwort.status === 204) return null
  return antwort.json()
}

async function hole(pfad: string): Promise<unknown> {
  return schicke('GET', pfad)
}

// AP-07s: Sortierbare Spalten und Richtungen — dieselben Aufzählungen wie die
// API (Literal-Typen dort). Alles andere antwortete 422; die Oberfläche wählt
// nur aus diesen Werten.
export type Sortierspalte =
  | 'eroeffnet_am'
  | 'beendet_am'
  | 'underlying'
  | 'asset_class'
  | 'seite'
  | 'anzahl_rolls'
  | 'endzustand'
  | 'oa_strategie'

export type Richtung = 'asc' | 'desc'

export interface KettenAbfrage {
  basiswert?: string
  anlageklasse?: string
  endzustand?: string
  min_rolls?: number
  max_rolls?: number
  // AP-07s/AP-08s: Sortierung auf dem Server, vor dem Blättern. Die
  // Oberfläche sortiert nie selbst — sie schickt nur Spalte und Richtung mit.
  sortierung?: Sortierspalte
  richtung?: Richtung
  // AP-08z: globaler Zeitraum aus dem Wähler im Kopf (AP-08f2). Die API
  // liefert die Ketten, die im Zeitraum aktiv waren (AP-07f, Z3) — der
  // Browser rechnet und filtert nichts selbst.
  von?: string | null
  bis?: string | null
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
  if (abfrage.sortierung !== undefined) zusaetze.set('sortierung', abfrage.sortierung)
  if (abfrage.richtung !== undefined) zusaetze.set('richtung', abfrage.richtung)
  if (abfrage.von) zusaetze.set('von', abfrage.von)
  if (abfrage.bis) zusaetze.set('bis', abfrage.bis)
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

// AP-07t, Tagesübersicht und Kalender (AP-08j): gleiche Grundregel wie oben —
// Geld bleibt Zeichenkette, Reihenfolge wie geliefert, nichts gerechnet.

export interface TagesKette {
  chain_id: number
  natur_schluessel: string
  underlying: string
  asset_class: string
  seite: string | null
  anzahl_rolls: number
  endzustand: string | null
  eroeffnet_am: string
  beendet_am: string | null
}

export interface TagesRoll {
  chain_id: number
  structure_id: number
  underlying: string
  sequenz: number
  eroeffnet_am: string
}

export interface TagesRealisiert {
  waehrung: string
  sicht: string
  anzahl_strukturen: number
  brutto: string
  kommission: string
  netto: string
}

export interface Tagesuebersicht {
  datum: string
  sicht: string
  eroeffnet: TagesKette[]
  beendet: TagesKette[]
  rolls: TagesRoll[]
  realisiert: TagesRealisiert[]
}

export interface KalenderRealisiert {
  waehrung: string
  sicht: string
  netto: string
}

export interface Kalendertag {
  datum: string
  eroeffnet: number
  beendet: number
  rolls: number
  realisiert: KalenderRealisiert[]
}

export interface Monatskalender {
  monat: string
  sicht: string
  tage: Kalendertag[]
}

// AP-08-kampagnen: bestätigte Kampagnen — wie immer gilt: Geld bleibt
// Zeichenkette, Reihenfolge wie geliefert, nichts gerechnet.
export interface Kampagne {
  campaign_id: number
  underlying: string
  eroeffnet_am: string
  beendet_am: string | null
  netto_pnl_eur: string | null
  anzahl_ketten: number
}

export interface KampagnenKette {
  chain_id: number
  natur_schluessel: string
  beziehungstyp: string
  erkennung: string
  bestaetigt_am: string | null
}

export interface KampagnenDetail extends Kampagne {
  ketten: KampagnenKette[]
}

export interface KampagnenListe {
  gesamt: number
  treffer: Kampagne[]
}

// AP-07j, Journal (AP-08j): Notizen und Tags eines Bereichs. Der Text bleibt
// unverändert — Leerraum inklusive; Zeitstempel sind Zeichenketten der API.

export interface Notiz {
  id: number
  scope_typ: string
  scope_id: string
  text: string
  erstellt_am: string
  geaendert_am: string | null
}

export interface JournalInhalt {
  scope_typ: string
  scope_id: string
  notizen: Notiz[]
  tags: string[]
}

export interface Schlagwort {
  name: string
  anzahl: number
}

export function holeTag(datum: string): Promise<Tagesuebersicht> {
  return hole(`/tage/${datum}`) as Promise<Tagesuebersicht>
}

export function holeKalender(monat: string): Promise<Monatskalender> {
  return hole(`/kalender?monat=${encodeURIComponent(monat)}`) as Promise<Monatskalender>
}

// AP-08-kampagnen: ohne Filter das ganze Verzeichnis der bestätigten
// Kampagnen.
export function holeKampagnen(underlying?: string): Promise<KampagnenListe> {
  const zusaetze = new URLSearchParams()
  if (underlying) zusaetze.set('underlying', underlying)
  const query = zusaetze.toString()
  return hole(`/kampagnen${query === '' ? '' : `?${query}`}`) as Promise<KampagnenListe>
}

export function holeKampagne(campaignId: number): Promise<KampagnenDetail> {
  return hole(`/kampagnen/${campaignId}`) as Promise<KampagnenDetail>
}

export function holeJournal(scopeTyp: string, scopeId: string): Promise<JournalInhalt> {
  return hole(`/journal/${scopeTyp}/${encodeURIComponent(scopeId)}`) as Promise<JournalInhalt>
}

export function legeNotizAn(scopeTyp: string, scopeId: string, text: string): Promise<Notiz> {
  return schicke('POST', `/journal/${scopeTyp}/${encodeURIComponent(scopeId)}/notizen`, {
    text,
  }) as Promise<Notiz>
}

export function aendereNotiz(id: number, text: string): Promise<Notiz> {
  return schicke('PUT', `/journal/notizen/${id}`, { text }) as Promise<Notiz>
}

export function loescheNotiz(id: number): Promise<null> {
  return schicke('DELETE', `/journal/notizen/${id}`) as Promise<null>
}

export function ersetzeTags(
  scopeTyp: string,
  scopeId: string,
  tags: string[],
): Promise<JournalInhalt> {
  return schicke('PUT', `/journal/${scopeTyp}/${encodeURIComponent(scopeId)}/tags`, {
    tags,
  }) as Promise<JournalInhalt>
}

export function holeAlleSchlagwoerter(): Promise<Schlagwort[]> {
  return hole('/tags') as Promise<Schlagwort[]>
}

// AP-06e, Equity-Kurve und Drawdown (Dashboard): wie immer gilt — Geld
// bleibt Zeichenkette, Reihenfolge wie geliefert, nichts gerechnet.

export interface EquityTag {
  datum: string
  netto_eur: string
  kumuliert_eur: string
  drawdown_eur: string
  anzahl_strukturen: number
  anzahl_strukturen_kurs_fehlt: number
}

export interface EquityMonat {
  monat: string
  anzahl_strukturen: number
  summe_netto_eur: string
  durchschnitt_netto_eur: string | null
  trefferquote: string | null
  anzahl_strukturen_kurs_fehlt: number
}

export interface Equity {
  tage: EquityTag[]
  monate: EquityMonat[]
  max_drawdown_eur: string
  max_drawdown_datum: string | null
}

// AP-08f2: von/bis im ISO-Format, beide einschließlich; ohne Angabe alles.
function zeitraumQuery(von?: string | null, bis?: string | null): string {
  const zusaetze = new URLSearchParams()
  if (von) zusaetze.set('von', von)
  if (bis) zusaetze.set('bis', bis)
  const query = zusaetze.toString()
  return query === '' ? '' : `?${query}`
}

export function holeEquity(von?: string | null, bis?: string | null): Promise<Equity> {
  return hole(`/equity${zeitraumQuery(von, bis)}`) as Promise<Equity>
}

// AP-06f, Kosten & Erträge. Kategorien in fester Reihenfolge; Kommissionen
// und Barausgleich tragen im_ergebnis_enthalten = true (schon im Ergebnis).
export type CashflowKategorieName =
  | 'kommissionen'
  | 'kommissionsanpassungen'
  | 'gebuehren'
  | 'zinsen_erhalten'
  | 'zinsen_gezahlt'
  | 'dividenden'
  | 'quellensteuer'
  | 'barausgleich'
  | 'sonstige'
  | 'ein_auszahlungen'

export interface CashflowKategorie {
  kategorie: CashflowKategorieName
  anzahl: number
  summe_eur: string
  anzahl_kurs_fehlt: number
  im_ergebnis_enthalten: boolean
}

export interface CashflowMonat {
  monat: string
  kategorie: CashflowKategorieName
  anzahl: number
  summe_eur: string
  anzahl_kurs_fehlt: number
}

export interface Cashflows {
  kategorien: CashflowKategorie[]
  monate: CashflowMonat[]
}

export function holeCashflows(von?: string | null, bis?: string | null): Promise<Cashflows> {
  return hole(`/cashflows${zeitraumQuery(von, bis)}`) as Promise<Cashflows>
}

// AP-06g, Kapitalentwicklung (realisiert, kein NAV). Im Zeitraum der Bestand,
// nicht ab 0; Anfang + Einzahlungen + Ergebnis + Cash = Ende.
export interface KapitalTag {
  datum: string
  einzahlungen_kumuliert: string
  ergebnis_kumuliert: string
  cash_kumuliert: string
  kapital: string
}

export interface Kapital {
  tage: KapitalTag[]
  anfangskapital: string
  endkapital: string
  einzahlungen_im_zeitraum: string
  ergebnis_im_zeitraum: string
  cash_im_zeitraum: string
  anzahl_kurs_fehlt: number
}

export function holeKapital(von?: string | null, bis?: string | null): Promise<Kapital> {
  return hole(`/kapital${zeitraumQuery(von, bis)}`) as Promise<Kapital>
}

// AP-06h, Kontowert laut IB (realisiert + unrealisiert) je Tag; gewinn =
// Kontowert − kumulierte Einzahlungen. Im Zeitraum der Bestand.
export interface NavTag {
  datum: string
  gesamt: string
  cash: string | null
  aktien: string | null
  optionen: string | null
  rohstoffe: string | null
  einzahlungen_kumuliert: string
  gewinn: string
}

export interface Nav {
  tage: NavTag[]
  anfangswert: string | null
  endwert: string | null
  anzahl_kurs_fehlt: number
}

export function holeNav(von?: string | null, bis?: string | null): Promise<Nav> {
  return hole(`/nav${zeitraumQuery(von, bis)}`) as Promise<Nav>
}
