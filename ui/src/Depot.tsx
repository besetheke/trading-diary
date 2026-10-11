import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeDepot } from './api'
import type { Depot as DepotDaten, DepotPosition } from './api'
import Betrag from './Betrag'
import { betrag, datumDe, mengeDe } from './format'

// AP-08d: das Depot — der Bestand laut IB zum letzten Bericht, je Position mit
// letztem bekanntem Kurs, Marktwert und unrealisiertem Ergebnis. Alles Werte
// der Quelle (GET /depot), nichts im Browser gerechnet oder neu bewertet
// (Vertrag 8). Die Positionsliste zeigt Ketten von Geschäften; das Depot zeigt,
// was du jetzt hältst — Aktien aus Zuteilungen eingeschlossen.

function Beschreibung({ p }: { p: DepotPosition }): JSX.Element {
  if (p.anlageklasse === 'OPT' || p.anlageklasse === 'FOP') {
    const teile = [
      p.verfall ? datumDe(p.verfall) : null,
      p.strike,
      p.seite,
    ].filter((t): t is string => t !== null)
    return <>{teile.join(' · ')}</>
  }
  return <>{p.symbol}</>
}

function Tabelle({ titel, positionen }: { titel: string; positionen: DepotPosition[] }): JSX.Element | null {
  if (positionen.length === 0) return null
  return (
    <>
      <h3>
        {titel} ({positionen.length})
      </h3>
      <table className="depot">
        <thead>
          <tr>
            <th>Basiswert</th>
            <th>Position</th>
            <th className="zahl">Menge</th>
            <th className="zahl">Einstand</th>
            <th className="zahl">Letzter Kurs</th>
            <th className="zahl">Marktwert</th>
            <th className="zahl">Marktwert (EUR)</th>
            <th className="zahl">Unrealisiert</th>
            <th className="zahl">Unrealisiert (EUR)</th>
          </tr>
        </thead>
        <tbody>
          {positionen.map((p) => (
            <tr key={p.conid}>
              <td>
                <Link to={`/?basiswert=${encodeURIComponent(p.basiswert)}`}>{p.basiswert}</Link>
              </td>
              <td>
                <Beschreibung p={p} />
              </td>
              <td className="zahl" title={p.menge}>
                {mengeDe(p.menge)}
              </td>
              <td className="zahl" title={p.einstandskurs ?? undefined}>
                {p.einstandskurs === null ? '—' : betrag(p.einstandskurs)} {p.waehrung}
              </td>
              <td className="zahl" title={p.kurs ?? undefined}>
                {p.kurs === null ? '—' : betrag(p.kurs)} {p.waehrung}
              </td>
              <td className="zahl">
                <Betrag wert={p.marktwert} waehrung={p.waehrung} />
              </td>
              <td className="zahl">
                <Betrag wert={p.marktwert_eur} />
              </td>
              <td className="zahl">
                <Betrag wert={p.unrealisiert} waehrung={p.waehrung} />
              </td>
              <td className="zahl">
                <Betrag wert={p.unrealisiert_eur} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  )
}

export default function Depot(): JSX.Element {
  const [depot, setzeDepot] = useState<DepotDaten | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    holeDepot()
      .then((ergebnis) => {
        if (!abgebrochen) setzeDepot(ergebnis)
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
        <h2>Depot</h2>
        <p>{fehler}</p>
      </section>
    )
  }
  if (depot === null) return <p className="laedt">Lade Depot …</p>
  if (depot.stichtag === null) {
    return (
      <section className="hinweis">
        <h2>Depot</h2>
        <p>Noch kein Bestand importiert — die Flex-Query braucht den Abschnitt „Open Positions“.</p>
      </section>
    )
  }

  const aktien = depot.positionen.filter((p) => p.anlageklasse === 'STK')
  const optionen = depot.positionen.filter((p) => p.anlageklasse === 'OPT' || p.anlageklasse === 'FOP')
  const uebrige = depot.positionen.filter(
    (p) => p.anlageklasse !== 'STK' && p.anlageklasse !== 'OPT' && p.anlageklasse !== 'FOP',
  )

  return (
    <section className="depot-seite">
      <h2>Depot</h2>
      <dl className="kopf">
        <div>
          <dt>Stand (letzter Bericht)</dt>
          <dd>{datumDe(depot.stichtag)}</dd>
        </div>
        <div>
          <dt>Marktwert gesamt (EUR)</dt>
          <dd>
            <Betrag wert={depot.summen.marktwert_eur} />
          </dd>
        </div>
        <div>
          <dt>Unrealisiert gesamt (EUR)</dt>
          <dd>
            <Betrag wert={depot.summen.unrealisiert_eur} />
          </dd>
        </div>
        <div>
          <dt>Offene Positionen</dt>
          <dd>{depot.positionen.length}</dd>
        </div>
      </dl>

      <table className="depot">
        <thead>
          <tr>
            <th>Klasse</th>
            <th className="zahl">Positionen</th>
            <th className="zahl">Marktwert (EUR)</th>
            <th className="zahl">Unrealisiert (EUR)</th>
          </tr>
        </thead>
        <tbody>
          {depot.summen.je_klasse.map((k) => (
            <tr key={k.anlageklasse}>
              <td>{k.anlageklasse}</td>
              <td className="zahl">{k.anzahl}</td>
              <td className="zahl">
                <Betrag wert={k.marktwert_eur} />
              </td>
              <td className="zahl">
                <Betrag wert={k.unrealisiert_eur} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Tabelle titel="Aktien" positionen={aktien} />
      <Tabelle titel="Optionen" positionen={optionen} />
      <Tabelle titel="Übrige" positionen={uebrige} />

      <p className="sicht fussnote">
        Bestand laut IB zum {datumDe(depot.stichtag)}: Kurs, Marktwert und unrealisiertes Ergebnis
        sind IBs Werte des letzten Berichts (der Kurs ist der letzte bekannte, kein Echtzeitkurs).
        EUR mit IBs Umrechnungskurs der Zeile. Das <strong>unrealisierte Ergebnis ist hier kein
        Teil der Equity</strong>: Die Equity zählt nur abgeschlossene Geschäfte. Der Marktwert aller
        Positionen entspricht dem Anteil „Aktien + Optionen" am Kontowert laut IB im Dashboard.
      </p>
    </section>
  )
}
