// AP-08g1, D1 (auftraege/AP-08f.md): eigener SVG-Baustein, keine
// Diagramm-Bibliothek. Ein Balken je Eintrag — positiv grün, negativ rot
// (die Farben von .positiv/.negativ in stil.css, hier als Füllung). D2:
// Number() nur für die Balkenhöhe (Pixel); Beschriftung und Zeiger zeigen
// die API-Texte über die Formatierer (Vertrag 8 gilt für alles Sichtbare).
// x ist eine Monatsbeschriftung (z. B. 2025-03), daher steht im Zeiger
// monatKurz() statt datumDe().

import { useMemo, useState } from 'react'
import type { MouseEvent } from 'react'
import { geldDe } from '../format'
import {
  BALKEN_BREITE,
  BALKEN_HOEHE,
  RAND,
  grafikBreite,
  grafikHoehe,
  monatKurz,
  yAchse,
  yPixel,
  yRaster,
  zeigerKasten,
} from './skala'
import type { Punkt } from './skala'

interface Eigenschaften {
  balken: Punkt[]
  titel?: string
}

export default function Balken({ balken, titel }: Eigenschaften): JSX.Element {
  const [aktiv, setzeAktiv] = useState<number | null>(null)

  const geruest = useMemo(() => {
    if (balken.length === 0) return null
    const werte = balken.map((eintrag) => Number(eintrag.y))
    const raster = yRaster(Math.min(0, ...werte), Math.max(0, ...werte))
    const slot = grafikBreite(BALKEN_BREITE) / balken.length
    const breite = Math.min(slot * 0.65, 48)
    const py = (wert: number): number => yPixel(wert, raster.von, raster.bis, BALKEN_HOEHE)
    const schritt = Math.max(1, Math.ceil(balken.length / 10))
    return { raster, slot, breite, py, schritt }
  }, [balken])

  function zeigeMaus(e: MouseEvent<SVGSVGElement>): void {
    if (!geruest) return
    const rahmen = e.currentTarget.getBoundingClientRect()
    const grafikX = ((e.clientX - rahmen.left) / rahmen.width) * BALKEN_BREITE
    const index = Math.floor((grafikX - RAND.links) / geruest.slot)
    setzeAktiv(Math.min(Math.max(index, 0), balken.length - 1))
  }

  if (!geruest) {
    return <p className="diagramm-leer">Keine Werte — nichts zu zeichnen.</p>
  }

  const nullY = geruest.py(0)
  const unten = RAND.oben + grafikHoehe(BALKEN_HOEHE)
  const gewaehlt = aktiv !== null ? { i: aktiv, eintrag: balken[aktiv] } : null

  return (
    <figure className="diagramm">
      {titel ? <figcaption>{titel}</figcaption> : null}
      <svg
        viewBox={`0 0 ${BALKEN_BREITE} ${BALKEN_HOEHE}`}
        role="img"
        onMouseMove={zeigeMaus}
        onMouseLeave={() => setzeAktiv(null)}
      >
        {yAchse(geruest.raster, BALKEN_HOEHE, BALKEN_BREITE)}
        {balken.map((eintrag, i) => {
          const x = RAND.links + i * geruest.slot + (geruest.slot - geruest.breite) / 2
          const wert = Number(eintrag.y)
          const oben = wert >= 0 ? geruest.py(wert) : nullY
          const hoehe = Math.max(Math.abs(nullY - geruest.py(wert)), 1)
          return (
            <g key={eintrag.x}>
              <rect
                className={wert < 0 ? 'balken-negativ' : 'balken-positiv'}
                x={x.toFixed(1)}
                y={oben.toFixed(1)}
                width={geruest.breite.toFixed(1)}
                height={hoehe.toFixed(1)}
              />
              {i % geruest.schritt === 0 || i === balken.length - 1 ? (
                <text
                  x={(RAND.links + i * geruest.slot + geruest.slot / 2).toFixed(1)}
                  y={unten + 16}
                  textAnchor="middle"
                >
                  {monatKurz(eintrag.x)}
                </text>
              ) : null}
            </g>
          )
        })}
        {gewaehlt ? (
          <g>
            <line
              className="zeiger-linie"
              x1={RAND.links + gewaehlt.i * geruest.slot + geruest.slot / 2}
              y1={RAND.oben}
              x2={RAND.links + gewaehlt.i * geruest.slot + geruest.slot / 2}
              y2={unten}
            />
            {zeigerKasten(
              [monatKurz(gewaehlt.eintrag.x), geldDe(gewaehlt.eintrag.y)],
              RAND.links + gewaehlt.i * geruest.slot + geruest.slot / 2,
              geruest.py(Number(gewaehlt.eintrag.y)),
              `${gewaehlt.eintrag.x} · ${gewaehlt.eintrag.y}`,
              BALKEN_BREITE,
              BALKEN_HOEHE,
            )}
          </g>
        ) : null}
      </svg>
    </figure>
  )
}
