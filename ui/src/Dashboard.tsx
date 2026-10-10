import { useEffect, useState } from 'react'
import { fehlerText, holeEquity } from './api'
import type { Equity } from './api'
import Betrag from './Betrag'
import { datumDe, prozent } from './format'

// AP-06e/Dashboard: Equity-Kurve und Drawdown als Tabellen, kein Diagramm —
// stil.css nennt das ausdrücklich als Gestaltungsprinzip der Oberfläche
// ("Lesen und Nachvollziehen, kein Diagramm"). Geld bleibt Zeichenkette,
// nichts wird hier gerechnet (Vertrag 8/9 wie überall). AP-08f1: deutsche
// Schreibweise, Rohwert im title.

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
        Equity-Kurve und Monatsübersicht, Kontosicht, in EUR — Ergebnis am Tag der
        Schließung. Der genaue Wert steht im Tooltip.
      </p>

      {equity.tage.length === 0 ? (
        <section className="hinweis">
          <p>Noch keine abgeschlossene Struktur mit Kurs — die Equity-Kurve ist leer.</p>
        </section>
      ) : (
        <>
          <dl className="kopf">
            <div>
              <dt>Stand {letzterTag ? `(${datumDe(letzterTag.datum)})` : ''}</dt>
              <dd>
                <Betrag wert={letzterTag ? letzterTag.kumuliert_eur : null} />
              </dd>
            </div>
            <div>
              <dt>
                Maximaler Drawdown
                {equity.max_drawdown_datum ? ` (${datumDe(equity.max_drawdown_datum)})` : ''}
              </dt>
              <dd>
                <Betrag wert={equity.max_drawdown_eur} />
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
              {equity.monate
                .slice()
                .reverse()
                .map((m) => (
                  <tr key={m.monat}>
                    <td>{m.monat}</td>
                    <td className="zahl">{m.anzahl_strukturen}</td>
                    <td className="zahl">
                      <Betrag wert={m.summe_netto_eur} />
                    </td>
                    <td className="zahl">
                      <Betrag wert={m.durchschnitt_netto_eur} />
                    </td>
                    <td className="zahl">{prozent(m.trefferquote)}</td>
                    <td className="zahl">{m.anzahl_strukturen_kurs_fehlt || ''}</td>
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
                      <td>{datumDe(t.datum)}</td>
                      <td className="zahl">{t.anzahl_strukturen}</td>
                      <td className="zahl">
                        <Betrag wert={t.netto_eur} />
                      </td>
                      <td className="zahl">
                        <Betrag wert={t.kumuliert_eur} />
                      </td>
                      <td className="zahl">
                        <Betrag wert={t.drawdown_eur} />
                      </td>
                      <td className="zahl">{t.anzahl_strukturen_kurs_fehlt || ''}</td>
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
