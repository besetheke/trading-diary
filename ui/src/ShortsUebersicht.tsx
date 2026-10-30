// AP-19: Shorts im Konto — jede Short-Option (Spread oder naked) mit Ampel, getrennt nach Indizes und Einzelwerten.
// Eine Zeile je Position wie in der TWS (Ticker, Verfall, Strikes mit Art, Position, Kurs, DTE, Kurswert, unrealisiert);
// gehört die Position zu einer Roller-Kette, steht die Kette in derselben Zeile, und ein Klick klappt darunter alles
// auf, was man über Kette und Position wissen muss: Lage mit Freigabe, Kettenhistorie, Strike-Leiter, Rollregel,
// Kostenbremse, Kettenverlauf. Bewertet wird im Roller (roller/shorts.py); hier wird nur gezeigt.
// Reihenfolge (Nutzer 29.10.2026): Ticker alphabetisch, dann |Δ| absteigend, dann DTE aufsteigend.

import { Fragment, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeRollerLive, sendeRollerBefehl } from './api'
import type { Ampel, JournalKetteKurz, RollerKetteStand, RollerRegeln, RollerShort, RollerShorts, RollerStrategie } from './api'
import { zeitDe } from './format'
import { Kettenverlauf, Kostenbremse, RollRegel, StrikeLeiter } from './Kettenkarte'

const AMPEL_TEXT: Record<Ampel, string> = { rot: 'handeln', gelb: 'beobachten', grau: 'ohne Daten', gruen: 'ok' }
const REGEL =
  'rot: Short im Geld oder |Δ| ≥ Schwelle (bei DTE ≤ 1 wird gelb zu rot) · gelb: |Δ| ≥ 80 % der Schwelle · ' +
  'ohne Delta von IB entscheidet ersatzweise der Abstand (unter 1 % Index, 3 % Einzelwert)'
const HERKUNFT: Record<RollerShort['schwelle_herkunft'], string> = {
  roller: 'Schwelle der Roller-Kette',
  position: 'von Hand für diese Position',
  ticker: 'von Hand für den Ticker',
  staffel: 'DTE-Staffel des Rollers',
}
const SPEICHER = 'shorts-nur-handlungsbedarf'
const MONAT = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const ART_TWS: Record<string, string> = {
  BPS: 'Bull-Put',
  BCS: 'Bear-Call',
  'Debit Put': 'Bear-Put',
  'Debit Call': 'Bull-Call',
  'Kalender Put': 'Put-Kalender',
  'Kalender Call': 'Call-Kalender',
  'Diagonal Put': 'Put-Diagonal',
  'Diagonal Call': 'Call-Diagonal',
}

// Verfall wie in der TWS: Oct29'26
function tws(jjjjmmtt: string): string {
  return jjjjmmtt.length === 8 ? `${MONAT[Number(jjjjmmtt.slice(4, 6)) - 1]}${jjjjmmtt.slice(6, 8)}'${jjjjmmtt.slice(2, 4)}` : jjjjmmtt
}

function strike(x: number): string {
  return x.toLocaleString('en-US', { maximumFractionDigits: 2, useGrouping: false })
}

function verfallText(z: RollerShort): string {
  return z.long_verfall ? `${tws(z.verfall)}/${tws(z.long_verfall)}` : tws(z.verfall)
}

// Strikes zuerst, dann die Art wie in der TWS: „7655/7625 Bull-Put“, Einzelposition „265 CALL“. Puts absteigend, Calls aufsteigend.
function strikeText(z: RollerShort): string {
  const recht = z.recht === 'P' ? 'PUT' : 'CALL'
  if (z.long === null) return `${strike(z.short)} ${recht}`
  const strikes = z.strikes && z.strikes.length > 0 ? z.strikes : [z.short, z.long]
  const werte = z.deckung === 'kalender' ? [z.short] : strikes
  return `${werte.map(strike).join('/')} ${ART_TWS[z.art] ?? z.art}`
}

// Vorzeichen wie in der TWS: Short-Positionen und Credit-Spreads negativ, Debit-Spreads, Kalender und Diagonale positiv.
function menge(z: RollerShort): number {
  const positiv = z.deckung === 'debit' || z.deckung === 'kalender' || z.deckung === 'diagonal'
  return positiv ? z.menge : -z.menge
}

function kettenVon(z: RollerShort): string[] {
  return z.ketten && z.ketten.length > 0 ? z.ketten : z.kette ? [z.kette] : []
}

