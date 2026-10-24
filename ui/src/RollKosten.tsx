import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeRollKosten } from './api'
import type { RollKostenAntwort, RollKostenKette } from './api'
import { betrag, datumDe, geldDe, prozent, vorzeichen } from './format'

// AP-17g (M01): Was kosten zusätzliche Rolls, und wohin geht die Kommission? Alle Werte kommen aus den
// Rechenkernen (analytics/degradation.py, analytics/kommission.py) über GET /roll-kosten-auswertung,
// in EUR wirtschaftlich; im Browser wird nichts gerechnet.

const DIMENSIONEN: [string, string][] = [
  ['roll_anzahl', 'Anzahl Rolls'],
  ['strategie', 'Strategie'],
  ['index', 'Basiswert'],
  ['anlageklasse', 'Anlageklasse'],
]

const MODI: Record<string, string> = {
  belegt: 'belegt (nur automatisch erkannte Rolls)',
  belegt_bestaetigt: 'belegt + manuell bestätigt',
}

// Drilldown: die Ketten hinter einer Zeile, jede mit Beträgen und Link zur Position.
function KettenListe({ ids, ohneKurs, ketten, spalten }: {
  ids: number[]; ohneKurs: number[]; ketten: Record<string, RollKostenKette>; spalten: number
}): JSX.Element {
  const zeile = (id: number, mangel: boolean) => {
    const k = ketten[String(id)]
    return (
      <tr key={`${mangel ? 'm' : 'k'}${id}`} className={mangel ? 'warnung' : undefined}>
        <td><Link to={`/positionen/${id}`}>Kette {id}</Link>{mangel ? ' (ohne Kurs)' : ''}</td>
        <td>{k ? `${k.basiswert} · ${k.strategie ?? 'ohne Strategie'}` : '—'}</td>
        <td>{k ? `${datumDe(k.eroeffnet_am)} – ${k.beendet_am ? datumDe(k.beendet_am) : 'offen'}` : '—'}</td>
        <td className="zahl">{k ? `${k.rolls} Rolls` : '—'}</td>
        <td className={vorzeichen(k?.brutto_eur ?? null)}>{k && k.brutto_eur !== null ? betrag(k.brutto_eur) : '—'}</td>
        <td className={vorzeichen(k?.kommission_eur ?? null)}>{k && k.kommission_eur !== null ? betrag(k.kommission_eur) : '—'}</td>
        <td className={vorzeichen(k?.netto_eur ?? null)}>{k && k.netto_eur !== null ? betrag(k.netto_eur) : '—'}</td>
      </tr>
    )
  }
  return (
    <tr>
      <td colSpan={spalten}>
        <table className="positionen dichte-kompakt">
          <thead><tr><th>Position</th><th>Basiswert · Strategie</th><th>Zeitraum</th><th>Rolls</th><th>Brutto</th><th>Kommission</th><th>Netto</th></tr></thead>
          <tbody>{ids.map((i) => zeile(i, false))}{ohneKurs.map((i) => zeile(i, true))}</tbody>
        </table>
      </td>
    </tr>
  )
}

