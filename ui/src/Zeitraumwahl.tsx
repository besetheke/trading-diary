import { useEffect, useState } from 'react'
import { datumDe } from './format'
import { passendeVorgabe, useZeitraum, vorgaben } from './zeitraum'

// AP-08f2: Zeitraum-Wähler im Kopf. Eine Auswahlliste mit den Vorgaben
// (Z1) und „Von–bis …" für einen freien Zeitraum; der gewählte Zeitraum
// steht in der Adresse und gilt für jede Ansicht, die Zeit kennt.

const EIGEN = 'eigen'

export default function Zeitraumwahl({ wirkt }: { wirkt: boolean }): JSX.Element {
  const [zeitraum, setzeZeitraum] = useZeitraum()
  const liste = vorgaben()
  const passend = passendeVorgabe(zeitraum)
  const [eigen, setzeEigen] = useState(passend === null)
  const [entwurf, setzeEntwurf] = useState({ von: zeitraum.von ?? '', bis: zeitraum.bis ?? '' })

  // Kommt der Zeitraum von außen (Verweis, Zurück-Taste), Entwurf nachziehen.
  useEffect(() => {
    setzeEntwurf({ von: zeitraum.von ?? '', bis: zeitraum.bis ?? '' })
    if (passendeVorgabe(zeitraum) === null) setzeEigen(true)
  }, [zeitraum.von, zeitraum.bis])

  function waehle(schluessel: string): void {
    if (schluessel === EIGEN) {
      setzeEigen(true)
      return
    }
    setzeEigen(false)
    const vorgabe = liste.find((v) => v.schluessel === schluessel)
    if (vorgabe) setzeZeitraum(vorgabe.zeitraum)
  }

  const ungueltig = entwurf.von !== '' && entwurf.bis !== '' && entwurf.von > entwurf.bis

  const beschreibung =
    zeitraum.von === null && zeitraum.bis === null
      ? 'gesamte Historie'
      : `${zeitraum.von ? datumDe(zeitraum.von) : 'Anfang'} – ${
          zeitraum.bis ? datumDe(zeitraum.bis) : 'heute'
        }`

  return (
    <div className="zeitraumwahl">
      <label>
        Zeitraum
        <select
          value={eigen ? EIGEN : (passend?.schluessel ?? EIGEN)}
          onChange={(e) => waehle(e.target.value)}
        >
          {liste.map((v) => (
            <option key={v.schluessel} value={v.schluessel}>
              {v.titel}
            </option>
          ))}
          <option value={EIGEN}>Von – bis …</option>
        </select>
      </label>
      {eigen && (
        <form
          className="eigen"
          onSubmit={(e) => {
            e.preventDefault()
            if (!ungueltig) setzeZeitraum({ von: entwurf.von || null, bis: entwurf.bis || null })
          }}
        >
          <input
            type="date"
            value={entwurf.von}
            onChange={(e) => setzeEntwurf({ ...entwurf, von: e.target.value })}
            aria-label="von"
          />
          <span>–</span>
          <input
            type="date"
            value={entwurf.bis}
            onChange={(e) => setzeEntwurf({ ...entwurf, bis: e.target.value })}
            aria-label="bis"
          />
          <button type="submit" disabled={ungueltig}>
            Übernehmen
          </button>
          {ungueltig && <span className="negativ">„von" liegt nach „bis"</span>}
        </form>
      )}
      <span className="beschreibung">{beschreibung}</span>
      {!wirkt && (zeitraum.von || zeitraum.bis) && (
        <span className="fussnote">— wirkt auf dieser Seite noch nicht</span>
      )}
    </div>
  )
}