function zahl(x: number | null | undefined, stellen = 0): string {
  return x === null || x === undefined
    ? '—'
    : x.toLocaleString('de-DE', { minimumFractionDigits: stellen, maximumFractionDigits: stellen })
}

// Ticker alphabetisch, dann |Δ| absteigend (gefährdetste zuerst; ohne Delta zuletzt), dann DTE aufsteigend.
export function ordne(zeilen: RollerShort[]): RollerShort[] {
  return [...zeilen].sort(
    (a, b) =>
      a.symbol.localeCompare(b.symbol, 'de') ||
      (b.delta ?? -1) - (a.delta ?? -1) ||
      a.dte - b.dte ||
      a.verfall.localeCompare(b.verfall) ||
      a.short - b.short,
  )
}

function Balken({ z }: { z: RollerShort }): JSX.Element {
  if (z.ohne_delta || z.delta_anteil === null) {
    return (
      <span className="delta-balken ohne" title="Kein Delta von IB — die Ampel entscheidet nach dem Abstand">
        ohne Delta
      </span>
    )
  }
  const breite = (Math.min(z.delta_anteil, 1.25) / 1.25) * 100
  return (
    <span className="delta-balken" title={`${Math.round(z.delta_anteil * 100)} % der Schwelle (${HERKUNFT[z.schwelle_herkunft]})`}>
      <span className={`fuellung ${z.ampel}`} style={{ width: `${breite}%` }} />
      <span className="marke" />
      <span className="text">
        {zahl(z.delta, 2)} / {zahl(z.schwelle, 2)}
      </span>
    </span>
  )
}

function SchwelleForm(props: { z: RollerShort; konto: 'paper' | 'live' }): JSX.Element {
  const { z, konto } = props
  const [wert, setzeWert] = useState(z.schwelle === null ? '' : String(z.schwelle))
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [gesendet, setzeGesendet] = useState(false)
  const senden = (p: { ticker?: string; position?: string; wert?: string }): void => {
    setzeFehler(null)
    sendeRollerBefehl('schwelle-setzen', { ...p, konto })
      .then(() => setzeGesendet(true))
      .catch((e: unknown) => setzeFehler(fehlerText(e)))
  }
  return (
    <div className="schwelle-form">
      |Δ|-Schwelle ({HERKUNFT[z.schwelle_herkunft]}){' '}
      <input value={wert} onChange={(e) => setzeWert(e.target.value)} size={5} aria-label="Schwelle" />{' '}
      <button type="button" onClick={() => senden({ ticker: z.symbol, wert })}>
        für {z.symbol}
      </button>{' '}
      <button type="button" onClick={() => senden({ position: z.key, wert })}>
        nur diese Position
      </button>{' '}
      {z.schwelle_herkunft === 'ticker' ? (
        <button type="button" onClick={() => senden({ ticker: z.symbol })}>
          Ticker zurücksetzen
        </button>
      ) : null}
      {z.schwelle_herkunft === 'position' ? (
        <button type="button" onClick={() => senden({ position: z.key })}>
          Position zurücksetzen
        </button>
      ) : null}
      <span className="sicht">
        {gesendet ? ' Gespeichert — gilt ab der nächsten Prüfung (alle 2 Minuten).' : ' Gilt ab der nächsten Prüfung (alle 2 Minuten).'}
      </span>
      {fehler ? <p className="meldung">{fehler}</p> : null}
    </div>
  )
}

type KettenInfo = { kette: RollerKetteStand; regeln?: RollerRegeln }

// DTE-Staffel des Rollers (STAFFEL_STANDARD) — Grundlage der Schwelle manueller Positionen (OF-109).
const STAFFEL_STANDARD: [number, number][] = [[7, 0.38], [14, 0.42], [21, 0.46], [28, 0.5]]

function jjjjmmtt(iso: string | null): string {
  return iso ? iso.slice(0, 10).replace(/-/g, '') : ''
}

