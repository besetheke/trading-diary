import { useEffect, useState } from 'react'
import type { Rollgruppe, Rollkandidaten as Liste } from './api'
import { fehlerText, holeRollkandidaten, sendeRollurteil } from './api'
import { betrag, zeitDe } from './format'

// AP-08r: Durchsicht der Rollkandidaten in der Oberfläche — dieselben Gruppen
// und Regeln wie die Datei-Rundreise (AP-04d). Ein Roll ohne gemeinsame Order
// ist nur ein Vorschlag (Regel 7); hier entscheidet der Nutzer je Kandidat.
// Urteile wirken beim nächsten Neuaufbau (nächtlicher Abruf oder
// `journal rebuild`); ein entschiedener Kandidat verschwindet sofort.

const JE_SEITE = 25

type Urteil = 'bestaetigt' | 'abgelehnt'

export default function Rollkandidaten(): JSX.Element {
  const [liste, setzeListe] = useState<Liste | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [seite, setzeSeite] = useState(0)
  const [meldung, setzeMeldung] = useState<string | null>(null)
  const [laeuft, setzeLaeuft] = useState<string | null>(null)
  const [entschieden, setzeEntschieden] = useState(0)

  useEffect(() => {
    holeRollkandidaten()
      .then(setzeListe)
      .catch((e) => setzeFehler(fehlerText(e)))
  }, [])

  function entscheide(gruppe: Rollgruppe, schluesselStruktur: string, urteil: Urteil): void {
    const kennung = `${gruppe.schluessel_kette}→${schluesselStruktur}`
    setzeLaeuft(kennung)
    setzeMeldung(null)
    sendeRollurteil(gruppe.schluessel_kette, schluesselStruktur, urteil)
      .then(() => {
        setzeEntschieden((n) => n + 1)
        setzeListe((alt) => {
          if (alt === null) return alt
          const gruppen = alt.gruppen
            .map((g) =>
              g.schluessel_kette === gruppe.schluessel_kette
                ? {
                    ...g,
                    kandidaten: g.kandidaten.filter(
                      (k) => k.schluessel_struktur !== schluesselStruktur,
                    ),
                  }
                : g,
            )
            .filter((g) => g.kandidaten.length > 0)
          return {
            anzahl_gruppen: gruppen.length,
            anzahl_kandidaten: alt.anzahl_kandidaten - 1,
            gruppen,
          }
        })
      })
      .catch((e) => setzeMeldung(fehlerText(e)))
      .finally(() => setzeLaeuft(null))
  }

  if (fehler) {
    return (
      <section className="fehler">
        <h2>Rollkandidaten konnten nicht geladen werden</h2>
        <p>{fehler}</p>
      </section>
    )
  }
  if (liste === null) return <p className="laedt">Lade Rollkandidaten … (einige Sekunden)</p>

  const seiten = Math.max(1, Math.ceil(liste.gruppen.length / JE_SEITE))
  const aktuelle = Math.min(seite, seiten - 1)
  const sichtbar = liste.gruppen.slice(aktuelle * JE_SEITE, (aktuelle + 1) * JE_SEITE)

  return (
    <section className="rollkandidaten">
      <h2>Rolls prüfen</h2>
      <p className="sicht">
        {liste.anzahl_kandidaten} offene Kandidat(en) in {liste.anzahl_gruppen} Gruppe(n). Ein
        Kandidat ist eine Position, die kurz nach dem Schließen einer anderen eröffnet wurde, aber
        nicht in derselben Order — vielleicht ein Roll. „Roll“ verbindet beide zu einer Position,
        „Kein Roll“ hält sie getrennt. Wirksam beim nächsten Neuaufbau (nächtlicher Abruf).
        {entschieden > 0 ? ` In dieser Sitzung entschieden: ${entschieden}.` : ''}
      </p>
      {meldung ? <p className="fehler">{meldung}</p> : null}
      {liste.gruppen.length === 0 ? (
        <p className="hinweis">Keine offenen Kandidaten.</p>
      ) : null}
      {sichtbar.map((g) => (
        <article key={g.schluessel_kette} className="rollgruppe">
          <header>
            <strong>
              {g.basiswert} · {g.seite}
            </strong>{' '}
            geschlossen {zeitDe(g.alt_geschlossen)}, Preis zu {betrag(g.alt_preis_zu)}
            <div className="legs">{g.alt_legs}</div>
          </header>
          <table>
            <thead>
              <tr>
                <th>Rang</th>
                <th>Neue Position</th>
                <th>Eröffnet</th>
                <th>Abstand</th>
                <th>Preis auf</th>
                <th>Menge</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {g.kandidaten.map((k) => {
                const kennung = `${g.schluessel_kette}→${k.schluessel_struktur}`
                return (
                  <tr key={k.schluessel_struktur}>
                    <td>{k.rang}</td>
                    <td className="legs">{k.neu_legs}</td>
                    <td>{zeitDe(k.neu_eroeffnet)}</td>
                    <td>{k.abstand_minuten} min</td>
                    <td>{betrag(k.neu_preis_auf)}</td>
                    <td title="Mengenverhältnis neu zu alt">{k.mengenverhaeltnis}</td>
                    <td className="aktionen">
                      <button
                        type="button"
                        disabled={laeuft !== null}
                        onClick={() => entscheide(g, k.schluessel_struktur, 'bestaetigt')}
                      >
                        {laeuft === kennung ? '…' : 'Roll'}
                      </button>
                      <button
                        type="button"
                        disabled={laeuft !== null}
                        onClick={() => entscheide(g, k.schluessel_struktur, 'abgelehnt')}
                      >
                        Kein Roll
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </article>
      ))}
      {seiten > 1 ? (
        <div className="blaettern">
          <button type="button" disabled={aktuelle === 0} onClick={() => setzeSeite(aktuelle - 1)}>
            Zurück
          </button>
          <span>
            Seite {aktuelle + 1} von {seiten}
          </span>
          <button
            type="button"
            disabled={aktuelle >= seiten - 1}
            onClick={() => setzeSeite(aktuelle + 1)}
          >
            Weiter
          </button>
        </div>
      ) : null}
    </section>
  )
}
