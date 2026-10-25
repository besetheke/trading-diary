import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import type { Datenqualitaet, OaStand, Uebersicht as Daten } from './api'
import { fehlerText, holeDatenqualitaet, holeOaStand, holeUebersicht } from './api'
import Betrag from './Betrag'
import { datumDe } from './format'

// AP-08ue: Startseite. Alle Zahlen kommen fertig aus GET /uebersicht (NAV,
// Equity, Bestand laut IB) — der Browser rechnet kein Geld (Vertrag 8).

export default function Uebersicht(): JSX.Element {
  const [daten, setzeDaten] = useState<Daten | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [oaStand, setzeOaStand] = useState<OaStand | null>(null)
  const [qualitaet, setzeQualitaet] = useState<Datenqualitaet | null>(null)

  useEffect(() => {
    holeUebersicht()
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)))
    holeOaStand()
      .then(setzeOaStand)
      .catch(() => setzeOaStand(null))
    holeDatenqualitaet(true)
      .then(setzeQualitaet)
      .catch(() => setzeQualitaet(null))
  }, [])

  if (fehler) {
    return (
      <section className="fehler">
        <h2>Die Übersicht konnte nicht geladen werden</h2>
        <p>{fehler}</p>
      </section>
    )
  }
  if (daten === null) return <p className="laedt">Lade Übersicht …</p>

  return (
    <section className="uebersicht">
      <h2>Übersicht · {datumDe(daten.heute)}</h2>
      {qualitaet && qualitaet.punkte.some((p) => p.schwere !== 'hinweis') && (
        <p className={qualitaet.status === 'fehler' ? 'fehler' : 'warnung'}>
          {qualitaet.status === 'fehler' ? '✘ Datenqualität: Fehler offen' : '⚠ Datenqualität: Warnungen offen'} —{' '}
          {qualitaet.punkte.filter((p) => p.schwere !== 'hinweis').slice(0, 2).map((p) => p.titel).join('; ')}{' '}
          <Link to="/datenqualitaet">Zur Arbeitsliste</Link>
        </p>
      )}
      <div className="kacheln">
        <div className="kachel">
          <h3>Kontowert laut IB</h3>
          <p className="gross">
            {daten.kontowert_eur === null ? '—' : <Betrag wert={daten.kontowert_eur} />}
          </p>
          <p className="sicht">
            {daten.kontowert_stand ? `Stand ${datumDe(daten.kontowert_stand)}` : 'kein Bericht'}
          </p>
        </div>
        <div className="kachel">
          <h3>Realisiert netto</h3>
          <dl className="zeilen">
            <div>
              <dt>diese Woche</dt>
              <dd>
                <Betrag wert={daten.realisiert_woche_eur} />
              </dd>
            </div>
            <div>
              <dt>dieser Monat</dt>
              <dd>
                <Betrag wert={daten.realisiert_monat_eur} />
              </dd>
            </div>
            <div>
              <dt>dieses Jahr</dt>
              <dd>
                <Betrag wert={daten.realisiert_jahr_eur} />
              </dd>
            </div>
          </dl>
          <p className="sicht">am Tag der Schließung, Kontosicht</p>
        </div>
        <div className="kachel">
          <h3>Offene Positionen</h3>
          <p className="gross">
            {daten.unrealisiert_eur === null ? '—' : <Betrag wert={daten.unrealisiert_eur} />}
          </p>
          <p className="sicht">
            unrealisiert, {daten.offene_positionen} Position(en)
            {daten.bestand_stand ? `, Stand ${datumDe(daten.bestand_stand)}` : ''} ·{' '}
            <Link to="/bestand">Depot</Link>
          </p>
        </div>
      </div>

      <h3>Nächste Verfälle</h3>
      {daten.verfaelle.length === 0 ? (
        <p className="hinweis">Keine offenen Optionen mit kommendem Verfall.</p>
      ) : (
        <table className="verfaelle">
          <thead>
            <tr>
              <th>Verfall</th>
              <th>Basiswert</th>
              <th>Positionen</th>
            </tr>
          </thead>
          <tbody>
            {daten.verfaelle.map((v) => (
              <tr key={`${v.verfall}-${v.basiswert}`}>
                <td>{datumDe(v.verfall)}</td>
                <td>
                  <Link to={`/?basiswert=${encodeURIComponent(v.basiswert)}&endzustand=Offen`}>
                    {v.basiswert}
                  </Link>
                </td>
                <td className="zahl">{v.anzahl}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>Zu erledigen</h3>
      <ul className="aufgaben">
        <li>
          <Link to="/rolls">Rolls prüfen</Link> — Vorschläge für Rolls in getrennten Orders
          bestätigen oder verwerfen.
        </li>
        {oaStand !== null && oaStand.ohne_export > 0 ? (
          <li>
            OptionApp-Export erneuern: {oaStand.ohne_export} OA-Trade(s) seit{' '}
            {datumDe(oaStand.ohne_export_ab)} ohne Strategie (Export bis{' '}
            {datumDe(oaStand.export_bis)}). Datei nach <code>C:\Trading\oa</code> legen.
          </li>
        ) : null}
      </ul>
    </section>
  )
}
