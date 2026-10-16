import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeTitel } from './api'
import type { TitelAntwort, TitelZeile } from './api'
import Betrag from './Betrag'
import { datumDe } from './format'

// AP-16: Ergebnis je Titel über alle Instrumente. Eine Zeile je Basiswert — Optionen, Aktien und Futures
// zusammen —, im Unterschied zur Positionsliste (eine Zeile je Trade). Alles Werte der Quelle
// (GET /titel-auswertung, dieselbe Rechengrundlage wie die Auswertung der Positionsliste); im Browser
// wird nur sortiert und gefiltert.

type Spalte = 'basiswert' | 'ketten' | 'realisiert' | 'opt' | 'stk' | 'sonst' | 'unrealisiert' | 'gesamt'

function betragVon(z: TitelZeile, klasse: string): string {
  return z.je_klasse.find((k) => k.anlageklasse === klasse)?.realisiert_eur ?? '0'
}

function sonstige(z: TitelZeile): number {
  return z.je_klasse
    .filter((k) => k.anlageklasse !== 'OPT' && k.anlageklasse !== 'STK')
    .reduce((summe, k) => summe + Number(k.realisiert_eur), 0)
}

function wert(z: TitelZeile, spalte: Spalte): number | string {
  switch (spalte) {
    case 'basiswert': return z.basiswert
    case 'ketten': return z.ketten
    case 'realisiert': return Number(z.realisiert_eur)
    case 'opt': return Number(betragVon(z, 'OPT'))
    case 'stk': return Number(betragVon(z, 'STK'))
    case 'sonst': return sonstige(z)
    case 'unrealisiert': return Number(z.unrealisiert_eur)
    case 'gesamt': return Number(z.gesamt_eur)
  }
}

const KOEPFE: [Spalte, string, string][] = [
  ['basiswert', 'Basiswert', 'Klick auf den Namen zeigt die Ketten dieses Titels in den Positionen'],
  ['ketten', 'Ketten (offen)', 'Zahl der Ketten dieses Titels, davon noch offene'],
  ['realisiert', 'Realisiert', 'Abgeschlossene Strukturen und lose Beine, EUR — wie die Auswertung der Positionsliste'],
  ['opt', 'davon Optionen', 'Prämien und Optionsergebnisse (auch der Optionsanteil zugeteilter Positionen)'],
  ['stk', 'davon Aktien', 'Kursergebnis der Aktien; Einstand ist der Zuteilungs- oder Kaufpreis (Prämien stehen bei den Optionen)'],
  ['sonst', 'davon Futures u. a.', 'Futures, Futures-Optionen und übrige Klassen'],
  ['unrealisiert', 'Unrealisiert', 'Offene Beine gegen IBs Bestand des letzten Stichtags, EUR'],
  ['gesamt', 'Gesamt', 'Realisiert plus unrealisiert'],
]

function Summenzeile({ z }: { z: TitelZeile }): JSX.Element {
  return (
    <tr className="summe">
      <td><strong>Summe aller Titel</strong></td>
      <td className="zahl">{z.ketten} ({z.ketten_offen})</td>
      <td className="zahl"><Betrag wert={z.realisiert_eur} /></td>
      <td className="zahl"><Betrag wert={betragVon(z, 'OPT')} /></td>
      <td className="zahl"><Betrag wert={betragVon(z, 'STK')} /></td>
      <td className="zahl"><Betrag wert={String(sonstige(z))} /></td>
      <td className="zahl"><Betrag wert={z.unrealisiert_eur} /></td>
      <td className="zahl"><Betrag wert={z.gesamt_eur} /></td>
    </tr>
  )
}

