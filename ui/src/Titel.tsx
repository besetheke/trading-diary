import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeTitel } from './api'
import type { TitelAntwort, TitelZeile } from './api'
import Betrag from './Betrag'
import { datumDe } from './format'
import { useZeitraum } from './zeitraum'

// AP-16: Ergebnis je Titel über alle Instrumente. Eine Zeile je Basiswert — Optionen, Aktien und Futures
// zusammen —, im Unterschied zur Positionsliste (eine Zeile je Trade). Alles Werte der Quelle
// (GET /titel-auswertung, dieselbe Rechengrundlage wie die Auswertung der Positionsliste); im Browser
// wird nur sortiert und gefiltert.

type Spalte = 'basiswert' | 'ketten' | 'realisiert' | 'opt' | 'stk' | 'sonst' | 'unrealisiert' | 'gesamt' | 'ertraege' | 'gesamt_ertraege' | 'teil'

// Anzeige: 'EUR' (jede Seite zum Kurs ihres Tages, wie die Auswertung) oder die Währung der Geschäfte
// (z. B. 'USD', ohne Umrechnung — vergleichbar mit Broker-Auszügen). „Ohne Kommission“ rechnet die im
// Realisierten enthaltene Kommission wieder heraus.
interface Zahlen {
  realisiert: number
  opt: number
  stk: number
  sonst: number
  unrealisiert: number
  gesamt: number
  ertraege: number
  gesamtErtraege: number
}

function zahlen(z: TitelZeile, anzeige: string, ohneKomm: boolean): Zahlen {
  let realisiert: number
  let unrealisiert: number
  let ertraege: number
  const je: Record<string, number> = {}
  if (anzeige === 'EUR') {
    realisiert = Number(z.realisiert_eur) - (ohneKomm ? Number(z.kommission_eur) : 0)
    unrealisiert = Number(z.unrealisiert_eur)
    ertraege = Number(z.ertraege_eur)
    for (const k of z.je_klasse) {
      je[k.anlageklasse] = Number(k.realisiert_eur) - (ohneKomm ? Number(k.kommission_eur) : 0)
    }
  } else {
    const n = z.nativ.find((x) => x.waehrung === anzeige)
    realisiert = n ? Number(n.realisiert) - (ohneKomm ? Number(n.kommission) : 0) : 0
    unrealisiert = n ? Number(n.unrealisiert) : 0
    ertraege = n ? Number(n.dividenden) + Number(n.quellensteuer) : 0
    for (const k of n?.je_klasse ?? []) {
      je[k.anlageklasse] = Number(k.realisiert) - (ohneKomm ? Number(k.kommission) : 0)
    }
  }
  const opt = je['OPT'] ?? 0
  const stk = je['STK'] ?? 0
  const sonst = Object.entries(je)
    .filter(([k]) => k !== 'OPT' && k !== 'STK')
    .reduce((summe, [, v]) => summe + v, 0)
  const gesamt = realisiert + unrealisiert
  return { realisiert, opt, stk, sonst, unrealisiert, gesamt, ertraege, gesamtErtraege: gesamt + ertraege }
}

function wert(z: TitelZeile, spalte: Spalte, anzeige: string, ohneKomm: boolean): number | string {
  if (spalte === 'basiswert') return z.basiswert
  if (spalte === 'ketten') return z.ketten
  const n = zahlen(z, anzeige, ohneKomm)
  switch (spalte) {
    case 'realisiert': return n.realisiert
    case 'opt': return n.opt
    case 'stk': return n.stk
    case 'sonst': return n.sonst
    case 'teil': return anzeige === 'EUR' ? Number(z.teilrealisiert_eur) : 0
    case 'unrealisiert': return n.unrealisiert
    case 'gesamt': return n.gesamt
    case 'ertraege': return n.ertraege
    case 'gesamt_ertraege': return n.gesamtErtraege
  }
}

