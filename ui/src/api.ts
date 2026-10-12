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
  // Kontrakte bzw. Stück der Eröffnung (menge des ersten Glieds), Text wie die
  // API ihn liefert.
  menge: string | null
  struktur_summe_netto: string | null
  realisiert_bisher?: string | null
  // AP-06se: Schrittansicht — Nummer des Glieds und Zahl der Glieder.
  // AP-06sf: Prämienwert der offenen Legs (EUR, Verkäufersicht, Credit positiv).
  praemie_offen_eur?: string | null
  praemie_aktuell_eur?: string | null
  schritt?: number | null
  schritte_gesamt?: number | null
  waehrung: string | null
  waehrungen: string[]
  sicht: string
  // AP-13x: OA-Strategie/-Status/-Erkennung der Kette (AP-13wk) — reine
  // Anzeige, Text oder leer; keine Interpretation.
  oa_strategie: string | null
  oa_status: string | null
  oa_erkennung: string | null
  // AP-07ku: unrealisiert (EUR) der offenen Legs; null bei geschlossenen.
  unrealisiert_eur: string | null
  offene_legs_ohne_kurs: number
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

// AP-07f/AP-08g2b: die Kettenfilter, die /ketten und /auswertung gemeinsam
// kennen. Datumswerte ISO (JJJJ-MM-TT), beide Enden einschließlich.
// AP-07fm: Die sechs Auswahlfilter dürfen mehrere Werte tragen (ODER).
export interface KettenFilter {
  basiswert?: string[]
  anlageklasse?: string[]
  waehrung?: string[]
  strategie?: string[]
  seite?: string[]
  endzustand?: string[]
  min_rolls?: number
  max_rolls?: number
  eroeffnet_ab?: string
  eroeffnet_bis?: string
  geschlossen_ab?: string
  geschlossen_bis?: string
}

function filterZusaetze(filter: KettenFilter, zusaetze: URLSearchParams): void {
  const texte: (keyof KettenFilter)[] = [
    'basiswert',
    'anlageklasse',
    'waehrung',
    'strategie',
    'seite',
    'endzustand',
    'eroeffnet_ab',
    'eroeffnet_bis',
    'geschlossen_ab',
    'geschlossen_bis',
  ]
  for (const schluessel of texte) {
    const wert = filter[schluessel]
    if (Array.isArray(wert)) {
      // AP-07fm: je Wert ein Parameter (`?basiswert=A&basiswert=B`).
      for (const eins of wert) if (eins) zusaetze.append(schluessel, eins)
    } else if (wert) {
      zusaetze.set(schluessel, String(wert))
    }
  }
  if (filter.min_rolls !== undefined) zusaetze.set('min_rolls', String(filter.min_rolls))
  if (filter.max_rolls !== undefined) zusaetze.set('max_rolls', String(filter.max_rolls))
}

export interface KettenAbfrage extends KettenFilter {
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
  // AP-06se: 'schritte' = eine Zeile je Kettenglied (Roll-Schritt).
  ansicht?: 'ketten' | 'schritte'
}

