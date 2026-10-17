import { useEffect, useState } from 'react'
import { fehlerText, holeSteuer } from './api'
import type { SteuerAntwort } from './api'
import Betrag from './Betrag'

// Steuer nach Zufluss je Zahlungsstrom (AP-10c): reines Durchreichen der Aufbereitung aus GET /steuer-auswertung.
// Nichts wird hier gerechnet, verrechnet oder umgerechnet. Arbeitsstand des Steuerberaters (OF-92/OF-93), ungeprüft:
// keine Steuerberatung, keine Verlustverrechnung.

const TOPF_NAME: Record<string, string> = {
  aktien: 'Aktien',
  termingeschaefte: 'Termingeschäfte',
  stillhalter: 'Stillhalter (Prämie, Rückkauf)',
  dividenden: 'Dividenden',
  zinsen: 'Habenzinsen',
  nicht_abziehbar: 'nicht abziehbar (Sollzinsen, Gebühren)',
  so_kandidat: 'Ersatzzahlungen (SO-Kandidat, Einordnung offen)',
}
const TOPF_REIHENFOLGE = ['aktien', 'stillhalter', 'termingeschaefte', 'dividenden', 'zinsen', 'so_kandidat', 'nicht_abziehbar']

const QST_NAME: Record<string, string> = {
  vorlaeufig_anrechenbar: 'vorläufig anrechenbar',
  erstattungsfaehig: 'möglicherweise erstattungsfähig',
  ungeklaert: 'ungeklärt',
  ersatzzahlung_zu_pruefen: 'auf Ersatzzahlungen (zu prüfen)',
}

