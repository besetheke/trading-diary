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
