import { useEffect, useRef, useState } from 'react'
import type { KeyboardEvent, PointerEvent } from 'react'

export function useDiagrammBreite(maximaleBreite: number): {
  ref: React.RefObject<HTMLElement>
  breite: number
} {
  const ref = useRef<HTMLElement>(null)
  const [breite, setzeBreite] = useState(maximaleBreite)

  useEffect(() => {
    const messen = (): void => {
      const gemessen = Math.round(ref.current?.getBoundingClientRect().width ?? 0)
      if (gemessen > 0) setzeBreite(Math.max(240, Math.min(maximaleBreite, gemessen)))
    }
    messen()
    window.addEventListener('resize', messen)
    return () => window.removeEventListener('resize', messen)
  }, [maximaleBreite])

  return { ref, breite }
}

export function zeigerX(ereignis: PointerEvent<SVGSVGElement>, breite: number): number {
  const rahmen = ereignis.currentTarget.getBoundingClientRect()
  return ((ereignis.clientX - rahmen.left) / rahmen.width) * breite
}

export function tastaturIndex(
  ereignis: KeyboardEvent<SVGSVGElement>,
  aktiv: number | null,
  anzahl: number,
): number | undefined {
  if (anzahl === 0) return undefined
  let index: number
  if (ereignis.key === 'Home') index = 0
  else if (ereignis.key === 'End') index = anzahl - 1
  else if (ereignis.key === 'ArrowLeft' || ereignis.key === 'ArrowDown') {
    index = Math.max(0, (aktiv ?? 0) - 1)
  } else if (ereignis.key === 'ArrowRight' || ereignis.key === 'ArrowUp') {
    index = Math.min(anzahl - 1, (aktiv ?? -1) + 1)
  } else return undefined
  ereignis.preventDefault()
  return index
}

export function DiagrammWert({ zeilen }: { zeilen: string[] }): JSX.Element | null {
  if (zeilen.length === 0) return null
  return (
    <p className="diagramm-wert" aria-live="polite">
      {zeilen.join(' · ')}
    </p>
  )
}
