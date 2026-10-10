// AP-08g1: Das gemeinsame Raster der Diagramm-Bausteine — Achsenwerte,
// Zeitmarken und Zeiger-Kasten. D2 (auftraege/AP-08f.md) erlaubt genau eine
// Ausnahme von Vertrag 8: Der Text der API darf in eine Zahl gewandelt
// werden, um einen Punkt zu platzieren. Genau das passiert hier — für
// Pixelpositionen und runde Achsenwerte. Angezeigt wird ausschließlich der
// API-Text über die Formatierer (betrag, geldDe, datumDe); kein Ergebnis
// dieser Datei erscheint als eigener Wert in der Oberfläche.

import { betrag } from '../format'

// Ein Punkt der API: x = ISO-Datum (JJJJ-MM-TT) oder Monatsbeschriftung
// (JJJJ-MM), y = Betrag als unveränderter Text.
export interface Punkt {
  x: string
  y: string
}

// Abmessungen: feste Höhe, über viewBox responsiv (width: 100% in stil.css).
export const KURVE_BREITE = 720
export const KURVE_HOEHE = 220
export const BALKEN_BREITE = 720
export const BALKEN_HOEHE = 180

// Platz für Achsenbeschriftung links und unten.
export const RAND = { links: 60, rechts: 12, oben: 14, unten: 26 }

export function grafikBreite(breite: number): number {
  return breite - RAND.links - RAND.rechts
}

export function grafikHoehe(hoehe: number): number {
  return hoehe - RAND.oben - RAND.unten
}

// Runde Teilstriche der y-Achse: Schrittbreite auf 1, 2, 2,5 oder 5 × 10^k
// gerundet, der Bereich auf ganze Schritte erweitert — das ergibt 4 bis 6
// Striche. Zahlen nur fürs Raster (D2), die Beschriftung geht durch betrag().
export function yRaster(
  minWert: number,
  maxWert: number,
): { von: number; bis: number; striche: number[] } {
  let min = minWert
  let max = maxWert
  if (min === max) {
    min = Math.min(0, min)
    max = Math.max(0, max)
    if (min === max) max = min + 1
  }
  const roh = (max - min) / 4
  const potenz = Math.pow(10, Math.floor(Math.log10(roh)))
  const normiert = roh / potenz
  const faktor =
    normiert <= 1 ? 1 : normiert <= 2 ? 2 : normiert <= 2.5 ? 2.5 : normiert <= 5 ? 5 : 10
  const schritt = faktor * potenz
  const von = Math.floor(min / schritt) * schritt
  const bis = Math.ceil(max / schritt) * schritt
  const striche: number[] = []
  for (let w = von; w <= bis + schritt / 2; w += schritt) striche.push(w)
  return { von, bis, striche }
}

// Pixelhöhe eines Werts — nur fürs Zeichnen (D2).
export function yPixel(wert: number, von: number, bis: number, hoehe: number): number {
  const anteil = bis === von ? 0.5 : (wert - von) / (bis - von)
  return RAND.oben + (1 - anteil) * grafikHoehe(hoehe)
}

// Ein ISO-Datum als Millisekunden — UTC-Mitternacht, damit die Zeitzone des
// Browsers den Tag nicht verschiebt. Nur fürs Zeichnen (D2).
export function isoMs(iso: string): number {
  return Date.parse(`${iso.slice(0, 10)}T00:00:00Z`)
}

// Beschriftung eines Monats („2025-03“ → „03/25“) — reine Zeichenarbeit.
export function monatKurz(monat: string): string {
  const [jahr, mm] = monat.split('-')
  return `${mm}/${jahr.slice(2)}`
}

// Zeitmarken der x-Achse: bis etwa 18 Monate Monatsanfänge (MM/JJ), darüber
// Jahresanfänge (JJJJ). Mehr als zehn Marken verlieren den Rang.
export function xMarken(ersteIso: string, letzteIso: string): { ms: number; text: string }[] {
  const erste = new Date(isoMs(ersteIso))
  const letzte = new Date(isoMs(letzteIso))
  const jahrV = erste.getUTCFullYear()
  const monatV = erste.getUTCMonth()
  const jahrB = letzte.getUTCFullYear()
  const monatB = letzte.getUTCMonth()
  const monate = (jahrB - jahrV) * 12 + (monatB - monatV) + 1
  const marken: { ms: number; text: string }[] = []
  if (monate <= 18) {
    let jahr = jahrV
    let monat = monatV + 1
    if (monat > 11) {
      monat = 0
      jahr += 1
    }
    while (jahr < jahrB || (jahr === jahrB && monat <= monatB)) {
      marken.push({
        ms: Date.UTC(jahr, monat, 1),
        text: `${String(monat + 1).padStart(2, '0')}/${String(jahr).slice(2)}`,
      })
      monat += 1
      if (monat > 11) {
        monat = 0
        jahr += 1
      }
    }
  } else {
    for (let jahr = jahrV + 1; jahr <= jahrB; jahr += 1) {
      marken.push({ ms: Date.UTC(jahr, 0, 1), text: String(jahr) })
    }
  }
  if (marken.length > 10) {
    const schritt = Math.ceil(marken.length / 10)
    return marken.filter((_, i) => i % schritt === 0 || i === marken.length - 1)
  }
  return marken
}