const KAP_NAME: Record<string, string> = {
  ausl_kapitalertraege_saldo: 'Saldo ausländische Kapitalerträge',
  aktiengewinne: 'davon Aktiengewinne',
  verluste_ohne_aktien: 'davon Verluste ohne Aktien',
  aktienverluste: 'davon Aktienverluste',
  anrechenbare_quellensteuer: 'anrechenbare Quellensteuer (vorläufige Obergrenze)',
}

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

  const gewaehlt = daten.jahre.find((j) => j.jahr === jahr) ?? null
  const topf = (j: SteuerAntwortJahr, name: string) => j.toepfe.find((t) => t.topf === name)
  return (
    <section>
      <h2>Steuer — Zufluss je Zahlungsstrom</h2>
      <p className="hinweis">
        <strong>Arbeitsstand, ungeprüft — keine Steuerberatung, keine Verlustverrechnung.</strong> Die Regeln stammen aus
        der Antwort des Steuerberaters (OF-92) und sind von ihm zu bestätigen. Stillhalterprämien zählen im Zuflussjahr,
        Rückkäufe im Zahlungsjahr, Spreads je Bein; Aktien zum Strike mit Erwerbs- und Veräußerungskosten;
        Fremdwährung je Zahlungsstrom. Offene Positionen sind enthalten.
      </p>
      <p className="sicht">
        Kursquelle: {daten.methode.kursquelle} (Kursdatum: {daten.methode.kursdatum_feld}); Prüfstatus:{' '}
        {daten.methode.pruefstatus}. Datumsregeln je Vorgang (Steuerdatum / Kursdatum):{' '}
        {Object.entries(daten.methode.datumsregeln)
          .map(([k, v]) => `${k} ${v.steuerdatum}/${v.fx}`)
          .join(', ')}
        .
      </p>
      {daten.warnungen.map((w) => (
        <p className="hinweis" key={w}>{w}</p>
      ))}

      <h3>Jahresübersicht (EUR, Saldo je Topf — nicht verrechnet)</h3>
      <div className="tabelle-rahmen">
        <table className="positionen dichte-kompakt">
          <thead>
            <tr>
              <th>Zuflussjahr</th>
              {TOPF_REIHENFOLGE.map((t) => (
                <th key={t} className="zahl">{TOPF_NAME[t]}</th>
              ))}
              <th className="zahl" title="Buchungen, die bei einem Wechsel der Datumsregel (Handels-/Abrechnungstag) in ein anderes Jahr fielen">
                am Jahreswechsel betroffen
              </th>
              <th>Export</th>
            </tr>
          </thead>
          <tbody>
            {daten.jahre.map((j) => (
              <tr key={j.jahr} className={j.jahr === jahr ? 'summe' : undefined}>
                <td>
                  <button type="button" className="sortierer" onClick={() => setzeJahr(j.jahr)} title="Details unten zeigen">
                    {j.jahr}
                  </button>
                </td>
                {TOPF_REIHENFOLGE.map((t) => (
                  <td key={t} className="zahl"><Betrag wert={topf(j, t)?.saldo ?? '0'} /></td>
                ))}
                <td className="zahl">{j.betroffen}</td>
                <td><a href={`/steuer-csv?jahr=${j.jahr}`} download>CSV {j.jahr}</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <a href="/steuer-csv" download>Alle Jahre als CSV</a> ·{' '}
        <a href="/steuer-csv?methode=alt" download title="Altverfahren: Ergebnis im Schließungsjahr, nur zum Vergleich">
          Altverfahren (nur zum Vergleich, nicht zur Übernahme)
        </a>
      </p>

      {gewaehlt && (
        <>
          <h3>{gewaehlt.jahr}: Gewinne und Verluste je Topf (getrennt, nicht verrechnet)</h3>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <thead>
                <tr>
                  <th>Topf</th>
                  <th className="zahl">Gewinne / Einnahmen</th>
                  <th className="zahl">Verluste / Rückkäufe</th>
                  <th className="zahl">Saldo</th>
                  <th className="zahl">Posten</th>
                </tr>
              </thead>
              <tbody>
                {TOPF_REIHENFOLGE.filter((t) => topf(gewaehlt, t)).map((t) => {
                  const z = topf(gewaehlt, t)!
                  return (
                    <tr key={t}>
                      <td>{TOPF_NAME[t]}</td>
                      <td className="zahl"><Betrag wert={z.gewinne} /></td>
                      <td className="zahl"><Betrag wert={z.verluste} /></td>
                      <td className="zahl"><Betrag wert={z.saldo} /></td>
                      <td className="zahl">{z.anzahl}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <h3>{gewaehlt.jahr}: Quellensteuer (vorläufige Obergrenze, EUR)</h3>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <tbody>
                {Object.entries(QST_NAME).map(([k, name]) => (
                  <tr key={k}>
                    <td>{name}</td>
                    <td className="zahl"><Betrag wert={gewaehlt.quellensteuer[k] ?? '0'} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="sicht">
            Anrechenbar ist hier höchstens der Satz des Quellenstaats (USA 15 %) auf die Bruttodividende; die deutsche
            Anrechnungsbegrenzung ist nicht geprüft. Der Überhang kann erstattungsfähig sein. Ersatzzahlungen gehen nicht
            automatisch in die Anrechnung.
          </p>

          <h3>
            {gewaehlt.jahr}: Vorschau Anlage KAP (vorläufig, nicht verrechnet) — Zeilen {gewaehlt.kap.formularjahr}:{' '}
            {gewaehlt.kap.status === 'ungeprueft' ? 'ungeprüft' : 'laut Antwort des Steuerberaters'}
          </h3>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <thead>
                <tr>
                  <th className="zahl">Zeile</th>
                  <th>Posten</th>
                  <th className="zahl">Betrag EUR</th>
                </tr>
              </thead>
              <tbody>
                {gewaehlt.kap.posten.map((p) => (
                  <tr key={p.posten}>
                    <td className="zahl">{p.zeile}</td>
                    <td>{KAP_NAME[p.posten] ?? p.posten}</td>
                    <td className="zahl"><Betrag wert={p.betrag} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Offene Regeln — nicht in den Töpfen oder noch ungeklärt</h3>
      {daten.regeln_offen.length === 0 ? (
        <p className="sicht">Keine.</p>
      ) : (
        <div className="tabelle-rahmen">
          <table className="positionen dichte-kompakt">
            <thead>
              <tr>
                <th>Art</th>
                <th className="zahl">Anzahl</th>
                <th className="zahl">Betrag EUR</th>
                <th>Hinweis</th>
              </tr>
            </thead>
            <tbody>
              {daten.regeln_offen.map((r) => (
                <tr key={r.art}>
                  <td>{r.art}</td>
                  <td className="zahl">{r.anzahl}</td>
                  <td className="zahl"><Betrag wert={r.betrag_eur} /></td>
                  <td>{r.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>Datenlücken</h3>
      {daten.datenluecken.length === 0 ? (
        <p className="sicht">Keine: Jeder gebuchte Zahlungsstrom hat seinen Kurs.</p>
      ) : (
        <ul>
          {daten.datenluecken.slice(0, 50).map((d) => (
            <li key={`${d.schluessel}-${d.grund}`}>{d.text} ({d.schluessel})</li>
          ))}
        </ul>
      )}

      <h3>Offene Fragen für den Steuerberater</h3>
      <ol>
        <li>Datumsfeld je Vorgang (Handels- oder Abrechnungstag) und Kursquelle (IB oder EZB) bestätigen — der IB-Kurs
          gehört zum Handelstag; wo die Regel den Abrechnungstag verlangt, steht „kursdatum_abweichend“.</li>
        <li>Ersatzzahlungen und SYEP: Einordnung (§ 22 Nr. 3 oder § 20), Ursache je Buchung, Quellensteuer.</li>
        <li>ETF/ETN/ETP (Investmentsteuergesetz) und gekaufte Optionen mit Lieferung (Long Call/Put) prüfen.</li>
        <li>USD-Konto: Verzinsung und Funktion (§ 20 oder § 23), Anfangsbestände und Verlustvorträge.</li>
      </ol>
    </section>
  )
}

type SteuerAntwortJahr = SteuerAntwort['jahre'][number]
