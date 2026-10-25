// AP-17g (M02, zweite Stufe): offene Kandidaten bestätigen oder verwerfen, ohne Datei-Rundreise.
// Jede Entscheidung ist ein Vorschlag des Nutzers (erkennung = manuell); eine Verwerfung wird nie gelöscht,
// sie lässt sich nur ausdrücklich durch eine Bestätigung ersetzen.

import { useCallback, useEffect, useState } from 'react'
import { entscheideKandidat, fehlerText, holeKampagnenKandidaten } from './api'
import type { KampagnenKandidat, KampagnenKandidaten } from './api'
import { zeitDe } from './format'

const TYPEN = ['ic_leg', 'financing', 'contract_roll', 'independent']

function KetteZelle(props: { k: KampagnenKandidat['a'] }): JSX.Element {
  const { k } = props
  return (
    <>
      <strong>{k.seite ?? '—'}</strong> {k.schluessel}
      <br />
      <span className="fussnote">
        {zeitDe(k.eroeffnet_am)} → {k.beendet_am === null ? 'offen' : zeitDe(k.beendet_am)}, {k.rolls ?? 0} Rolls
      </span>
    </>
  )
}

function abstandText(k: KampagnenKandidat): string {
  if (k.typ === 'financing') return k.abstand_minuten === null ? '—' : `${k.abstand_minuten} min`
  return k.ueberlappung_tage === null ? 'unbegrenzt' : `${k.ueberlappung_tage} Tage`
}

function KandidatZeile(props: {
  kandidat: KampagnenKandidat
  fertig: () => void
  melde: (text: string | null) => void
}): JSX.Element {
  const { kandidat, fertig, melde } = props
  const [typA, setzeTypA] = useState(kandidat.a.typ)
  const [typB, setzeTypB] = useState(kandidat.b.typ)
  const [bemerkung, setzeBemerkung] = useState('')

  function entscheide(urteil: 'ja' | 'nein'): void {
    melde(null)
    entscheideKandidat({
      schluessel_a: kandidat.a.schluessel,
      schluessel_b: kandidat.b.schluessel,
      typ: kandidat.typ,
      urteil,
      typ_a: typA,
      typ_b: typB,
      bemerkung: bemerkung.trim() || undefined,
    })
      .then(fertig)
      .catch((u: unknown) => melde(fehlerText(u)))
  }

  return (
    <tr>
      <td>{kandidat.rang}</td>
      <td>{kandidat.typ === 'ic' ? 'Iron Condor' : 'Financing'}</td>
      <td>
        <KetteZelle k={kandidat.a} />
      </td>
      <td>
        <KetteZelle k={kandidat.b} />
      </td>
      <td className="zahl">{abstandText(kandidat)}</td>
      <td>
        <select value={typA} onChange={(e) => setzeTypA(e.target.value)} aria-label="Typ Kette A">
          {TYPEN.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>{' '}
        <select value={typB} onChange={(e) => setzeTypB(e.target.value)} aria-label="Typ Kette B">
          {TYPEN.map((t) => (
            <option key={t}>{t}</option>
          ))}
        </select>
      </td>
      <td>
        <input value={bemerkung} onChange={(e) => setzeBemerkung(e.target.value)} placeholder="Bemerkung" />
      </td>
      <td>
        <button type="button" onClick={() => entscheide('ja')}>
          Bestätigen
        </button>{' '}
        <button type="button" onClick={() => entscheide('nein')}>
          Verwerfen
        </button>
      </td>
    </tr>
  )
}

export default function KampagnenKandidatenListe(props: { geaendert: () => void }): JSX.Element {
  const [daten, setzeDaten] = useState<KampagnenKandidaten | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [meldung, setzeMeldung] = useState<string | null>(null)

  const laden = useCallback(() => {
    holeKampagnenKandidaten()
      .then(setzeDaten)
      .catch((u: unknown) => setzeFehler(fehlerText(u)))
  }, [])
  useEffect(laden, [laden])

  function fertig(): void {
    laden()
    props.geaendert()
  }

  if (fehler !== null) return <p className="meldung">{fehler}</p>
  if (daten === null) return <p className="laedt">Lade Vorschläge …</p>
  return (
    <section>
      <h3>Offene Vorschläge ({daten.anzahl})</h3>
      <p className="sicht fussnote">
        Vorschläge, keine Tatsachen: Erst deine Entscheidung macht daraus eine Kampagne (Erkennung „manuell“). Eine Gruppe ist eine
        Kette A mit allen möglichen Partnern; bei mehr als einem Eintrag ist die Lage mehrdeutig. Verwerfen löscht nichts und lässt sich
        nur durch ausdrückliches Bestätigen ersetzen.
      </p>
      {meldung !== null ? <p className="meldung">{meldung}</p> : null}
      {daten.gruppen.map((g) => (
        <table key={g.gruppe} className="positionen">
          <caption>
            Gruppe {g.gruppe}
            {g.mehrdeutig ? ' — mehrdeutig' : ''}
          </caption>
          <thead>
            <tr>
              <th>Rang</th>
              <th>Art</th>
              <th>Kette A</th>
              <th>Kette B</th>
              <th>Abstand / Überlappung</th>
              <th>Typen A / B</th>
              <th>Bemerkung</th>
              <th>Entscheidung</th>
            </tr>
          </thead>
          <tbody>
            {g.kandidaten.map((k) => (
              <KandidatZeile key={`${k.a.schluessel}|${k.b.schluessel}|${k.typ}`} kandidat={k} fertig={fertig} melde={setzeMeldung} />
            ))}
          </tbody>
        </table>
      ))}
      {daten.verworfen.length > 0 ? (
        <details>
          <summary>Verworfene Paare ({daten.verworfen.length})</summary>
          <ul>
            {daten.verworfen.map((v) => (
              <li key={`${v.schluessel_a}|${v.schluessel_b}|${v.typ}`}>
                {v.schluessel_a} → {v.schluessel_b} ({v.typ}){v.notiz !== null ? ` — ${v.notiz}` : ''}{' '}
                <button
                  type="button"
                  onClick={() => {
                    setzeMeldung(null)
                    entscheideKandidat({
                      schluessel_a: v.schluessel_a,
                      schluessel_b: v.schluessel_b,
                      typ: v.typ,
                      urteil: 'ja',
                      ueberschreiben: true,
                    })
                      .then(fertig)
                      .catch((u: unknown) => setzeMeldung(fehlerText(u)))
                  }}
                >
                  doch bestätigen
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  )
}
