import { useEffect, useRef, useState } from 'react'
import Kalenderwahl from './Kalenderwahl'
import { datumDe } from './format'
import { passendeVorgabe, useZeitraum, vorgaben } from './zeitraum'
import type { Vorgabe, Zeitraum } from './zeitraum'

// AP-08f2, überarbeitet: Zeitraum-Wähler im Kopf. Eine Schaltfläche zeigt den
// gewählten Zeitraum; sie öffnet ein Fenster mit den Vorgaben (Z1) links und
// einem Kalender rechts — erster Klick Start, zweiter Klick Ende. Der Zeitraum
// steht in der Adresse und gilt für jede Ansicht, die Zeit kennt.

export default function Zeitraumwahl({ wirkt }: { wirkt: boolean }): JSX.Element {
  const [zeitraum, setzeZeitraum] = useZeitraum()
  const [offen, setzeOffen] = useState(false)
  const huelle = useRef<HTMLDivElement>(null)
  const liste = vorgaben()
  const passend = passendeVorgabe(zeitraum)

  // Außerhalb klicken oder Esc schließt das Fenster.
  useEffect(() => {
    if (!offen) return
    function ausserhalb(e: MouseEvent): void {
      if (huelle.current && !huelle.current.contains(e.target as Node)) setzeOffen(false)
    }
    function taste(e: KeyboardEvent): void {
      if (e.key === 'Escape') setzeOffen(false)
    }
    document.addEventListener('mousedown', ausserhalb)
    document.addEventListener('keydown', taste)
    return () => {
      document.removeEventListener('mousedown', ausserhalb)
      document.removeEventListener('keydown', taste)
    }
  }, [offen])

  function uebernimm(z: Zeitraum): void {
    setzeZeitraum(z)
    setzeOffen(false)
  }

  const beschreibung =
    zeitraum.von === null && zeitraum.bis === null
      ? 'gesamte Historie'
      : `${zeitraum.von ? datumDe(zeitraum.von) : 'Anfang'} – ${
          zeitraum.bis ? datumDe(zeitraum.bis) : 'heute'
        }`

  const gruppen: { name: string | null; eintraege: Vorgabe[] }[] = []
  for (const v of liste) {
    const name = v.gruppe ?? null
    const letzte = gruppen[gruppen.length - 1]
    if (letzte && letzte.name === name) letzte.eintraege.push(v)
    else gruppen.push({ name, eintraege: [v] })
  }

  return (
    <div className="zeitraumwahl" ref={huelle}>
      <span className="bezeichnung">Zeitraum</span>
      <button
        type="button"
        className="auswahl"
        aria-expanded={offen}
        aria-haspopup="dialog"
        onClick={() => setzeOffen(!offen)}
      >
        {passend ? `${passend.titel} · ` : ''}
        {beschreibung} <span aria-hidden="true">▾</span>
      </button>
      {!wirkt && (zeitraum.von || zeitraum.bis) && (
        <span className="fussnote">— wirkt auf dieser Seite noch nicht</span>
      )}

      {offen && (
        <div className="fenster" role="dialog" aria-label="Zeitraum wählen">
          <div className="vorgaben">
            {gruppen.map((gruppe) => (
              <div key={gruppe.name ?? 'ohne'} className="gruppe">
                {gruppe.name && <h4>{gruppe.name}</h4>}
                <ul>
                  {gruppe.eintraege.map((v) => (
                    <li key={v.schluessel}>
                      <button
                        type="button"
                        aria-pressed={passend?.schluessel === v.schluessel}
                        className={passend?.schluessel === v.schluessel ? 'gewaehlt' : undefined}
                        onClick={() => uebernimm(v.zeitraum)}
                      >
                        {v.titel}
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <Kalenderwahl zeitraum={zeitraum} waehle={uebernimm} />
        </div>
      )}
    </div>
  )
}
