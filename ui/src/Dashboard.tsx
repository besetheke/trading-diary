import { useEffect, useState } from 'react'
import { fehlerText, holeEquity } from './api'
import type { Equity } from './api'
import { datum, geld } from './format'

// AP-06e/Dashboard: Equity-Kurve und Drawdown als Tabellen, kein Diagramm —
// stil.css nennt das ausdrücklich als Gestaltungsprinzip der Oberfläche
// ("Lesen und Nachvollziehen, kein Diagramm"). Geld bleibt Zeichenkette,
// nichts wird hier gerechnet (Vertrag 8/9 wie überall).

export default function Dashboard(): JSX.Element {
  const [equity, setzeEquity] = useState<Equity | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    holeEquity()
      .then((ergebnis) => {
        if (!abgebrochen) setzeEquity(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [])

  if (fehler) {
    return (
      <section className="fehler">
        <h3>Das Dashboard konnte nicht geladen werden</h3>
        <p>{fehler}</p>
      </section>
    )
  }

  if (equity === null) {
    return <p className="laedt">Lade Dashboard …</p>
  }

  const letzterTag = equity.tage.length > 0 ? equity.tage[equity.tage.length - 1] : null

  return (
    <section>
      <h2>Dashboard</h2>
      <p className="sicht fussnote">
        Equity-Kurve und Monatsübersicht, Kontosicht, in EUR — nichts gerechnet, nur
        durchgereicht von <code>GET /equity</code>.
      </p>

      {equity.tage.length === 0 ? (
        <section className="hinweis">
          <p>Noch keine abgeschlossene Struktur mit Kurs — die Equity-Kurve ist leer.</p>
        </section>
      ) : (
        <>
          <dl className="kopf">
            <div>
              <dt>Stand</dt>
              <dd>
                {letzterTag ? geld(letzterTag.kumuliert_eur, 'EUR') : '—'}
                {letzterTag ? ` (${datum(letzterTag.datum)})` : ''}
              </dd>
            </div>
            <div>
              <dt>Maximaler Drawdown</dt>
              <dd>
                {geld(equity.max_drawdown_eur, 'EUR')}
                {equity.max_drawdown_datum ? ` (${datum(equity.max_drawdown_datum)})` : ''}
              </dd>
            </div>
            <div>
              <dt>Tage mit Aktivität</dt>
              <dd>{equity.tage.length}</dd>
            </div>
          </dl>

          <h3>Monatsübersicht</h3>
          <table>
            <thead>
              <tr>
                <th>Monat</th>
                <th className="zahl">Strukturen</th>
                <th className="zahl">Summe netto</th>
                <th className="zahl">Durchschnitt</th>
                <th className="zahl">Trefferquote</th>
                <th className="zahl">Kursmangel</th>
              </tr>
            </thead>
            <tbody>
              {equity.monate.map((m) => (
                <tr key={m.monat}>
                  <td>{m.monat}</td>
                  <td className="zahl">{m.anzahl_strukturen}</td>
                  <td className="zahl">{geld(m.summe_netto_eur, 'EUR')}</td>
                  <td className="zahl">
                    {m.durchschnitt_netto_eur === null
                      ? '—'
                      : geld(m.durchschnitt_netto_eur, 'EUR')}
                  </td>
                  <td className="zahl">{m.trefferquote ?? '—'}</td>
                  <td className="zahl">{m.anzahl_strukturen_kurs_fehlt}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <details className="tagesreihe">
            <summary>Tagesreihe ({equity.tage.length} Tage)</summary>
            <table>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th className="zahl">Strukturen</th>
                  <th className="zahl">Netto</th>
                  <th className="zahl">Kumuliert</th>
                  <th className="zahl">Drawdown</th>
                  <th className="zahl">Kursmangel</th>
                </tr>
              </thead>
              <tbody>
                {equity.tage
                  .slice()
                  .reverse()
                  .map((t) => (
                    <tr key={t.datum}>
                      <td>{datum(t.datum)}</td>
                      <td className="zahl">{t.anzahl_strukturen}</td>
                      <td className="zahl">{geld(t.netto_eur, 'EUR')}</td>
                      <td className="zahl">{geld(t.kumuliert_eur, 'EUR')}</td>
                      <td className="zahl">{geld(t.drawdown_eur, 'EUR')}</td>
                      <td className="zahl">{t.anzahl_strukturen_kurs_fehlt}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </section>
  )
}
