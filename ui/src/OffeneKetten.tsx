// Offene Ketten des Rollers als eine Liste: Ticker-Spalte, Filter wie in Excel (Dropdown im Spaltenkopf),
// Standardreihenfolge Ticker → DTE → |Δ|; Klick auf eine Zeile klappt darunter die Kettenhistorie auf.

import { Fragment, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { RollerKetteStand } from './api'

type Spalte = 'ticker' | 'strategie' | 'verfall' | 'dte' | 'delta'

const TITEL: Record<Spalte, string> = {
  ticker: 'Ticker',
  strategie: 'Strategie',
  verfall: 'Verfall',
  dte: 'DTE',
  delta: '|Δ| Short',
}

export function tickerVon(k: RollerKetteStand): string {
  if (k.symbol) return k.symbol
  const m = /^(?:T\s+)?([A-Z]+):/.exec(k.strategie)
  return m ? m[1] : '—'
}

function deltaBetrag(k: RollerKetteStand): number | null {
  return k.short_delta === null || k.short_delta === undefined ? null : Math.abs(k.short_delta)
}

// Delta in Fünfer-Stufen, damit der Filter sinnvolle Auswahlwerte hat.
function deltaStufe(k: RollerKetteStand): string {
  const d = deltaBetrag(k)
  if (d === null) return '—'
  const u = Math.floor(d * 20) / 20
  return `${u.toFixed(2)}–${(u + 0.05).toFixed(2)}`
}

function wert(k: RollerKetteStand, s: Spalte): string {
  switch (s) {
    case 'ticker':
      return tickerVon(k)
    case 'strategie':
      return k.strategie
    case 'verfall':
      return k.aktiv.verfall
    case 'dte':
      return k.dte === undefined || k.dte === null ? '—' : String(k.dte)
    case 'delta':
      return deltaStufe(k)
  }
}

function vergleich(a: RollerKetteStand, b: RollerKetteStand, s: Spalte): number {
  if (s === 'dte') return (a.dte ?? 1e9) - (b.dte ?? 1e9)
  if (s === 'delta') return (deltaBetrag(a) ?? 1e9) - (deltaBetrag(b) ?? 1e9)
  return wert(a, s).localeCompare(wert(b, s), 'de')
}

const STANDARD: Spalte[] = ['ticker', 'dte', 'delta']

function Filterkopf(props: {
  spalte: Spalte
  werte: string[]
  gewaehlt: Set<string> | undefined
  setze: (w: Set<string> | undefined) => void
  sortiert: '↑' | '↓' | null
  sortiere: () => void
  zahl?: boolean
}): JSX.Element {
  const { spalte, werte, gewaehlt, setze, sortiert, sortiere, zahl } = props
  const aktiv = gewaehlt !== undefined
  const umschalten = (w: string): void => {
    const neu = new Set(gewaehlt ?? werte)
    if (neu.has(w)) neu.delete(w)
    else neu.add(w)
    setze(neu.size === werte.length ? undefined : neu)
  }
  return (
    <th className={zahl ? 'zahl' : undefined}>
      <span onClick={sortiere} title="Sortieren">
        {TITEL[spalte]}
        {sortiert !== null ? ` ${sortiert}` : ''}
      </span>{' '}
      <details className="spaltenfilter">
        <summary className={aktiv ? 'aktiv' : undefined} title="Filtern" aria-label={`${TITEL[spalte]} filtern`}>
          ▾
        </summary>
        <div className="spaltenfilter-box">
          <p>
            <button type="button" onClick={() => setze(undefined)}>
              Alle
            </button>{' '}
            <button type="button" onClick={() => setze(new Set())}>
              Keine
            </button>
          </p>
          {werte.map((w) => (
            <label key={w}>
              <input type="checkbox" checked={gewaehlt === undefined || gewaehlt.has(w)} onChange={() => umschalten(w)} /> {w}
            </label>
          ))}
        </div>
      </details>
    </th>
  )
}

export default function OffeneKetten(props: {
  ketten: RollerKetteStand[]
  verfall: (jjjjmmtt: string) => string
  zahl: (x: number | null | undefined, n?: number) => string
  verlauf: (k: RollerKetteStand) => ReactNode
  lage: (k: RollerKetteStand) => ReactNode
}): JSX.Element {
  const { ketten, verfall, zahl, verlauf, lage } = props
  const [filter, setzeFilter] = useState<Partial<Record<Spalte, Set<string>>>>({})
  const [sortierung, setzeSortierung] = useState<{ spalte: Spalte; abwaerts: boolean } | null>(null)
  const [aufgeklappt, setzeAufgeklappt] = useState<string | null>(null)

  const werte = useMemo(() => {
    const aus = (s: Spalte): string[] => {
      const alle = Array.from(new Set(ketten.map((k) => wert(k, s))))
      return alle.sort((a, b) => a.localeCompare(b, 'de', { numeric: true }))
    }
    return {
      ticker: aus('ticker'),
      strategie: aus('strategie'),
      verfall: aus('verfall'),
      dte: aus('dte'),
      delta: aus('delta'),
    } as Record<Spalte, string[]>
  }, [ketten])

  const sichtbar = useMemo(() => {
    const treffer = ketten.filter((k) =>
      (Object.keys(filter) as Spalte[]).every((s) => filter[s] === undefined || filter[s]!.has(wert(k, s))),
    )
    const reihenfolge = sortierung ? [sortierung.spalte, ...STANDARD] : STANDARD
    return [...treffer].sort((a, b) => {
      for (const s of reihenfolge) {
        const v = vergleich(a, b, s)
        if (v !== 0) return sortierung && s === sortierung.spalte && sortierung.abwaerts ? -v : v
      }
      return a.kette_id.localeCompare(b.kette_id, 'de', { numeric: true })
    })
  }, [ketten, filter, sortierung])

  const kopf = (spalte: Spalte, zahlSpalte = false): JSX.Element => (
    <Filterkopf
      spalte={spalte}
      werte={werte[spalte]}
      gewaehlt={filter[spalte]}
      setze={(w) => setzeFilter((f) => ({ ...f, [spalte]: w }))}
      sortiert={sortierung?.spalte === spalte ? (sortierung.abwaerts ? '↓' : '↑') : null}
      sortiere={() =>
        setzeSortierung((s) => (s?.spalte === spalte ? (s.abwaerts ? null : { spalte, abwaerts: true }) : { spalte, abwaerts: false }))
      }
      zahl={zahlSpalte}
    />
  )
  const gefiltert = Object.values(filter).some((w) => w !== undefined)

  return (
    <div className="tabelle-rahmen">
      {gefiltert ? (
        <p className="sicht">
          {sichtbar.length} von {ketten.length} Ketten sichtbar.{' '}
          <button type="button" onClick={() => setzeFilter({})}>
            Filter aufheben
          </button>
        </p>
      ) : null}
      <table className="strategie-tabelle offene-ketten">
        <thead>
          <tr>
            <th>Kette</th>
            {kopf('ticker')}
            {kopf('strategie')}
            {kopf('verfall')}
            {kopf('dte', true)}
            <th className="zahl">Short/Long</th>
            {kopf('delta', true)}
            <th className="zahl">Schwelle</th>
            <th className="zahl" title="Summe aller Kredite minus Debits der Kette (Cash-Flow, kein Gewinn)">Netto</th>
            <th className="zahl" title="Ergebnis, wenn die Kette jetzt geschlossen würde: Mittelkurs (natürlicher Preis); alle 10 Minuten neu">
              Wert jetzt
            </th>
            <th className="zahl">Rolls</th>
            <th className="zahl" title="Rückkauf-Limit des Profit-Targets">PT</th>
            <th>Lage</th>
          </tr>
        </thead>
        <tbody>
          {sichtbar.map((k) => {
            const offen = aufgeklappt === k.kette_id
            const d = deltaBetrag(k)
            return (
              <Fragment key={k.kette_id}>
                <tr
                  className={`klickbar${k.alarm || k.status === 'pruefen' ? ' warnung' : ''}${offen ? ' gewaehlt' : ''}`}
                  onClick={() => setzeAufgeklappt(offen ? null : k.kette_id)}
                  title="Klicken: Kettenhistorie ein-/ausklappen"
                >
                  <td>{offen ? '▾' : '▸'} {k.kette_id}</td>
                  <td>{tickerVon(k)}</td>
                  <td>{k.strategie}</td>
                  <td>{verfall(k.aktiv.verfall)}</td>
                  <td className="zahl">{k.dte ?? '—'}</td>
                  <td className="zahl">{k.aktiv.short}/{k.aktiv.long}</td>
                  <td className="zahl">{d === null ? '—' : d.toFixed(3)}</td>
                  <td className="zahl">{zahl(k.schwelle)}</td>
                  <td className="zahl">{zahl(k.netto)}</td>
                  <td className="zahl" title={k.wert ? `Stand ${k.wert.zeit}` : 'noch keine Bewertung'}>
                    {k.wert && k.wert.geld_mitte !== null
                      ? `${k.wert.geld_mitte.toFixed(0)} (${k.wert.geld_natuerlich === null ? '—' : k.wert.geld_natuerlich.toFixed(0)}) ${k.wert.waehrung}`
                      : '—'}
                  </td>
                  <td className="zahl">{k.rolls}</td>
                  <td className="zahl">{zahl(k.pt_limit)}</td>
                  <td onClick={(e) => e.stopPropagation()}>{lage(k)}</td>
                </tr>
                {offen ? (
                  <tr className="verlaufszeile">
                    <td colSpan={13}>{verlauf(k)}</td>
                  </tr>
                ) : null}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
