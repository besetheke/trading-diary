import { useEffect, useState } from 'react'
import { fehlerText, holeEquity } from './api'
import type { Equity } from './api'
import Betrag from './Betrag'
import Balken from './diagramm/Balken'
import Flaeche from './diagramm/Flaeche'
import Linie from './diagramm/Linie'
import { datumDe, prozent } from './format'
import { useZeitraum } from './zeitraum'

// AP-06e/Dashboard: Equity-Kurve und Drawdown. Seit AP-08g1 (D1–D3 in
// auftraege/AP-08f.md) stehen über den Tabellen eigene SVG-Diagramme —
// Linie, Fläche, Balken, ohne Diagramm-Bibliothek; die Tabellen bleiben
// darunter (D3: Nachvollziehen geht vor). Geld bleibt Zeichenkette, nichts
// wird hier gerechnet (Vertrag 8/9 wie überall; Ausnahme nur für Pixel in
// den Bausteinen, D2). AP-08f1: deutsche Schreibweise, Rohwert im title.

export default function Dashboard(): JSX.Element {
  const [zeitraum] = useZeitraum()
  const [equity, setzeEquity] = useState<Equity | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    setzeEquity(null)
    setzeFehler(null)
    holeEquity(zeitraum.von, zeitraum.bis)
      .then((ergebnis) => {
        if (!abgebrochen) setzeEquity(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  const imZeitraum = zeitraum.von !== null || zeitraum.bis !== null

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
        Schließung.
        {imZeitraum
          ? ' Im gewählten Zeitraum beginnt die Kurve bei 0; der Drawdown zählt nur darin.'
          : ''}
      </p>

      {equity.tage.length === 0 ? (
        <section className="hinweis">
          <p>
            {imZeitraum
              ? 'Im gewählten Zeitraum wurde keine Struktur mit Kurs geschlossen.'
              : 'Noch keine abgeschlossene Struktur mit Kurs — die Equity-Kurve ist leer.'}
          </p>
        </section>
      ) : (
        <>
          <dl className="kopf">
            <div>
              <dt>
                {imZeitraum ? 'Ergebnis im Zeitraum' : 'Stand'}{' '}
                {letzterTag ? `(bis ${datumDe(letzterTag.datum)})` : ''}
              </dt>
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

          <h3>Equity-Kurve</h3>
          <Linie punkte={equity.tage.map((t) => ({ x: t.datum, y: t.kumuliert_eur }))} />

          <h3>Drawdown</h3>
          <Flaeche punkte={equity.tage.map((t) => ({ x: t.datum, y: t.drawdown_eur }))} />

          <h3>Monatsübersicht</h3>
          <Balken balken={equity.monate.map((m) => ({ x: m.monat, y: m.summe_netto_eur }))} />
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
