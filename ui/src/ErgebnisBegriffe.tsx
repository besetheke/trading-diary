import { useEffect, useState } from 'react'
import { holeDepot } from './api'
import { datumDe } from './format'
import { useZeitraum } from './zeitraum'

// M06: Einheitliche Begriffe für Ergebnisse in allen Ansichten (Dashboard, Positionen, Titel, Strategien, Kampagnen) und
// der ausdrücklich bezeichnete Bewertungsstichtag. Erste Stufe: Ist für den gewählten Endtag keine historische Bewertung
// verfügbar (Unrealisiertes gilt nur zum Stichtag des letzten Bestands), steht das deutlich da — nie ein stilles Weglassen.

export default function ErgebnisBegriffe(): JSX.Element {
  const [zeitraum] = useZeitraum()
  const [stichtag, setzeStichtag] = useState<string | null | undefined>(undefined)
  useEffect(() => {
    holeDepot().then((d) => setzeStichtag(d.stichtag)).catch(() => setzeStichtag(null))
  }, [])
  const historisch = Boolean(zeitraum.bis && stichtag && zeitraum.bis < stichtag)
  return (
    <details className="begriffe">
      <summary>
        Ergebnisbegriffe · Bewertungsstichtag {stichtag === undefined ? '…' : stichtag ? datumDe(stichtag) : 'unbekannt'}
        {historisch ? ' · ⚠ für den gewählten Endtag keine historische Bewertung' : ''}
      </summary>
      {historisch && (
        <p className="warnung">
          Der gewählte Zeitraum endet am {datumDe(zeitraum.bis)}, der Bestand zur Bewertung stammt vom {datumDe(stichtag ?? null)}.
          Das <strong>Realisierte</strong> gilt für den gewählten Zeitraum; <strong>Unrealisiertes</strong> ist für einen früheren Endtag
          nicht verfügbar (es gibt keine Rekonstruktion des damaligen Depots) und wird dort nicht angezeigt.
        </p>
      )}
      <ul className="liste-ohne-punkt">
        <li><strong>Realisiert:</strong> Ergebnis geschlossener Beine am Tag ihrer Schließung, in EUR zum Kurs der jeweiligen Seite,
          nach Kommission. Gilt für den gewählten Zeitraum.</li>
        <li><strong>Teilrealisiert:</strong> bereits geschlossene Beine einer noch offenen Struktur oder Kette. Ihr Ergebnis zählt als
          realisiert, die Struktur ist aber nicht abgeschlossen (Titelseite: Spalte „Teil-realisiert“).</li>
        <li><strong>Unrealisiert:</strong> offene Beine gegen den Bestand laut IB zum Bewertungsstichtag (Kurs gegen IB-Einstand bzw. gegen
          den tatsächlichen Einkaufspreis, beides ausgewiesen). Gilt nur zum Stichtag, nicht rückwirkend.</li>
        <li><strong>Gesamt:</strong> Realisiert plus Unrealisiert; Dividenden, Zinsen und Gebühren stehen getrennt.</li>
      </ul>
    </details>
  )
}
