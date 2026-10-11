import { useMemo, useState } from 'react'
import { ERSTES_JAHR, iso } from './zeitraum'
import type { Zeitraum } from './zeitraum'

// Zeitraum-Kalender: Monatsansicht, erster Klick = Start, zweiter Klick =
// Ende (liegt er vor dem Start, werden beide getauscht). Ein zweimaliger
// Klick auf denselben Tag wählt diesen einen Tag. Alle Daten sind lokale
// ISO-Strings (JJJJ-MM-TT) — kein toISOString, das je nach Zeitzone auf den
// Vortag rutscht. Es wird nichts gerechnet außer dem Datumsgitter.

const MONATE = [
  'Januar',
  'Februar',
  'März',
  'April',
  'Mai',
  'Juni',
  'Juli',
  'August',
  'September',
  'Oktober',
  'November',
  'Dezember',
]
const WOCHENTAGE = ['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So']

interface Eigenschaften {
  zeitraum: Zeitraum
  waehle: (zeitraum: Zeitraum) => void
}

function ersterAnzeigeMonat(zeitraum: Zeitraum): { jahr: number; monat: number } {
  const quelle = zeitraum.bis ?? zeitraum.von ?? iso(new Date())
  return { jahr: Number(quelle.slice(0, 4)), monat: Number(quelle.slice(5, 7)) - 1 }
}

export default function Kalenderwahl({ zeitraum, waehle }: Eigenschaften): JSX.Element {
  const [ansicht, setzeAnsicht] = useState(() => ersterAnzeigeMonat(zeitraum))
  // Nach dem ersten Klick steht der Start hier, bis der zweite Klick kommt.
  const [anker, setzeAnker] = useState<string | null>(null)
  const [schwebe, setzeSchwebe] = useState<string | null>(null)

  const heute = iso(new Date())
  const letztesJahr = new Date().getFullYear() + 1

  const tage = useMemo(() => {
    const erster = new Date(ansicht.jahr, ansicht.monat, 1)
    const versatz = (erster.getDay() + 6) % 7 // Montag = 0
    const anzahl = new Date(ansicht.jahr, ansicht.monat + 1, 0).getDate()
    const zellen: (string | null)[] = Array.from({ length: versatz }, () => null)
    for (let t = 1; t <= anzahl; t++) zellen.push(iso(new Date(ansicht.jahr, ansicht.monat, t)))
    return zellen
  }, [ansicht.jahr, ansicht.monat])

  // Was gerade markiert ist: die Vorschau zwischen Anker und Mauszeiger, sonst
  // der gewählte Zeitraum.
  let markVon = zeitraum.von
  let markBis = zeitraum.bis
  if (anker !== null) {
    const ende = schwebe ?? anker
    markVon = anker < ende ? anker : ende
    markBis = anker < ende ? ende : anker
  }

  function blaettere(schritt: number): void {
    const d = new Date(ansicht.jahr, ansicht.monat + schritt, 1)
    setzeAnsicht({ jahr: d.getFullYear(), monat: d.getMonth() })
  }

  function klick(tag: string): void {
    if (anker === null) {
      setzeAnker(tag)
      setzeSchwebe(null)
      return
    }
    const von = tag < anker ? tag : anker
    const bis = tag < anker ? anker : tag
    setzeAnker(null)
    setzeSchwebe(null)
    waehle({ von, bis })
  }

  const jahre: number[] = []
  for (let j = ERSTES_JAHR; j <= letztesJahr; j++) jahre.push(j)

  return (
    <div className="kalenderwahl">
      <div className="kopfzeile">
        <button type="button" aria-label="Voriger Monat" onClick={() => blaettere(-1)}>
          ‹
        </button>
        <select
          aria-label="Monat"
          value={ansicht.monat}
          onChange={(e) => setzeAnsicht({ ...ansicht, monat: Number(e.target.value) })}
        >
          {MONATE.map((name, i) => (
            <option key={name} value={i}>
              {name}
            </option>
          ))}
        </select>
        <select
          aria-label="Jahr"
          value={ansicht.jahr}
          onChange={(e) => setzeAnsicht({ ...ansicht, jahr: Number(e.target.value) })}
        >
          {jahre.map((j) => (
            <option key={j} value={j}>
              {j}
            </option>
          ))}
        </select>
        <button type="button" aria-label="Nächster Monat" onClick={() => blaettere(1)}>
          ›
        </button>
      </div>

      <div className="raster" role="grid" onMouseLeave={() => setzeSchwebe(null)}>
        {WOCHENTAGE.map((name) => (
          <span key={name} className="wochentag">
            {name}
          </span>
        ))}
        {tage.map((tag, i) => {
          if (tag === null) return <span key={`leer${i}`} />
          const imBereich = markVon !== null && markBis !== null && tag >= markVon && tag <= markBis
          const klassen = ['tag']
          if (imBereich) klassen.push('im-bereich')
          if (tag === markVon) klassen.push('start')
          if (tag === markBis) klassen.push('ende')
          if (tag === heute) klassen.push('heute')
          return (
            <button
              key={tag}
              type="button"
              className={klassen.join(' ')}
              aria-pressed={imBereich}
              onClick={() => klick(tag)}
              onMouseEnter={() => anker !== null && setzeSchwebe(tag)}
            >
              {Number(tag.slice(8))}
            </button>
          )
        })}
      </div>

      <p className="hinweis-klick">
        {anker === null
          ? 'Erster Klick: Start, zweiter Klick: Ende.'
          : 'Jetzt das Ende wählen (derselbe Tag wählt nur diesen Tag).'}
      </p>
    </div>
  )
}