const KOEPFE: [Spalte, string, string][] = [
  ['basiswert', 'Basiswert', 'Klick auf den Namen zeigt die Ketten dieses Titels in den Positionen'],
  ['ketten', 'Ketten (offen)', 'Zahl der Ketten dieses Titels, davon noch offene'],
  ['realisiert', 'Realisiert', 'Abgeschlossene Strukturen und lose Beine, EUR — wie die Auswertung der Positionsliste'],
  ['opt', 'davon Optionen', 'Prämien und Optionsergebnisse (auch der Optionsanteil zugeteilter Positionen)'],
  ['stk', 'davon Aktien', 'Kursergebnis der Aktien; Einstand ist der Zuteilungs- oder Kaufpreis (Prämien stehen bei den Optionen)'],
  ['sonst', 'davon Futures u. a.', 'Futures, Futures-Optionen und übrige Klassen'],
  ['teil', 'Teil-realisiert', 'Beine, die schon geschlossen sind, deren Struktur aber noch offen ist (z. B. ein Roll-Bein). Sie zählen erst mit der Struktur im Realisierten — hier nur zur Information, nicht in den Summen; nur in EUR'],
  ['unrealisiert', 'Unrealisiert', 'Offene Beine gegen IBs Bestand des letzten Stichtags, EUR'],
  ['gesamt', 'Handel gesamt', 'Realisiert plus unrealisiert (ohne Dividenden)'],
  ['ertraege', 'Dividenden netto', 'Dividenden und Ersatzzahlungen abzüglich Quellensteuer, EUR (Buchungsdatum im Zeitraum)'],
  ['gesamt_ertraege', 'Gesamt inkl. Dividenden', 'Handel gesamt plus Dividenden netto — was der Titel insgesamt gebracht hat'],
]

function Zellen({ z, anzeige, ohneKomm }: { z: TitelZeile; anzeige: string; ohneKomm: boolean }): JSX.Element {
  const n = zahlen(z, anzeige, ohneKomm)
  const b = (x: number): JSX.Element => <Betrag wert={String(x)} waehrung={anzeige} />
  return (
    <>
      <td className="zahl">{b(n.realisiert)}</td>
      <td className="zahl">{b(n.opt)}</td>
      <td className="zahl">{b(n.stk)}</td>
      <td className="zahl">{b(n.sonst)}</td>
      <td className="zahl" title="Schon geschlossene Beine in offenen Strukturen — nicht in den Summen">
        {anzeige === 'EUR' ? <Betrag wert={z.teilrealisiert_eur} /> : '—'}
      </td>
      <td className="zahl">{b(n.unrealisiert)}</td>
      <td className="zahl">{b(n.gesamt)}</td>
      <td className="zahl" title={`Dividenden ${z.dividenden_eur} EUR, Quellensteuer ${z.quellensteuer_eur} EUR`}>
        {b(n.ertraege)}
      </td>
      <td className="zahl"><strong>{b(n.gesamtErtraege)}</strong></td>
    </>
  )
}

function Summenzeile({ z, anzeige, ohneKomm }: { z: TitelZeile; anzeige: string; ohneKomm: boolean }): JSX.Element {
  return (
    <tr className="summe">
      <td><strong>Summe aller Titel</strong></td>
      <td className="zahl">{z.ketten} ({z.ketten_offen})</td>
      <Zellen z={z} anzeige={anzeige} ohneKomm={ohneKomm} />
    </tr>
  )
}

