import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { fehlerText, holeKetten } from './api'
import type { Kette, KettenListe, Richtung, Sortierspalte } from './api'
import { zeit, zeitKurz, aufZweiNachkommastellen } from './format'

const LIMITS = [10, 25, 50, 100]

// Werte aus dem Datenbankschema (CHECK instruments.asset_class) und aus dem
// Wiederhersteller (chains.endzustand) — die Oberfläche erfindet keine.
const ANLAGEKLASSEN = ['OPT', 'FOP', 'FUT', 'STK', 'CASH']
const ENDZUSTAENDE = ['Offen', 'Geschlossen', 'Verfall', 'Assigned']

// AP-08s: Spalten der Positionsliste. Die Eröffnung steht zuerst — Datum und
// Uhrzeit in einer Zeile —, danach Basiswert, Klasse, Seite, Ende (ebenso in
// einer Zeile), Rolls, Endzustand, OA-Strategie und die abgeleiteten Werte.
// Sortiert wird ausschließlich die API (AP-07s): „sortierbar" heißt, der Kopf
// schickt sortierung/richtung mit; der erste Klick wählt die natürliche
// Richtung (neueste zuerst bei Zeit und Rolls, A bis Z bei Text), jeder
// weitere Klick kehrt um.
type SpaltenId =
  | 'eroeffnet_am'
  | 'underlying'
  | 'asset_class'
  | 'seite'
  | 'beendet_am'
  | 'anzahl_rolls'
  | 'endzustand'
  | 'oa_strategie'
  | 'eroeffnungspreis'
  | 'schlusspreis'
  | 'struktur_summe_netto'
  | 'waehrung'

interface Spalte {
  titel: string
  sortierbar: boolean
  ersteRichtung?: Richtung
}

const SPALTEN: Record<SpaltenId, Spalte> = {
  eroeffnet_am: { titel: 'Eröffnung', sortierbar: true, ersteRichtung: 'desc' },
  underlying: { titel: 'Basiswert', sortierbar: true, ersteRichtung: 'asc' },
  asset_class: { titel: 'Klasse', sortierbar: true, ersteRichtung: 'asc' },
  seite: { titel: 'Seite', sortierbar: true, ersteRichtung: 'asc' },
  beendet_am: { titel: 'Ende', sortierbar: true, ersteRichtung: 'desc' },
  anzahl_rolls: { titel: 'Rolls', sortierbar: true, ersteRichtung: 'desc' },
  endzustand: { titel: 'Endzustand', sortierbar: true, ersteRichtung: 'asc' },
  oa_strategie: { titel: 'OA-Strategie', sortierbar: true, ersteRichtung: 'asc' },
  // Preise, Ergebnis und Währung sind je Seite zusammengestellt — nicht
  // sortierbar (AP-07s): Eine Sortierung nur über die aktuelle Seite wäre
  // irreführend; der Kopf sagt das im title.
  eroeffnungspreis: { titel: 'Preis auf', sortierbar: false },
  schlusspreis: { titel: 'Preis zu', sortierbar: false },
  struktur_summe_netto: { titel: 'Ergebnis netto¹', sortierbar: false },
  waehrung: { titel: 'Währung', sortierbar: false },
}

const ALLE_SPALTEN = Object.keys(SPALTEN) as SpaltenId[]
const STANDARD_SPALTEN: SpaltenId[] = [...ALLE_SPALTEN]
const ZAHL_SPALTEN: SpaltenId[] = [
  'anzahl_rolls',
  'eroeffnungspreis',
  'schlusspreis',
  'struktur_summe_netto',
]
const NICHT_SORTIERBAR_TITEL =
  'Nicht sortierbar — der Wert gilt nur für die angezeigte Seite'

function istSortierbareSpalte(wert: string | null): wert is Sortierspalte {
  return (
    wert !== null && ALLE_SPALTEN.some((id) => id === wert && SPALTEN[id].sortierbar)
  )
}

// AP-08s, Punkt 3: Auswahl und Reihenfolge der Spalten stehen im Browser.
// Fehlt der Speicher oder ist der Inhalt unlesbar oder ungültig, gilt die
// Vorgabe — vollständig oder gar nicht, nichts wird still repariert.
function leseSpalten(): SpaltenId[] | null {
  try {
    const roh = window.localStorage.getItem('positionen.spalten')
    if (roh === null) return null
    const geparst: unknown = JSON.parse(roh)
    if (!Array.isArray(geparst) || geparst.length === 0) return null
    if (!geparst.every((eintrag) => ALLE_SPALTEN.includes(eintrag as SpaltenId))) {
      return null
    }
    if (new Set(geparst).size !== geparst.length) return null
    return geparst as SpaltenId[]
  } catch {
    return null
  }
}

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