// Das Gerüst einer Kurve über der Zeit — von Linie.tsx und Flaeche.tsx
// gemeinsam genutzt. Number() bestimmt ausschließlich Pixelpositionen (D2).
export function kurvenGeruest(punkte: Punkt[]) {
  const werte = punkte.map((punkt) => Number(punkt.y))
  const raster = yRaster(Math.min(...werte), Math.max(...werte))
  const ms = punkte.map((punkt) => isoMs(punkt.x))
  const msVon = ms[0]
  const msBis = ms[ms.length - 1]
  const px = (i: number): number =>
    RAND.links +
    (msBis === msVon
      ? grafikBreite(KURVE_BREITE) / 2
      : ((ms[i] - msVon) / (msBis - msVon)) * grafikBreite(KURVE_BREITE))
  const py = (wert: number): number => yPixel(wert, raster.von, raster.bis, KURVE_HOEHE)
  const pfad = punkte
    .map(
      (punkt, i) => `${i === 0 ? 'M' : 'L'}${px(i).toFixed(1)} ${py(Number(punkt.y)).toFixed(1)}`,
    )
    .join(' ')
  const marken = xMarken(punkte[0].x, punkte[punkte.length - 1].x)
  return { raster, ms, msVon, msBis, px, py, pfad, marken }
}

export type KurvenGeruest = ReturnType<typeof kurvenGeruest>

// Index des zeitlich nächsten Punkts zur Mausposition (D2: Pixel, nicht
// Inhalt) — für die senkrechte Hilfslinie des Zeigers.
export function naechsterIndex(ms: number[], grafikX: number): number {
  const msVon = ms[0]
  const msBis = ms[ms.length - 1]
  const ziel = msVon + ((grafikX - RAND.links) / grafikBreite(KURVE_BREITE)) * (msBis - msVon)
  let bester = 0
  let abstand = Infinity
  for (let i = 0; i < ms.length; i += 1) {
    const entfernt = Math.abs(ms[i] - ziel)
    if (entfernt < abstand) {
      abstand = entfernt
      bester = i
    }
  }
  return bester
}

// Die y-Achse: Teilstriche mit Beschriftung über betrag(), die Nulllinie
// deutlicher, wenn sie im Bereich liegt.
export function yAchse(
  raster: { von: number; bis: number; striche: number[] },
  hoehe: number,
  breite: number,
): JSX.Element {
  return (
    <g className="raster">
      {raster.striche.map((wert) => {
        const y = yPixel(wert, raster.von, raster.bis, hoehe)
        const istNull = Math.abs(wert) < 1e-9
        return (
          <g key={wert} className={istNull ? 'nulllinie' : undefined}>
            <line
              x1={RAND.links}
              y1={y}
              x2={breite - RAND.rechts}
              y2={y}
              strokeWidth={istNull ? 1.4 : 1}
            />
            <text x={RAND.links - 6} y={y + 4} textAnchor="end">
              {betrag(String(wert))}
            </text>
          </g>
        )
      })}
    </g>
  )
}

// Die x-Achse: feine Senkrechte je Marke mit Beschriftung darunter.
export function xAchse(
  marken: { ms: number; text: string }[],
  msVon: number,
  msBis: number,
  breite: number,
  hoehe: number,
): JSX.Element {
  const unten = RAND.oben + grafikHoehe(hoehe)
  return (
    <g className="marke">
      {marken.map((marke) => {
        if (marke.ms < msVon || marke.ms > msBis) return null
        const x = RAND.links + ((marke.ms - msVon) / (msBis - msVon)) * grafikBreite(breite)
        return (
          <g key={marke.ms}>
            <line x1={x} y1={RAND.oben} x2={x} y2={unten} />
            <text x={x} y={unten + 16} textAnchor="middle">
              {marke.text}
            </text>
          </g>
        )
      })}
    </g>
  )
}

// Der Zeiger-Kasten: eine Zeile je Eintrag (Datum, Beträge …), der Rohwert
// der API im <title>. Bleibt innerhalb des Rahmens.
export function zeigerKasten(
  zeilen: string[],
  x: number,
  y: number,
  rohwert: string,
  breite: number,
  hoehe: number,
): JSX.Element {
  const kastenBreite = Math.max(...zeilen.map((zeile) => zeile.length)) * 6.4 + 14
  const kastenHoehe = zeilen.length * 16 + 10
  let kx = x + 9
  if (kx + kastenBreite > breite - RAND.rechts) kx = x - 9 - kastenBreite
  const ky = Math.min(Math.max(RAND.oben + 2, y - kastenHoehe - 7), hoehe - RAND.unten - kastenHoehe)
  return (
    <g className="zeiger">
      <title>{rohwert}</title>
      <rect
        x={kx.toFixed(1)}
        y={ky.toFixed(1)}
        width={kastenBreite}
        height={kastenHoehe}
        rx={3}
      />
      {zeilen.map((zeile, i) => (
        <text key={i} x={kx + 7} y={ky + 16 + i * 16}>
          {zeile}
        </text>
      ))}
    </g>
  )
}


