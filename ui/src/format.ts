// Darstellungshilfen — rein textlich: Zeiten und Geldbeträge bleiben
// Zeichenketten und werden nur geschnitten oder ergänzt, nie umgerechnet
// oder durch Zahlen geschickt (AP-08l, Vertrag 8 und 9).

export function zeit(iso: string | null): string {
  return iso ? iso.replace('T', ' ') : '—'
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

