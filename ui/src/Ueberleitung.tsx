import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeUeberleitung } from './api'
import type { Ueberleitung as UeberleitungDaten } from './api'
import Betrag from './Betrag'
import { datumDe } from './format'

// AP-08u: Vom Ergebnis zum Kontostand. IBs Gewinn (Kontowert minus
// Einzahlungen) in seine Bestandteile zerlegt, daneben das realisierte Ergebnis
// des Journals. Alles Werte der API (GET /ueberleitung), nichts im Browser
// gerechnet (Vertrag 8); jede Zeile nennt ihre Quelle.

export default function Ueberleitung(): JSX.Element | null {
  const [daten, setzeDaten] = useState<UeberleitungDaten | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    holeUeberleitung()
      .then((ergebnis) => {
        if (!abgebrochen) setzeDaten(ergebnis)
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
        <h3>Die Überleitung konnte nicht geladen werden</h3>
        <p>{fehler}</p>
      </section>
    )
  }
  if (daten === null) return <p className="laedt">Lade Überleitung …</p>
  if (daten.stichtag === null || daten.ib === null || daten.journal === null) return null

  const { ib, journal } = daten
  const luecke = daten.abdeckung.ausfuehrungen - daten.abdeckung.mit_ib_wert

  return (
    <section className="ueberleitung">
      <h3>Vom Ergebnis zum Kontostand</h3>
      <p className="sicht">
        Stand {datumDe(daten.stichtag)}, gesamte Historie, EUR. Jede Zeile ist ein Wert aus IBs
        Bericht; „Rest“ ist, was IB nicht einzeln ausweist.
      </p>
      <table className="ueberleitung">
        <thead>
          <tr>
            <th>Posten</th>
            <th className="zahl">Betrag</th>
            <th>Was es ist</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Einzahlungen (kumuliert)</td>
            <td className="zahl">
              <Betrag wert={daten.einzahlungen} />
            </td>
            <td>Eingezahltes Geld abzüglich Auszahlungen</td>
          </tr>
          <tr>
            <td>+ Realisiertes Ergebnis laut IB</td>
            <td className="zahl">
              <Betrag wert={ib.realisiert} />
            </td>
            <td>Abgeschlossene Geschäfte, netto nach Kommission</td>
          </tr>
          <tr>
            <td>+ Unrealisiertes Ergebnis</td>
            <td className="zahl">
              <Betrag wert={ib.unrealisiert} />
            </td>
            <td>
              Offene Positionen zum letzten Kurs, <Link to="/bestand">siehe Depot</Link>
              {daten.bestand_stichtag ? ` (Stand ${datumDe(daten.bestand_stichtag)})` : ''}
            </td>
          </tr>
          <tr>
            <td>+ Sonstige Buchungen</td>
            <td className="zahl">
              <Betrag wert={ib.sonstige_buchungen} />
            </td>
            <td>Dividenden, Zinsen, Gebühren, Quellensteuer</td>
          </tr>
          <tr>
            <td>+ Währung und Abgrenzungen (Rest)</td>
            <td className="zahl">
              <Betrag wert={ib.rest} />
            </td>
            <td>
              Differenz zum Kontowert: Umrechnung von Fremdwährungs-Cash, aufgelaufene Zinsen und
              Dividenden, alles, was IB nicht einzeln ausweist
            </td>
          </tr>
          <tr className="summe">
            <td>= Kontowert laut IB</td>
            <td className="zahl">
              <Betrag wert={daten.kontowert} />
            </td>
            <td>
              Davon Gewinn laut IB: <Betrag wert={daten.gewinn_ib} />
            </td>
          </tr>
        </tbody>
      </table>

      <h4>Das realisierte Ergebnis im Journal</h4>
      <table className="ueberleitung">
        <tbody>
          <tr>
            <td>Realisiert laut Journal (Equity)</td>
            <td className="zahl">
              <Betrag wert={journal.realisiert} />
            </td>
          </tr>
          <tr>
            <td>Realisiert laut IB</td>
            <td className="zahl">
              <Betrag wert={ib.realisiert} />
            </td>
          </tr>
          <tr className="summe">
            <td>Unterschied (Journal minus IB)</td>
            <td className="zahl">
              <Betrag wert={journal.differenz_realisiert} />
            </td>
          </tr>
        </tbody>
      </table>
      <p className="sicht fussnote">
        Der Unterschied ist <strong>überwiegend Methode</strong>: Das Journal zählt die Prämie einer
        Zuteilung sofort als Ertrag der Option; IB schlägt sie auf den Einstand der Aktie und
        weist sie erst beim Verkauf der Aktie aus (bei noch gehaltenen Aktien steht sie im
        unrealisierten Ergebnis). Dazu rechnet IB das Ergebnis zum Kurs des Schließungstags, das
        Journal jede Seite zum Kurs ihrer Ausführung. Ein Rest ist noch nicht im Einzelnen
        belegt (OF-78).
        {luecke > 0
          ? ` Achtung: IBs realisierter Wert liegt nur für ${daten.abdeckung.mit_ib_wert} von ${daten.abdeckung.ausfuehrungen} Ausführungen vor.`
          : ''}
        {daten.anzahl_kurs_fehlt > 0
          ? ` ${daten.anzahl_kurs_fehlt} Zeile(n) ohne Umrechnungskurs sind nicht enthalten.`
          : ''}
      </p>
    </section>
  )
}
