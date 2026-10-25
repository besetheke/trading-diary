// AP-17g (M07): den Live-Partner eines Backtest-Trades korrigieren. Die Paarung nach Zeitfenster ist ein Vorschlag;
// die Korrektur trägt die Erkennung „manuell“, eine Rücknahme löscht nichts, es gilt wieder die Zeitfenster-Paarung.

import { useState } from 'react'
import { fehlerText, holePartnerKandidaten, nimmPartnerZurueck, setzePartner } from './api'
import type { BacktestPaar, PartnerKandidat } from './api'

export default function BacktestPartner(props: {
  paar: BacktestPaar
  oaStrategie: string
  geaendert: () => void
}): JSX.Element | null {
  const { paar, oaStrategie, geaendert } = props
  const [offen, setzeOffen] = useState(false)
  const [kandidaten, setzeKandidaten] = useState<PartnerKandidat[] | null>(null)
  const [wahl, setzeWahl] = useState('')
  const [begruendung, setzeBegruendung] = useState('')
  const [fehler, setzeFehler] = useState<string | null>(null)

  if (paar.oo_trade == null) return null
  const ooTrade = Number(paar.oo_trade)
  const manuell = paar.partner_herkunft === 'manuell'

  function oeffnen(): void {
    setzeOffen(true)
    setzeFehler(null)
    holePartnerKandidaten(ooTrade, oaStrategie)
      .then((k) => {
        setzeKandidaten(k)
        setzeWahl(paar.oa_trade ?? k[0]?.oa_trade ?? '')
      })
      .catch((e: unknown) => setzeFehler(fehlerText(e)))
  }

  function speichern(): void {
    setzeFehler(null)
    setzePartner(ooTrade, oaStrategie, wahl === '' ? null : wahl, begruendung.trim())
      .then(() => {
        setzeOffen(false)
        geaendert()
      })
      .catch((e: unknown) => setzeFehler(fehlerText(e)))
  }

  function zuruecknehmen(): void {
    setzeFehler(null)
    nimmPartnerZurueck(ooTrade)
      .then(geaendert)
      .catch((e: unknown) => setzeFehler(fehlerText(e)))
  }

  return (
    <div className="partner">
      {manuell ? <span className="sicht" title="Vom Nutzer festgelegt (Erkennung: manuell)">manuell · </span> : null}
      {!offen ? (
        <>
          <button type="button" onClick={oeffnen}>
            Partner ändern
          </button>
          {manuell ? (
            <>
              {' '}
              <button type="button" onClick={zuruecknehmen}>
                zurücknehmen
              </button>
            </>
          ) : null}
        </>
      ) : (
        <div>
          <select value={wahl} onChange={(e) => setzeWahl(e.target.value)} aria-label="Live-Partner">
            <option value="">kein Partner</option>
            {(kandidaten ?? []).map((k) => (
              <option key={k.oa_trade} value={k.oa_trade}>
                {k.oa_trade} · {k.zeit.slice(0, 16)} · {k.abstand_min > 0 ? '+' : ''}
                {k.abstand_min} min · {k.kontrakte}×{k.offen ? ' · offen' : ''}
              </option>
            ))}
          </select>{' '}
          <input value={begruendung} onChange={(e) => setzeBegruendung(e.target.value)} placeholder="Begründung" />{' '}
          <button type="button" onClick={speichern}>
            Speichern
          </button>{' '}
          <button type="button" onClick={() => setzeOffen(false)}>
            Abbrechen
          </button>
        </div>
      )}
      {fehler !== null ? <p className="meldung">{fehler}</p> : null}
    </div>
  )
}
