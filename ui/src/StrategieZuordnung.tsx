import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { fehlerText, holeFilterwerte, holeStrategieZuordnung, nimmStrategieZuordnungZurueck, setzeStrategieZuordnung } from './api'
import type { StrategieZuordnungStand } from './api'
import { zeitDe } from './format'

// M03: dauerhafte, manuelle Strategiezuordnung an einer Kette (auch diskretionäre Positionen ohne OA-Trade). Sie hängt am
// Naturschlüssel der Kette, überlebt Import und Rebuild und wirkt in allen Filtern und Auswertungen. Rücknahme löscht nichts.

export default function StrategieZuordnung({ chainId }: { chainId: number }): JSX.Element {
  const [stand, setzeStand] = useState<StrategieZuordnungStand | null>(null)
  const [vorschlaege, setzeVorschlaege] = useState<string[]>([])
  const [strategie, setzeStrategie] = useState('')
  const [begruendung, setzeBegruendung] = useState('')
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [beschaeftigt, setzeBeschaeftigt] = useState(false)

  useEffect(() => {
    setzeFehler(null)
    holeStrategieZuordnung(chainId)
      .then((s) => { setzeStand(s); setzeStrategie(s.manuell?.strategie ?? s.strategie ?? ''); setzeBegruendung(s.manuell?.begruendung ?? '') })
      .catch((e) => setzeFehler(fehlerText(e)))
    holeFilterwerte().then((f) => setzeVorschlaege(f.strategien)).catch(() => setzeVorschlaege([]))
  }, [chainId])

  function speichern(ereignis: FormEvent): void {
    ereignis.preventDefault()
    if (!strategie.trim()) return
    setzeBeschaeftigt(true)
    setzeFehler(null)
    setzeStrategieZuordnung(chainId, strategie.trim(), begruendung)
      .then(setzeStand)
      .catch((e) => setzeFehler(fehlerText(e)))
      .finally(() => setzeBeschaeftigt(false))
  }

  function zuruecknehmen(): void {
    if (!window.confirm('Die manuelle Strategiezuordnung zurücknehmen? Der Stand davor kehrt zurück, die Zeile bleibt gespeichert.')) return
    setzeBeschaeftigt(true)
    setzeFehler(null)
    nimmStrategieZuordnungZurueck(chainId)
      .then((s) => { setzeStand(s); setzeStrategie(s.strategie ?? ''); setzeBegruendung('') })
      .catch((e) => setzeFehler(fehlerText(e)))
      .finally(() => setzeBeschaeftigt(false))
  }

  return (
    <section className="journal">
      <h3>Strategie</h3>
      {fehler && <p className="meldung">{fehler}</p>}
      {stand && (
        <>
          <p>
            Aktuell: <strong>{stand.strategie ?? 'keine'}</strong>
            {stand.herkunft ? ` (${stand.herkunft === 'manuell' ? 'von dir gesetzt' : stand.herkunft === 'auto' ? 'OA, automatisch erkannt' : `OA, ${stand.herkunft}`})` : ''}
            {stand.manuell?.geaendert_am || stand.manuell?.erstellt_am ? ` · seit ${zeitDe(stand.manuell?.geaendert_am ?? stand.manuell?.erstellt_am ?? '')}` : ''}
          </p>
          {stand.manuell?.begruendung && <p className="sicht">Begründung: {stand.manuell.begruendung}</p>}
          {stand.manuell?.oa_widerspricht && (
            <p className="warnung">
              OA ordnet diese Kette einer anderen Strategie zu („{stand.manuell.oa_widerspricht}“). Deine Zuordnung gilt; sie bleibt, bis du sie zurücknimmst.
            </p>
          )}
          <form onSubmit={speichern}>
            <label htmlFor={`strategie-${chainId}`}>Strategie festlegen (auch neue Namen möglich)</label>{' '}
            <input id={`strategie-${chainId}`} list={`strategien-${chainId}`} value={strategie} onChange={(e) => setzeStrategie(e.target.value)} size={32} />
            <datalist id={`strategien-${chainId}`}>{vorschlaege.map((n) => <option key={n} value={n} />)}</datalist>{' '}
            <input value={begruendung} onChange={(e) => setzeBegruendung(e.target.value)} placeholder="Begründung (optional)" size={36} />{' '}
            <button type="submit" disabled={beschaeftigt || !strategie.trim()}>Speichern</button>
            {stand.manuell && <button type="button" disabled={beschaeftigt} onClick={zuruecknehmen}>Zuordnung zurücknehmen</button>}
          </form>
        </>
      )}
    </section>
  )
}
