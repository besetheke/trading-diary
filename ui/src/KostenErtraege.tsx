// AP-08g2: Kosten & Erträge — reines Durchreichen der Kategorien und Monate
// aus GET /cashflows (AP-06f). Nichts wird hier gerechnet: weder Summen über
// Monate oder Kategorien noch Umrechnungen (Vertrag 8); fehlt eine Zahl, ist
// das eine Rückmeldung an die API, kein Grund, im Browser zu addieren.
// Monate ohne Buchung in der gewählten Kategorie listet die API nicht — der
// Balken zeigt nur Buchungsmonate: Lücke statt 0.

import { useEffect, useState } from 'react'
import { fehlerText, holeCashflows } from './api'
import type { CashflowKategorieName, Cashflows } from './api'
import Betrag from './Betrag'
import Balken from './diagramm/Balken'
import { monatKurz } from './diagramm/skala'
import { useZeitraum } from './zeitraum'

// Deutsche Beschriftung der Kategorien (die Schlüssel nennt AP-06f).
const KATEGORIE_TITEL: Record<CashflowKategorieName, string> = {
  kommissionen: 'Kommissionen',
  kommissionsanpassungen: 'Kommissionsanpassungen',
  gebuehren: 'Gebühren',
  zinsen_erhalten: 'Zinsen erhalten',
  zinsen_gezahlt: 'Zinsen gezahlt',
  dividenden: 'Dividenden',
  quellensteuer: 'Quellensteuer',
  barausgleich: 'Barausgleich',
  sonstige: 'Sonstiges',
  ein_auszahlungen: 'Ein-/Auszahlungen',
}

export default function KostenErtraege(): JSX.Element {
  const [zeitraum] = useZeitraum()
  const [cashflows, setzeCashflows] = useState<Cashflows | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  // Welche Kategorie das Balkendiagramm zeigt — Vorgabe: Kommissionen.
  const [kategorie, setzeKategorie] = useState<CashflowKategorieName>('kommissionen')

  useEffect(() => {
    let abgebrochen = false
    setzeCashflows(null)
    setzeFehler(null)
    holeCashflows(zeitraum.von, zeitraum.bis)
      .then((ergebnis) => {
        if (!abgebrochen) setzeCashflows(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  if (fehler !== null) {
    return (
      <section>
        <h2>Kosten &amp; Erträge</h2>
        <section className="fehler">
          <h3>Die Kosten konnten nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      </section>
    )
  }

  if (cashflows === null) {
    return (
      <section>
        <h2>Kosten &amp; Erträge</h2>
        <p className="laedt">Lade Kosten &amp; Erträge …</p>
      </section>
    )
  }

  if (cashflows.kategorien.length === 0) {
    return (
      <section>
        <h2>Kosten &amp; Erträge</h2>
        <section className="hinweis">
          <p>Noch keine Buchung in Kosten &amp; Erträgen.</p>
        </section>
      </section>
    )
  }

  // Werte der gewählten Kategorie — direkt aus den monate-Zeilen, keine
  // Summe im Browser.
  const monateDerKategorie = cashflows.monate.filter((monat) => monat.kategorie === kategorie)
  // Die Monate der Tabelle, neueste zuerst; die API liefert aufsteigend.
  const monateNeu = [...new Set(cashflows.monate.map((monat) => monat.monat))].reverse()
  // Zugriff Monat × Kategorie — ein Verzeichnis der API-Zeilen, kein Rechnen.
  const zellen = new Map(cashflows.monate.map((monat) => [`${monat.monat}|${monat.kategorie}`, monat]))
  const ohneKategorie = cashflows.kategorien.every((kat) => kat.kategorie !== kategorie)

  return (
    <section>
      <h2>Kosten &amp; Erträge</h2>
      <p className="sicht fussnote">
        Beträge in EUR, Kontosicht, wie die API sie liefert. „(im Ergebnis
        enthalten)“ heißt: steckt schon im realisierten Ergebnis — Ausweis, kein
        Zusatzposten. Ein-/Auszahlungen sind Kapitalbewegung, kein Ertrag.
      </p>

      <dl className="kopf">
        {cashflows.kategorien.map((kat) => (
          <div
            key={kat.kategorie}
            className={kat.kategorie === 'ein_auszahlungen' ? 'abgesetzt' : undefined}
          >
            <dt>
              {KATEGORIE_TITEL[kat.kategorie]}
              {kat.im_ergebnis_enthalten ? ' (im Ergebnis enthalten)' : ''}
              {kat.kategorie === 'ein_auszahlungen' ? ' (Kapitalbewegung, kein Ertrag)' : ''}
            </dt>
            <dd>
              <Betrag wert={kat.summe_eur} />
            </dd>
          </div>
        ))}
      </dl>
      {cashflows.kategorien
        .filter((kat) => kat.anzahl_kurs_fehlt > 0)
        .map((kat) => (
          <p key={kat.kategorie} className="sicht fussnote">
            {KATEGORIE_TITEL[kat.kategorie]}: {kat.anzahl_kurs_fehlt} Buchungen ohne Kurs.
          </p>
        ))}

      <div className="filter">
        <label htmlFor="kategorie-wahl">
          Kategorie
          <select
            id="kategorie-wahl"
            value={kategorie}
            onChange={(ereignis) =>
              setzeKategorie(ereignis.target.value as CashflowKategorieName)
            }
          >
            {cashflows.kategorien.map((kat) => (
              <option key={kat.kategorie} value={kat.kategorie}>
                {KATEGORIE_TITEL[kat.kategorie]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {ohneKategorie || monateDerKategorie.length === 0 ? (
        <p className="diagramm-leer">
          In „{KATEGORIE_TITEL[kategorie]}“ steht kein Monat mit Buchung.
        </p>
      ) : (
        <Balken balken={monateDerKategorie.map((monat) => ({ x: monat.monat, y: monat.summe_eur }))} />
      )}

      <table className="kosten">
        <thead>
          <tr>
            <th>Monat</th>
            {cashflows.kategorien.map((kat) => (
              <th key={kat.kategorie} className="zahl">
                {KATEGORIE_TITEL[kat.kategorie]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {monateNeu.map((monat) => (
            <tr key={monat}>
              <td>{monatKurz(monat)}</td>
              {cashflows.kategorien.map((kat) => {
                const zeile = zellen.get(`${monat}|${kat.kategorie}`)
                return (
                  <td key={kat.kategorie} className="zahl">
                    {zeile ? <Betrag wert={zeile.summe_eur} /> : ''}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
