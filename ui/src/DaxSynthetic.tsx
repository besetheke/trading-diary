import { useEffect, useMemo, useState } from 'react'
import { fehlerText, holeDaxSynthetic } from './api'
import type { DaxSyntheticAntwort } from './api'
import { betrag, datumDe, geldDe, vorzeichen } from './format'

// DAX Synthetic: Long-Future + Long-Put (lange Laufzeit) + Short-Call (eine Woche). Die Zuordnung ist ein
// Vorschlag nach festen Merkmalen (GET /dax-synthetic-auswertung), keine Tatsache; alles in EUR.

const NAMEN: Record<string, string> = {
  future: 'Long-Future (FDAX)',
  schutz_put: 'Schutz-Put (lange Laufzeit)',
  short_call: 'Short-Call (Woche)',
}

export default function DaxSynthetic(): JSX.Element {
  const [daten, setzeDaten] = useState<DaxSyntheticAntwort | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [filter, setzeFilter] = useState('alle')
  useEffect(() => {
    holeDaxSynthetic().then(setzeDaten).catch((e) => setzeFehler(fehlerText(e)))
  }, [])
  const trades = useMemo(
    () => (daten?.trades ?? []).filter((x) => filter === 'alle' || x.baustein === filter),
    [daten, filter],
  )
  if (fehler) return <p className="fehler">{fehler}</p>
  if (!daten) return <p className="laedt">Lade DAX Synthetic …</p>
  const summe = daten.bausteine.reduce((s, b) => s + Number(b.netto), 0)
  return (
    <section>
      <h2>DAX Synthetic</h2>
      <p className="sicht">
        Vorschlag nach festen Merkmalen: Schutz-Put = gekaufter Put mit mindestens {daten.regeln.schutz_put_min_dte} Tagen
        Restlaufzeit, Short-Call = nackter (einzelner) verkaufter Call mit höchstens {daten.regeln.short_call_max_dte} Tagen. Andere DAX-Legs
        ({daten.sonstige}) zählen nicht mit. Aktiv (Future und Schutz-Put zugleich): {datumDe(daten.aktiv_von)} bis{' '}
        {daten.aktiv_bis ? datumDe(daten.aktiv_bis) : 'heute'}.
      </p>
      <h3>Bausteine</h3>
      <table className="positionen dichte-kompakt">
        <thead><tr><th>Baustein</th><th>Legs</th><th>Kontrakte</th><th>offen</th><th>Brutto</th><th>Kommission</th><th>Netto</th></tr></thead>
        <tbody>
          {daten.bausteine.map((b) => (
            <tr key={b.art}>
              <td>{NAMEN[b.art] ?? b.art}</td><td>{b.anzahl}</td><td>{b.kontrakte}</td><td>{b.offen || ''}</td>
              <td className={vorzeichen(b.brutto)}>{betrag(b.brutto)}</td>
              <td className={vorzeichen(b.kommission)}>{betrag(b.kommission)}</td>
              <td className={vorzeichen(b.netto)}>{betrag(b.netto)}</td>
            </tr>
          ))}
          <tr><td><strong>Summe (realisiert)</strong></td><td colSpan={5}></td><td><strong>{geldDe(String(summe))}</strong></td></tr>
        </tbody>
      </table>
      <h3>Je Schutz-Put</h3>
      <p className="sicht">Realisiertes Netto, das in der Haltezeit des Puts geschlossen wurde.</p>
      <table className="positionen dichte-kompakt">
        <thead>
          <tr><th>Put (Strike, Verfall)</th><th>Haltezeit</th><th>Future</th><th>Short-Calls</th><th>Put</th><th>Summe</th></tr>
        </thead>
        <tbody>
          {daten.einheiten.map((e) => {
            const w = (k: string) => e.ergebnis[k] ?? '0'
            const gesamt = String(Number(w('future')) + Number(w('short_call')) + Number(w('schutz_put')))
            return (
              <tr key={e.put_leg_id}>
                <td>{betrag(e.strike).replace(',00', '')} · {datumDe(e.verfall)}</td>
                <td>{datumDe(e.eroeffnet)} – {e.beendet ? datumDe(e.beendet) : 'offen'}</td>
                <td className={vorzeichen(w('future'))}>{betrag(w('future'))}</td>
                <td className={vorzeichen(w('short_call'))}>{betrag(w('short_call'))}</td>
                <td className={vorzeichen(w('schutz_put'))}>{betrag(w('schutz_put'))}</td>
                <td className={vorzeichen(gesamt)}>{betrag(gesamt)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <h3>Alle Trades einzeln</h3>
      <p className="sicht">
        Zeigen:{' '}
        <select value={filter} onChange={(e) => setzeFilter(e.target.value)}>
          <option value="alle">alle Bausteine</option>
          {Object.entries(NAMEN).map(([k, n]) => <option key={k} value={k}>{n}</option>)}
        </select>{' '}
        · {trades.length} Trades, jüngste zuerst
      </p>
      <table className="positionen dichte-kompakt">
        <thead>
          <tr><th>Baustein</th><th>Eröffnet</th><th>Geschlossen</th><th>Kontrakt</th><th>Menge</th><th>Brutto</th><th>Kommission</th><th>Netto</th></tr>
        </thead>
        <tbody>
          {[...trades].reverse().map((x) => (
            <tr key={x.leg_id}>
              <td>{NAMEN[x.baustein] ?? x.baustein}</td>
              <td>{datumDe(x.eroeffnet)}</td>
              <td>{x.beendet ? datumDe(x.beendet) : 'offen'}</td>
              <td>
                {x.art === 'FUT' ? `Future ${x.verfall ? datumDe(x.verfall) : ''}`
                  : `${x.recht === 'P' ? 'Put' : 'Call'} ${x.strike ? betrag(x.strike).replace(',00', '') : ''} · ${x.verfall ? datumDe(x.verfall) : ''}`}
              </td>
              <td>{x.menge}</td>
              <td className={vorzeichen(x.brutto)}>{x.brutto === null ? '—' : betrag(x.brutto)}</td>
              <td className={vorzeichen(x.kommission)}>{x.kommission === null ? '—' : betrag(x.kommission)}</td>
              <td className={vorzeichen(x.netto)}>{x.netto === null ? '—' : betrag(x.netto)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
