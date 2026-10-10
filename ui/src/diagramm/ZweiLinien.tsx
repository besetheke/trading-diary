// AP-08h: Zwei Kurven in einem Raster — der kräftigen Hauptlinie (Kontowert
// gesamt oder Gewinn laut IB) folgt eine dünnere zweite Linie mit eigenen
// Zeitpunkten (Einzahlungen beziehungsweise realisierte Equity); optional
// liegt zwischen beiden eine Fläche. Achsen, Raster und Zeiger stammen aus
// skala.tsx (AP-08g1, D1–D3 in auftraege/AP-08f.md). D2: Number() bestimmt
// ausschließlich Pixelpositionen; angezeigt werden nur die API-Texte über
// die Formatierer (Vertrag 8 gilt für alles Sichtbare).

import { useMemo, useState } from 'react'
import type { MouseEvent } from 'react'
import { datumDe, geldDe } from '../format'
import {
  KURVE_BREITE,
  KURVE_HOEHE,
  RAND,
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
  // Kräftige Hauptlinie.
  oben: Punkt[]
  // Dünnere zweite Linie mit eigenen Zeitpunkten; null zeichnet keine.
  unten: Punkt[] | null
  // Fläche zwischen den Linien — setzt voraus, dass beide Reihen dieselben
  // x-Werte tragen (in AP-08h kommen beide aus nav.tage).
  flaeche?: boolean
  // Füllfarbe der Fläche nach Inhalt.
  farbe?: 'positiv' | 'negativ'
  legendeOben?: string
  legendeUnten?: string | null
  titel?: string
}

export default function ZweiLinien({
  oben,
  unten,
  flaeche = false,
  farbe = 'positiv',
  legendeOben,
  legendeUnten,
  titel,
}: Eigenschaften): JSX.Element {
  const [aktiv, setzeAktiv] = useState<number | null>(null)

  const geruest = useMemo(() => {
    if (oben.length === 0) return null
    const msOben = oben.map((punkt) => isoMs(punkt.x))
    const msUnten = unten ? unten.map((punkt) => isoMs(punkt.x)) : []
    const msVon = msUnten.length > 0 ? Math.min(msOben[0], msUnten[0]) : msOben[0]
    const msBis =
      msUnten.length > 0
        ? Math.max(msOben[msOben.length - 1], msUnten[msUnten.length - 1])
        : msOben[msOben.length - 1]
    const werte = [...oben, ...(unten ?? [])].map((punkt) => Number(punkt.y))
    const raster = yRaster(Math.min(...werte), Math.max(...werte))
    const breite = KURVE_BREITE - RAND.links - RAND.rechts
    const px = (ms: number): number =>
      RAND.links + (msBis === msVon ? breite / 2 : ((ms - msVon) / (msBis - msVon)) * breite)
    const py = (wert: number): number => yPixel(wert, raster.von, raster.bis, KURVE_HOEHE)
    const pfad = (punkte: Punkt[]): string =>
      punkte
        .map(
          (punkt, i) =>
            `${i === 0 ? 'M' : 'L'}${px(isoMs(punkt.x)).toFixed(1)} ${py(Number(punkt.y)).toFixed(1)}`,
        )
        .join(' ')
    const pfadOben = pfad(oben)
    const pfadUnten = unten ? pfad(unten) : null
    let fuellung: string | null = null
    if (flaeche && unten && unten.length === oben.length) {
      const zurueck = unten
        .map((punkt) => `L${px(isoMs(punkt.x)).toFixed(1)} ${py(Number(punkt.y)).toFixed(1)}`)
        .reverse()
        .join(' ')
      fuellung = `${pfadOben} ${zurueck} Z`
    }
    const marken = xMarken(
      new Date(msVon).toISOString().slice(0, 10),
      new Date(msBis).toISOString().slice(0, 10),
    )
    return { msOben, msUnten, msVon, msBis, raster, px, py, pfadOben, pfadUnten, fuellung, marken }
  }, [oben, unten, flaeche])

  function zeigeMaus(e: MouseEvent<SVGSVGElement>): void {
    if (!geruest) return
    const rahmen = e.currentTarget.getBoundingClientRect()
    const grafikX = ((e.clientX - rahmen.left) / rahmen.width) * KURVE_BREITE
    setzeAktiv(naechsterIndex(geruest.msOben, grafikX))
  }

  if (!geruest) {
    return <p className="diagramm-leer">Keine Werte — nichts zu zeichnen.</p>
  }

  const gewaehlt = aktiv !== null ? { i: aktiv, punkt: oben[aktiv] } : null
  // Passender Punkt der zweiten Reihe zur Zeigerzeit — die Reihen können
  // unterschiedliche Tage tragen (Gewinn laut IB gegen realisierte Equity).
  const untenPunkt =
    gewaehlt && geruest.msUnten.length > 0 && unten
      ? unten[
          naechsterIndex(
            geruest.msUnten,
            geruest.px(geruest.msOben[gewaehlt.i]),
          )
        ]
      : null

  const zeilen = gewaehlt
    ? [datumDe(gewaehlt.punkt.x), geldDe(gewaehlt.punkt.y)]
    : []
  if (gewaehlt && untenPunkt) zeilen.push(geldDe(untenPunkt.y))

  return (
    <figure className="diagramm">
      {titel ? <figcaption>{titel}</figcaption> : null}
      {legendeOben || legendeUnten ? (
        <ul className="diagramm-legende">
          {legendeOben ? (
            <li>
              <span className="probe kraeftig" />
              {legendeOben}
            </li>
          ) : null}
          {legendeUnten ? (
            <li>
              <span className="probe duenn" />
              {legendeUnten}
            </li>
          ) : null}
        </ul>
      ) : null}
      <svg
        viewBox={`0 0 ${KURVE_BREITE} ${KURVE_HOEHE}`}
        role="img"
        onMouseMove={zeigeMaus}
        onMouseLeave={() => setzeAktiv(null)}
      >
        {yAchse(geruest.raster, KURVE_HOEHE, KURVE_BREITE)}
        {xAchse(geruest.marken, geruest.msVon, geruest.msBis, KURVE_BREITE, KURVE_HOEHE)}
        {geruest.fuellung ? <path className={`fuellung-${farbe}`} d={geruest.fuellung} /> : null}
        {geruest.pfadUnten ? <path className="kurve-duenn" d={geruest.pfadUnten} /> : null}
        <path className="kurve" d={geruest.pfadOben} />
        {gewaehlt ? (
          <g>
            <line
              className="zeiger-linie"
              x1={geruest.px(geruest.msOben[gewaehlt.i])}
              y1={RAND.oben}
              x2={geruest.px(geruest.msOben[gewaehlt.i])}
              y2={RAND.oben + grafikHoehe(KURVE_HOEHE)}
            />
            {zeigerKasten(
              zeilen,
              geruest.px(geruest.msOben[gewaehlt.i]),
              geruest.py(Number(gewaehlt.punkt.y)),
              `${gewaehlt.punkt.x} · ${gewaehlt.punkt.y}${untenPunkt ? ` · ${untenPunkt.y}` : ''}`,
              KURVE_BREITE,
              KURVE_HOEHE,
            )}
          </g>
        ) : null}
      </svg>
    </figure>
  )
}
