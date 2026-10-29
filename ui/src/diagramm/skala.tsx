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

interface Zeitmarke {
  ms: number
  text: string
}

function isoVonMs(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10)
}

function kurzesDatum(ms: number, mitJahr: boolean): string {
  const [jahr, monat, tag] = isoVonMs(ms).split('-')
  return mitJahr ? `${tag}.${monat}.${jahr.slice(2)}` : `${tag}.${monat}.`
}

function markenAusduennen(marken: Zeitmarke[], hoechstzahl: number): Zeitmarke[] {
  if (marken.length <= hoechstzahl) return marken
  const schritt = (marken.length - 1) / (hoechstzahl - 1)
  return Array.from({ length: hoechstzahl }, (_, i) => marken[Math.round(i * schritt)])
}

// Zeitmarken folgen dem sichtbaren Zeitraum und der tatsächlichen Diagrammbreite.
// Start und Ende bleiben immer lesbar; auch ein einzelner Monat erhält eine Achse.
export function xMarken(ersteIso: string, letzteIso: string, breite = KURVE_BREITE): Zeitmarke[] {
  const von = isoMs(ersteIso)
  const bis = isoMs(letzteIso)
  if (von === bis) return [{ ms: von, text: kurzesDatum(von, true) }]
  const tage = Math.round((bis - von) / 86_400_000)
  const marken: Zeitmarke[] = [{ ms: von, text: '' }]
  if (tage <= 62) {
    for (let ms = von + 86_400_000; ms < bis; ms += 86_400_000) marken.push({ ms, text: '' })
  } else if (tage <= 210) {
    const wochentag = new Date(von).getUTCDay()
    let ms = von + ((8 - wochentag) % 7 || 7) * 86_400_000
    for (; ms < bis; ms += 7 * 86_400_000) marken.push({ ms, text: '' })
  } else {
    const erste = new Date(von)
    const letzte = new Date(bis)
    const monate = (letzte.getUTCFullYear() - erste.getUTCFullYear()) * 12 + letzte.getUTCMonth() - erste.getUTCMonth()
    if (monate <= 24) {
      let jahr = erste.getUTCFullYear()
      let monat = erste.getUTCMonth() + 1
      if (monat > 11) {
        monat = 0
        jahr += 1
      }
      while (jahr < letzte.getUTCFullYear() || (jahr === letzte.getUTCFullYear() && monat <= letzte.getUTCMonth())) {
        const ms = Date.UTC(jahr, monat, 1)
        if (ms < bis) marken.push({ ms, text: `${String(monat + 1).padStart(2, '0')}/${String(jahr).slice(2)}` })
        monat += 1
        if (monat > 11) {
          monat = 0
          jahr += 1
        }
      }
    } else {
      for (let jahr = erste.getUTCFullYear() + 1; jahr <= letzte.getUTCFullYear(); jahr += 1) {
        const ms = Date.UTC(jahr, 0, 1)
        if (ms < bis) marken.push({ ms, text: String(jahr) })
      }
    }
  }
  marken.push({ ms: bis, text: '' })
  const hoechstzahl = Math.max(2, Math.floor(grafikBreite(breite) / 72))
  return markenAusduennen(marken, hoechstzahl).map((marke, i, auswahl) => ({
    ...marke,
    text: marke.text || kurzesDatum(marke.ms, i === 0 || i === auswahl.length - 1),
  }))
}

// Das Gerüst einer Kurve über der Zeit — von Linie.tsx und Flaeche.tsx
// gemeinsam genutzt. Number() bestimmt ausschließlich Pixelpositionen (D2).
export function kurvenGeruest(punkte: Punkt[], breite = KURVE_BREITE) {
  const werte = punkte.map((punkt) => Number(punkt.y))
  const raster = yRaster(Math.min(...werte), Math.max(...werte))
  const ms = punkte.map((punkt) => isoMs(punkt.x))
  const msVon = ms[0]
  const msBis = ms[ms.length - 1]
  const px = (i: number): number =>
    RAND.links +
    (msBis === msVon
      ? grafikBreite(breite) / 2
      : ((ms[i] - msVon) / (msBis - msVon)) * grafikBreite(breite))
  const py = (wert: number): number => yPixel(wert, raster.von, raster.bis, KURVE_HOEHE)
  const pfad = punkte
    .map(
      (punkt, i) => `${i === 0 ? 'M' : 'L'}${px(i).toFixed(1)} ${py(Number(punkt.y)).toFixed(1)}`,
    )
    .join(' ')
  const marken = xMarken(punkte[0].x, punkte[punkte.length - 1].x, breite)
  return { raster, ms, msVon, msBis, px, py, pfad, marken }
}

export type KurvenGeruest = ReturnType<typeof kurvenGeruest>

// Index des zeitlich nächsten Punkts zur Zeigerposition (D2: Pixel, nicht Inhalt).
export function naechsterIndex(ms: number[], grafikX: number, breite = KURVE_BREITE): number {
  const msVon = ms[0]
  const msBis = ms[ms.length - 1]
  const ziel = msVon + ((grafikX - RAND.links) / grafikBreite(breite)) * (msBis - msVon)
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
  einheit: 'geld' | 'prozent' = 'geld',
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
              {einheit === 'prozent' ? ' %' : ''}
            </text>
          </g>
        )
      })}
    </g>
  )
}

// Die x-Achse: feine Senkrechte je Marke mit Beschriftung darunter.
export function xAchse(
  marken: Zeitmarke[],
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
        const x = msBis === msVon
          ? RAND.links + grafikBreite(breite) / 2
          : RAND.links + ((marke.ms - msVon) / (msBis - msVon)) * grafikBreite(breite)
        const anker = msBis === msVon ? 'middle' : marke.ms === msVon ? 'start' : marke.ms === msBis ? 'end' : 'middle'
        return (
          <g key={marke.ms}>
            <line x1={x} y1={RAND.oben} x2={x} y2={unten} />
            <text x={x} y={unten + 16} textAnchor={anker}>
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
  const maximaleBreite = Math.max(80, breite - 16)
  const maximaleZeichen = Math.max(12, Math.floor((maximaleBreite - 14) / 6.4))
  const textzeilen = zeilen.flatMap((zeile) => {
    const umbrochen: string[] = []
    let aktuell = ''
    for (const wort of zeile.split(' ')) {
      const naechste = aktuell ? `${aktuell} ${wort}` : wort
      if (naechste.length > maximaleZeichen && aktuell) {
        umbrochen.push(aktuell)
        aktuell = wort
      } else aktuell = naechste
    }
    if (aktuell) umbrochen.push(aktuell)
    return umbrochen
  })
  const kastenBreite = Math.min(maximaleBreite, Math.max(...textzeilen.map((zeile) => zeile.length)) * 6.4 + 14)
  const kastenHoehe = textzeilen.length * 16 + 10
  const kx = Math.max(8, Math.min(x + 9, breite - kastenBreite - 8))
  const ky = Math.max(RAND.oben + 2, Math.min(y - kastenHoehe - 7, hoehe - RAND.unten - kastenHoehe))
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
      {textzeilen.map((zeile, i) => (
        <text key={i} x={kx + 7} y={ky + 16 + i * 16}>
          {zeile}
        </text>
      ))}
    </g>
  )
}


