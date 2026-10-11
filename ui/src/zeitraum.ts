import { useSearchParams } from 'react-router-dom'

// AP-08f2, Z1: ein Zeitraum für alle Ansichten, in der Adresse
// (?von=JJJJ-MM-TT&bis=JJJJ-MM-TT, beide Enden einschließlich). Ohne Angabe:
// alles. Daten werden aus der lokalen Zeit gebildet — kein toISOString, das
// je nach Zeitzone auf den Vortag rutscht (wie heuteDatum in main.tsx).

export interface Zeitraum {
  von: string | null
  bis: string | null
}

export interface Vorgabe {
  schluessel: string
  titel: string
  zeitraum: Zeitraum
  // Überschrift der Gruppe in der Liste neben dem Kalender; ohne Angabe steht
  // die Vorgabe allein (z. B. „Alles").
  gruppe?: 'Rückblick' | 'Kalender' | 'Jahre'
}

export function iso(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const t = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${t}`
}

function tag(jahr: number, monat: number, t: number): string {
  // Date normalisiert Überläufe: Tag 0 ist der letzte des Vormonats.
  return iso(new Date(jahr, monat, t))
}

export const ERSTES_JAHR = 2022

export function vorgaben(heute: Date = new Date()): Vorgabe[] {
  const j = heute.getFullYear()
  const m = heute.getMonth()
  const wochentag = (heute.getDay() + 6) % 7 // Montag = 0
  const montag = new Date(j, m, heute.getDate() - wochentag)
  const sonntag = new Date(j, m, heute.getDate() - wochentag + 6)
  const q = Math.floor(m / 3)
  const bis = iso(heute)
  // Rückblick: die letzten n Tage einschließlich heute (7 Tage = heute und die
  // sechs davor), beide Enden einschließlich wie überall (Z1).
  const rueckblick = (n: number): Zeitraum => ({
    von: iso(new Date(j, m, heute.getDate() - (n - 1))),
    bis,
  })
  const liste: Vorgabe[] = [
    { schluessel: 'alles', titel: 'Alles', zeitraum: { von: null, bis: null } },
    { schluessel: 'r7', titel: 'Letzte 7 Tage', zeitraum: rueckblick(7), gruppe: 'Rückblick' },
    { schluessel: 'r30', titel: 'Letzte 30 Tage', zeitraum: rueckblick(30), gruppe: 'Rückblick' },
    { schluessel: 'r90', titel: 'Letzte 90 Tage', zeitraum: rueckblick(90), gruppe: 'Rückblick' },
    { schluessel: 'r365', titel: 'Letzte 365 Tage', zeitraum: rueckblick(365), gruppe: 'Rückblick' },
    {
      schluessel: 'ytd',
      titel: 'Seit Jahresbeginn',
      zeitraum: { von: `${j}-01-01`, bis },
      gruppe: 'Rückblick',
    },
    {
      schluessel: 'woche',
      titel: 'Diese Woche',
      zeitraum: { von: iso(montag), bis: iso(sonntag) },
      gruppe: 'Kalender',
    },
    {
      schluessel: 'monat',
      titel: 'Dieser Monat',
      zeitraum: { von: tag(j, m, 1), bis: tag(j, m + 1, 0) },
      gruppe: 'Kalender',
    },
    {
      schluessel: 'vormonat',
      titel: 'Letzter Monat',
      zeitraum: { von: tag(j, m - 1, 1), bis: tag(j, m, 0) },
      gruppe: 'Kalender',
    },
    {
      schluessel: 'quartal',
      titel: 'Dieses Quartal',
      zeitraum: { von: tag(j, q * 3, 1), bis: tag(j, q * 3 + 3, 0) },
      gruppe: 'Kalender',
    },
    {
      schluessel: 'jahr',
      titel: 'Dieses Jahr',
      zeitraum: { von: `${j}-01-01`, bis: `${j}-12-31` },
      gruppe: 'Kalender',
    },
    {
      schluessel: 'vorjahr',
      titel: 'Letztes Jahr',
      zeitraum: { von: `${j - 1}-01-01`, bis: `${j - 1}-12-31` },
      gruppe: 'Kalender',
    },
  ]
  for (let jahr = j - 2; jahr >= ERSTES_JAHR; jahr--) {
    liste.push({
      schluessel: `j${jahr}`,
      titel: String(jahr),
      zeitraum: { von: `${jahr}-01-01`, bis: `${jahr}-12-31` },
      gruppe: 'Jahre',
    })
  }
  return liste
}

export function passendeVorgabe(z: Zeitraum, heute: Date = new Date()): Vorgabe | null {
  return vorgaben(heute).find((v) => v.zeitraum.von === z.von && v.zeitraum.bis === z.bis) ?? null
}

const ISO_DATUM = /^\d{4}-\d{2}-\d{2}$/

export function useZeitraum(): [Zeitraum, (z: Zeitraum) => void] {
  const [suche, setzeSuche] = useSearchParams()
  const von = suche.get('von')
  const bis = suche.get('bis')
  const zeitraum: Zeitraum = {
    von: von && ISO_DATUM.test(von) ? von : null,
    bis: bis && ISO_DATUM.test(bis) ? bis : null,
  }
  function setze(z: Zeitraum): void {
    const naechste = new URLSearchParams(suche)
    if (z.von) naechste.set('von', z.von)
    else naechste.delete('von')
    if (z.bis) naechste.set('bis', z.bis)
    else naechste.delete('bis')
    // Ein neuer Zeitraum beginnt beim Blättern wieder vorn.
    naechste.delete('offset')
    setzeSuche(naechste)
  }
  return [zeitraum, setze]
}

// Für Verweise zwischen Ansichten: der Zeitraum wandert mit.
export function zeitraumSuche(z: Zeitraum): string {
  const s = new URLSearchParams()
  if (z.von) s.set('von', z.von)
  if (z.bis) s.set('bis', z.bis)
  const text = s.toString()
  return text === '' ? '' : `?${text}`
}
