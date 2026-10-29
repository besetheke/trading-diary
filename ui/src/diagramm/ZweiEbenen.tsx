import { useMemo, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import { datumDe, geldDe } from '../format'
import { DiagrammWert, tastaturIndex, useDiagrammBreite, zeigerX } from './bedienung'
import {
  KURVE_BREITE,
  KURVE_HOEHE,
  RAND,
  grafikBreite,
  grafikHoehe,
  isoMs,
  naechsterIndex,
  xAchse,
  xMarken,
  yAchse,
  yPixel,
  yRaster,
  zeigerKasten,
} from './skala'
import type { Punkt } from './skala'

interface Eigenschaften {
  oben: Punkt[]
  unten: Punkt[]
  nameOben: string
  nameUnten: string
  titel: string
}

export default function ZweiEbenen({ oben, unten, nameOben, nameUnten, titel }: Eigenschaften): JSX.Element {
  const [aktivMs, setzeAktivMs] = useState<number | null>(null)
  const { ref, breite } = useDiagrammBreite(KURVE_BREITE)

  const geruest = useMemo(() => {
    const msOben = oben.map((punkt) => isoMs(punkt.x))
    const msUnten = unten.map((punkt) => isoMs(punkt.x))
    const zeitpunkte = Array.from(new Set([...msOben, ...msUnten])).sort((a, b) => a - b)
    if (zeitpunkte.length === 0) return null
    const msVon = zeitpunkte[0]
    const msBis = zeitpunkte[zeitpunkte.length - 1]
    const zeichenBreite = grafikBreite(breite)
    const px = (ms: number): number =>
      RAND.links + (msBis === msVon ? zeichenBreite / 2 : ((ms - msVon) / (msBis - msVon)) * zeichenBreite)
    const raster = (punkte: Punkt[]) => {
      if (punkte.length === 0) return null
      const werte = punkte.map((punkt) => Number(punkt.y))
      return yRaster(Math.min(...werte), Math.max(...werte))
    }
    const rasterOben = raster(oben)
    const rasterUnten = raster(unten)
    const pfad = (punkte: Punkt[], skala: NonNullable<typeof rasterOben>): string =>
      punkte
        .map((punkt, i) => {
          const y = yPixel(Number(punkt.y), skala.von, skala.bis, KURVE_HOEHE)
          return `${i === 0 ? 'M' : 'L'}${px(isoMs(punkt.x)).toFixed(1)} ${y.toFixed(1)}`
        })
        .join(' ')
    const marken = xMarken(
      new Date(msVon).toISOString().slice(0, 10),
      new Date(msBis).toISOString().slice(0, 10),
      breite,
    )
    return {
      msOben,
      msUnten,
      zeitpunkte,
      msVon,
      msBis,
      px,
      rasterOben,
      rasterUnten,
      pfadOben: rasterOben ? pfad(oben, rasterOben) : '',
      pfadUnten: rasterUnten ? pfad(unten, rasterUnten) : '',
      marken,
    }
  }, [oben, unten, breite])

  function zeigeZeiger(e: PointerEvent<SVGSVGElement>, ms: number[]): void {
    if (!geruest || ms.length === 0) return
    setzeAktivMs(ms[naechsterIndex(ms, zeigerX(e, breite), breite)])
  }

  function taste(e: KeyboardEvent<SVGSVGElement>): void {
    if (!geruest) return
    const aktiv = aktivMs === null ? null : geruest.zeitpunkte.indexOf(aktivMs)
    const index = tastaturIndex(e, aktiv, geruest.zeitpunkte.length)
    if (index !== undefined) setzeAktivMs(geruest.zeitpunkte[index])
  }

  if (!geruest) return <p className="diagramm-leer">Keine Werte — nichts zu zeichnen.</p>

  const gewaehltOben = aktivMs !== null && oben.length > 0
    ? oben[naechsterIndex(geruest.msOben, geruest.px(aktivMs), breite)]
    : null
  const gewaehltUnten = aktivMs !== null && unten.length > 0
    ? unten[naechsterIndex(geruest.msUnten, geruest.px(aktivMs), breite)]
    : null
  const zeilen = [
    gewaehltOben ? `${nameOben}: ${geldDe(gewaehltOben.y)} (${datumDe(gewaehltOben.x)})` : '',
    gewaehltUnten ? `${nameUnten}: ${geldDe(gewaehltUnten.y)} (${datumDe(gewaehltUnten.x)})` : '',
  ].filter((zeile) => zeile !== '')
  const fokus = (): void => {
    if (geruest.zeitpunkte.length > 0) {
      setzeAktivMs((wert) => wert ?? geruest.zeitpunkte[geruest.zeitpunkte.length - 1])
    }
  }

  const ebene = (
    punkte: Punkt[],
    ms: number[],
    name: string,
    pfad: string,
    raster: typeof geruest.rasterOben,
    gewaehlt: Punkt | null,
  ): JSX.Element => (
    <div className="diagramm-ebene">
      <span className="diagramm-ebene-titel">{name}</span>
      {punkte.length === 0 || !raster ? (
        <p className="diagramm-leer">Keine Werte in dieser Zeitreihe.</p>
      ) : (
        <svg
          viewBox={`0 0 ${breite} ${KURVE_HOEHE}`}
          role="img"
          aria-label={`${name}. Zeiger antippen oder mit den Pfeiltasten bewegen; beide Panels verwenden dieselbe Zeitachse.`}
          tabIndex={0}
          onPointerMove={(e) => zeigeZeiger(e, ms)}
          onPointerDown={(e) => zeigeZeiger(e, ms)}
          onPointerLeave={() => setzeAktivMs(null)}
          onFocus={fokus}
          onBlur={() => setzeAktivMs(null)}
          onKeyDown={taste}
        >
          <title>{name}</title>
          {yAchse(raster, KURVE_HOEHE, breite)}
          {xAchse(geruest.marken, geruest.msVon, geruest.msBis, breite, KURVE_HOEHE)}
          <path className={name === nameOben ? 'kurve' : 'kurve-duenn'} d={pfad} />
          {gewaehlt ? (
            <g>
              <line
                className="zeiger-linie"
                x1={geruest.px(isoMs(gewaehlt.x))}
                y1={RAND.oben}
                x2={geruest.px(isoMs(gewaehlt.x))}
                y2={RAND.oben + grafikHoehe(KURVE_HOEHE)}
              />
              {zeigerKasten(
                [datumDe(gewaehlt.x), `${name}: ${geldDe(gewaehlt.y)}`],
                geruest.px(isoMs(gewaehlt.x)),
                yPixel(Number(gewaehlt.y), raster.von, raster.bis, KURVE_HOEHE),
                `${gewaehlt.x} · ${gewaehlt.y}`,
                breite,
                KURVE_HOEHE,
              )}
            </g>
          ) : null}
        </svg>
      )}
    </div>
  )

  return (
    <figure className="diagramm diagramm-ebenen" ref={ref}>
      <figcaption>{titel}</figcaption>
      {ebene(oben, geruest.msOben, nameOben, geruest.pfadOben, geruest.rasterOben, gewaehltOben)}
      {ebene(unten, geruest.msUnten, nameUnten, geruest.pfadUnten, geruest.rasterUnten, gewaehltUnten)}
      <DiagrammWert zeilen={zeilen} />
    </figure>
  )
}
