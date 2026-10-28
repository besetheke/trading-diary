// AP-19: Shorts im Konto — jede Short-Option (Spread oder naked) mit Ampel, getrennt nach Indizes und Einzelwerten.
// Ziel: auf einen Blick sehen, was ins Geld läuft und gerollt werden muss. Bewertet wird im Roller (roller/shorts.py);
// hier wird nur gezeigt. Der Roller handelt davon nur seine eigenen Ketten, alles andere ist Anzeige.

import { useEffect, useState } from 'react'
import { fehlerText, holeRollerLive, sendeRollerBefehl } from './api'
import type { Ampel, RollerShort, RollerShorts } from './api'
import { zeitDe } from './format'

const AMPEL_TEXT: Record<Ampel, string> = { rot: 'handeln', gelb: 'beobachten', grau: 'ohne Daten', gruen: 'ok' }
const REGEL =
  'rot: Short im Geld oder |Δ| ≥ Schwelle (bei DTE ≤ 1 wird gelb zu rot) · gelb: |Δ| ≥ 80 % der Schwelle oder ' +
  'Abstand unter 1 % (Index) bzw. 3 % (Einzelwert) · ohne Delta entscheidet der Abstand'
const HERKUNFT: Record<RollerShort['schwelle_herkunft'], string> = {
  roller: 'Schwelle der Roller-Kette',
  position: 'von Hand für diese Position',
  ticker: 'von Hand für den Ticker',
  staffel: 'DTE-Staffel des Rollers',
}
const SPEICHER = 'shorts-nur-handlungsbedarf'

function datum(jjjjmmtt: string): string {
  return jjjjmmtt.length === 8 ? `${jjjjmmtt.slice(6, 8)}.${jjjjmmtt.slice(4, 6)}.` : jjjjmmtt
}

function zahl(x: number | null | undefined, stellen = 0): string {
  return x === null || x === undefined
    ? '—'
    : x.toLocaleString('de-DE', { minimumFractionDigits: stellen, maximumFractionDigits: stellen })
}

function Balken({ z }: { z: RollerShort }): JSX.Element {
  if (z.ohne_delta || z.delta_anteil === null) {
    return (
      <span className="delta-balken ohne" title="Kein Delta von IB — die Ampel entscheidet nach dem Abstand">
        ohne Delta
      </span>
    )
  }
  const breite = Math.min(z.delta_anteil, 1.25) / 1.25 * 100
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

function SchwelleForm(props: { z: RollerShort; konto: 'paper' | 'live'; fertig: () => void }): JSX.Element {
  const { z, konto, fertig } = props
  const [wert, setzeWert] = useState(z.schwelle === null ? '' : String(z.schwelle))
  const [fehler, setzeFehler] = useState<string | null>(null)
  const senden = (p: { ticker?: string; position?: string; wert?: string }): void => {
    setzeFehler(null)
    sendeRollerBefehl('schwelle-setzen', { ...p, konto })
      .then(fertig)
      .catch((e: unknown) => setzeFehler(fehlerText(e)))
  }
  return (
    <div className="schwelle-form">
      |Δ|-Schwelle{' '}
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
      ) : null}{' '}
      <button type="button" onClick={fertig}>
        Abbrechen
      </button>
      <span className="sicht"> Neu bewertet wird bei der nächsten Prüfung (alle 2 Minuten).</span>
      {fehler ? <p className="meldung">{fehler}</p> : null}
    </div>
  )
}

