import { useEffect, useState } from 'react'
import { fehlerText, holeSteuer } from './api'
import type { SteuerAntwort } from './api'
import Betrag from './Betrag'

// Steuer nach Zufluss je Zahlungsstrom (AP-10c): reines Durchreichen der Aufbereitung aus GET /steuer-auswertung.
// Nichts wird hier gerechnet, verrechnet oder umgerechnet. Keine Steuerberatung, keine Verlustverrechnung. Jede Regel
// steht mit Marker und Grundlage in der Tabelle „Regeln und Grundlage“ (Quellenhierarchie, OF-99).

const TOPF_NAME: Record<string, string> = {
  aktien: 'Aktien',
  termingeschaefte: 'Termingeschäfte',
  stillhalter: 'Stillhalter (Prämie, Rückkauf)',
  dividenden: 'Dividenden',
  zinsen: 'Habenzinsen',
  nicht_abziehbar: 'nicht abziehbar (Sollzinsen, Gebühren)',
  so_kandidat: 'Ersatzzahlungen PIL (Anlage SO)',
  so_syep: 'SYEP-Vergütung (Anlage SO)',
  so_belastung: 'PIL-Belastung Leerverkauf (nicht saldiert)',
}
const TOPF_REIHENFOLGE = ['aktien', 'stillhalter', 'termingeschaefte', 'dividenden', 'zinsen', 'so_kandidat', 'so_syep', 'so_belastung', 'nicht_abziehbar']

const QST_NAME: Record<string, string> = {
  vorlaeufig_anrechenbar: 'vorläufig anrechenbar',
  erstattungsfaehig: 'möglicherweise erstattungsfähig',
  ungeklaert: 'ungeklärt',
  ersatzzahlung_zu_pruefen: 'auf Ersatzzahlungen (zu prüfen)',
}