// Eine Position ohne Roller-Kette als „Kette“ für die Karten: Strikes, Kurs, Delta und Schwelle aus der Übersicht,
// Rolls und Verlauf aus der Kette im Journal (Glieder in Reihenfolge; Netto je Glied ist das Ergebnis des Glieds).
function kunstKette(z: RollerShort): KettenInfo {
  const j = z.journal
  const schritte = j?.schritte ?? []
  const verlauf = schritte.map((s, i) => {
    const vorher = schritte[i - 1]
    return {
      art: i === 0 ? 'eroeffnung' : s.art === 'close' ? 'schliessen' : 'roll',
      netto: s.netto === null ? null : Number(s.netto),
      zeit: s.eroeffnet_am,
      von: vorher
        ? { verfall: jjjjmmtt(vorher.verfall), short: Number(vorher.short ?? 0), long: Number(vorher.long ?? vorher.short ?? 0) }
        : null,
    }
  })
  // naked: keine Breite — für den Bildrand 1 % des Strikes, damit die Leiter nicht auf null schrumpft
  const breite = z.long !== null && z.long !== z.short ? Math.abs(z.short - z.long) : Math.max(z.short * 0.01, 1)
  const regeln: RollerRegeln = {
    seite: z.recht === 'P' ? 'BPS' : 'BCS',
    ziel_delta: 0,
    breite,
    ziel_dte: 0,
    verfall_modus: '',
    pt_restwert: 0,
    kontrakte: z.menge,
    staffel: STAFFEL_STANDARD,
    delta_puffer: 0,
    gap_aufschlag: 0.1,
    roll_wochen_max: 0,
    max_verschiebung: 0,
    max_debit_normal: 0,
    early_exit_delta: 0,
    early_exit_fenster_min: 0,
    max_kettenverlust_anteil: null,
    max_rolls_pro_tag: 0,
    tagesende_schliessen: false,
    multiplikator: '100',
    waehrung: j?.waehrung ?? '',
  }
  const kette: RollerKetteStand = {
    kette_id: j ? `Journal #${j.chain_id}` : 'Position',
    strategie: j?.strategie ?? z.art,
    aktiv: { verfall: z.verfall, short: z.short, long: z.long ?? z.short, menge: z.menge },
    erstkredit: null,
    netto: j?.realisiert_bisher ? Number(j.realisiert_bisher) : 0,
    rolls: j?.anzahl_rolls ?? 0,
    pt_limit: null,
    spot: z.spot,
    short_delta: z.delta === null ? null : z.recht === 'P' ? -z.delta : z.delta,
    dte: z.dte,
    schwelle: z.schwelle,
    verlauf,
  }
  return { kette, regeln }
}

