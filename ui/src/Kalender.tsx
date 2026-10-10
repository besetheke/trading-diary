import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeKalender } from './api'
import type { Monatskalender } from './api'
import Betrag from './Betrag'
import { datumDe } from './format'

// AP-08j, Punkt 5: Der Monatskalender. Die Tage und Werte kommen fertig aus
// der API (AP-07t) — nur Tage mit Ereignissen, aufsteigend; hier wird nichts
// gerechnet oder umgerechnet, Netto steht immer mit Währung dabei.

function monatHeute(): string {
  const jetzt = new Date()
  return `${jetzt.getFullYear()}-${String(jetzt.getMonth() + 1).padStart(2, '0')}`
}

// Monatsweise blättern über UTC-Stückelung — reine Datumsangabe, kein Geld.
function monatVerschoben(monat: string, schritt: number): string {
  const [jahr, monatNummer] = monat.split('-').map(Number)
  const stueck = new Date(Date.UTC(jahr, monatNummer - 1 + schritt, 1))
  return `${stueck.getUTCFullYear()}-${String(stueck.getUTCMonth() + 1).padStart(2, '0')}`
}

export default function Kalender(): JSX.Element {
  const [monat, setzeMonat] = useState(monatHeute)
  const [kalender, setzeKalender] = useState<Monatskalender | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    setzeKalender(null)
    setzeFehler(null)
    holeKalender(monat)
      .then((ergebnis) => {
        if (!abgebrochen) setzeKalender(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [monat])

  return (
    <section>
      <h2>Kalender {monat}</h2>
      <p className="sicht">Kontosicht — Beträge unverändert, wie die API sie liefert.</p>
      <nav className="monatswahl">
        <button type="button" onClick={() => setzeMonat(monatVerschoben(monat, -1))}>
          ← Vorheriger Monat
        </button>
        <label htmlFor="monatswahl">Monat</label>
        <input
          id="monatswahl"
          type="month"
          value={monat}
          onChange={(ereignis) => {
            // Leere Eingabe (Browser löscht das Feld) bleibt beim Monat.
            if (ereignis.target.value !== '') setzeMonat(ereignis.target.value)
          }}
        />
        <button type="button" onClick={() => setzeMonat(monatVerschoben(monat, 1))}>
          Nächster Monat →
        </button>
        <button type="button" onClick={() => setzeMonat(monatHeute())}>
          Aktueller Monat
        </button>
      </nav>

      {fehler && (
        <section className="fehler">
          <h3>Der Kalender konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      )}
      {kalender === null && fehler === null && <p className="laedt">Lade Kalender …</p>}

      {kalender !== null &&
        (kalender.tage.length === 0 ? (
          <p className="leer">Im {kalender.monat} gab es keine Ereignisse.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Datum</th>
                <th className="zahl">Eröffnet</th>
                <th className="zahl">Beendet</th>
                <th className="zahl">Rolls</th>
                <th className="zahl">Realisiert netto</th>
              </tr>
            </thead>
            <tbody>
              {kalender.tage.map((tag) => (
                <tr key={tag.datum}>
                  <td>
                    <Link to={`/tag/${tag.datum}`}>{datumDe(tag.datum)}</Link>
                  </td>
                  <td className="zahl">{tag.eroeffnet}</td>
                  <td className="zahl">{tag.beendet}</td>
                  <td className="zahl">{tag.rolls}</td>
                  <td className="zahl realisiert">
                    {tag.realisiert.length === 0
                      ? '—'
                      : tag.realisiert.map((posten) => (
                          <span key={posten.waehrung} title={`Kontosicht — ${posten.sicht}`}>
                            <Betrag wert={posten.netto} waehrung={posten.waehrung} />
                          </span>
                        ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
    </section>
  )
}