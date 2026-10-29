// AP-08g1, D1 (auftraege/AP-08f.md): eigener SVG-Baustein, keine
// Diagramm-Bibliothek — wie Linie.tsx, dazu die Fläche zwischen Kurve und
// Nulllinie. Für den Drawdown (Werte bis 0 hinab) rot gefüllt. D2: Number()
// bestimmt ausschließlich Pixelpositionen; angezeigt werden nur die
// API-Texte über die Formatierer (Vertrag 8 gilt für alles Sichtbare).

import { useMemo, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'
import { betrag, datumDe, geldDe } from '../format'
import { DiagrammWert, tastaturIndex, useDiagrammBreite, zeigerX } from './bedienung'
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
  // Achse und Zeiger als Geld (Vorgabe) oder als Prozent (Werte schon in %).
  einheit?: 'geld' | 'prozent'
}

export default function Flaeche({
  punkte,
  titel,
  farbe = 'negativ',
  einheit = 'geld',
}: Eigenschaften): JSX.Element {
  const [aktiv, setzeAktiv] = useState<number | null>(null)
  const { ref, breite } = useDiagrammBreite(KURVE_BREITE)
  const geruest = useMemo(() => (punkte.length === 0 ? null : kurvenGeruest(punkte, breite)), [punkte, breite])
  const beschreibung = titel ?? (einheit === 'prozent' ? 'Prozentualer Verlauf' : 'Werteverlauf')

  function zeigeZeiger(e: PointerEvent<SVGSVGElement>): void {
    if (!geruest) return
    setzeAktiv(naechsterIndex(geruest.ms, zeigerX(e, breite), breite))
  }

  function taste(e: KeyboardEvent<SVGSVGElement>): void {
    const index = tastaturIndex(e, aktiv, punkte.length)
    if (index !== undefined) setzeAktiv(index)
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
  const gewaehlt = aktiv !== null && aktiv < punkte.length ? { i: aktiv, punkt: punkte[aktiv] } : null
  const zeilen = gewaehlt
    ? [
        datumDe(gewaehlt.punkt.x),
        einheit === 'prozent' ? `${betrag(gewaehlt.punkt.y)} %` : geldDe(gewaehlt.punkt.y),
      ]
    : []

  return (
    <figure className="diagramm" ref={ref}>
      {titel ? <figcaption>{titel}</figcaption> : null}
      <svg
        viewBox={`0 0 ${breite} ${KURVE_HOEHE}`}
        role="img"
        aria-label={`${beschreibung}. Zeiger antippen oder mit den Pfeiltasten bewegen; Pos1 und Ende springen an die Ränder.`}
        tabIndex={0}
        onPointerMove={zeigeZeiger}
        onPointerDown={zeigeZeiger}
        onPointerLeave={() => setzeAktiv(null)}
        onFocus={() => setzeAktiv((wert) => wert ?? punkte.length - 1)}
        onBlur={() => setzeAktiv(null)}
        onKeyDown={taste}
      >
        <title>{beschreibung}</title>
        {yAchse(geruest.raster, KURVE_HOEHE, breite, einheit)}
        {xAchse(geruest.marken, geruest.msVon, geruest.msBis, breite, KURVE_HOEHE)}
        <path className={`fuellung-${farbe}`} d={fuellung} />
        <path className={`kurve kurve-${farbe}`} d={geruest.pfad} />
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
              zeilen,
              geruest.px(gewaehlt.i),
              geruest.py(Number(gewaehlt.punkt.y)),
              `${gewaehlt.punkt.x} · ${gewaehlt.punkt.y}`,
              breite,
              KURVE_HOEHE,
            )}
          </g>
        ) : null}
      </svg>
      <DiagrammWert zeilen={zeilen} />
    </figure>
  )
}