const KAP_NAME: Record<string, string> = {
  inl_kapitalertraege_saldo: 'Saldo inländische Kapitalerträge ohne Steuerabzug (deutsche Emittenten)',
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
        // Vorgabe: das letzte abgeschlossene Jahr (die Steuererklärung betrifft ein volles Jahr); sonst das jüngste.
        const letztes = new Date().getFullYear() - 1
        const vorgabe = d.jahre.find((j) => j.jahr === letztes) ?? d.jahre[d.jahre.length - 1]
        setzeJahr(vorgabe ? vorgabe.jahr : null)
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
        <strong>Aufbereitung, keine Steuerberatung und keine Verlustverrechnung.</strong> Grundlage ist die
        Quellenhierarchie {daten.methode.quellenhierarchie.map((q, i) => `${i + 1}. ${q}`).join(' · ')}. Jede Regel trägt
        einen Marker (amtlich belegt, aus Daten belegt, vorsichtige Standardbehandlung), siehe unten. Verbindlich ist nur
        die Entscheidung des Finanzamts oder eines Gerichts; für Vorgänge, die schon verwirklicht sind, gibt es keine
        verbindliche Auskunft (§ 89 Abs. 2 AO) — die Berechnung wird mit einer kurzen Erläuterung unter „Ergänzende
        Angaben zur Steuererklärung“ eingereicht (§ 150 Abs. 7 AO). Stillhalterprämien zählen im Zuflussjahr, Rückkäufe im
        Zahlungsjahr, Spreads je Bein; Aktien zum Strike; Fremdwährung je Zahlungsstrom; offene Positionen sind
        enthalten.
      </p>
      <p className="sicht">
        Kursquelle: {daten.methode.kursquelle} (Kursdatum: {daten.methode.kursdatum_feld}); Prüfung:{' '}
        {daten.methode.pruefstatus} (Marker je Regel). Datumsregeln je Vorgang (Steuerdatum / Kursdatum):{' '}
        {Object.entries(daten.methode.datumsregeln)
          .map(([k, v]) => `${k} ${v.steuerdatum}/${v.fx}`)
          .join(', ')}
        .
      </p>
      <p className="sicht">
        {daten.methode.stroeme} Zahlungsströme; bei {daten.methode.kursdatum_abweichend} gehört der IB-Kurs (Handelstag)
        nicht zum Datum, das die Regel verlangt (Abrechnungstag) — „kursdatum_abweichend“ im CSV. Einzelfall-Listen für den
        Steuerberater: <code>journal steuer-listen ORDNER</code>.
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

      <div className="diagramm-wahl" role="group" aria-label="Jahr der Details">
        {[...daten.jahre].reverse().map((j) => {
          const heute = new Date().getFullYear()
          const zusatz = j.jahr === heute ? ' (laufend, bis Stichtag)' : j.jahr === heute - 1 ? ' (letztes Jahr)' : ''
          return (
            <button
              key={j.jahr}
              type="button"
              aria-pressed={j.jahr === jahr}
              title={`Details und KAP-Vorschau für ${j.jahr} zeigen`}
              onClick={() => setzeJahr(j.jahr)}
            >
              {j.jahr}
              {zusatz}
            </button>
          )
        })}
        {gewaehlt && <a href={`/steuer-csv?jahr=${gewaehlt.jahr}`} download>CSV {gewaehlt.jahr}</a>}
      </div>

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

          <div className={gewaehlt.deklarationsstatus.status === 'nicht_deklarationsfaehig' ? 'fehler' : 'hinweis'}>
            <strong>
              {gewaehlt.jahr}:{' '}
              {gewaehlt.deklarationsstatus.status === 'nicht_deklarationsfaehig'
                ? 'nicht deklarationsfähig'
                : 'deklarierbar mit Erläuterung'}
            </strong>
            {gewaehlt.deklarationsstatus.gruende.length > 0 && (
              <>
                {' '}
                — blockierend:
                <ul>
                  {gewaehlt.deklarationsstatus.gruende.map((g) => (
                    <li key={g}>{g}</li>
                  ))}
                </ul>
              </>
            )}
            Hinweise (nicht blockierend):
            <ul>
              {gewaehlt.deklarationsstatus.hinweise.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </div>

          <h3>{gewaehlt.jahr}: Anlage SO — Ersatzzahlungen und SYEP (§ 22 Nr. 3 EStG), EUR</h3>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <tbody>
                <tr><td>Empfangene Ersatzzahlungen (PIL, abzüglich Stornos)</td><td className="zahl"><Betrag wert={gewaehlt.so.ersatzzahlungen_netto} /></td></tr>
                <tr><td>Laufende SYEP-Vergütung (getrennt ausgewiesen)</td><td className="zahl"><Betrag wert={gewaehlt.so.syep_verguetung} /></td></tr>
                <tr className="summe"><td><strong>Summe vor zusammenhängenden Kosten</strong></td><td className="zahl"><strong><Betrag wert={gewaehlt.so.summe} /></strong></td></tr>
                <tr>
                  <td>Freigrenze {gewaehlt.so.freigrenze} € (für alle Einkünfte dieser Kategorie zusammen)</td>
                  <td className="zahl">{gewaehlt.so.freigrenze_ueberschritten ? 'überschritten' : 'nicht überschritten'}</td>
                </tr>
                <tr><td>PIL-Belastung aus Leerverkauf (nicht saldiert, nicht als abzugsfähig angesetzt)</td><td className="zahl"><Betrag wert={gewaehlt.so.belastung_nicht_saldiert} /></td></tr>
                <tr><td>Quellensteuer auf Ersatzzahlungen (nicht in Zeile 41; Anlage AUS bzw. Erstattung gesondert prüfen)</td><td className="zahl"><Betrag wert={gewaehlt.so.pil_quellensteuer} /></td></tr>
              </tbody>
            </table>
          </div>
          <h3>
            {gewaehlt.jahr}: Vorschau Anlage KAP in zwei Varianten (vorläufig, nicht verrechnet) — Zeilen{' '}
            {gewaehlt.kap_varianten[0].formularjahr}:{' '}
            {gewaehlt.kap_varianten[0].status === 'amtlich_belegt'
              ? 'laut amtlichem Vordruck'
              : 'Vordruck liegt nicht vor, wie 2025 angenommen'}
          </h3>
          <p className="sicht">
            <strong>Zeile 19</strong> ist der Saldo der ausländischen Kapitalerträge (Aktien, Optionen, Stillhalter,
            Dividenden, Habenzinsen), <strong>Zeile 18</strong> der Teil aus Aktien deutscher Emittenten; <strong>Zeile 20</strong> die darin enthaltenen Aktiengewinne,{' '}
            <strong>Zeile 22</strong> die Bruttoverluste ohne Aktien (einzelne Optionsgeschäfte, Barausgleich, Futures —
            bei hohem Umschlag sehr große Zahlen) und <strong>Zeile 23</strong> die Aktienverluste. Der Saldo steht in
            Zeile 19; die Zeilen 20, 22 und 23 sind „davon“-Beträge und werden nicht voneinander abgezogen. Welche
            Variante gilt, entscheidet der Steuerberater.
          </p>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <thead>
                <tr>
                  <th className="zahl">Zeile</th>
                  <th>Posten</th>
                  {gewaehlt.kap_varianten.map((k) => (
                    <th key={k.variante} className="zahl" title={k.beschreibung}>{k.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {gewaehlt.kap_varianten[0].posten.map((p, idx) => (
                  <tr key={p.posten}>
                    <td className="zahl">{p.zeile}</td>
                    <td>{KAP_NAME[p.posten] ?? p.posten}</td>
                    {gewaehlt.kap_varianten.map((k) => (
                      <td key={k.variante} className="zahl"><Betrag wert={k.posten[idx].betrag} /></td>
                    ))}
                  </tr>
                ))}
                {gewaehlt.kap_varianten.flatMap((k) =>
                  k.alternativen.map((a) => (
                    <tr key={`${k.variante}-${a.posten}-alt`} className="hinweis">
                      <td className="zahl">{a.zeile}</td>
                      <td colSpan={gewaehlt.kap_varianten.length}>
                        {k.name}: {a.name} → <Betrag wert={a.betrag} />
                      </td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
          <div className="tabelle-rahmen">
            <table className="positionen dichte-kompakt">
              <thead>
                <tr>
                  <th>Zusammensetzung von Zeile 19</th>
                  <th className="zahl">Betrag EUR</th>
                </tr>
              </thead>
              <tbody>
                {gewaehlt.kap_varianten.map((k) => (
                  <>
                    <tr key={`${k.variante}-kopf`} className="summe">
                      <td colSpan={2}><strong>{k.name}</strong> — {k.beschreibung}</td>
                    </tr>
                    {k.zusammensetzung.map((t) => (
                      <tr key={`${k.variante}-${t.name}`}>
                        <td>{t.name}</td>
                        <td className="zahl"><Betrag wert={t.betrag} /></td>
                      </tr>
                    ))}
                    {k.hinweise.map((h) => (
                      <tr key={`${k.variante}-${h}`}>
                        <td colSpan={2} className="hinweis">{h}</td>
                      </tr>
                    ))}
                  </>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Überleitung zu IBs Realized P/L (Activity Statement), EUR</h3>
      <p className="sicht">
        Warum die Station von den Summen im Activity Statement abweicht: <strong>IB schiebt die Prämie einer zugeteilten
        Option in den Einstand der Aktie</strong> (die Option bucht 0) — die Station lässt sie als Stillhalterprämie
        stehen (Arbeitsstand des Steuerberaters). Das verschiebt Beträge zwischen Aktien und Optionen, nicht die Summe.
        Dazu zählen offene Short-Positionen in der Station schon im Zuflussjahr. „Rest“ ist nicht weiter aufgeschlüsselt
        (Zuflussjahr statt Schließungsjahr, Kommission, Kurs, Rundung). Aktien der Station inklusive ETFs.
      </p>
      <div className="tabelle-rahmen">
        <table className="positionen dichte-kompakt">
          <thead>
            <tr>
              <th>Jahr</th>
              <th className="zahl">IB Aktien</th>
              <th className="zahl">− in die Aktie geschobene Prämien</th>
              <th className="zahl">± Rest</th>
              <th className="zahl"><strong>= Station Aktien</strong></th>
              <th className="zahl">IB Optionen + Futures</th>
              <th className="zahl">+ geschobene Prämien (Stillhalter)</th>
              <th className="zahl">+ offene Prämien</th>
              <th className="zahl">± Rest</th>
              <th className="zahl"><strong>= Station Stillhalter + Termin</strong></th>
            </tr>
          </thead>
          <tbody>
            {daten.ib_ueberleitung.map((u) => (
              <tr key={u.jahr}>
                <td>{u.jahr}</td>
                <td className="zahl"><Betrag wert={u.ib_aktien} /></td>
                <td className="zahl"><Betrag wert={String(-Number(u.verschobene_praemien))} /></td>
                <td className="zahl"><Betrag wert={u.rest_aktien} /></td>
                <td className="zahl"><strong><Betrag wert={u.station_aktien} /></strong></td>
                <td className="zahl"><Betrag wert={u.ib_optionen_futures} /></td>
                <td className="zahl"><Betrag wert={u.verschobene_praemien} /></td>
                <td className="zahl"><Betrag wert={u.offene_praemien} /></td>
                <td className="zahl"><Betrag wert={u.rest_optionen} /></td>
                <td className="zahl"><strong><Betrag wert={u.station_optionen} /></strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Fremdwährungssalden laut IB (Cash Report, nur zur Anzeige)</h3>
      <p className="sicht">
        Ein negativer Endbestand ist ein <strong>Sollsaldo</strong> (Margin-Kredit in dieser Währung), kein Guthaben. Der
        Kurseffekt darauf ist hier nicht gerechnet; die Einordnung (§ 20 oder § 23) klärt der Steuerberater (AP-10d).
      </p>
      <div className="tabelle-rahmen">
        <table className="positionen dichte-kompakt">
          <thead>
            <tr>
              <th>Währung</th>
              <th>von</th>
              <th>bis</th>
              <th className="zahl">Anfangsbestand</th>
              <th className="zahl">Endbestand</th>
            </tr>
          </thead>
          <tbody>
            {daten.fremdwaehrung_salden
              .filter((s) => s.waehrung !== 'EUR')
              .map((s) => (
                <tr key={`${s.waehrung}-${s.von}`}>
                  <td>{s.waehrung}</td>
                  <td>{s.von}</td>
                  <td>{s.bis}</td>
                  <td className="zahl"><Betrag wert={s.anfangsbestand} waehrung={s.waehrung} /></td>
                  <td className="zahl"><Betrag wert={s.endbestand} waehrung={s.waehrung} /></td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>

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

      <h3>Regeln und Grundlage</h3>
      <div className="tabelle-rahmen">
        <table className="positionen dichte-kompakt">
          <thead>
            <tr>
              <th>Regel</th>
              <th>Marker</th>
              <th>Grundlage</th>
            </tr>
          </thead>
          <tbody>
            {daten.methode.regeln.map((r) => (
              <tr key={r.id}>
                <td>{r.text}</td>
                <td>
                  {r.marker === 'amtlich_belegt'
                    ? 'amtlich belegt'
                    : r.marker === 'aus_daten_belegt'
                      ? 'aus Daten belegt'
                      : 'vorsichtige Standardbehandlung'}
                </td>
                <td>{r.quelle}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sicht">
        Rechtsquellen und Randnummern sind nicht von der Software geprüft; sie stehen als Hinweis zum Nachlesen da.
      </p>

      <h3>Offene Punkte</h3>
      <ol>
        <li>Quellensteuer auf Ersatzzahlungen: Entlastung (Anlage AUS bzw. ausländische Erstattung) gesondert prüfen.</li>
        <li>Gezahlte Kompensation aus Leerverkäufen: mögliche Abziehbarkeit, bis dahin nicht angesetzt.</li>
        <li>ETF/ETN/ETP (Investmentsteuergesetz) und Zeilen der Anlage KAP 2026 (Vordruck liegt nicht vor).</li>
        <li>USD-Sollsaldo: Einordnung der Kurseffekte (§ 20 oder § 23), Verlustvorträge, Verlustverrechnung.</li>
      </ol>
    </section>
  )
}

type SteuerAntwortJahr = SteuerAntwort['jahre'][number]
