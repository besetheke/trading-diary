import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeKalender } from './api'
import type { Kalendertag, Monatskalender } from './api'
import Betrag from './Betrag'
import { datumDe, vorzeichen } from './format'

// AP-08j, Punkt 5: Der Monatskalender. Die Tage und Werte kommen fertig aus
// der API (AP-07t) — nur Tage mit Ereignissen, aufsteigend; hier wird nichts
// gerechnet oder umgerechnet, Netto steht immer mit Währung dabei.

function monatHeute(): string {
  const jetzt = new Date()
  return `${jetzt.getFullYear()}-${String(jetzt.getMonth() + 1).padStart(2, '0')}`
}

function heuteDatum(): string {
  const jetzt = new Date()
  return `${monatHeute()}-${String(jetzt.getDate()).padStart(2, '0')}`
}

// Monatsweise blättern über UTC-Stückelung — reine Datumsangabe, kein Geld.
function monatVerschoben(monat: string, schritt: number): string {
  const [jahr, monatNummer] = monat.split('-').map(Number)
  const stueck = new Date(Date.UTC(jahr, monatNummer - 1 + schritt, 1))
  return `${stueck.getUTCFullYear()}-${String(stueck.getUTCMonth() + 1).padStart(2, '0')}`
}

function kalenderWochen(monat: string): (string | null)[][] {
  const [jahr, monatNummer] = monat.split('-').map(Number)
  const erster = new Date(Date.UTC(jahr, monatNummer - 1, 1))
  const tage = new Date(Date.UTC(jahr, monatNummer, 0)).getUTCDate()
  const zellen: (string | null)[] = Array((erster.getUTCDay() + 6) % 7).fill(null)
  for (let tag = 1; tag <= tage; tag += 1) {
    zellen.push(`${jahr}-${String(monatNummer).padStart(2, '0')}-${String(tag).padStart(2, '0')}`)
  }
  while (zellen.length % 7 !== 0) zellen.push(null)
  return Array.from({ length: zellen.length / 7 }, (_, i) => zellen.slice(i * 7, i * 7 + 7))
}

function Tageszelle({ datum, tag }: { datum: string | null; tag?: Kalendertag }): JSX.Element {
  if (datum === null) return <td className="leer" aria-hidden="true" />
  const wochentag = new Date(`${datum}T00:00:00Z`).getUTCDay()
  const richtungen = Array.from(new Set(tag?.realisiert.map((posten) => vorzeichen(posten.netto)).filter(Boolean) ?? []))
  const richtung = richtungen.length === 1 ? richtungen[0] : richtungen.length > 1 ? 'gemischt' : ''
  const klassen = [wochentag === 0 || wochentag === 6 ? 'wochenende' : '', richtung, datum === heuteDatum() ? 'heute' : '']
    .filter(Boolean)
    .join(' ')
  return (
    <td className={klassen}>
      <div className="kalender-tagnummer">
        {tag ? <Link to={`/tag/${datum}`}>{Number(datum.slice(-2))}</Link> : Number(datum.slice(-2))}
      </div>
      {tag && (
        <>
          <div className="kalender-ereignisse" aria-label={`${tag.eroeffnet} eröffnet, ${tag.beendet} beendet, ${tag.rolls} Rolls`}>
            {tag.eroeffnet > 0 && <span title="Eröffnet">E {tag.eroeffnet}</span>}
            {tag.beendet > 0 && <span title="Beendet">B {tag.beendet}</span>}
            {tag.rolls > 0 && <span title="Rolls">R {tag.rolls}</span>}
          </div>
          <div className="kalender-wert realisiert">
            {tag.realisiert.map((posten) => (
              <span key={posten.waehrung} title={`Kontosicht — ${posten.sicht}`}>
                <Betrag wert={posten.netto} waehrung={posten.waehrung} />
              </span>
            ))}
          </div>
        </>
      )}
    </td>
  )
}

function Monatsraster({ daten }: { daten: Monatskalender }): JSX.Element {
  const jeTag = new Map(daten.tage.map((tag) => [tag.datum, tag]))
  return (
    <div className="kalender-scroll">
      <table className="monatskalender" aria-label={`Monatskalender ${daten.monat}`}>
        <thead><tr>{['Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So'].map((tag) => <th key={tag}>{tag}</th>)}</tr></thead>
        <tbody>
          {kalenderWochen(daten.monat).map((woche, i) => (
            <tr key={woche.find((datum) => datum !== null) ?? i}>
              {woche.map((datum, j) => <Tageszelle key={datum ?? `leer-${j}`} datum={datum} tag={datum ? jeTag.get(datum) : undefined} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Monatstabelle({ daten }: { daten: Monatskalender }): JSX.Element {
  if (daten.tage.length === 0) return <p className="leer">Im {daten.monat} gab es keine Ereignisse.</p>
  return (
    <div className="tabelle-rahmen">
      <table>
        <thead>
          <tr><th>Datum</th><th className="zahl">Eröffnet</th><th className="zahl">Beendet</th><th className="zahl">Rolls</th><th className="zahl">Realisiert netto</th></tr>
        </thead>
        <tbody>
          {daten.tage.map((tag) => (
            <tr key={tag.datum}>
              <td><Link to={`/tag/${tag.datum}`}>{datumDe(tag.datum)}</Link></td>
              <td className="zahl">{tag.eroeffnet}</td>
              <td className="zahl">{tag.beendet}</td>
              <td className="zahl">{tag.rolls}</td>
              <td className="zahl realisiert">
                {tag.realisiert.length === 0 ? '—' : tag.realisiert.map((posten) => (
                  <span key={posten.waehrung} title={`Kontosicht — ${posten.sicht}`}>
                    <Betrag wert={posten.netto} waehrung={posten.waehrung} />
                  </span>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function Kalender(): JSX.Element {
  const [monat, setzeMonat] = useState(monatHeute)
  const [kalender, setzeKalender] = useState<Monatskalender | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [ansicht, setzeAnsicht] = useState<'raster' | 'tabelle'>('raster')

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
        <button type="button" onClick={() => setzeMonat(monatVerschoben(monat, -1))}>← Vorheriger Monat</button>
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
        <button type="button" onClick={() => setzeMonat(monatVerschoben(monat, 1))}>Nächster Monat →</button>
        <button type="button" onClick={() => setzeMonat(monatHeute())}>Aktueller Monat</button>
      </nav>
      <div className="diagramm-wahl" role="group" aria-label="Kalenderdarstellung">
        <button type="button" aria-pressed={ansicht === 'raster'} onClick={() => setzeAnsicht('raster')}>Monatsraster</button>
        <button type="button" aria-pressed={ansicht === 'tabelle'} onClick={() => setzeAnsicht('tabelle')}>Tabelle</button>
      </div>

      {fehler && (
        <section className="fehler">
          <h3>Der Kalender konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      )}
      {kalender === null && fehler === null && <p className="laedt">Lade Kalender …</p>}

      {kalender !== null && (
        <>
          {ansicht === 'raster' ? (
            <>
              <p className="sicht kalender-legende">E = eröffnet · B = beendet · R = Rolls · ein Tag mit Ereignissen führt zur Tagesansicht.</p>
              {kalender.tage.length === 0 && <p className="leer">Im {kalender.monat} gab es keine Ereignisse.</p>}
              <Monatsraster daten={kalender} />
            </>
          ) : <Monatstabelle daten={kalender} />}
        </>
      )}
    </section>
  )
}
