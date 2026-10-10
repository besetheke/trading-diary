import { geldDe, vorzeichen } from './format'

// AP-08f1: ein Geldbetrag in deutscher Schreibweise, rot/grün nach
// Vorzeichen, der genaue Rohwert der API im title (Tooltip) — nichts geht
// verloren, nichts wird gerechnet.
export default function Betrag({
  wert,
  waehrung = 'EUR',
}: {
  wert: string | null
  waehrung?: string
}): JSX.Element {
  return (
    <span className={vorzeichen(wert)} title={wert ?? undefined}>
      {geldDe(wert, waehrung)}
    </span>
  )
}
