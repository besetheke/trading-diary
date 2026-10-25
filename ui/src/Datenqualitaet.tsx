import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeDatenqualitaet } from './api'
import type { BetriebsLauf, Datenqualitaet as Daten } from './api'
import { betrag, datumDe, zeitDe } from './format'

// M04: eine einheitliche Arbeitsliste statt verstreuter Hinweise. Oben der Betriebsstatus (letzter erfolgreicher Abruf,
// Import und Rebuild getrennt, dazu Fehlschläge), darunter die Punkte mit Zeitraum, betroffenen Objekten und Lösungsweg.

const NAMEN: Record<string, string> = { abruf: 'Abruf', import: 'Import', rebuild: 'Neuaufbau (Rebuild)' }
const SCHWERE: Record<string, string> = { fehler: '✘ Fehler', warnung: '⚠ Warnung', hinweis: 'ⓘ Hinweis' }

function LaufZeile({ name, lauf }: { name: string; lauf: BetriebsLauf }): JSX.Element {
  const z = lauf.zuletzt
  const schlecht = z && z.ergebnis !== 'ok' && (lauf.zuletzt_ok === null || z.zeit > lauf.zuletzt_ok)
  return (
    <tr className={schlecht ? 'warnung' : undefined}>
      <td>{name}</td>
      <td>{lauf.zuletzt_ok ? zeitDe(lauf.zuletzt_ok) : 'noch nie protokolliert'}{lauf.herkunft ? ` (${lauf.herkunft})` : ''}</td>
      <td>{z ? `${zeitDe(z.zeit)}: ${z.ergebnis}${z.meldung ? ` — ${z.meldung}` : ''}` : '—'}</td>
    </tr>
  )
}

export default function Datenqualitaet(): JSX.Element {
  const [daten, setzeDaten] = useState<Daten | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  useEffect(() => {
    holeDatenqualitaet(false).then(setzeDaten).catch((e) => setzeFehler(fehlerText(e)))
  }, [])
  if (fehler) return <p className="fehler">{fehler}</p>
  if (!daten) return <p className="laedt">Prüfe die Datenqualität (der Abgleich dauert einige Sekunden) …</p>
  return (
    <section>
      <h2>Datenqualität · {datumDe(daten.stand)}</h2>
      <p className="sicht">
        Gesamtstand: <strong>{daten.status === 'ok' ? 'in Ordnung' : daten.status === 'warnung' ? 'Warnungen offen' : 'Fehler offen'}</strong>.
        Jeder Punkt nennt seinen Zeitraum: alte Fragen blockieren neue, unabhängige Zeiträume nicht.
      </p>
      <h3>Betriebsstatus</h3>
      <table className="positionen dichte-kompakt">
        <thead><tr><th></th><th>zuletzt erfolgreich</th><th>jüngster Lauf</th></tr></thead>
        <tbody>
          <LaufZeile name={NAMEN.abruf} lauf={daten.laeufe.abruf} />
          <LaufZeile name={NAMEN.import} lauf={daten.laeufe.import} />
          <LaufZeile name={NAMEN.rebuild} lauf={daten.laeufe.rebuild} />
        </tbody>
      </table>
      <h3>Arbeitsliste ({daten.punkte.length})</h3>
      {daten.punkte.length === 0 && <p className="leer">Nichts offen.</p>}
      <table className="positionen dichte-kompakt">
        <thead>
          <tr><th>Schwere</th><th>Punkt</th><th>Anzahl</th><th>Zeitraum</th><th>Betroffen</th><th>Lösungsweg</th></tr>
        </thead>
        <tbody>
          {daten.punkte.map((p) => (
            <tr key={p.id} className={p.schwere === 'fehler' ? 'warnung' : undefined}>
              <td>{SCHWERE[p.schwere]}</td>
              <td>{p.link ? <Link to={p.link}>{p.titel}</Link> : p.titel}</td>
              <td className="zahl">{p.anzahl ?? ''}{p.betrag ? ` · ${betrag(p.betrag)} €` : ''}</td>
              <td>{p.von ? `${datumDe(p.von)}${p.bis && p.bis !== p.von ? ` – ${datumDe(p.bis)}` : ''}` : '—'}</td>
              <td>{p.betroffen.length ? p.betroffen.join(', ') : '—'}</td>
              <td>{p.loesung}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
