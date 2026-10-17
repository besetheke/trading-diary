import { useEffect, useState } from 'react'
import { fehlerText, holeSteuer } from './api'
import type { SteuerAntwort } from './api'
import Betrag from './Betrag'

// Steuer (AP-10): die Töpfe je Zuflussjahr und die Erträge, wie die API sie aufbereitet. Hier wird nichts
// gerechnet — weder verrechnet noch umgerechnet. Das ist eine Aufbereitung für den Steuerberater, keine
// Steuerberatung und keine Verlustverrechnung.

const TOPF_NAME: Record<string, string> = { aktien: 'Aktien', termingeschaefte: 'Termingeschäfte' }

export default function Steuer(): JSX.Element {
  const [daten, setzeDaten] = useState<SteuerAntwort | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [jahr, setzeJahr] = useState<number | null>(null)

  useEffect(() => {
    let abgebrochen = false
    holeSteuer()
      .then((d) => {
        if (abgebrochen) return
        setzeDaten(d)
        setzeJahr(d.jahre.length > 0 ? d.jahre[d.jahre.length - 1].jahr : null)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [])

  if (fehler) return <p className="fehler">{fehler}</p>
  if (daten === null) return <p className="laedt">Bereite die Steuerzahlen auf …</p>

  const toepfe = daten.toepfe.filter((t) => t.jahr === jahr)
  const kursFehlt = daten.jahre.reduce((s, j) => s + j.eur_kurs_fehlt, 0)
  const ungeklaert = daten.jahre.reduce((s, j) => s + j.ungeklaert, 0)
  return (
    <section>
      <h2>Steuer — Aufbereitung nach Zuflussjahr</h2>
      <p className="sicht">
        Aufbereitung für den Steuerberater, <strong>keine Steuerberatung und keine Verlustverrechnung</strong>: Es gilt
        das Jahr der schließenden Ausführung (Zuflussprinzip), getrennt nach Aktien und Termingeschäften. Euro-Beträge
        rechnen mit dem Buchungskurs der Schließung, den auch IB verwendet. Dividenden, Quellensteuer, Zinsen und
        Gebühren stehen daneben, nicht in den Töpfen.
      </p>
      {(kursFehlt > 0 || ungeklaert > 0 || daten.fehler.length > 0) && (
        <p className="hinweis">
          {kursFehlt > 0 ? `${kursFehlt} Geschäfte ohne Buchungskurs zählen nicht in den Euro-Summen. ` : ''}
          {ungeklaert > 0 ? `${ungeklaert} Geschäfte mit ungeklärter Basis stehen außerhalb der Summen. ` : ''}
          {daten.fehler.length > 0 ? `${daten.fehler.length} Hinweise in der Fehlerliste (CSV-Export).` : ''}
        </p>
      )}

      <h3>Jahresübersicht (EUR)</h3>
      <div className="tabelle-rahmen">
        <table className="positionen dichte-kompakt">
          <thead>
            <tr>
              <th>Zuflussjahr</th>
              <th className="zahl">Aktien</th>
              <th className="zahl">Termingeschäfte</th>
              <th
                className="zahl"
                title="Prämien von Optionen, die mit Lieferung endeten (Zuteilung/Ausübung): Sie stehen in den Termingeschäften, die Aktie trägt den Gegenposten im Aktien-Topf — siehe Fragen unten"
              >
                davon Prämie bei Lieferung
              </th>
              <th className="zahl">Dividenden</th>
              <th className="zahl">Quellensteuer</th>
              <th className="zahl">Zinsen erhalten</th>
              <th className="zahl">Zinsen gezahlt</th>
              <th className="zahl">Gebühren</th>
              <th>Export</th>
            </tr>
          </thead>
          <tbody>
            {daten.jahre.map((j) => (
              <tr key={j.jahr} className={j.jahr === jahr ? 'summe' : undefined}>
                <td>
                  <button
                    type="button"
                    className="sortierer"
                    onClick={() => setzeJahr(j.jahr)}
                    title="Töpfe dieses Jahres unten zeigen"
                  >
                    {j.jahr}
                  </button>
                </td>
                <td className="zahl"><Betrag wert={j.aktien_eur} /></td>
                <td className="zahl"><Betrag wert={j.termin_eur} /></td>
                <td className="zahl"><Betrag wert={j.praemie_lieferung_eur} /></td>
                <td className="zahl"><Betrag wert={j.ertraege.dividenden} /></td>
                <td className="zahl"><Betrag wert={j.ertraege.quellensteuer} /></td>
                <td className="zahl"><Betrag wert={j.ertraege.zinsen_erhalten} /></td>
                <td className="zahl"><Betrag wert={j.ertraege.zinsen_gezahlt} /></td>
                <td className="zahl"><Betrag wert={j.ertraege.gebuehren} /></td>
                <td><a href={`/steuer-csv?jahr=${j.jahr}`} download>CSV {j.jahr}</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <a href="/steuer-csv" download>Alle Jahre als CSV</a>
      </p>

      {jahr !== null && (
        <>
          <h3>Töpfe {jahr} je Währung</h3>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <thead>
                <tr>
                  <th>Topf</th>
                  <th>Währung</th>
                  <th className="zahl">Brutto</th>
                  <th className="zahl">Kommission</th>
                  <th className="zahl">Netto</th>
                  <th className="zahl" title="Netto × Buchungskurs der Schließung">Netto in EUR</th>
                  <th className="zahl">Legs</th>
                  <th className="zahl">ohne Kurs</th>
                </tr>
              </thead>
              <tbody>
                {toepfe.map((t) => (
                  <tr key={`${t.topf}-${t.waehrung}`}>
                    <td>{TOPF_NAME[t.topf] ?? t.topf}</td>
                    <td>{t.waehrung}</td>
                    <td className="zahl"><Betrag wert={t.brutto} waehrung={t.waehrung} /></td>
                    <td className="zahl"><Betrag wert={t.kommission} waehrung={t.waehrung} /></td>
                    <td className="zahl"><Betrag wert={t.netto} waehrung={t.waehrung} /></td>
                    <td className="zahl"><Betrag wert={t.netto_eur_ib} /></td>
                    <td className="zahl">{t.anzahl_legs}</td>
                    <td className="zahl">{t.eur_kurs_fehlt}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Offene Fragen für den Steuerberater</h3>
      <ol>
        <li>
          <strong>Prämie bei Zuteilung (Short Put/Call mit Lieferung):</strong> Hier steht die Prämie im Topf der
          Termingeschäfte (Spalte „davon Prämie bei Lieferung“), die gelieferte Aktie führt den Verlust gegen den
          Strike im Aktien-Topf. Möglicherweise gehört die Prämie steuerlich in die Anschaffungskosten der Aktie (so
          bucht auch IB). Das verschiebt Beträge zwischen den Töpfen — mit dem Steuerberater klären.
        </li>
        <li>
          <strong>Umrechnung:</strong> EUR über den Buchungskurs der Schließung (wie IB). Steuerlich kann der Kurs je
          Zahlungsstrom (Eröffnung und Schließung einzeln) gefordert sein (OF-59).
        </li>
        <li>
          <strong>Jahresgrenze:</strong> Das Jahr folgt der gespeicherten Handelszeit ohne Zeitzone; Geschäfte kurz vor
          Mitternacht am Jahreswechsel können im anderen Jahr stehen (OF-58).
        </li>
        <li>
          <strong>Verlustverrechnung und Anlage KAP:</strong> Die Seite verrechnet nichts (Aktienverluste,
          Termingeschäfte, Zinsen, Quellensteuer-Anrechnung). Das ist Sache des Steuerberaters.
        </li>
      </ol>
    </section>
  )
}