export default function Titel(): JSX.Element {
  const [daten, setzeDaten] = useState<TitelAntwort | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [suche, setzeSuche] = useState('')
  const [nurOffen, setzeNurOffen] = useState(false)
  const [spalte, setzeSpalte] = useState<Spalte>('gesamt')
  const [absteigend, setzeAbsteigend] = useState(false)   // Vorgabe: größter Verlust zuerst

  useEffect(() => {
    holeTitel()
      .then(setzeDaten)
      .catch((ursache: unknown) => setzeFehler(fehlerText(ursache)))
  }, [])

  const zeilen = useMemo(() => {
    if (daten === null) return []
    const text = suche.trim().toUpperCase()
    const liste = daten.titel.filter(
      (z) =>
        (text === '' || z.basiswert.toUpperCase().includes(text)) &&
        (!nurOffen || z.ketten_offen > 0 || Number(z.unrealisiert_eur) !== 0),
    )
    liste.sort((a, b) => {
      const x = wert(a, spalte)
      const y = wert(b, spalte)
      const c = typeof x === 'string' ? x.localeCompare(String(y), 'de') : (x as number) - (y as number)
      return absteigend ? -c : c
    })
    return liste
  }, [daten, suche, nurOffen, spalte, absteigend])

  function sortiere(neu: Spalte): void {
    if (neu === spalte) setzeAbsteigend(!absteigend)
    else {
      setzeSpalte(neu)
      setzeAbsteigend(neu === 'basiswert' ? false : false)
    }
  }

  if (fehler) return <p className="fehler">{fehler}</p>
  if (daten === null) return <p className="laedt">Rechne das Ergebnis je Titel …</p>

  const ohneKurs = daten.summen.offene_ohne_kurs
  const kursFehlt = daten.summen.kurs_fehlt
  return (
    <section>
      <h2>Titel — Ergebnis über alle Instrumente</h2>
      <p className="sicht">
        Eine Zeile je Basiswert (Optionen, Aktien, Futures zusammen); die Positionsliste zeigt dagegen einen Trade je
        Zeile. Bestand zum Stichtag {daten.stichtag ? datumDe(daten.stichtag) : '—'}. Dividenden, Zinsen und
        Gebühren außerhalb der Ausführungen sind nicht enthalten. Optionsprämien stehen bei den Optionen, das
        Kursergebnis einer zugeteilten Aktie bei den Aktien — IB dagegen schiebt die Prämie in den Einstand der Aktie.
      </p>
      <p>
        <input
          type="search"
          placeholder="Basiswert suchen …"
          value={suche}
          onChange={(e) => setzeSuche(e.target.value)}
          aria-label="Basiswert suchen"
        />{' '}
        <label>
          <input type="checkbox" checked={nurOffen} onChange={(e) => setzeNurOffen(e.target.checked)} /> nur Titel mit
          offenem Bestand
        </label>{' '}
        <span className="hinweis">{zeilen.length} von {daten.titel.length} Titeln</span>
      </p>
      {(ohneKurs > 0 || kursFehlt > 0) && (
        <p className="hinweis">
          {kursFehlt > 0 ? `${kursFehlt} abgeschlossene Strukturen ohne Buchungskurs zählen nicht. ` : ''}
          {ohneKurs > 0 ? `${ohneKurs} offene Beine ohne Bestandszeile bei IB (z. B. angepasste Optionen) zählen nicht im unrealisierten Ergebnis.` : ''}
        </p>
      )}
      <div className="tabelle-rahmen">
        <table className="positionen dichte-kompakt">
          <thead>
            <tr>
              {KOEPFE.map(([id, name, hinweis]) => (
                <th key={id} className={id === 'basiswert' ? undefined : 'zahl'} title={hinweis}>
                  <button type="button" className="sortierer" onClick={() => sortiere(id)}>
                    {name}
                    {spalte === id ? (absteigend ? ' ▼' : ' ▲') : ''}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <Summenzeile z={daten.summen} />
            {zeilen.map((z) => (
              <tr key={z.basiswert}>
                <td>
                  <Link to={`/?basiswert=${encodeURIComponent(z.basiswert)}`} title="Ketten dieses Titels in den Positionen">
                    {z.basiswert}
                  </Link>
                  {z.waehrungen.length > 1 ? <span className="hinweis"> ({z.waehrungen.join('/')})</span> : null}
                </td>
                <td className="zahl">{z.ketten} ({z.ketten_offen})</td>
                <td className="zahl"><Betrag wert={z.realisiert_eur} /></td>
                <td className="zahl"><Betrag wert={betragVon(z, 'OPT')} /></td>
                <td className="zahl"><Betrag wert={betragVon(z, 'STK')} /></td>
                <td className="zahl"><Betrag wert={String(sonstige(z))} /></td>
                <td className="zahl"><Betrag wert={z.unrealisiert_eur} /></td>
                <td className="zahl"><Betrag wert={z.gesamt_eur} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
