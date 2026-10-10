// AP-08-kampagnen: bestätigte Kampagnen — nur Durchreichen der Tabellen,
// kein Rechnen. Offene (unbestätigte) Kandidaten der Dateirundreise erscheinen
// hier nicht; bestätigt wird über die CLI, nicht über diese Seite.

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fehlerText, holeKampagne, holeKampagnen } from './api'
import type { Kampagne, KampagnenDetail, KampagnenListe } from './api'
import { aufZweiNachkommastellen, zeitKurz } from './format'

interface Entwurf {
  basiswert: string
}

// Eine Zeile der Liste. Klick auf die Zeile klappt die verknüpften Ketten auf
// (Vertrag AP-08-kampagnen) — der Knopf am Ende tut dasselbe und bleibt für
// die Tastatur bedienbar. Das Detail wird erst beim ersten Aufklappen geholt.
function KampagnenZeile(props: {
  kampagne: Kampagne
  offen: boolean
  umschalten: () => void
}): JSX.Element {
  const { kampagne, offen, umschalten } = props
  const [detail, setzeDetail] = useState<KampagnenDetail | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    if (!offen || detail !== null) return
    let abgebrochen = false
    setzeFehler(null)
    holeKampagne(kampagne.campaign_id)
      .then((ergebnis) => {
        if (!abgebrochen) setzeDetail(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [offen, detail, kampagne.campaign_id])

  // Ergebnis wie in der Positionsliste: auf zwei Nachkommastellen gekürzt,
  // nur Zeichenarbeit — der volle Wert steht im title der Zelle.
  const voll = kampagne.netto_pnl_eur
  const kurz = voll === null ? null : aufZweiNachkommastellen(voll)

  return (
    <>
      <tr onClick={umschalten}>
        <td className="zeit">{zeitKurz(kampagne.eroeffnet_am)}</td>
        <td>{kampagne.underlying}</td>
        <td className="zeit">{zeitKurz(kampagne.beendet_am)}</td>
        <td className="zahl" title={voll !== null && kurz !== voll ? `${voll} EUR` : undefined}>
          {kurz === null ? '—' : `${kurz} EUR`}
        </td>
        <td className="zahl">{kampagne.anzahl_ketten}</td>
        <td>
          <button
            type="button"
            aria-expanded={offen}
            onClick={(e) => {
              e.stopPropagation()
              umschalten()
            }}
          >
            {offen ? 'ausblenden' : 'Ketten'}
          </button>
        </td>
      </tr>
      {offen ? (
        <tr className="kampagnendetail">
          <td colSpan={6}>
            {fehler !== null ? (
              <p className="meldung">{fehler}</p>
            ) : detail === null ? (
              <p className="laedt">Lade Ketten …</p>
            ) : (
              <table className="positionen kampagnenketten">
                <thead>
                  <tr>
                    <th>Kette</th>
                    <th>Beziehungstyp</th>
                    <th>Erkennung</th>
                    <th>Bestätigt am</th>
                    <th>Position</th>
                  </tr>
                </thead>
                <tbody>
                  {detail.ketten.map((kette) => (
                    <tr key={kette.chain_id}>
                      <td>{kette.natur_schluessel}</td>
                      <td>{kette.beziehungstyp}</td>
                      <td>{kette.erkennung}</td>
                      <td className="zeit">{zeitKurz(kette.bestaetigt_am)}</td>
                      <td>
                        <Link to={`/positionen/${kette.chain_id}`}>öffnen</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </td>
        </tr>
      ) : null}
    </>
  )
}

export default function Kampagnen(): JSX.Element {
  const [suche, setzeSuche] = useSearchParams()
  const basiswert = suche.get('basiswert') ?? ''

  const [entwurf, setzeEntwurf] = useState<Entwurf>({ basiswert })
  const [liste, setzeListe] = useState<KampagnenListe | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  // Nur eine Kampagne ist zugleich aufgeklappt; ein neuer Filter klappt zu.
  const [offen, setzeOffen] = useState<number | null>(null)

  useEffect(() => {
    let abgebrochen = false
    setzeListe(null)
    setzeFehler(null)
    setzeOffen(null)
    holeKampagnen(basiswert || undefined)
      .then((ergebnis) => {
        if (!abgebrochen) setzeListe(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [basiswert])

  function anwenden(ereignis: FormEvent): void {
    ereignis.preventDefault()
    const naechste = new URLSearchParams()
    const basis = entwurf.basiswert.trim()
    if (basis) naechste.set('basiswert', basis)
    setzeSuche(naechste)
  }

  function zuruecksetzen(): void {
    setzeEntwurf({ basiswert: '' })
    setzeSuche(new URLSearchParams())
  }

  return (
    <section>
      <h2>Kampagnen</h2>
      <p className="sicht fussnote">
        Nur bestätigte Kampagnen — offene Vorschläge der Dateirundreise erscheinen
        hier nicht. Beträge unverändert, wie die API sie liefert.
      </p>
      <form className="filter" onSubmit={anwenden}>
        <label>
          Basiswert
          <input
            value={entwurf.basiswert}
            onChange={(e) => setzeEntwurf({ ...entwurf, basiswert: e.target.value })}
            placeholder="z. B. ESTX50"
          />
        </label>
        <button type="submit">Anwenden</button>
        <button type="button" onClick={zuruecksetzen}>
          Zurücksetzen
        </button>
      </form>

      {fehler !== null ? (
        <section className="fehler">
          <h3>Die Liste konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      ) : liste === null ? (
        <p className="laedt">Lade Kampagnen …</p>
      ) : liste.gesamt === 0 ? (
        <section className="hinweis">
          <p>
            {basiswert
              ? `Keine bestätigte Kampagne für ${basiswert}.`
              : 'Noch keine bestätigte Kampagne.'}
          </p>
          {/* Die Seite ist nicht kaputt: Kandidaten entstehen außerhalb ihrer
              (Plan §6, Block B, Regel 2). Ohne den Befehl wirkt sie tot. */}
          <p>
            Kampagnen werden über die CLI-Rundreise bestätigt:{' '}
            <code>journal kampagnen-ausschreiben</code> schreibt die offenen
            Kandidaten aus, nach dem Urteil liest{' '}
            <code>journal kampagnen-einlesen</code> sie ein, und{' '}
            <code>journal rebuild</code> macht die Entscheidungen wirksam —
            erst danach erscheinen sie hier.
          </p>
        </section>
      ) : (
        <table className="positionen kampagnen">
          <thead>
            <tr>
              <th>Eröffnung</th>
              <th>Basiswert</th>
              <th>Ende</th>
              <th className="zahl">Ergebnis netto EUR</th>
              <th className="zahl">Ketten</th>
              <th scope="col">Details</th>
            </tr>
          </thead>
          <tbody>
            {liste.treffer.map((kampagne) => (
              <KampagnenZeile
                key={kampagne.campaign_id}
                kampagne={kampagne}
                offen={offen === kampagne.campaign_id}
                umschalten={() =>
                  setzeOffen(offen === kampagne.campaign_id ? null : kampagne.campaign_id)
                }
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