export default function RollKosten(): JSX.Element {
  const [sicht, setzeSicht] = useState('kette')
  const [nurA, setzeNurA] = useState(false)
  const [dimension, setzeDimension] = useState('roll_anzahl')
  const [daten, setzeDaten] = useState<RollKostenAntwort | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [offen, setzeOffen] = useState<string | null>(null)

  useEffect(() => {
    setzeFehler(null)
    setzeOffen(null)
    holeRollKosten(sicht, nurA).then(setzeDaten).catch((e) => setzeFehler(fehlerText(e)))
  }, [sicht, nurA])

  if (fehler) return <p className="fehler">{fehler}</p>
  if (!daten) return <p className="laedt">Lade Roll-Kosten …</p>
  const zeilen = daten.kommission.filter((z) => z.dimension === dimension)
  const degradation = daten.degradation
  return (
    <section>
      <h2>Roll-Kosten und Kommission</h2>
      <p className="sicht">
        Sicht:{' '}
        <select value={sicht} onChange={(e) => setzeSicht(e.target.value)}>
          <option value="kette">Kettensicht (Rolls zusammengefasst)</option>
          <option value="konto">Kontosicht (wie die Broker-Auszüge)</option>
        </select>{' '}
        <label>
          <input type="checkbox" checked={nurA} onChange={(e) => setzeNurA(e.target.checked)} /> nur Qualitätsstufe A
        </label>{' '}
        · {daten.anzahl_ketten_gesamt} Ketten insgesamt · Beträge in EUR, nur abgeschlossene Ketten mit vollständigem Kurs
      </p>

      {degradation ? (
        <>
          <h3>Ergebnis nach Anzahl Rolls</h3>
          <p className="sicht">
            Vergleich der Ketten mit 0, 1, 2 und 3+ Rolls (kein Verlauf je Kette). Die Differenz der Durchschnitte zeigt, was zusätzliche
            Rolls im Mittel bringen oder kosten.
          </p>
          {['belegt', 'belegt_bestaetigt'].map((modus) => (
            <div key={modus}>
              <h4>{MODI[modus]}</h4>
              <table className="positionen dichte-kompakt">
                <thead>
                  <tr><th>Rolls</th><th>Ketten</th><th>Summe netto</th><th>Ø netto</th><th>Trefferquote</th><th>ohne Kurs</th></tr>
                </thead>
                <tbody>
                  {degradation.filter((g) => g.modus === modus).flatMap((g) => {
                    const schluessel = `deg|${modus}|${g.roll_gruppe}`
                    const zeilen = [
                    <tr key={g.roll_gruppe} onClick={() => setzeOffen(offen === schluessel ? null : schluessel)} style={{ cursor: 'pointer' }}
                        title="Klicken: die gezählten Ketten anzeigen">
                      <td>{offen === schluessel ? '▾' : '▸'} {g.roll_gruppe}</td>
                      <td>{g.anzahl_ketten}</td>
                      <td className={vorzeichen(g.summe_netto_eur)}>{geldDe(g.summe_netto_eur)}</td>
                      <td className={vorzeichen(g.durchschnitt_netto_eur)}>{geldDe(g.durchschnitt_netto_eur)}</td>
                      <td>{prozent(g.trefferquote)}</td>
                      <td>{g.anzahl_ketten_kurs_fehlt || ''}</td>
                    </tr>,
                    ]
                    if (offen === schluessel) {
                      zeilen.push(<KettenListe key={`${g.roll_gruppe}-liste`} ids={g.ketten_ids} ohneKurs={g.ketten_ids_kurs_fehlt}
                                               ketten={daten.ketten} spalten={6} />)
                    }
                    return zeilen
                  })}
                </tbody>
              </table>
              {daten.degradation_abdeckung.filter((a) => a.modus === modus).map((a) => (
                <p key={a.modus} className="sicht">
                  Abdeckung: {a.ketten_ausgewertet} von {a.ketten_abgeschlossen} abgeschlossenen Ketten ({prozent(a.abdeckung_ketten)}) ·{' '}
                  {a.rollverknuepfungen} Roll-Verknüpfungen · offene Rollkandidaten: {a.offene_kandidaten ?? '—'} (Abdeckung der
                  Verknüpfungen {prozent(a.abdeckung_rollverknuepfungen)})
                </p>
              ))}
            </div>
          ))}
        </>
      ) : (
        <p className="hinweis">Die Roll-Degradation gibt es nur in der Kettensicht.</p>
      )}

      <h3>Kommission</h3>
      <p className="sicht">
        Gruppiert nach{' '}
        <select value={dimension} onChange={(e) => setzeDimension(e.target.value)}>
          {DIMENSIONEN.map(([wert, name]) => <option key={wert} value={wert}>{name}</option>)}
        </select>
      </p>
      <table className="positionen dichte-kompakt">
        <thead>
          <tr><th>Gruppe</th><th>Ketten</th><th>Brutto</th><th>Kommission</th><th>Netto</th><th>Anteil</th><th>ohne Kurs</th></tr>
        </thead>
        <tbody>
          {zeilen.flatMap((z) => {
            const schluessel = `kom|${dimension}|${z.schluessel}`
            const reihe = [
            <tr key={z.schluessel} onClick={() => setzeOffen(offen === schluessel ? null : schluessel)} style={{ cursor: 'pointer' }}
                title="Klicken: die gezählten Ketten anzeigen">
              <td>{offen === schluessel ? '▾' : '▸'} {z.schluessel}</td>
              <td>{z.anzahl_ketten}</td>
              <td className={vorzeichen(z.brutto_eur)}>{betrag(z.brutto_eur)}</td>
              <td className={vorzeichen(z.kommission_eur)}>{betrag(z.kommission_eur)}</td>
              <td className={vorzeichen(z.netto_eur)}>{betrag(z.netto_eur)}</td>
              <td>{prozent(z.kommissionsanteil)}</td>
              <td>{z.anzahl_ketten_kurs_fehlt || ''}</td>
            </tr>,
            ]
            if (offen === schluessel) {
              reihe.push(<KettenListe key={`${z.schluessel}-liste`} ids={z.ketten_ids} ohneKurs={z.ketten_ids_kurs_fehlt}
                                      ketten={daten.ketten} spalten={7} />)
            }
            return reihe
          })}
          {zeilen.length === 0 && <tr><td colSpan={7}>Keine abgeschlossenen Ketten.</td></tr>}
        </tbody>
      </table>
    </section>
  )
}
