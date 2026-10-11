import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeUeberleitung } from './api'
import type { Ueberleitung as UeberleitungDaten, UeberleitungSpalte } from './api'
import Betrag from './Betrag'
import { datumDe } from './format'

// AP-08u/AP-08u2: Vom Ergebnis zum Kontostand — Journal (selbst gerechnet) und
// IB (Bericht) nebeneinander, beide Spalten ergeben denselben Kontowert; darunter
// die Zerlegung des Unterschieds im realisierten Ergebnis. Alles Werte der API
// (GET /ueberleitung), nichts im Browser gerechnet (Vertrag 8).

type Feld = keyof UeberleitungSpalte

const ZEILEN: { feld: Feld; titel: string; journal: string; ib: string }[] = [
  {
    feld: 'einzahlungen',
    titel: 'Einzahlungen (kumuliert)',
    journal: 'Aus IBs Cash-Buchungen',
    ib: 'Gleiche Quelle',
  },
  {
    feld: 'realisiert',
    titel: '+ Realisiertes Ergebnis',
    journal: 'Equity: geschlossene Strukturen und lose Aktiengeschäfte',
    ib: 'Σ fifoPnlRealized je Ausführung, netto nach Kommission',
  },
  {
    feld: 'unrealisiert',
    titel: '+ Unrealisiertes Ergebnis',
    journal: 'IBs letzter Kurs gegen den Journal-Einstand',
    ib: 'IBs Wert je offener Position',
  },
  {
    feld: 'sonstige_buchungen',
    titel: '+ Sonstige Buchungen',
    journal: 'Dividenden, Zinsen, Gebühren, Quellensteuer',
    ib: 'Gleiche Quelle',
  },
  {
    feld: 'rest',
    titel: '+ Rest',
    journal: 'Saldo zum Kontowert — enthält Währungsmethode und Zeitpunkt (siehe unten)',
    ib: 'Saldo: Währung, Abgrenzungen',
  },
]

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
  if (
    daten.stichtag === null ||
    daten.ib === null ||
    daten.journal === null ||
    daten.journal_spalte === null ||
    daten.unterschied_spalte === null ||
    daten.abgleich_realisiert === null
  ) {
    return null
  }

  const ib: UeberleitungSpalte = { ...daten.ib, einzahlungen: daten.einzahlungen ?? '0' }
  const journal = daten.journal_spalte
  const unterschied = daten.unterschied_spalte
  const a = daten.abgleich_realisiert
  const luecke = daten.abdeckung.ausfuehrungen - daten.abdeckung.mit_ib_wert

  return (
    <section className="ueberleitung">
      <h3>Vom Ergebnis zum Kontostand</h3>
      <p className="sicht">
        Stand {datumDe(daten.stichtag)}, gesamte Historie, EUR. Links die Rechnung des Journals,
        rechts IBs Bericht — beide Spalten ergeben denselben Kontowert.
      </p>
      <table className="ueberleitung">
        <thead>
          <tr>
            <th>Posten</th>
            <th className="zahl">Journal (berechnet)</th>
            <th className="zahl">IB (Bericht)</th>
            <th className="zahl">Unterschied</th>
            <th>Quelle</th>
          </tr>
        </thead>
        <tbody>
          {ZEILEN.map((z) => (
            <tr key={z.feld}>
              <td>{z.titel}</td>
              <td className="zahl">
                <Betrag wert={journal[z.feld]} />
              </td>
              <td className="zahl">
                <Betrag wert={ib[z.feld]} />
              </td>
              <td className="zahl">
                <Betrag wert={unterschied[z.feld]} />
              </td>
              <td>
                Journal: {z.journal}. IB: {z.ib}.
                {z.feld === 'unrealisiert' ? (
                  <>
                    {' '}
                    <Link to="/bestand">Depot</Link>
                  </>
                ) : null}
              </td>
            </tr>
          ))}
          <tr className="summe">
            <td>= Kontowert laut IB</td>
            <td className="zahl">
              <Betrag wert={daten.kontowert} />
            </td>
            <td className="zahl">
              <Betrag wert={daten.kontowert} />
            </td>
            <td className="zahl">—</td>
            <td>
              Gewinn laut IB: <Betrag wert={daten.gewinn_ib} />
            </td>
          </tr>
        </tbody>
      </table>

      <h4>Warum das realisierte Ergebnis abweicht</h4>
      <p className="sicht">
        Verglichen wird jede schließende Ausführung: {a.zeilen_gleich.toLocaleString('de-DE')}{' '}
        stimmen mit IB genau überein, {a.zeilen_abweichend.toLocaleString('de-DE')} weichen ab —
        fast alle im Zusammenhang mit Zuteilung oder Ausübung.
      </p>
      <table className="ueberleitung">
        <tbody>
          <tr>
            <td>Prämien im Einstand gehaltener Aktien</td>
            <td className="zahl">
              <Betrag wert={a.praemien_im_einstand} />
            </td>
            <td>
              Das Journal zählt die Prämie einer Zuteilung sofort als Ertrag; IB schlägt sie auf
              den Aktieneinstand und weist sie erst beim Verkauf aus. Bei noch gehaltenen Aktien
              steht sie bei IB im unrealisierten Ergebnis (Kurs der Eröffnung).
            </td>
          </tr>
          <tr>
            <td>Währungsmethode</td>
            <td className="zahl">
              <Betrag wert={a.waehrungsmethode} />
            </td>
            <td>
              Das Journal rechnet jede Seite zum Kurs ihres Tages (wie für die Steuer), IB das
              Ergebnis in Positionswährung zum Kurs der Schließung.
            </td>
          </tr>
          <tr>
            <td>Zeitpunkt</td>
            <td className="zahl">
              <Betrag wert={a.zeitpunkt_beitrag} />
            </td>
            <td>
              {a.anzahl_legs_offene_strukturen} geschlossene Legs in noch offenen Strukturen: Das
              Journal zählt sie erst, wenn die ganze Struktur geschlossen ist; IB je Ausführung.
            </td>
          </tr>
          <tr>
            <td>Rest</td>
            <td className="zahl">
              <Betrag wert={a.nicht_zugeordnet} />
            </td>
            <td>
              Was nach den drei Ursachen bleibt, zerlegt je Basiswert (Aktie und ihre Optionen über
              die ISIN, alte und neue Kennung über Kapitalmaßnahmen verbunden):
              <details className="rest-details">
                <summary>
                  Kurseffekt <Betrag wert={a.kurseffekt_praemien} /> und{' '}
                  {a.einzelreste.length} Einstandsabweichungen
                </summary>
                <p>
                  <strong>Kurseffekt</strong>: Die verschobene Prämie gleicht sich in Positionswährung
                  aus, nicht in Euro — das Journal rechnet sie zum Kurs der Zuteilung, IB zum Kurs
                  des späteren Aktienverkaufs.
                </p>
                <p>
                  <strong>Einstandsabweichungen</strong> in Positionswährung: IB führt den Einstand
                  anders — z. B. der Barteil einer Fusion (PARA → PSKY), Kapitalrückzahlungen bei
                  Ausschüttungswerten (IB senkt den Einstand nachträglich), Devisentausch.
                </p>
                <table>
                  <tbody>
                    {a.einzelreste.map((r) => (
                      <tr key={r.gruppe}>
                        <td>{r.gruppe}</td>
                        <td className="zahl">
                          <Betrag wert={r.nativ} waehrung={r.waehrung} />
                        </td>
                        <td className="zahl">
                          <Betrag wert={r.eur} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </td>
          </tr>
          <tr className="summe">
            <td>= Unterschied realisiert (Journal − IB)</td>
            <td className="zahl">
              <Betrag wert={daten.journal.differenz_realisiert} />
            </td>
            <td />
          </tr>
        </tbody>
      </table>
      {luecke > 0 || daten.anzahl_kurs_fehlt > 0 ? (
        <p className="sicht fussnote">
          {luecke > 0
            ? `IBs realisierter Wert liegt nur für ${daten.abdeckung.mit_ib_wert} von ${daten.abdeckung.ausfuehrungen} Ausführungen vor. `
            : ''}
          {daten.anzahl_kurs_fehlt > 0
            ? `${daten.anzahl_kurs_fehlt} Zeile(n) ohne Umrechnungskurs sind nicht enthalten.`
            : ''}
        </p>
      ) : null}
    </section>
  )
}
