import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { fehlerText, holeTag } from './api'
import type { TagesKette, Tagesuebersicht } from './api'
import { geld, zeit } from './format'
import Journal from './Journal'

// AP-08j, Punkt 4: Die Tagesansicht. Alles Fachliche kommt fertig aus der
// API (AP-07t): vier Listen in gelieferter Reihenfolge, Beträge unverändert
// als Zeichenkette — hier wird nichts gerechnet, summiert oder umgerechnet.

const DATUM_MUSTER = /^\d{4}-\d{2}-\d{2}$/

// Nur ein Kalenderdatum prüfen — keine Zeitzonen: die Stückelung läuft über
// UTC, toISOString würde je lokaler Zone einen Tag verlieren.
export function istGueltigesDatum(datum: string): boolean {
  if (!DATUM_MUSTER.test(datum)) return false
  const [jahr, monat, tag] = datum.split('-').map(Number)
  const stueck = new Date(Date.UTC(jahr, monat - 1, tag))
  return (
    stueck.getUTCFullYear() === jahr &&
    stueck.getUTCMonth() === monat - 1 &&
    stueck.getUTCDate() === tag
  )
}

export function tagVerschoben(datum: string, tage: number): string {
  const [jahr, monat, tag] = datum.split('-').map(Number)
  const stueck = new Date(Date.UTC(jahr, monat - 1, tag + tage))
  const monatText = String(stueck.getUTCMonth() + 1).padStart(2, '0')
  const tagText = String(stueck.getUTCDate()).padStart(2, '0')
  return `${stueck.getUTCFullYear()}-${monatText}-${tagText}`
}

// Eröffnete und beendete Ketten zeigen dieselben Spalten; nur die Zeitspalte
// heißt anders. Der Naturschlüssel steht im Hinweis des Verweises.
function KettenTabelle({
  zeilen,
  spalte,
}: {
  zeilen: TagesKette[]
  spalte: 'eroeffnet_am' | 'beendet_am'
}): JSX.Element {
  return (
    <table>
      <thead>
        <tr>
          <th>{spalte === 'eroeffnet_am' ? 'Eröffnet' : 'Beendet'}</th>
          <th>Kette</th>
          <th>Klasse</th>
          <th>Seite</th>
          <th className="zahl">Rolls</th>
          <th>Endzustand</th>
        </tr>
      </thead>
      <tbody>
        {zeilen.map((kette) => (
          <tr key={kette.chain_id}>
            <td>{zeit(kette[spalte])}</td>
            <td>
              <Link to={`/positionen/${kette.chain_id}`} title={kette.natur_schluessel}>
                {kette.underlying} · Kette {kette.chain_id}
              </Link>
            </td>
            <td>{kette.asset_class}</td>
            <td>{kette.seite ?? '—'}</td>
            <td className="zahl">{kette.anzahl_rolls}</td>
            <td>{kette.endzustand ?? '—'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function Tag(): JSX.Element {
  const { datum: datumText } = useParams()
  const navigate = useNavigate()
  const gueltig = datumText !== undefined && istGueltigesDatum(datumText)
  const [uebersicht, setzeUebersicht] = useState<Tagesuebersicht | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    if (!gueltig || datumText === undefined) return
    let abgebrochen = false
    setzeUebersicht(null)
    setzeFehler(null)
    holeTag(datumText)
      .then((ergebnis) => {
        if (!abgebrochen) setzeUebersicht(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [gueltig, datumText])

  if (!gueltig || datumText === undefined) {
    return (
      <section className="hinweis">
        <p>Diese Adresse nennt kein Datum der Form JJJJ-MM-TT.</p>
        <p>
          <Link to="/monat">Zum Kalender</Link>
        </p>
      </section>
    )
  }

  return (
    <section>
      <nav className="zurueck">
        <Link to="/monat">← Zum Kalender</Link>
      </nav>
      <h2>Handelstag {datumText}</h2>
      <p className="sicht">Kontosicht — Beträge unverändert, wie die API sie liefert.</p>
      <nav className="tageswahl">
        <button type="button" onClick={() => navigate(`/tag/${tagVerschoben(datumText, -1)}`)}>
          ← Vortag
        </button>
        <button type="button" onClick={() => navigate(`/tag/${tagVerschoben(datumText, 1)}`)}>
          Folgetag →
        </button>
      </nav>

      {fehler && (
        <section className="fehler">
          <h3>Der Handelstag konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      )}
      {uebersicht === null && fehler === null && <p className="laedt">Lade Handelstag …</p>}

      {uebersicht !== null && (
        <>
          <h3>Eröffnete Ketten ({uebersicht.eroeffnet.length})</h3>
          {uebersicht.eroeffnet.length === 0 ? (
            <p className="leer">An diesem Tag wurde keine Kette eröffnet.</p>
          ) : (
            <KettenTabelle zeilen={uebersicht.eroeffnet} spalte="eroeffnet_am" />
          )}

          <h3>Beendete Ketten ({uebersicht.beendet.length})</h3>
          {uebersicht.beendet.length === 0 ? (
            <p className="leer">An diesem Tag wurde keine Kette beendet.</p>
          ) : (
            <KettenTabelle zeilen={uebersicht.beendet} spalte="beendet_am" />
          )}

          <h3>Rolls ({uebersicht.rolls.length})</h3>
          {uebersicht.rolls.length === 0 ? (
            <p className="leer">An diesem Tag wurde kein Roll eröffnet.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Eröffnet</th>
                  <th>Kette</th>
                  <th>Basiswert</th>
                  <th className="zahl">Glied</th>
                </tr>
              </thead>
              <tbody>
                {uebersicht.rolls.map((roll) => (
                  <tr key={`${roll.chain_id}-${roll.structure_id}`}>
                    <td>{zeit(roll.eroeffnet_am)}</td>
                    <td>
                      <Link to={`/positionen/${roll.chain_id}`}>Kette {roll.chain_id}</Link>
                    </td>
                    <td>{roll.underlying}</td>
                    <td className="zahl">{roll.sequenz}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Realisiert ({uebersicht.realisiert.length})</h3>
          {uebersicht.realisiert.length === 0 ? (
            <p className="leer">An diesem Tag wurde keine Struktur geschlossen.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Währung</th>
                  <th className="zahl">Strukturen</th>
                  <th className="zahl">Brutto</th>
                  <th className="zahl">Kommission</th>
                  <th className="zahl">Netto</th>
                </tr>
              </thead>
              <tbody>
                {uebersicht.realisiert.map((posten) => (
                  <tr key={posten.waehrung}>
                    <td>{posten.waehrung}</td>
                    <td className="zahl">{posten.anzahl_strukturen}</td>
                    <td className="zahl">{geld(posten.brutto, posten.waehrung)}</td>
                    <td className="zahl">{geld(posten.kommission, posten.waehrung)}</td>
                    <td className="zahl">{geld(posten.netto, posten.waehrung)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <Journal scopeTyp="tag" scopeId={datumText} />
        </>
      )}
    </section>
  )
}