function Abschnitt(props: {
  titel: string
  zeilen: RollerShort[]
  nurHandeln: boolean
  konto: 'paper' | 'live'
  zurKette: (kette: string) => void
}): JSX.Element | null {
  const { titel, zeilen, nurHandeln, konto, zurKette } = props
  const [bearbeiten, setzeBearbeiten] = useState<string | null>(null)
  if (zeilen.length === 0) return null
  const sichtbar = nurHandeln ? zeilen.filter((z) => z.ampel === 'rot' || z.ampel === 'gelb' || z.ampel === 'grau') : zeilen
  const ausgeblendet = zeilen.length - sichtbar.length
  const okJeTicker = Object.entries(
    zeilen.filter((z) => !sichtbar.includes(z)).reduce<Record<string, number>>((a, z) => ({ ...a, [z.symbol]: (a[z.symbol] ?? 0) + 1 }), {}),
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
                <th>Art</th>
                <th>Verfall</th>
                <th className="zahl">DTE</th>
                <th className="zahl">Short/Long</th>
                <th className="zahl">Menge</th>
                <th className="zahl">Kurs</th>
                <th className="zahl" title="Abstand Kurs zum Short; negativ = Short im Geld">Abstand</th>
                <th title={`|Δ| des Shorts gegen die Schwelle; Strich = Schwelle. ${REGEL}`}>|Δ| / Schwelle</th>
                <th>Quelle</th>
                <th>Grund</th>
              </tr>
            </thead>
            <tbody>
              {sichtbar.map((z, i) => {
                const neueGruppe = z.gruppe !== null && sichtbar[i - 1]?.gruppe !== z.gruppe
                return [
                  <tr key={z.key} className={`ampel-${z.ampel}${z.gruppe ? ' in-gruppe' : ''}${neueGruppe ? ' gruppen-anfang' : ''}`}>
                    <td title={AMPEL_TEXT[z.ampel]}>
                      <span className={`punkt ${z.ampel}`} aria-label={AMPEL_TEXT[z.ampel]} />
                    </td>
                    <td>{z.symbol}</td>
                    <td>
                      {z.art}
                      {z.naked ? <span className="marke-naked" title="Risiko weder durch ein Long-Bein noch durch Aktien begrenzt"> ungedeckt</span> : null}
                      {z.deckung === 'aktien' ? <span className="sicht" title="Durch Aktien im Depot gedeckt"> · Aktien</span> : null}
                      {z.gruppe ? (
                        <span className="sicht" title="Short Put und Short Call desselben Verfalls">
                          {' · '}
                          {z.deckung === 'kalender' || z.deckung === 'diagonal' ? 'DC' : 'IC'}
                        </span>
                      ) : null}
                    </td>
                    <td>{datum(z.verfall)}</td>
                    <td className="zahl">{z.dte}</td>
                    <td className="zahl">
                      {zahl(z.short, z.short % 1 ? 1 : 0)}
                      {z.long !== null ? `/${zahl(z.long, z.long % 1 ? 1 : 0)}` : ''}
                      {z.long_verfall ? <span className="sicht" title="Verfall des Long-Beins"> ({datum(z.long_verfall)})</span> : null}
                    </td>
                    <td className="zahl">{z.menge}</td>
                    <td className={`zahl${z.daten_alt ? ' alt' : ''}`}
                      title={z.daten_alt ? `Letzter bekannter Wert vom ${zeitDe(z.daten_alt)} (IB liefert gerade nichts)` : undefined}>
                      {zahl(z.spot, z.klasse === 'index' ? 0 : 2)}
                      {z.daten_alt ? <span className="sicht"> · {z.daten_alt.slice(11, 16)}</span> : null}
                    </td>
                    <td className={`zahl${z.abstand !== null && z.abstand < 0 ? ' im-geld' : ''}`}>
                      {z.abstand === null ? '—' : `${z.abstand > 0 ? '+' : ''}${zahl(z.abstand, z.klasse === 'index' ? 0 : 2)}`}
                      {z.abstand_pct === null ? '' : <span className="sicht"> ({zahl(z.abstand_pct, 1)} %)</span>}
                    </td>
                    <td>
                      <Balken z={z} />
                      {!z.kette ? (
                        <button type="button" className="klein" title="Schwelle überschreiben"
                          onClick={() => setzeBearbeiten(bearbeiten === z.key ? null : z.key)}>
                          ✎
                        </button>
                      ) : null}
                    </td>
                    <td>
                      {z.kette ? (
                        <button type="button" className="link" onClick={() => zurKette(z.kette as string)}>
                          Roller {z.kette}
                        </button>
                      ) : (
                        'manuell'
                      )}
                    </td>
                    <td className="grund" title={z.grund}>{z.grund || '—'}</td>
                  </tr>,
                  bearbeiten === z.key ? (
                    <tr key={`${z.key}-form`}>
                      <td colSpan={12}>
                        <SchwelleForm z={z} konto={konto} fertig={() => setzeBearbeiten(null)} />
                      </td>
                    </tr>
                  ) : null,
                ]
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {ausgeblendet > 0 ? (
        <p className="sicht">
          ok, ausgeblendet: {okJeTicker.map(([t, n]) => `${t} ${n}`).join(' · ')}
        </p>
      ) : null}
    </>
  )
}

function Block(props: { titel: string; daten: RollerShorts; konto: 'paper' | 'live'; nurHandeln: boolean; paper?: boolean }): JSX.Element {
  const { titel, daten, konto, nurHandeln, paper } = props
  const zurKette = (kette: string): void => {
    document.getElementById(`kette-${kette}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }
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
      <Abschnitt titel="Indizes" zeilen={index} nurHandeln={nurHandeln} konto={konto} zurKette={zurKette} />
      <Abschnitt titel="Einzelwerte" zeilen={einzel} nurHandeln={nurHandeln} konto={konto} zurKette={zurKette} />
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

export default function ShortsUebersicht({ paper }: { paper: RollerShorts | null | undefined }): JSX.Element {
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
          <Block titel="LIVE-Konto" daten={liveDaten} konto="live" nurHandeln={nurHandeln} />
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
        <Block titel="PAPER-Konto" daten={paper} konto="paper" nurHandeln={nurHandeln} paper />
      ) : (
        <p className="hinweis">Der Roller liefert noch keine Übersicht (älterer Stand des Dienstes).</p>
      )}
    </section>
  )
}