export default function Titel(): JSX.Element {
  const [zeitraum] = useZeitraum()
  const [daten, setzeDaten] = useState<TitelAntwort | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [suche, setzeSuche] = useState('')
  const [nurOffen, setzeNurOffen] = useState(false)
  const [spalte, setzeSpalte] = useState<Spalte>('gesamt')
  const [absteigend, setzeAbsteigend] = useState(false)   // Vorgabe: größter Verlust zuerst
  const [anzeige, setzeAnzeige] = useState('EUR')
  const [ohneKomm, setzeOhneKomm] = useState(false)

  useEffect(() => {
    let abgebrochen = false
    setzeFehler(null)
    holeTitel(zeitraum.von, zeitraum.bis)
      .then((d) => {
        if (!abgebrochen) setzeDaten(d)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  const zeitraumGesetzt = zeitraum.von !== null || zeitraum.bis !== null
  const zeilen = useMemo(() => {
    if (daten === null) return []
    const text = suche.trim().toUpperCase()
    const liste = daten.titel.filter(
      (z) =>
        (text === '' || z.basiswert.toUpperCase().includes(text)) &&
        (anzeige === 'EUR' || z.nativ.some((n) => n.waehrung === anzeige)) &&
        (!nurOffen || z.ketten_offen > 0 || Number(z.unrealisiert_eur) !== 0) &&
        // Mit Zeitraum nur Titel, die darin etwas zählen (Schließung, Kursmangel) oder offen bewertet sind.
        (!zeitraumGesetzt ||
          z.abgeschlossen_im_zeitraum > 0 ||
          z.kurs_fehlt > 0 ||
          Number(z.ertraege_eur) !== 0 ||
          Number(z.unrealisiert_eur) !== 0),
    )
    liste.sort((a, b) => {
      const x = wert(a, spalte, anzeige, ohneKomm)
      const y = wert(b, spalte, anzeige, ohneKomm)
      const c = typeof x === 'string' ? x.localeCompare(String(y), 'de') : (x as number) - (y as number)
      return absteigend ? -c : c
    })
    return liste
  }, [daten, suche, nurOffen, spalte, absteigend, zeitraumGesetzt, anzeige, ohneKomm])

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
  const ertragOhneKurs = daten.summen.ertraege_kurs_fehlt
  return (
    <section>
      <h2>Titel — Ergebnis über alle Instrumente</h2>
      <p className="sicht">
        Eine Zeile je Basiswert (Optionen, Aktien, Futures zusammen); die Positionsliste zeigt dagegen einen Trade je
        Zeile. Bestand zum Stichtag {daten.stichtag ? datumDe(daten.stichtag) : '—'}.
        {zeitraumGesetzt
          ? ' Der gewählte Zeitraum gilt für das Realisierte (Schließungstag); das Unrealisierte gilt zum Stichtag und entfällt, wenn der Zeitraum davor endet.'
          : ''}{' '}
        „Handel gesamt“ enthält keine Dividenden; die Spalten
        „Dividenden netto“ (nach Quellensteuer, Buchungsdatum im Zeitraum) und „Gesamt inkl. Dividenden“ ergänzen sie.
        Zinsen und Gebühren haben keinen Titel und fehlen hier. Optionsprämien stehen bei den Optionen, das
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
      <div className="diagramm-wahl" role="group" aria-label="Währung der Anzeige">
        {['EUR', ...Array.from(new Set(daten.summen.nativ.map((n) => n.waehrung))).filter((w) => w !== 'EUR')].map((w) => (
          <button
            key={w}
            type="button"
            aria-pressed={anzeige === w}
            title={w === 'EUR' ? 'Jede Seite zum Kurs ihres Tages — wie die Auswertung' : `In ${w}, ohne Umrechnung — vergleichbar mit Broker-Auszügen`}
            onClick={() => setzeAnzeige(w)}
          >
            {w === 'EUR' ? 'EUR (Tageskurse)' : `${w} (Original)`}
          </button>
        ))}
        <label>
          <input type="checkbox" checked={ohneKomm} onChange={(e) => setzeOhneKomm(e.target.checked)} /> ohne
          Kommission
        </label>
      </div>
      {(ohneKurs > 0 || kursFehlt > 0 || ertragOhneKurs > 0) && (
        <p className="hinweis">
          {kursFehlt > 0 ? `${kursFehlt} abgeschlossene Strukturen ohne Buchungskurs zählen nicht. ` : ''}
          {ertragOhneKurs > 0 ? `${ertragOhneKurs} Dividenden-Buchungen ohne Kurs zählen nicht. ` : ''}
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
            <Summenzeile z={daten.summen} anzeige={anzeige} ohneKomm={ohneKomm} />
            {zeilen.map((z) => (
              <tr key={z.basiswert}>
                <td>
                  <Link to={`/?basiswert=${encodeURIComponent(z.basiswert)}`} title="Ketten dieses Titels in den Positionen">
                    {z.basiswert}
                  </Link>
                  {z.waehrungen.length > 1 ? <span className="hinweis"> ({z.waehrungen.join('/')})</span> : null}
                </td>
                <td className="zahl">{z.ketten} ({z.ketten_offen})</td>
                <Zellen z={z} anzeige={anzeige} ohneKomm={ohneKomm} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
