import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeAlleSchlagwoerter, sucheJournal } from './api'
import type { Schlagwort, SucheTreffer } from './api'
import { datumDe } from './format'

// M05: Suche über Notiztexte und Tags. Ohne Suchbegriff und Filter steht die zentrale Liste aller markierten oder
// kommentierten Situationen da. Jeder Treffer zeigt die Position als Kontext und führt zu ihr.

const BEREICHE: Record<string, string> = { chain: 'Kette', structure: 'Struktur', campaign: 'Kampagne', tag: 'Tag' }

export default function JournalSuche(): JSX.Element {
  const [q, setzeQ] = useState('')
  const [gewaehlt, setzeGewaehlt] = useState<string[]>([])
  const [modus, setzeModus] = useState<'alle' | 'irgendeines'>('alle')
  const [mitAnhang, setzeMitAnhang] = useState(false)
  const [tagListe, setzeTagListe] = useState<Schlagwort[]>([])
  const [treffer, setzeTreffer] = useState<SucheTreffer[] | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    holeAlleSchlagwoerter().then(setzeTagListe).catch(() => setzeTagListe([]))
  }, [])

  useEffect(() => {
    setzeFehler(null)
    const timer = window.setTimeout(() => {
      sucheJournal(q, gewaehlt, modus, mitAnhang).then(setzeTreffer).catch((e) => setzeFehler(fehlerText(e)))
    }, 250)
    return () => window.clearTimeout(timer)
  }, [q, gewaehlt, modus, mitAnhang])

  const umschalten = (name: string) =>
    setzeGewaehlt(gewaehlt.includes(name) ? gewaehlt.filter((n) => n !== name) : [...gewaehlt, name])

  return (
    <section>
      <h2>Journal-Suche</h2>
      <p className="sicht">
        Suche über Notiztexte und Tags. Tags wählen: „alle“ verlangt alle gewählten Tags, „irgendeines“ mindestens einen.
      </p>
      <p>
        <input type="search" value={q} onChange={(e) => setzeQ(e.target.value)} placeholder="Suchbegriff in Notizen und Tags" size={40} />{' '}
        <label><input type="checkbox" checked={mitAnhang} onChange={(e) => setzeMitAnhang(e.target.checked)} /> nur mit Anhang</label>
      </p>
      <p>
        {tagListe.length === 0 && <span className="leer">Noch keine Tags.</span>}
        {tagListe.map((t) => (
          <label key={t.name} style={{ marginRight: '0.8em' }}>
            <input type="checkbox" checked={gewaehlt.includes(t.name)} onChange={() => umschalten(t.name)} /> {t.name} ({t.anzahl})
          </label>
        ))}
        {gewaehlt.length > 1 && (
          <select value={modus} onChange={(e) => setzeModus(e.target.value as 'alle' | 'irgendeines')}>
            <option value="alle">alle dieser Tags</option>
            <option value="irgendeines">irgendeines dieser Tags</option>
          </select>
        )}
      </p>
      {fehler && <p className="fehler">{fehler}</p>}
      {treffer === null && !fehler && <p className="laedt">Suche …</p>}
      {treffer !== null && (
        <>
          <p className="sicht">{treffer.length} Treffer, jüngste Aktivität zuerst</p>
          <ul className="notizen">
            {treffer.map((t) => (
              <li key={`${t.scope_typ}-${t.scope_id}`}>
                <strong>
                  {t.kontext?.link ? <Link to={t.kontext.link}>{t.kontext.text}</Link> : (t.kontext?.text ?? `${BEREICHE[t.scope_typ] ?? t.scope_typ} ${t.scope_id}`)}
                </strong>{' '}
                <span className="sicht">
                  {t.kontext ? `${datumDe(t.kontext.von)}${t.kontext.bis ? ` – ${datumDe(t.kontext.bis)}` : ''}` : ''}
                  {t.kontext?.strategie ? ` · ${t.kontext.strategie}` : ''}
                  {t.anzahl_anhaenge > 0 ? ` · ${t.anzahl_anhaenge} Anhang/Anhänge` : ''}
                </span>
                {t.tags.length > 0 && <div className="sicht">Tags: {t.tags.join(', ')}</div>}
                {t.notizen.map((n) => <div key={n.id}>„{n.snippet}“</div>)}
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