// Eine Tabellenzelle je Spalte — reine Zeichenarbeit (Vertrag 8): Die
// Zeichenfolge wird nur geschnitten, nie umgerechnet.
function zelle(kette: Kette, id: SpaltenId, verweis: SpaltenId): JSX.Element {
  const istVerweis = id === verweis
  switch (id) {
    case 'eroeffnet_am':
      // Volle Zeit (mit Sekunden) im title, eine Zeile ohne Umbruch.
      return (
        <td className="zeit" title={zeit(kette.eroeffnet_am)}>
          {istVerweis ? (
            <Link to={`/positionen/${kette.chain_id}`}>{zeitKurz(kette.eroeffnet_am)}</Link>
          ) : (
            zeitKurz(kette.eroeffnet_am)
          )}
        </td>
      )
    case 'underlying':
      return istVerweis ? (
        <td>
          <Link to={`/positionen/${kette.chain_id}`}>{kette.underlying}</Link>
        </td>
      ) : (
        <td>{kette.underlying}</td>
      )
    case 'asset_class':
      return <td>{kette.asset_class}</td>
    case 'seite':
      return <td>{kette.seite ?? '—'}</td>
    case 'beendet_am':
      return (
        <td className="zeit" title={kette.beendet_am ? zeit(kette.beendet_am) : undefined}>
          {kette.beendet_am ? zeitKurz(kette.beendet_am) : '—'}
        </td>
      )
    case 'anzahl_rolls':
      return <td className="zahl">{kette.anzahl_rolls}</td>
    case 'endzustand':
      return <td>{kette.endzustand ?? '—'}</td>
    // AP-13x: OA-Strategie der Kette (AP-13wk), reines Durchreichen; leer
    // bleibt —. Status und Erkennung bleiben der Detailansicht vorbehalten.
    case 'oa_strategie':
      return <td>{kette.oa_strategie ?? '—'}</td>
    // AP-08lk, Punkt 2 (vom Nutzer freigegeben) und AP-08fp, Vertrag 4: Die
    // Liste zeigt zwei Nachkommastellen — reine Zeichenarbeit (Vertrag 8),
    // der vollständige Wert steht im title der Zelle. Die Detailansicht
    // bleibt unverändert genau.
    case 'eroeffnungspreis': {
      const voll = kette.eroeffnungspreis
      const kurz = voll === null ? null : aufZweiNachkommastellen(voll)
      return (
        <td className="zahl" title={voll !== null && kurz !== voll ? voll : undefined}>
          {kurz ?? '—'}
        </td>
      )
    }
    case 'schlusspreis': {
      const voll = kette.schlusspreis
      const kurz = voll === null ? null : aufZweiNachkommastellen(voll)
      return (
        <td className="zahl" title={voll !== null && kurz !== voll ? voll : undefined}>
          {kurz ?? '—'}
        </td>
      )
    }
    case 'struktur_summe_netto': {
      const voll = kette.struktur_summe_netto
      const kurz = voll === null ? null : aufZweiNachkommastellen(voll)
      return (
        <td className="zahl" title={voll !== null && kurz !== voll ? voll : undefined}>
          {kurz ?? '—'}
        </td>
      )
    }
    case 'waehrung':
      return (
        <td>
          {kette.waehrung ?? (
            <span title="Kette enthält mehrere Währungen — keine Summe möglich">
              {kette.waehrungen.join(' / ')}
            </span>
          )}
        </td>
      )
  }
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

  // AP-08s: Die Sortierung steht in der Adresse — Neuladen und Lesezeichen
  // erhalten sie. Ungültiges darin wird nicht durchgereicht (die API
  // antwortete 422); es gilt die Vorgabe: Eröffnung absteigend (AP-07s).
  const sortierungParam = suche.get('sortierung')
  const richtungParam = suche.get('richtung')
  const sortierung: Sortierspalte = istSortierbareSpalte(sortierungParam)
    ? sortierungParam
    : 'eroeffnet_am'
  const richtung: Richtung =
    richtungParam === 'asc' || richtungParam === 'desc' ? richtungParam : 'desc'

  const [entwurf, setzeEntwurf] = useState<Entwurf>({
    basiswert,
    anlageklasse,
    endzustand,
    minRolls,
    maxRolls,
  })
  const [liste, setzeListe] = useState<KettenListe | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  // AP-08s, Punkt 3: Auswahl und Reihenfolge der sichtbaren Spalten.
  const [sichtbare, setzeSichtbare] = useState<SpaltenId[]>(
    () => leseSpalten() ?? STANDARD_SPALTEN,
  )

  // Die Wahl gilt auch beim nächsten Besuch. Fehlt der Speicher, gilt sie
  // still nur für diese Sitzung — die Ansicht bricht darüber nicht.
  useEffect(() => {
    try {
      window.localStorage.setItem('positionen.spalten', JSON.stringify(sichtbare))
    } catch {
      /* Speicher fehlt oder ist voll — nichts weiter zu tun. */
    }
  }, [sichtbare])

  // Der Verweis auf die Detailansicht hängt an der Eröffnung, solange sie
  // sichtbar ist; sonst an der ersten sichtbaren Spalte (AP-08s, Punkt 3).
  const verweisSpalte: SpaltenId = sichtbare.includes('eroeffnet_am')
    ? 'eroeffnet_am'
    : sichtbare[0]
  const versteckte = ALLE_SPALTEN.filter((id) => !sichtbare.includes(id))

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
      sortierung,
      richtung,
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
  }, [basiswert, anlageklasse, endzustand, minRolls, maxRolls, limit, offset, sortierung, richtung])

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
    // Die Sortierung gehört zur Ansicht — sie bleibt beim Anwenden der
    // Filter erhalten (AP-08s); limit und offset fallen auf die Vorgabe
    // zurück.
    if (sortierung !== 'eroeffnet_am' || richtung !== 'desc') {
      naechste.set('sortierung', sortierung)
      naechste.set('richtung', richtung)
    }
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

  // AP-08s: Klick auf den Spaltenkopf — die Sortierung geht als sortierung
  // und richtung an GET /ketten (AP-07sk) und steht in der Adresse; ein
  // Wechsel setzt das Blättern auf die erste Seite zurück.
  function sortiereNach(id: SpaltenId): void {
    const spalte = SPALTEN[id]
    if (!spalte.sortierbar) return
    const naechste = new URLSearchParams(suche)
    naechste.set('sortierung', id)
    if (sortierung === id) {
      naechste.set('richtung', richtung === 'asc' ? 'desc' : 'asc')
    } else {
      naechste.set('richtung', spalte.ersteRichtung ?? 'asc')
    }
    naechste.delete('offset')
    setzeSuche(naechste)
  }

  // AP-08s, Punkt 3: Spaltenauswahl — mindestens eine Spalte bleibt sichtbar.
  function spalteUmschalten(id: SpaltenId): void {
    if (sichtbare.includes(id)) {
      if (sichtbare.length === 1) return
      setzeSichtbare(sichtbare.filter((eine) => eine !== id))
    } else {
      // Wieder eingeblendet wird an der Standardposition — sonst hinge die
      // Spalte ohne erkennbaren Grund am Ende.
      setzeSichtbare(
        [...sichtbare, id].sort(
          (a, b) => STANDARD_SPALTEN.indexOf(a) - STANDARD_SPALTEN.indexOf(b),
        ),
      )
    }
  }

  function spalteVerschieben(id: SpaltenId, schritt: number): void {
    const von = sichtbare.indexOf(id)
    const nach = von + schritt
    if (von < 0 || nach < 0 || nach >= sichtbare.length) return
    const naechste = [...sichtbare]
    ;[naechste[von], naechste[nach]] = [naechste[nach], naechste[von]]
    setzeSichtbare(naechste)
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

      {/* AP-08s: Spaltenauswahl — ein Kästchen je Spalte, Reihenfolge über
          die Pfeile, im Browser gespeichert (mit Rückfall auf die Vorgabe);
          „Standard wiederherstellen" setzt zurück. Die Liste zeigt die
          sichtbaren Spalten in ihrer Reihenfolge und darunter die
          ausgeblendeten. */}
      <details className="spaltenwahl">
        <summary>Spalten</summary>
        <ul>
          {sichtbare.map((id, stelle) => (
            <li key={id}>
              <label>
                <input
                  type="checkbox"
                  checked
                  disabled={sichtbare.length === 1}
                  onChange={() => spalteUmschalten(id)}
                />{' '}
                {SPALTEN[id].titel}
              </label>
              <button
                type="button"
                aria-label={`${SPALTEN[id].titel} nach oben`}
                disabled={stelle === 0}
                onClick={() => spalteVerschieben(id, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                aria-label={`${SPALTEN[id].titel} nach unten`}
                disabled={stelle === sichtbare.length - 1}
                onClick={() => spalteVerschieben(id, 1)}
              >
                ↓
              </button>
            </li>
          ))}
          {versteckte.map((id) => (
            <li key={id} className="aus">
              <label>
                <input type="checkbox" onChange={() => spalteUmschalten(id)} />{' '}
                {SPALTEN[id].titel}
              </label>
            </li>
          ))}
        </ul>
        <button type="button" onClick={() => setzeSichtbare([...STANDARD_SPALTEN])}>
          Standard wiederherstellen
        </button>
      </details>

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
          <table className="positionen">
            <thead>
              <tr>
                {sichtbare.map((id) => {
                  const spalte = SPALTEN[id]
                  const aktiv = spalte.sortierbar && sortierung === id
                  return (
                    <th
                      key={id}
                      className={ZAHL_SPALTEN.includes(id) ? 'zahl' : undefined}
                      aria-sort={
                        aktiv ? (richtung === 'asc' ? 'ascending' : 'descending') : undefined
                      }
                      title={spalte.sortierbar ? undefined : NICHT_SORTIERBAR_TITEL}
                    >
                      {spalte.sortierbar ? (
                        <button type="button" className="sortierer" onClick={() => sortiereNach(id)}>
                          {spalte.titel}
                          {aktiv ? (richtung === 'asc' ? ' ▲' : ' ▼') : ''}
                        </button>
                      ) : (
                        spalte.titel
                      )}
                    </th>
                  )
                })}
              </tr>
            </thead>
            <tbody>
              {liste.treffer.map((kette) => (
                <tr key={kette.chain_id}>
                  {sichtbare.map((id) => zelle(kette, id, verweisSpalte))}
                </tr>
              ))}
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