// Kette im Journal: Glieder (Eröffnung, Rolls, Schließen) mit Verfall, Strikes und Ergebnis.
function JournalSchritte({ j }: { j: JournalKetteKurz }): JSX.Element {
  return (
    <div className="tabelle-rahmen">
      <table className="strategie-tabelle">
        <thead>
          <tr>
            <th>#</th><th>Art</th><th>Eröffnet</th><th>Geschlossen</th><th>Verfall</th><th>Strikes</th>
            <th className="zahl">Menge</th><th className="zahl">Ergebnis</th>
          </tr>
        </thead>
        <tbody>
          {(j.schritte ?? []).map((s) => (
            <tr key={`${s.chain_id}-${s.sequenz}`}>
              <td>{s.sequenz}</td>
              <td>{s.art}</td>
              <td>{s.eroeffnet_am ? zeitDe(s.eroeffnet_am) : '—'}</td>
              <td>{s.geschlossen_am ? zeitDe(s.geschlossen_am) : 'offen'}</td>
              <td>{s.verfall ? tws(jjjjmmtt(s.verfall)) : '—'}</td>
              <td>{[s.short, s.long].filter((x) => x !== null).map((x) => strike(Number(x))).join('/')}</td>
              <td className="zahl">{s.menge ?? '—'}</td>
              <td className="zahl">{s.netto === null ? '—' : `${zahl(Number(s.netto), 2)} ${s.waehrung ?? ''}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Karten({ info }: { info: KettenInfo }): JSX.Element {
  return (
    <div className="kk-raster">
      <StrikeLeiter kette={info.kette} regeln={info.regeln} />
      <RollRegel kette={info.kette} regeln={info.regeln} />
      <Kostenbremse kette={info.kette} regeln={info.regeln} />
      <Kettenverlauf kette={info.kette} />
    </div>
  )
}

interface Werkzeuge {
  ketten: Map<string, KettenInfo>
  lage?: (k: RollerKetteStand) => ReactNode
  verlauf?: (k: RollerKetteStand) => ReactNode
  rest?: ReactNode
}

// Was an der Kette hängt: Hinweis in der Zeile (Signal, Vorschlag, angehalten).
function KettenZeile({ k }: { k: RollerKetteStand }): JSX.Element {
  const hinweis = k.status === 'pruefen' ? 'ANGEHALTEN' : k.vorschlag ? 'Vorschlag' : k.signal ? 'ROLL-SIGNAL' : null
  return (
    <>
      <strong>{k.kette_id}</strong> · Netto {zahl(k.netto, 1)}
      {hinweis ? <span className="kette-hinweis"> · {hinweis}</span> : null}
    </>
  )
}

// Aufgeklappt, direkt unter dem Trade: Ketteninfo, Lage mit Freigabe, Kettentrades und die Karten fürs Rollen —
// für jede Kette, die diese Position hält.
function Details(props: { z: RollerShort; konto: 'paper' | 'live'; w: Werkzeuge }): JSX.Element {
  const { z, konto, w } = props
  const ids = kettenVon(z)
  return (
    <div className="shorts-details">
      <p className="sicht">
        <strong>{z.symbol}</strong> {verfallText(z)} {strikeText(z)} · {z.art}
        {z.naked ? ' · ungedeckt' : ''} · Menge {menge(z)} · Einstand {zahl(z.einstand, 2)} · Kurswert {zahl(z.kurswert, 2)} · unrealisiert{' '}
        {zahl(z.unrealisiert, 2)}
        {z.grund ? ` · ${z.grund}` : ''}
      </p>
      {ids.length === 0 ? (
        <div className="kette-im-trade">
          <h5>
            {z.journal ? (
              <>
                Kette im Journal <Link to={`/positionen/${z.journal.chain_id}`}>#{z.journal.chain_id}</Link>
                {z.journal.strategie ? ` · ${z.journal.strategie}` : ''} · {z.journal.anzahl_rolls}{' '}
                {z.journal.anzahl_rolls === 1 ? 'Roll' : 'Rolls'}
                {z.journal.realisiert_bisher !== null ? ` · bisher realisiert ${zahl(Number(z.journal.realisiert_bisher), 2)} ${z.journal.waehrung ?? ''}` : ''}
              </>
            ) : (
              'Keine Kette im Journal gefunden (heute eröffnet oder Flex-Import steht noch aus)'
            )}
          </h5>
          {z.journal && (z.journal.schritte ?? []).length > 0 ? <JournalSchritte j={z.journal} /> : null}
          <Karten info={kunstKette(z)} />
          <SchwelleForm z={z} konto={konto} />
        </div>
      ) : null}
      {ids.map((id) => {
        const info = w.ketten.get(id)
        if (!info) return <p key={id} className="sicht">Kette {id}: Kettendaten fehlen im Status.</p>
        const k = info.kette
        return (
          <div key={id} className="kette-im-trade">
            <h5>
              Kette {k.kette_id} · {k.strategie} · {k.rolls} {k.rolls === 1 ? 'Roll' : 'Rolls'} · Netto {zahl(k.netto, 2)}
              {k.pt_limit !== null && k.pt_limit !== undefined ? ` · PT ${zahl(k.pt_limit, 2)}` : ''}
              {k.erstkredit !== null && k.erstkredit !== undefined ? ` · Erstkredit ${zahl(k.erstkredit, 2)}` : ''}
            </h5>
            {w.lage ? <div className="lage-block">{w.lage(k)}</div> : null}
            {w.verlauf ? w.verlauf(k) : null}
            <Karten info={info} />
            {!info.regeln ? <p className="sicht">Rollparameter dieser Strategie sind im Status nicht enthalten (Roller aktualisieren).</p> : null}
          </div>
        )
      })}
    </div>
  )
}

function Abschnitt(props: { titel: string; zeilen: RollerShort[]; nurHandeln: boolean; konto: 'paper' | 'live'; w: Werkzeuge }): JSX.Element | null {
  const { titel, zeilen, nurHandeln, konto, w } = props
  const [offen, setzeOffen] = useState<string | null>(null)
  if (zeilen.length === 0) return null
  const geordnet = ordne(zeilen)
  const sichtbar = nurHandeln ? geordnet.filter((z) => z.ampel === 'rot' || z.ampel === 'gelb' || z.ampel === 'grau') : geordnet
  const ausgeblendet = zeilen.length - sichtbar.length
  const okJeTicker = Object.entries(
    geordnet.filter((z) => !sichtbar.includes(z)).reduce<Record<string, number>>((a, z) => ({ ...a, [z.symbol]: (a[z.symbol] ?? 0) + 1 }), {}),
  )
  return (
    <>
      <h4>
        {titel} <span className="sicht">({zeilen.length})</span>
      </h4>
      {sichtbar.length > 0 ? (
        <div className="tabelle-rahmen">
          <table className="strategie-tabelle shorts">
            <thead>
              <tr>
                <th title={REGEL}>●</th>
                <th>Ticker</th>
                <th>Verfall</th>
                <th>Strikes</th>
                <th className="zahl" title="Wie in der TWS: Short und Credit-Spread negativ">Position</th>
                <th className="zahl" title="Kurs des Basiswerts">Kurs</th>
                <th className="zahl">DTE</th>
                <th className="zahl" title="Mittelkurs x Multiplikator x Menge, Short negativ (wie KRSWRT der TWS)">Kurswert</th>
                <th className="zahl" title="Kurswert minus Einstand (wie UNRLSRTR G&V der TWS)">Unrealisiert</th>
                <th title={`|Δ| des Shorts gegen die Schwelle; Strich = Schwelle. ${REGEL}`}>|Δ| / Schwelle</th>
                <th className="zahl" title="Abstand Kurs zum Short; negativ = Short im Geld">Abstand</th>
                <th className="zahl" title="Anzahl Rolls der Roller-Kette">Rolls</th>
                <th title="Roller-Kette dieser Position: Netto der Kette, Hinweis">Kette</th>
              </tr>
            </thead>
            <tbody>
              {sichtbar.map((z, i) => {
                const neuerTicker = i > 0 && sichtbar[i - 1].symbol !== z.symbol
                const aufgeklappt = offen === z.key
                const infos = kettenVon(z).map((id) => w.ketten.get(id)).filter((x): x is KettenInfo => Boolean(x))
                return (
                  <Fragment key={z.key}>
                    <tr
                      className={`klickbar ampel-${z.ampel}${neuerTicker ? ' gruppen-anfang' : ''}${aufgeklappt ? ' gewaehlt' : ''}`}
                      id={z.kette ? `kette-${z.kette}` : undefined}
                      onClick={() => setzeOffen(aufgeklappt ? null : z.key)}
                      title={`${z.grund || AMPEL_TEXT[z.ampel]} — Klicken: Kette und Position aufklappen`}
                    >
                      <td title={AMPEL_TEXT[z.ampel]}>
                        <span className={`punkt ${z.ampel}`} aria-label={AMPEL_TEXT[z.ampel]} />
                      </td>
                      <td>
                        {aufgeklappt ? '▾' : '▸'} {z.symbol}
                      </td>
                      <td>{verfallText(z)}</td>
                      <td>
                        {strikeText(z)}
                        {z.naked ? <span className="marke-naked" title="Risiko weder durch ein Long-Bein noch durch Aktien begrenzt"> ungedeckt</span> : null}
                        {z.deckung === 'aktien' ? <span className="sicht" title="Durch Aktien im Depot gedeckt"> · Aktien</span> : null}
                        {z.gruppe ? (
                          <span className="sicht" title="Short Put und Short Call desselben Verfalls">
                            {' · '}
                            {z.deckung === 'kalender' || z.deckung === 'diagonal' ? 'DC' : 'IC'}
                          </span>
                        ) : null}
                      </td>
                      <td className="zahl">{menge(z)}</td>
                      <td
                        className={`zahl${z.daten_alt ? ' alt' : ''}`}
                        title={z.daten_alt ? `Letzter bekannter Wert vom ${zeitDe(z.daten_alt)} (IB liefert gerade nichts)` : undefined}
                      >
                        {zahl(z.spot, z.klasse === 'index' ? 0 : 2)}
                        {z.daten_alt ? <span className="sicht"> · {z.daten_alt.slice(11, 16)}</span> : null}
                      </td>
                      <td className="zahl">{z.dte}</td>
                      <td className="zahl">{zahl(z.kurswert, 0)}</td>
                      <td className={`zahl${z.unrealisiert !== null && z.unrealisiert !== undefined ? (z.unrealisiert < 0 ? ' verlust' : ' gewinn') : ''}`}>
                        {zahl(z.unrealisiert, 0)}
                      </td>
                      <td>
                        <Balken z={z} />
                      </td>
                      <td className={`zahl${z.abstand !== null && z.abstand < 0 ? ' im-geld' : ''}`}>
                        {z.abstand === null ? '—' : `${z.abstand > 0 ? '+' : ''}${zahl(z.abstand, z.klasse === 'index' ? 0 : 2)}`}
                        {z.abstand_pct === null ? '' : <span className="sicht"> ({zahl(z.abstand_pct, 1)} %)</span>}
                      </td>
                      <td className="zahl">{infos.length > 0 ? infos.map((i) => i.kette.rolls).join(' / ') : z.journal ? z.journal.anzahl_rolls : '—'}</td>
                      <td>
                        {infos.length > 0
                          ? infos.map((i, n) => (
                              <Fragment key={i.kette.kette_id}>
                                {n > 0 ? ' · ' : ''}
                                <KettenZeile k={i.kette} />
                              </Fragment>
                            ))
                          : kettenVon(z).length > 0
                            ? kettenVon(z).join(', ')
                            : <span className="sicht">{z.journal ? `manuell · Journal #${z.journal.chain_id}` : 'manuell'}</span>}
                      </td>
                    </tr>
                    {aufgeklappt ? (
                      <tr className="verlaufszeile">
                        <td colSpan={13}>
                          <div className="verlauf-innen">
                            <Details z={z} konto={konto} w={w} />
                          </div>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {ausgeblendet > 0 ? <p className="sicht">ok, ausgeblendet: {okJeTicker.map(([t, n]) => `${t} ${n}`).join(' · ')}</p> : null}
    </>
  )
}

function Block(props: { titel: string; daten: RollerShorts; konto: 'paper' | 'live'; nurHandeln: boolean; paper?: boolean; w: Werkzeuge }): JSX.Element {
  const { titel, daten, konto, nurHandeln, paper, w } = props
  const z = daten.zaehler ?? {}
  const index = daten.positionen.filter((p) => p.klasse === 'index')
  const einzel = daten.positionen.filter((p) => p.klasse === 'einzelwert')
  return (
    <div className={`shorts-block${paper ? ' paper' : ''}`}>
      <p className="shorts-kopf">
        <strong>{titel}</strong>
        <span className="zaehler rot">● {z.rot ?? 0} handeln</span>
        <span className="zaehler gelb">● {z.gelb ?? 0} beobachten</span>
        <span className="zaehler gruen">● {z.gruen ?? 0} ok</span>
        {z.grau ? <span className="zaehler grau">● {z.grau} ohne Daten</span> : null}
        <span className="sicht">{daten.stand ? `Stand ${zeitDe(daten.stand)}` : ''}</span>
      </p>
      {daten.fehler ? <p className="warnung">{daten.fehler}</p> : null}
      {daten.positionen.length === 0 && !daten.fehler ? <p className="hinweis">Keine Short-Optionen im Konto.</p> : null}
      <Abschnitt titel="Indizes" zeilen={index} nurHandeln={nurHandeln} konto={konto} w={w} />
      <Abschnitt titel="Einzelwerte" zeilen={einzel} nurHandeln={nurHandeln} konto={konto} w={w} />
      {w.rest}
    </div>
  )
}

type Konto = 'live' | 'paper'
const KONTO_SPEICHER = 'shorts-konto'

// Live-Instanz: undefined = noch nicht gefragt, null = nicht erreichbar, 'alt' = erreichbar, aber ohne Übersicht.
type LiveStand = RollerShorts | null | 'alt' | undefined

function Reiter(props: { konto: Konto; gewaehlt: boolean; waehle: () => void; daten: RollerShorts | null; hinweis?: string }): JSX.Element {
  const { konto, gewaehlt, waehle, daten, hinweis } = props
  const z = daten?.zaehler ?? {}
  return (
    <button type="button" className={`konto-reiter ${konto}${gewaehlt ? ' gewaehlt' : ''}`} onClick={waehle} aria-pressed={gewaehlt}>
      <strong>{konto === 'live' ? 'LIVE' : 'PAPER'}</strong>{' '}
      {daten ? (
        <>
          <span className="zaehler rot">● {z.rot ?? 0}</span> <span className="zaehler gelb">● {z.gelb ?? 0}</span>{' '}
          <span className="zaehler gruen">● {z.gruen ?? 0}</span>
        </>
      ) : (
        <span className="sicht">{hinweis}</span>
      )}
    </button>
  )
}

export default function ShortsUebersicht(props: {
  paper: RollerShorts | null | undefined
  strategie?: RollerStrategie
  lage?: (k: RollerKetteStand) => ReactNode
  verlauf?: (k: RollerKetteStand) => ReactNode
  rest?: ReactNode
}): JSX.Element {
  const { paper, strategie, lage, verlauf, rest } = props
  const [nurHandeln, setzeNurHandeln] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SPEICHER) !== '0'
    } catch {
      return true
    }
  })
  const [konto, setzeKonto] = useState<Konto>(() => {
    try {
      return localStorage.getItem(KONTO_SPEICHER) === 'paper' ? 'paper' : 'live'
    } catch {
      return 'live'
    }
  })
  const [live, setzeLive] = useState<LiveStand>(undefined)
  useEffect(() => {
    let aktiv = true
    const laden = () =>
      holeRollerLive()
        .then((d) => aktiv && setzeLive(!d.erreichbar ? null : d.status?.shorts ? d.status.shorts : 'alt'))
        .catch(() => aktiv && setzeLive(null))
    laden()
    const takt = window.setInterval(laden, 15000)
    return () => {
      aktiv = false
      window.clearInterval(takt)
    }
  }, [])
  const merke = (schluessel: string, wert: string): void => {
    try {
      localStorage.setItem(schluessel, wert)
    } catch {
      /* nur eine Bequemlichkeit */
    }
  }
  const umschalten = (an: boolean): void => {
    setzeNurHandeln(an)
    merke(SPEICHER, an ? '1' : '0')
  }
  const waehle = (k: Konto): void => {
    setzeKonto(k)
    merke(KONTO_SPEICHER, k)
  }
  const regelnJe = new Map((strategie?.vorgaben ?? []).map((v) => [v.name, v.regeln]))
  const ketten = new Map<string, KettenInfo>((strategie?.ketten ?? []).map((k) => [k.kette_id, { kette: k, regeln: regelnJe.get(k.strategie) }]))
  const wPaper: Werkzeuge = { ketten, lage, verlauf, rest }
  const wLive: Werkzeuge = { ketten: new Map() } // die Roller-Ketten gehören zum Paper-Konto
  const liveDaten = live && live !== 'alt' ? live : null
  const liveHinweis = live === undefined ? 'frage …' : live === 'alt' ? 'Dienst ohne Übersicht (alter Stand)' : 'nicht verbunden'
  return (
    <section className={`shorts-uebersicht konto-${konto}`}>
      <h3>
        Shorts im Konto{' '}
        <label className="sicht">
          <input type="checkbox" checked={nurHandeln} onChange={(e) => umschalten(e.target.checked)} /> nur Handlungsbedarf
        </label>
      </h3>
      <div className="konto-wahl" role="group" aria-label="Konto">
        <Reiter konto="live" gewaehlt={konto === 'live'} waehle={() => waehle('live')} daten={liveDaten} hinweis={liveHinweis} />
        <Reiter konto="paper" gewaehlt={konto === 'paper'} waehle={() => waehle('paper')} daten={paper ?? null}
          hinweis="Dienst ohne Übersicht (alter Stand)" />
      </div>
      {konto === 'live' ? (
        liveDaten ? (
          <Block titel="LIVE-Konto" daten={liveDaten} konto="live" nurHandeln={nurHandeln} w={wLive} />
        ) : (
          <div className="shorts-block">
            <p className="warnung">
              <strong>Live-Konto: {liveHinweis}.</strong>{' '}
              {live === 'alt'
                ? 'Die Live-Instanz läuft mit einem Stand vor AP-19 — Roller deployen und neu starten.'
                : 'Die lesende Live-Instanz des Rollers antwortet nicht auf Port 8601.'}
            </p>
            <p className="hinweis">
              Auf dem Server im Roller-Ordner <code>.\Start-Dienst-Live-Lesen.ps1</code> starten (Live-TWS auf 7496 muss laufen; setzt nie eine
              Order). Das Journal braucht <code>ROLLER_LIVE_STATUS_PORT=8601</code> — der Paper-Schnellstart setzt es; ein schon laufendes
              Journal einmal neu starten.
            </p>
          </div>
        )
      ) : paper ? (
        <Block titel="PAPER-Konto" daten={paper} konto="paper" nurHandeln={nurHandeln} paper w={wPaper} />
      ) : (
        <p className="hinweis">Der Roller liefert noch keine Übersicht (älterer Stand des Dienstes).</p>
      )}
    </section>
  )
}
