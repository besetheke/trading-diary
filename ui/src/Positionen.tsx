import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fehlerText, holeKetten } from './api'
import type { KettenListe } from './api'
import { zeit, aufZweiNachkommastellen } from './format'

const LIMITS = [10, 25, 50, 100]

// Werte aus dem Datenbankschema (CHECK instruments.asset_class) und aus dem
// Wiederhersteller (chains.endzustand) — die Oberfläche erfindet keine.
const ANLAGEKLASSEN = ['OPT', 'FOP', 'FUT', 'STK', 'CASH']
const ENDZUSTAENDE = ['Offen', 'Geschlossen', 'Verfall', 'Assigned']

interface Entwurf {
  basiswert: string
  anlageklasse: string
  endzustand: string
  minRolls: string
  maxRolls: string
}

function zahlOderVorgabe(wert: string | null, vorgabe: number): number {
  const geparst = Number.parseInt(wert ?? '', 10)
  return Number.isNaN(geparst) ? vorgabe : geparst
}

export default function Positionen(): JSX.Element {
  const [suche, setzeSuche] = useSearchParams()
  const basiswert = suche.get('basiswert') ?? ''
  const anlageklasse = suche.get('anlageklasse') ?? ''
  const endzustand = suche.get('endzustand') ?? ''
  const minRolls = suche.get('min_rolls') ?? ''
  const maxRolls = suche.get('max_rolls') ?? ''
  const limit = Math.min(Math.max(zahlOderVorgabe(suche.get('limit'), 25), 1), 500)
  const offset = Math.max(zahlOderVorgabe(suche.get('offset'), 0), 0)

  const [entwurf, setzeEntwurf] = useState<Entwurf>({
    basiswert,
    anlageklasse,
    endzustand,
    minRolls,
    maxRolls,
  })
  const [liste, setzeListe] = useState<KettenListe | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    setzeListe(null)
    setzeFehler(null)
    const min = Number.parseInt(minRolls, 10)
    const max = Number.parseInt(maxRolls, 10)
    holeKetten({
      basiswert: basiswert || undefined,
      anlageklasse: anlageklasse || undefined,
      endzustand: endzustand || undefined,
      min_rolls: Number.isNaN(min) ? undefined : min,
      max_rolls: Number.isNaN(max) ? undefined : max,
      limit,
      offset,
    })
      .then((ergebnis) => {
        if (!abgebrochen) setzeListe(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [basiswert, anlageklasse, endzustand, minRolls, maxRolls, limit, offset])

  function anwenden(ereignis: FormEvent): void {
    ereignis.preventDefault()
    const naechste = new URLSearchParams()
    const basis = entwurf.basiswert.trim()
    const min = Number.parseInt(entwurf.minRolls, 10)
    const max = Number.parseInt(entwurf.maxRolls, 10)
    if (basis) naechste.set('basiswert', basis)
    if (entwurf.anlageklasse) naechste.set('anlageklasse', entwurf.anlageklasse)
    if (entwurf.endzustand) naechste.set('endzustand', entwurf.endzustand)
    if (!Number.isNaN(min) && min >= 0) naechste.set('min_rolls', String(min))
    if (!Number.isNaN(max) && max >= 0) naechste.set('max_rolls', String(max))
    setzeSuche(naechste) // limit und offset fallen auf die Vorgabe zurück
  }

  function zuruecksetzen(): void {
    setzeEntwurf({
      basiswert: '',
      anlageklasse: '',
      endzustand: '',
      minRolls: '',
      maxRolls: '',
    })
    setzeSuche(new URLSearchParams())
  }

  function blaettern(schritt: number): void {
    const naechste = new URLSearchParams(suche)
    naechste.set('limit', String(limit))
    naechste.set('offset', String(Math.max(offset + schritt, 0)))
    setzeSuche(naechste)
  }

  function jeSeite(wert: string): void {
    const naechste = new URLSearchParams(suche)
    naechste.set('limit', wert)
    naechste.delete('offset')
    setzeSuche(naechste)
  }

  return (
    <section>
      <h2>Positionen</h2>
      <form className="filter" onSubmit={anwenden}>
        <label>
          Basiswert
          <input
            value={entwurf.basiswert}
            onChange={(e) => setzeEntwurf({ ...entwurf, basiswert: e.target.value })}
            placeholder="z. B. DAX"
          />
        </label>
        <label>
          Anlageklasse
          <select
            value={entwurf.anlageklasse}
            onChange={(e) => setzeEntwurf({ ...entwurf, anlageklasse: e.target.value })}
          >
            <option value="">alle</option>
            {ANLAGEKLASSEN.map((klasse) => (
              <option key={klasse} value={klasse}>
                {klasse}
              </option>
            ))}
          </select>
        </label>
        <label>
          Rolls von
          <input
            type="number"
            min={0}
            value={entwurf.minRolls}
            onChange={(e) => setzeEntwurf({ ...entwurf, minRolls: e.target.value })}
          />
        </label>
        <label>
          bis
          <input
            type="number"
            min={0}
            value={entwurf.maxRolls}
            onChange={(e) => setzeEntwurf({ ...entwurf, maxRolls: e.target.value })}
          />
        </label>
        <label>
          Endzustand
          <select
            value={entwurf.endzustand}
            onChange={(e) => setzeEntwurf({ ...entwurf, endzustand: e.target.value })}
          >
            <option value="">alle</option>
            {ENDZUSTAENDE.map((zustand) => (
              <option key={zustand} value={zustand}>
                {zustand}
              </option>
            ))}
          </select>
        </label>
        <button type="submit">Anwenden</button>
        <button type="button" onClick={zuruecksetzen}>
          Zurücksetzen
        </button>
      </form>

      {fehler ? (
        <section className="fehler">
          <h3>Die Liste konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      ) : liste === null ? (
        <p className="laedt">Lade Positionen …</p>
      ) : liste.gesamt === 0 ? (
        <section className="hinweis">
          <p>Keine Positionen für diese Filter.</p>
          <p>Filter zurücksetzen oder andere Werte versuchen.</p>
        </section>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Basiswert</th>
                <th>Klasse</th>
                <th>Seite</th>
                <th>Eröffnung</th>
                <th>Ende</th>
                <th className="zahl">Rolls</th>
                <th>Endzustand</th>
                <th className="zahl">Preis auf</th>
                <th className="zahl">Preis zu</th>
                <th className="zahl">Ergebnis netto¹</th>
                <th>Währung</th>
              </tr>
            </thead>
            <tbody>
              {liste.treffer.map((kette) => {
                // AP-08lk, Punkt 2 (vom Nutzer freigegeben): Die Liste zeigt
                // zwei Nachkommastellen — reine Zeichenarbeit (Vertrag 8),
                // der vollständige Wert steht im title der Zelle. Die
                // Detailansicht bleibt unverändert genau. AP-08fp, Vertrag 4:
                // Dieselbe Kürzung gilt für die beiden Preisspalten.
                const netto = kette.struktur_summe_netto
                const kurz = netto === null ? null : aufZweiNachkommastellen(netto)
                const preisAuf = kette.eroeffnungspreis
                const preisAufKurz =
                  preisAuf === null ? null : aufZweiNachkommastellen(preisAuf)
                const preisZu = kette.schlusspreis
                const preisZuKurz = preisZu === null ? null : aufZweiNachkommastellen(preisZu)
                return (
                  <tr key={kette.chain_id}>
                    <td>
                      <Link to={`/positionen/${kette.chain_id}`}>{kette.underlying}</Link>
                    </td>
                    <td>{kette.asset_class}</td>
                    <td>{kette.seite ?? '—'}</td>
                    <td>{zeit(kette.eroeffnet_am)}</td>
                    <td>{kette.beendet_am ? zeit(kette.beendet_am) : '—'}</td>
                    <td className="zahl">{kette.anzahl_rolls}</td>
                    <td>{kette.endzustand ?? '—'}</td>
                    <td
                      className="zahl"
                      title={
                        preisAuf !== null && preisAufKurz !== preisAuf ? preisAuf : undefined
                      }
                    >
                      {preisAufKurz ?? '—'}
                    </td>
                    <td
                      className="zahl"
                      title={preisZu !== null && preisZuKurz !== preisZu ? preisZu : undefined}
                    >
                      {preisZuKurz ?? '—'}
                    </td>
                    <td className="zahl" title={netto !== null && kurz !== netto ? netto : undefined}>
                      {kurz ?? '—'}
                    </td>
                    <td>
                      {kette.waehrung ?? (
                        <span title="Kette enthält mehrere Währungen — keine Summe möglich">
                          {kette.waehrungen.join(' / ')}
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <footer className="blaettern">
            <button type="button" disabled={offset === 0} onClick={() => blaettern(-limit)}>
              Zurück
            </button>
            <p>
              Treffer {offset + 1}–{Math.min(offset + limit, liste.gesamt)} von{' '}
              {liste.gesamt}
            </p>
            <button
              type="button"
              disabled={offset + limit >= liste.gesamt}
              onClick={() => blaettern(limit)}
            >
              Weiter
            </button>
            <label>
              je Seite
              <select value={String(limit)} onChange={(e) => jeSeite(e.target.value)}>
                {LIMITS.map((wert) => (
                  <option key={wert} value={wert}>
                    {wert}
                  </option>
                ))}
              </select>
            </label>
          </footer>
          <p className="sicht fussnote">
            ¹ Kontosicht, Summe der Strukturergebnisse — in der Liste auf zwei
            Nachkommastellen gekürzt; die Zellenüberschrift zeigt den vollen
            Wert. Keine Umrechnung, nichts gerechnet.
          </p>
        </>
      )}
    </section>
  )
}
