// Darstellungshilfen — rein textlich: Zeiten und Geldbeträge bleiben
// Zeichenketten und werden nur geschnitten oder ergänzt, nie umgerechnet
// oder durch Zahlen geschickt (AP-08l, Vertrag 8 und 9).

export function zeit(iso: string | null): string {
  return iso ? iso.replace('T', ' ') : '—'
}

// AP-08s: Datum und Uhrzeit in einer Zeile, ohne Sekunden (JJJJ-MM-TT HH:MM)
// — nur geschnitten, nie umgerechnet; die volle Zeit bleibt im title.
export function zeitKurz(iso: string | null): string {
  return iso ? iso.replace('T', ' ').slice(0, 16) : '—'
}

export function datum(iso: string | null): string {
  return iso ? iso.slice(0, 10) : '—'
}

export function geld(wert: string | null, waehrung: string): string {
  return wert === null ? '—' : `${wert} ${waehrung}`
}

// AP-08lk, Punkt 2: Anzeige auf zwei Nachkommastellen — ausschließlich
// Zeichenarbeit am Text (Vertrag 8). Kein parseFloat, kein Number(), kein
// toFixed: alle drei schicken den Betrag durch eine Gleitkommazahl und
// hoben genau den Schutz auf, den die API aufbaut. Der vollständige Wert
// bleibt im title der Zelle sichtbar.
export function aufZweiNachkommastellen(wert: string): string {
  // Fremde Schreibweisen (Exponent) bleiben unangetastet stehen.
  if (wert.includes('e') || wert.includes('E')) return wert
  const punkt = wert.lastIndexOf('.')
  if (punkt === -1 || wert.length - punkt - 1 <= 2) return wert
  if (wert[punkt + 3] < '5') {
    // Die dritte Nachkommastelle rundet nicht auf — abschneiden genügt.
    return wert.slice(0, punkt + 3)
  }
  // Kaufmännisch runden, von Hand: die zweite Stelle im Text um eins
  // erhöhen, Übertrag Ziffer für Ziffer nach links weiterreichen.
  const ziffern = wert.slice(0, punkt + 3).split('')
  for (let i = ziffern.length - 1; i >= 0; i--) {
    const ziffer = ziffern[i]
    if (ziffer === '.' || ziffer === '-') continue
    if (ziffer === '9') {
      ziffern[i] = '0'
      continue
    }
    ziffern[i] = String.fromCharCode(ziffer.charCodeAt(0) + 1)
    return ziffern.join('')
  }
  // Alle Ziffern waren neun (etwa -9.999 → -10.00): Eins voranstellen.
  const vorzeichen = ziffern[0] === '-' ? '-' : ''
  const rest = vorzeichen ? ziffern.slice(1).join('') : ziffern.join('')
  return `${vorzeichen}1${rest}`
}

// AP-08f1: Deutsche Schreibweise für Beträge — Tausenderpunkt, Dezimalkomma,
// genau zwei Nachkommastellen, typografisches Minus. Wie oben reine
// Zeichenarbeit: kein Number(), kein parseFloat. Der Rohwert gehört in den
// title des Elements, damit nichts verloren geht.
function istNull(wert: string): boolean {
  return /^-?0*(\.0*)?$/.test(wert)
}

export function betrag(wert: string | null): string {
  if (wert === null) return '—'
  if (wert.includes('e') || wert.includes('E')) return wert
  const gerundet = aufZweiNachkommastellen(wert)
  const negativ = gerundet.startsWith('-') && !istNull(gerundet)
  const ohne = gerundet.startsWith('-') ? gerundet.slice(1) : gerundet
  const [ganz, nach = ''] = ohne.split('.')
  const ganzMitPunkten = (ganz === '' ? '0' : ganz).replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `${negativ ? '−' : ''}${ganzMitPunkten},${(nach + '00').slice(0, 2)}`
}

export function geldDe(wert: string | null, waehrung: string = 'EUR'): string {
  if (wert === null) return '—'
  return `${betrag(wert)} ${waehrung === 'EUR' ? '€' : waehrung}`
}

// CSS-Klasse für rot/grün — leer bei null und bei allem, was in der Anzeige
// als 0,00 erscheint (sonst stünde eine rote Null da).
export function vorzeichen(wert: string | null): string {
  if (wert === null || wert.includes('e') || wert.includes('E')) return ''
  const gerundet = aufZweiNachkommastellen(wert)
  if (istNull(gerundet)) return ''
  return gerundet.startsWith('-') ? 'negativ' : 'positiv'
}

// JJJJ-MM-TT (auch mit Uhrzeit dahinter) → TT.MM.JJJJ.
export function datumDe(iso: string | null): string {
  if (!iso) return '—'
  const [j, m, t] = iso.slice(0, 10).split('-')
  return `${t}.${m}.${j}`
}

// Quote der API (z. B. "0.5000") als Prozent mit zwei Stellen: "50,00 %".
// Komma um zwei Stellen verschieben — Zeichenarbeit, keine Multiplikation.
export function prozent(wert: string | null): string {
  if (wert === null) return '—'
  const negativ = wert.startsWith('-')
  const ohne = negativ ? wert.slice(1) : wert
  const [ganz, nach = ''] = ohne.split('.')
  const aufgefuellt = `${nach}00`
  const verschoben = `${ganz}${aufgefuellt.slice(0, 2)}.${aufgefuellt.slice(2) || '0'}`
  const ohneNullen = verschoben.replace(/^0+(?=\d)/, '')
  return `${betrag((negativ ? '-' : '') + ohneNullen)} %`
}

// AP-08f1: Datum mit Uhrzeit in deutscher Schreibweise (TT.MM.JJJJ HH:MM) —
// datumDe für den Tag, dahinter die Stunde aus dem ISO-Text geschnitten. Die
// volle Zeit (mit Sekunden) bleibt im title des Elements. Ohne Uhrzeit
// (reines Datum) bleibt es beim Datum.
export function zeitDe(iso: string | null): string {
  if (!iso) return '—'
  return iso.includes('T') ? `${datumDe(iso)} ${iso.slice(11, 16)}` : datumDe(iso)
}

