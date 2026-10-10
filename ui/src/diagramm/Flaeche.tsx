// AP-08g1, D1 (auftraege/AP-08f.md): eigener SVG-Baustein, keine
// Diagramm-Bibliothek — wie Linie.tsx, dazu die Fläche zwischen Kurve und
// Nulllinie. Für den Drawdown (Werte bis 0 hinab) rot gefüllt. D2: Number()
// bestimmt ausschließlich Pixelpositionen; angezeigt werden nur die
// API-Texte über die Formatierer (Vertrag 8 gilt für alles Sichtbare).

import { useMemo, useState } from 'react'
import type { MouseEvent } from 'react'
import { datumDe, geldDe } from '../format'
import {
  KURVE_BREITE,
  KURVE_HOEHE,
  RAND,
  grafikHoehe,
  kurvenGeruest,
  naechsterIndex,
  xAchse,
  yAchse,
  zeigerKasten,
} from './skala'
import type { Punkt } from './skala'

interface Eigenschaften {
  punkte: Punkt[]
  titel?: string
  // Füllfarbe nach Inhalt: Drawdown (Werte ≤ 0) rot. Vorgabe rot, weil
  // dieser Baustein für den Drawdown gebaut wurde.
  farbe?: 'negativ' | 'positiv'
}

export default function Flaeche({ punkte, titel, farbe = 'negativ' }: Eigenschaften): JSX.Element {
  const [aktiv, setzeAktiv] = useState<number | null>(null)

  const geruest = useMemo(() => (punkte.length === 0 ? null : kurvenGeruest(punkte)), [punkte])

  function zeigeMaus(e: MouseEvent<SVGSVGElement>): void {
    if (!geruest) return
    const rahmen = e.currentTarget.getBoundingClientRect()
    const grafikX = ((e.clientX - rahmen.left) / rahmen.width) * KURVE_BREITE
    setzeAktiv(naechsterIndex(geruest.ms, grafikX))
  }

  if (!geruest) {
    return <p className="diagramm-leer">Keine Werte — nichts zu zeichnen.</p>
  }

  // Nulllinie, auf den Achsenbereich geklemmt, wenn 0 außerhalb liegt.
  const basisY = geruest.py(Math.max(geruest.raster.von, Math.min(0, geruest.raster.bis)))
  const letzte = punkte.length - 1
  const fuellung = `${geruest.pfad} L${geruest.px(letzte).toFixed(1)} ${basisY.toFixed(
    1,
  )} L${geruest.px(0).toFixed(1)} ${basisY.toFixed(1)} Z`
  const gewaehlt = aktiv !== null ? { i: aktiv, punkt: punkte[aktiv] } : null

  return (
    <figure className="diagramm">
      {titel ? <figcaption>{titel}</figcaption> : null}
      <svg
        viewBox={`0 0 ${KURVE_BREITE} ${KURVE_HOEHE}`}
        role="img"
        onMouseMove={zeigeMaus}
        onMouseLeave={() => setzeAktiv(null)}
      >
        {yAchse(geruest.raster, KURVE_HOEHE, KURVE_BREITE)}
        {xAchse(geruest.marken, geruest.msVon, geruest.msBis, KURVE_BREITE, KURVE_HOEHE)}
        <path className={`fuellung-${farbe}`} d={fuellung} />
        <path className="kurve" d={geruest.pfad} />
        {gewaehlt ? (
          <g>
            <line
              className="zeiger-linie"
              x1={geruest.px(gewaehlt.i)}
              y1={RAND.oben}
              x2={geruest.px(gewaehlt.i)}
              y2={RAND.oben + grafikHoehe(KURVE_HOEHE)}
            />
            {zeigerKasten(
              geruest.px(gewaehlt.i),
              geruest.py(Number(gewaehlt.punkt.y)),
              datumDe(gewaehlt.punkt.x),
              geldDe(gewaehlt.punkt.y),
              `${gewaehlt.punkt.x} · ${gewaehlt.punkt.y}`,
              KURVE_BREITE,
              KURVE_HOEHE,
            )}
          </g>
        ) : null}
      </svg>
    </figure>
  )
}