export function holeKetten(abfrage: KettenAbfrage): Promise<KettenListe> {
  const zusaetze = new URLSearchParams()
  filterZusaetze(abfrage, zusaetze)
  if (abfrage.sortierung !== undefined) zusaetze.set('sortierung', abfrage.sortierung)
  if (abfrage.richtung !== undefined) zusaetze.set('richtung', abfrage.richtung)
  if (abfrage.von) zusaetze.set('von', abfrage.von)
  if (abfrage.bis) zusaetze.set('bis', abfrage.bis)
  zusaetze.set('limit', String(abfrage.limit))
  zusaetze.set('offset', String(abfrage.offset))
  if (abfrage.ansicht === 'schritte') zusaetze.set('ansicht', 'schritte')
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

// AP-14b: Status des Roller-Dienstes (durchgereicht, nur lesend).
export interface RollerEdge {
  theo_roll?: number | null
  edge_abs?: number | null
  edge_ccy?: string | null
  implied_term_spread?: number | null
  verdict?: string | null
  status?: string | null
  data_quality?: string | null
  ts?: string | null
}

export interface RollerBreach {
  position_key: string
  symbol: string
  expiration: string
  right: string
  short_strike: number
  danger_strike: number
  target_delta: number
  underlying: number | null
  short_delta: number | null
  dte: number
  menge: number
  puffer: number | null
  seit: string | null
  edge: RollerEdge | null
}

export interface RollerSpread {
  key: string
  typ: string
  symbol: string
  expiration: string
  short: number
  long: number
  menge: number
  short_delta: number | null
  underlying: number | null
}

export interface RollerStatus {
  dienst: string
  stufe: string
  gestartet: string
  herzschlag: string
  orders: { freigegeben: boolean; modus: string }
  ib: { verbunden: boolean; host: string; port: number; client_id: number }
  positionen: { spreads: number; einzel: number }
  scanner: {
    letzter_lauf: string | null
    laeufe: number
    dauer_s: number | null
    intervall_s: number | null
    symbole: string[]
  }
  breaches: RollerBreach[]
  spreads: RollerSpread[]
  log: string[]
}

export interface RollerAntwort {
  erreichbar: boolean
  status: RollerStatus | null
}

export function holeRoller(): Promise<RollerAntwort> {
  return hole('/roller-status') as Promise<RollerAntwort>
}

// AP-14a: Zustand der Station (Seite „System“).
export interface Dienst {
  name: string
  port: number | null
  erreichbar: boolean | null
  hinweis: string | null
}

export interface System {
  dienste: Dienst[]
  importe: { quelle: string; zuletzt: string | null; daten_bis: string | null }[]
}

export function holeSystem(): Promise<System> {
  return hole('/system') as Promise<System>
}

// AP-12a: Option-Omega-Backtests — Beträge als Text, USD je Kontrakt.
export interface BacktestZuordnung {
  oo_strategie: string
  oa_strategie: string
  erkennung: 'heuristik' | 'manuell'
  status: 'vorschlag' | 'bestaetigt' | 'abgelehnt'
  treffer: number
  anteil: string
  eindeutig: boolean
  oo_anzahl: number
  erster: string | null
  letzter: string | null
}

export interface BacktestUrsache {
  ursache: string
  anzahl: number
  summe: string
}

export interface BacktestVergleich {
  oo_strategie: string
  oa_strategie: string
  paare: number
  summe_backtest: string
  summe_live: string
  differenz: string
  nur_backtest: number
  summe_nur_backtest: string
  nur_live: number
  summe_nur_live: string
  offen: number
  ursachen: BacktestUrsache[]
  kontrakt_effekt: string
}

export interface Backtests {
  zuordnungen: BacktestZuordnung[]
  vergleich: BacktestVergleich[]
  ohne_zuordnung: { oo_strategie: string; anzahl: number }[]
}

export interface BacktestPaar {
  art: 'paar' | 'nur_backtest' | 'nur_live' | 'offen'
  zeit_backtest: string | null
  zeit_live: string | null
  oa_trade: string | null
  kontrakte_backtest: number | null
  kontrakte_live: number | null
  pl_backtest: string | null
  pl_live: string | null
  differenz: string | null
  ursache: string | null
  zeitversatz_min: number | null
  kontrakt_effekt: string | null
}

function zeitraumSuche(von?: string | null, bis?: string | null): URLSearchParams {
  const suche = new URLSearchParams()
  if (von) suche.set('von', von)
  if (bis) suche.set('bis', bis)
  return suche
}

export function holeBacktests(von?: string | null, bis?: string | null): Promise<Backtests> {
  const text = zeitraumSuche(von, bis).toString()
  return hole(`/backtests${text ? `?${text}` : ''}`) as Promise<Backtests>
}

export function holeBacktestPaare(
  oo: string,
  oa: string,
  von?: string | null,
  bis?: string | null,
): Promise<BacktestPaar[]> {
  const suche = zeitraumSuche(von, bis)
  suche.set('oo_strategie', oo)
  suche.set('oa_strategie', oa)
  return hole(`/backtests/paare?${suche.toString()}`) as Promise<BacktestPaar[]>
}

export function entscheideBacktest(
  oo: string,
  oa: string,
  status: 'bestaetigt' | 'abgelehnt' | 'vorschlag',
): Promise<unknown> {
  return schicke('POST', '/journal/backtests/zuordnung', {
    oo_strategie: oo,
    oa_strategie: oa,
    status,
  })
}

// AP-13ab: Abgleich OA ↔ IB — Beträge als Text in der Währung des Trades.
export interface OaTradeVergleich {
  oa_trade: string
  strategie: string | null
  status: string
  schluss_zeit: string | null
  waehrung: string
  oa_profit: string
  ib_netto: string | null
  differenz: string | null
  grund: string
}

export interface OaStrategieVergleich {
  strategie: string | null
  waehrung: string
  anzahl: number
  gleich: number
  verrechnet: number
  gering: number
  abweichend: number
  offen: number
  fehlt: number
  waehrung_unklar: number
  summe_oa: string
  summe_ib: string
  differenz: string
}

export interface OaAbgleich {
  strategien: OaStrategieVergleich[]
  abweichungen: OaTradeVergleich[]
  anzahl_trades: number
  anzahl_gleich: number
}

export function holeOaAbgleich(von?: string | null, bis?: string | null): Promise<OaAbgleich> {
  const suche = new URLSearchParams()
  if (von) suche.set('von', von)
  if (bis) suche.set('bis', bis)
  const text = suche.toString()
  return hole(`/oa-abgleich${text ? `?${text}` : ''}`) as Promise<OaAbgleich>
}

// AP-06sc: Strategie-Scorecard — Beträge und Quoten als Text.
export interface StrategieZeile {
  strategie: string | null
  anzahl: number
  offen: number
  gewinner: number
  verlierer: number
  kurs_fehlt: number
  trefferquote: string | null
  summe_eur: string
  durchschnitt_eur: string | null
  durchschnitt_gewinn_eur: string | null
  durchschnitt_verlust_eur: string | null
  profit_faktor: string | null
  groesster_gewinn_eur: string | null
  groesster_verlust_eur: string | null
  max_drawdown_eur: string
  zuteilungsquote: string | null
  haltedauer_tage: string | null
  erste_schliessung: string | null
  letzte_schliessung: string | null
  bisher_offene_eur: string
  max_drawdown_schritte_eur: string
}

export interface Strategien {
  zeilen: StrategieZeile[]
  summe_strategien_eur: string
  realisiert_gesamt_eur: string
  ohne_position_eur: string
  abgrenzung_eur: string
}

export function holeStrategien(
  von?: string | null,
  bis?: string | null,
  ansicht: 'positionen' | 'schritte' = 'positionen',
): Promise<Strategien> {
  const suche = new URLSearchParams()
  if (ansicht !== 'positionen') suche.set('ansicht', ansicht)
  if (von) suche.set('von', von)
  if (bis) suche.set('bis', bis)
  const text = suche.toString()
  return hole(`/strategien${text ? `?${text}` : ''}`) as Promise<Strategien>
}

// AP-08ue: Startseite — alle Beträge als Text aus GET /uebersicht.
export interface Uebersicht {
  heute: string
  kontowert_stand: string | null
  kontowert_eur: string | null
  realisiert_woche_eur: string
  realisiert_monat_eur: string
  realisiert_jahr_eur: string
  bestand_stand: string | null
  unrealisiert_eur: string | null
  offene_positionen: number
  verfaelle: { verfall: string; basiswert: string; anzahl: number }[]
}

// Das Datum „heute" setzt der Browser (lokale Zeit), damit Woche und Monat
// zur Uhr des Nutzers passen.
export function holeUebersicht(): Promise<Uebersicht> {
  const jetzt = new Date()
  const heute = `${jetzt.getFullYear()}-${String(jetzt.getMonth() + 1).padStart(2, '0')}-${String(jetzt.getDate()).padStart(2, '0')}`
  return hole(`/uebersicht?heute=${heute}`) as Promise<Uebersicht>
}

// AP-08r: Durchsicht der Rollkandidaten. Geld als Text (Vertrag 8).
export interface Rollkandidat {
  rang: number
  neu_legs: string
  neu_eroeffnet: string
  neu_preis_auf: string | null
  abstand_minuten: number
  mengenverhaeltnis: string
  schluessel_struktur: string
}

export interface Rollgruppe {
  basiswert: string
  seite: string
  alt_legs: string
  alt_geschlossen: string
  alt_preis_zu: string | null
  schluessel_kette: string
  kandidaten: Rollkandidat[]
}

export interface Rollkandidaten {
  anzahl_gruppen: number
  anzahl_kandidaten: number
  gruppen: Rollgruppe[]
}

export function holeRollkandidaten(): Promise<Rollkandidaten> {
  return hole('/rollkandidaten') as Promise<Rollkandidaten>
}

export function sendeRollurteil(
  schluesselKette: string,
  schluesselStruktur: string,
  urteil: 'bestaetigt' | 'abgelehnt',
): Promise<{ neu: boolean }> {
  return schicke('POST', '/journal/rollkandidaten/urteil', {
    schluessel_kette: schluesselKette,
    schluessel_struktur: schluesselStruktur,
    urteil,
  }) as Promise<{ neu: boolean }>
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
  // AP-06i: Aktiengeschäfte ohne Struktur; ihr Betrag steckt in netto_eur.
  anzahl_lose_legs: number
  anzahl_lose_legs_kurs_fehlt: number
}

export interface EquityMonat {
  monat: string
  anzahl_strukturen: number
  summe_netto_eur: string
  durchschnitt_netto_eur: string | null
  trefferquote: string | null
  anzahl_strukturen_kurs_fehlt: number
  lose_legs_eur: string
  anzahl_lose_legs: number
  anzahl_lose_legs_kurs_fehlt: number
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

// AP-07fw: wählbare Werte der Filter (Kontosicht, inklusive loser Legs).
export interface Filterwerte {
  basiswerte: string[]
  anlageklassen: string[]
  waehrungen: string[]
  strategien: string[]
  seiten: string[]
  endzustaende: string[]
}

export function holeFilterwerte(): Promise<Filterwerte> {
  return hole('/filterwerte') as Promise<Filterwerte>
}

// AP-13r2: Wie aktuell der OptionApp-Export ist.
export interface OaStand {
  export_bis: string | null
  ohne_export: number
  ohne_export_ab: string | null
}

export function holeOaStand(): Promise<OaStand> {
  return hole('/oa-stand') as Promise<OaStand>
}

// AP-07f: Verlauf und Ergebnis der gefilterten Ketten. von/bis gelten hier am
// Schließungstag (Z2/Z4), nicht als „aktiv im Zeitraum" wie bei /ketten.
export interface AuswertungErgebnis {
  anzahl_ketten: number
  anzahl_strukturen: number
  summe_netto_eur: string
  anzahl_kurs_fehlt: number
  lose_legs_eingeschlossen: boolean
}

export interface Auswertung extends Equity {
  ergebnis: AuswertungErgebnis
  // AP-07fu: Wochen (ISO) und das unrealisierte Ergebnis offener Positionen.
  wochen: { schluessel: string; beginn: string; ende: string; summe_netto_eur: string }[]
  unrealisiert: {
    stichtag: string | null
    eur: string
    anzahl_legs: number
    ohne_kurs: number
    // AP-07fv: realisiert + unrealisiert, Endpunkt der gestrichelten Linie.
    mit_realisiert_eur: string
  } | null
  // AP-07fv: aufsummiert realisiert für jeden Kalendertag; je Positionswährung.
  verlauf: { datum: string; kumuliert_eur: string }[]
  netto_je_waehrung: { waehrung: string; summe: string }[]
}

export function holeAuswertung(
  filter: KettenFilter,
  von?: string | null,
  bis?: string | null,
): Promise<Auswertung> {
  const zusaetze = new URLSearchParams()
  filterZusaetze(filter, zusaetze)
  if (von) zusaetze.set('von', von)
  if (bis) zusaetze.set('bis', bis)
  const query = zusaetze.toString()
  return hole(`/auswertung${query === '' ? '' : `?${query}`}`) as Promise<Auswertung>
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

// AP-08d: der Bestand laut IB mit letztem bekanntem Kurs und unrealisiertem
// Ergebnis (jüngster Stichtag der Flex-Auswertung). Werte der Quelle, nichts
// neu bewertet; die EUR-Werte kommen mit IBs Kurs der Zeile.
export interface DepotPosition {
  conid: number
  symbol: string
  basiswert: string
  anlageklasse: string
  seite: string | null
  verfall: string | null
  strike: string | null
  multiplikator: string | null
  menge: string
  waehrung: string
  einstandskurs: string | null
  kurs: string | null
  marktwert: string | null
  unrealisiert: string | null
  marktwert_eur: string | null
  unrealisiert_eur: string | null
}

export interface DepotKlasse {
  anlageklasse: string
  anzahl: number
  marktwert_eur: string
  unrealisiert_eur: string
}

export interface Depot {
  stichtag: string | null
  positionen: DepotPosition[]
  summen: { marktwert_eur: string; unrealisiert_eur: string; je_klasse: DepotKlasse[] }
}

export function holeDepot(): Promise<Depot> {
  return hole('/depot') as Promise<Depot>
}

// AP-08u: vom Ergebnis zum Kontostand. IBs Gewinn (Kontowert minus
// Einzahlungen) in realisiert, unrealisiert, sonstige Buchungen und Rest
// zerlegt, daneben das realisierte Ergebnis des Journals. Werte der API.
export interface Ueberleitung {
  stichtag: string | null
  bestand_stichtag: string | null
  kontowert: string | null
  einzahlungen: string | null
  gewinn_ib: string | null
  ib: {
    realisiert: string
    unrealisiert: string
    sonstige_buchungen: string
    rest: string
  } | null
  journal: { realisiert: string; differenz_realisiert: string } | null
  abdeckung: { ausfuehrungen: number; mit_ib_wert: number }
  anzahl_kurs_fehlt: number
  // AP-08u2: Journal neben IB, Unterschied je Zeile, Zerlegung des Unterschieds.
  journal_spalte: UeberleitungSpalte | null
  unterschied_spalte: UeberleitungSpalte | null
  abgleich_realisiert: {
    praemien_im_einstand: string
    waehrungsmethode: string
    zeitpunkt_offene_strukturen: string
    zeitpunkt_beitrag: string
    nicht_zugeordnet: string
    anzahl_legs_offene_strukturen: number
    zeilen_gleich: number
    zeilen_abweichend: number
    // AP-08u3: der Rest im Einzelnen.
    kurseffekt_praemien: string
    einzelreste: { gruppe: string; waehrung: string; nativ: string; eur: string }[]
  } | null
}

export interface UeberleitungSpalte {
  einzahlungen: string
  realisiert: string
  unrealisiert: string
  sonstige_buchungen: string
  rest: string
}

export function holeUeberleitung(): Promise<Ueberleitung> {
  return hole('/ueberleitung') as Promise<Ueberleitung>
}

// AP-08p: Wertentwicklung des Kontos — zeitgewichteter Index, Drawdown in % vom
// Höchststand, Wochen und Monate. Werte der API.
export interface PerformanceTag {
  datum: string
  kontowert: string
  gewinn_ib: string
  index: string
  drawdown_quote: string
  drawdown_prozent: string
}

export interface Periode {
  schluessel: string
  beginn: string
  ende: string
  gewinn_ib: string
  realisiert: string
  rendite_quote: string
}

export interface Performance {
  tage: PerformanceTag[]
  max_drawdown_quote: string
  max_drawdown_prozent: string
  max_drawdown_datum: string | null
  kontowert_ende: string | null
  gewinn_ib_zeitraum: string
  rendite_zeitraum_quote: string
  realisiert_zeitraum: string
  wochen: Periode[]
  monate: Periode[]
  realisiert_kumuliert: { datum: string; wert: string }[]
}

export function holePerformance(von?: string | null, bis?: string | null): Promise<Performance> {
  return hole(`/performance${zeitraumQuery(von, bis)}`) as Promise<Performance>
}
