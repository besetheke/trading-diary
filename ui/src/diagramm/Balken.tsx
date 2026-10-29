// AP-08g1, D1 (auftraege/AP-08f.md): eigener SVG-Baustein, keine
// Diagramm-Bibliothek. Ein Balken je Eintrag — positiv grün, negativ rot
// (die Farben von .positiv/.negativ in stil.css, hier als Füllung). D2:
// Number() nur für die Balkenhöhe (Pixel); Beschriftung und Zeiger zeigen
// die API-Texte über die Formatierer (Vertrag 8 gilt für alles Sichtbare).
// x ist eine Monatsbeschriftung (z. B. 2025-03), daher steht im Zeiger
// monatKurz() statt datumDe().

import { useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import { geldDe } from '../format'
import { DiagrammWert, tastaturIndex, useDiagrammBreite, zeigerX } from './bedienung'
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
  // Beschriftung der x-Achse und des Zeigers; Vorgabe Monat (JJJJ-MM).
  beschriftung?: (x: string) => string
  // Balken (x-Werte), die anders dargestellt werden — z. B. unrealisiert.
  hervorheben?: string[]
}

export default function Balken({
  balken,
  titel,
  beschriftung = monatKurz,
  hervorheben = [],
}: Eigenschaften): JSX.Element {
  const [aktiv, setzeAktiv] = useState<number | null>(null)
  const { ref, breite } = useDiagrammBreite(BALKEN_BREITE)
  const scrollRef = useRef<HTMLDivElement>(null)
  const svgBreite = Math.max(breite, RAND.links + RAND.rechts + balken.length * 28)
  const beschreibung = titel ?? 'Periodenwerte'

  useEffect(() => {
    if (scrollRef.current && svgBreite > breite) scrollRef.current.scrollLeft = scrollRef.current.scrollWidth
  }, [breite, svgBreite])

  const geruest = useMemo(() => {
    if (balken.length === 0) return null
    const werte = balken.map((eintrag) => Number(eintrag.y))
    const raster = yRaster(Math.min(0, ...werte), Math.max(0, ...werte))
    const slot = grafikBreite(svgBreite) / balken.length
    const balkenBreite = Math.min(slot * 0.65, 48)
    const py = (wert: number): number => yPixel(wert, raster.von, raster.bis, BALKEN_HOEHE)
    const schritt = Math.max(1, Math.ceil(balken.length / Math.max(2, Math.floor(grafikBreite(svgBreite) / 80))))
    return { raster, slot, balkenBreite, py, schritt }
  }, [balken, svgBreite])

  function zeigeZeiger(e: PointerEvent<SVGSVGElement>): void {
    if (!geruest) return
    const index = Math.floor((zeigerX(e, svgBreite) - RAND.links) / geruest.slot)
    setzeAktiv(Math.min(Math.max(index, 0), balken.length - 1))
  }

  function taste(e: KeyboardEvent<SVGSVGElement>): void {
    const index = tastaturIndex(e, aktiv, balken.length)
    if (index !== undefined) setzeAktiv(index)
  }

  if (!geruest) {
    return <p className="diagramm-leer">Keine Werte — nichts zu zeichnen.</p>
  }

  const nullY = geruest.py(0)
  const unten = RAND.oben + grafikHoehe(BALKEN_HOEHE)
  const gewaehlt = aktiv !== null && aktiv < balken.length ? { i: aktiv, eintrag: balken[aktiv] } : null
  const zeilen = gewaehlt ? [beschriftung(gewaehlt.eintrag.x), geldDe(gewaehlt.eintrag.y)] : []

  return (
    <figure className="diagramm" ref={ref}>
      {titel ? <figcaption>{titel}</figcaption> : null}
      <div className="diagramm-scroll" ref={scrollRef}>
        <svg
          viewBox={`0 0 ${svgBreite} ${BALKEN_HOEHE}`}
          style={{ width: `${svgBreite}px` }}
          role="img"
          aria-label={`${beschreibung}. Balken antippen oder mit den Pfeiltasten auswählen; Pos1 und Ende springen an die Ränder.`}
          tabIndex={0}
          onPointerMove={zeigeZeiger}
          onPointerDown={zeigeZeiger}
          onPointerLeave={() => setzeAktiv(null)}
          onFocus={() => setzeAktiv((wert) => wert ?? balken.length - 1)}
          onBlur={() => setzeAktiv(null)}
          onKeyDown={taste}
        >
          <title>{beschreibung}</title>
          {yAchse(geruest.raster, BALKEN_HOEHE, svgBreite)}
          {balken.map((eintrag, i) => {
            const x = RAND.links + i * geruest.slot + (geruest.slot - geruest.balkenBreite) / 2
            const wert = Number(eintrag.y)
            const oben = wert >= 0 ? geruest.py(wert) : nullY
            const hoehe = Math.max(Math.abs(nullY - geruest.py(wert)), 1)
            return (
              <g key={eintrag.x}>
                <rect
                  className={`${wert < 0 ? 'balken-negativ' : 'balken-positiv'}${
                    hervorheben.includes(eintrag.x) ? ' balken-offen' : ''
                  }`}
                  x={x.toFixed(1)}
                  y={oben.toFixed(1)}
                  width={geruest.balkenBreite.toFixed(1)}
                  height={hoehe.toFixed(1)}
                />
                {i === balken.length - 1 ||
                (i % geruest.schritt === 0 && balken.length - 1 - i >= geruest.schritt / 2) ? (
                  <text
                    x={(RAND.links + i * geruest.slot + geruest.slot / 2).toFixed(1)}
                    y={unten + 16}
                    textAnchor="middle"
                  >
                    {beschriftung(eintrag.x)}
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
                zeilen,
                RAND.links + gewaehlt.i * geruest.slot + geruest.slot / 2,
                geruest.py(Number(gewaehlt.eintrag.y)),
                `${gewaehlt.eintrag.x} · ${gewaehlt.eintrag.y}`,
                svgBreite,
                BALKEN_HOEHE,
              )}
            </g>
          ) : null}
        </svg>
      </div>
      <DiagrammWert zeilen={zeilen} />
    </figure>
  )
}
