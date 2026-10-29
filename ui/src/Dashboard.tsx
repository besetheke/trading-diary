import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeDepot, holePerformance } from './api'
import type { Depot, Performance, Periode } from './api'
import Betrag from './Betrag'
import Balken from './diagramm/Balken'
import Flaeche from './diagramm/Flaeche'
import { monatKurz } from './diagramm/skala'
import ZweiEbenen from './diagramm/ZweiEbenen'
import { betrag, datumDe, prozent } from './format'
import Ueberleitung from './Ueberleitung'
import { useZeitraum } from './zeitraum'
import ErgebnisBegriffe from './ErgebnisBegriffe'

// Dashboard (überarbeitet 11.10.2026, Wunsch des Nutzers): EIN Diagramm mit drei
// Ansichten statt vieler Einzelkurven —
//   1. Kontowert laut IB, dazu das realisierte Ergebnis (Journal),
//   2. Drawdown in % vom Höchststand (zeitgewichtet, Einzahlungen herausgerechnet),
//   3. Wochen- und Monatswerte (Gewinn laut IB oder realisiert).
// Darunter die Überleitung vom Ergebnis zum Kontostand. Alle Zahlen kommen als
// Text aus der API (GET /performance, /equity, /depot, /ueberleitung); Number()
// nur für Pixel in den Bausteinen (D2, Vertrag 8).

type Ansicht = 'kontowert' | 'drawdown' | 'perioden'
type Einteilung = 'woche' | 'monat'
type Kennzahl = 'gewinn_ib' | 'realisiert'

const ANSICHTEN: { schluessel: Ansicht; titel: string }[] = [
  { schluessel: 'kontowert', titel: 'Kontowert & Ergebnis' },
  { schluessel: 'drawdown', titel: 'Drawdown' },
  { schluessel: 'perioden', titel: 'Wochen / Monate' },
]

// '2026-W05' → 'KW 05/26'; Monate über monatKurz.
function wocheKurz(schluessel: string): string {
  const [jahr, woche] = schluessel.split('-W')
  return `KW ${woche}/${jahr.slice(2)}`
}

function Umschalter<T extends string>({
  werte,
  aktiv,
  waehle,
  beschriftung,
}: {
  werte: T[]
  aktiv: T
  waehle: (wert: T) => void
  beschriftung: (wert: T) => string
}): JSX.Element {
  return (
    <div className="diagramm-wahl" role="group">
      {werte.map((wert) => (
        <button
          key={wert}
          type="button"
          aria-pressed={aktiv === wert}
          className={aktiv === wert ? 'aktiv' : undefined}
          onClick={() => waehle(wert)}
        >
          {beschriftung(wert)}
        </button>
      ))}
    </div>
  )
}

function KontowertDaten({ daten }: { daten: Performance }): JSX.Element {
  const kontowert = new Map(daten.tage.map((tag) => [tag.datum, tag.kontowert]))
  const realisiert = new Map(daten.realisiert_kumuliert.map((punkt) => [punkt.datum, punkt.wert]))
  const tage = Array.from(new Set([...kontowert.keys(), ...realisiert.keys()])).sort((a, b) => b.localeCompare(a))
  return (
    <details className="perioden-tabelle">
      <summary>Daten zum Diagramm ({tage.length} Tage)</summary>
      <div className="tabelle-rahmen">
        <table>
          <thead>
            <tr><th>Datum</th><th className="zahl">Kontowert laut IB</th><th className="zahl">Realisiert kumuliert</th></tr>
          </thead>
          <tbody>
            {tage.map((datum) => (
              <tr key={datum}>
                <td>{datumDe(datum)}</td>
                <td className="zahl"><Betrag wert={kontowert.get(datum) ?? null} /></td>
                <td className="zahl"><Betrag wert={realisiert.get(datum) ?? null} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function DrawdownDaten({ daten }: { daten: Performance }): JSX.Element {
  return (
    <details className="perioden-tabelle">
      <summary>Daten zum Diagramm ({daten.tage.length} Tage)</summary>
      <div className="tabelle-rahmen">
        <table>
          <thead><tr><th>Datum</th><th className="zahl">Drawdown</th></tr></thead>
          <tbody>
            {[...daten.tage].reverse().map((tag) => (
              <tr key={tag.datum}>
                <td>{datumDe(tag.datum)}</td>
                <td className={`zahl ${tag.drawdown_prozent.startsWith('-') ? 'negativ' : ''}`} title={tag.drawdown_prozent}>
                  {betrag(tag.drawdown_prozent)} %
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

export default function Dashboard(): JSX.Element {
  const [zeitraum] = useZeitraum()
  const [performance, setzePerformance] = useState<Performance | null>(null)
  const [depot, setzeDepot] = useState<Depot | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [ansicht, setzeAnsicht] = useState<Ansicht>('kontowert')
  const [einteilung, setzeEinteilung] = useState<Einteilung>('woche')
  const [kennzahl, setzeKennzahl] = useState<Kennzahl>('gewinn_ib')

  useEffect(() => {
    let abgebrochen = false
    setzePerformance(null)
    setzeFehler(null)
    holePerformance(zeitraum.von, zeitraum.bis)
      .then((p) => {
        if (!abgebrochen) setzePerformance(p)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  useEffect(() => {
    holeDepot()
      .then(setzeDepot)
      .catch(() => setzeDepot(null))
  }, [])

  const imZeitraum = zeitraum.von !== null || zeitraum.bis !== null
  const perioden: Periode[] =
    performance === null ? [] : einteilung === 'woche' ? performance.wochen : performance.monate
  const beschrifte = einteilung === 'woche' ? wocheKurz : monatKurz

  return (
    <section className="dashboard">
      <h2>Dashboard</h2>
      <ErgebnisBegriffe />

      {fehler ? (
        <section className="fehler">
          <h3>Das Dashboard konnte nicht geladen werden</h3>
          <p>{fehler}</p>
        </section>
      ) : performance === null ? (
        <p className="laedt">Lade Dashboard …</p>
      ) : (
        <>
          <dl className="kopf">
            <div>
              <dt>Kontowert laut IB</dt>
              <dd>
                <Betrag wert={performance.kontowert_ende} />
              </dd>
            </div>
            <div>
              <dt>Gewinn laut IB{imZeitraum ? ' (Zeitraum)' : ''}</dt>
              <dd>
                <Betrag wert={performance.gewinn_ib_zeitraum} />
              </dd>
            </div>
            <div>
              <dt title="Zeitgewichtet: Ein- und Auszahlungen herausgerechnet">
                Rendite (zeitgewichtet)
              </dt>
              <dd
                className={
                  performance.rendite_zeitraum_quote.startsWith('-') ? 'negativ' : 'positiv'
                }
              >
                {prozent(performance.rendite_zeitraum_quote)}
              </dd>
            </div>
            <div>
              <dt>Realisiert laut Journal{imZeitraum ? ' (Zeitraum)' : ''}</dt>
              <dd>
                <Betrag wert={performance.realisiert_zeitraum} />
              </dd>
            </div>
            <div>
              <dt>
                Max. Drawdown
                {performance.max_drawdown_datum
                  ? ` (${datumDe(performance.max_drawdown_datum)})`
                  : ''}
              </dt>
              <dd className="negativ">{prozent(performance.max_drawdown_quote)}</dd>
            </div>
            {depot !== null && depot.stichtag !== null ? (
              <div>
                <dt>
                  Unrealisiert ({datumDe(depot.stichtag)}) · <Link to="/bestand">Depot</Link>
                </dt>
                <dd>
                  <Betrag wert={depot.summen.unrealisiert_eur} />
                </dd>
              </div>
            ) : null}
          </dl>

          <section className="diagramm-karte">
            <Umschalter
              werte={ANSICHTEN.map((a) => a.schluessel)}
              aktiv={ansicht}
              waehle={setzeAnsicht}
              beschriftung={(wert) => ANSICHTEN.find((a) => a.schluessel === wert)?.titel ?? wert}
            />

            {ansicht === 'kontowert' ? (
              <>
                <ZweiEbenen
                  oben={performance.tage.map((t) => ({ x: t.datum, y: t.kontowert }))}
                  unten={performance.realisiert_kumuliert.map((p) => ({ x: p.datum, y: p.wert }))}
                  titel="Kontowert und realisiertes Ergebnis"
                  nameOben="Kontowert laut IB (EUR)"
                  nameUnten={`Realisiert laut Journal (EUR)${imZeitraum ? ', ab Zeitraumbeginn' : ''}`}
                />
                <KontowertDaten daten={performance} />
                <p className="sicht fussnote">
                  Beide Panels haben dieselbe Zeitachse, aber eigene Werteachsen. Der Kontowert enthält
                  Einzahlungen und unrealisierte Ergebnisse; das realisierte Ergebnis zählt nur abgeschlossene
                  Geschäfte am Tag der Schließung. Wie beide zusammenhängen, zeigt die Überleitung darunter.
                </p>
              </>
            ) : null}

            {ansicht === 'drawdown' ? (
              <>
                <Flaeche
                  punkte={performance.tage.map((t) => ({ x: t.datum, y: t.drawdown_prozent }))}
                  einheit="prozent"
                  titel="Drawdown in Prozent"
                />
                <DrawdownDaten daten={performance} />
                <p className="sicht fussnote">
                  Abstand zum bisherigen Höchststand in Prozent, zeitgewichtet: Ein- und
                  Auszahlungen sind herausgerechnet (sonst sähe eine Einzahlung wie ein Gewinn
                  aus). Basis ist der Kontowert laut IB je Tag.
                  {imZeitraum ? ' Im Zeitraum ist der Vortag die Basis.' : ''}
                </p>
              </>
            ) : null}

            {ansicht === 'perioden' ? (
              <>
                <div className="diagramm-zeile">
                  <Umschalter
                    werte={['woche', 'monat'] as Einteilung[]}
                    aktiv={einteilung}
                    waehle={setzeEinteilung}
                    beschriftung={(wert) => (wert === 'woche' ? 'Wochen' : 'Monate')}
                  />
                  <Umschalter
                    werte={['gewinn_ib', 'realisiert'] as Kennzahl[]}
                    aktiv={kennzahl}
                    waehle={setzeKennzahl}
                    beschriftung={(wert) =>
                      wert === 'gewinn_ib' ? 'Gewinn laut IB' : 'Realisiert (Journal)'
                    }
                  />
                </div>
                <Balken
                  balken={perioden.map((p) => ({ x: p.schluessel, y: p[kennzahl] }))}
                  beschriftung={beschrifte}
                  titel={`${einteilung === 'woche' ? 'Wochen' : 'Monats'}werte: ${kennzahl === 'gewinn_ib' ? 'Gewinn laut IB' : 'Realisiert (Journal)'}`}
                />
                <details className="perioden-tabelle">
                  <summary>Daten zum Diagramm ({perioden.length})</summary>
                  <div className="tabelle-rahmen">
                    <table>
                      <thead>
                        <tr>
                          <th>{einteilung === 'woche' ? 'Woche' : 'Monat'}</th>
                          <th>Zeitraum</th>
                          <th className="zahl">Gewinn laut IB</th>
                          <th className="zahl">Rendite</th>
                          <th className="zahl">Realisiert (Journal)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {[...perioden].reverse().map((p) => (
                          <tr key={p.schluessel}>
                            <td>{beschrifte(p.schluessel)}</td>
                            <td>
                              {datumDe(p.beginn)} – {datumDe(p.ende)}
                            </td>
                            <td className="zahl">
                              <Betrag wert={p.gewinn_ib} />
                            </td>
                            <td
                              className={`zahl ${
                                p.rendite_quote.startsWith('-') ? 'negativ' : 'positiv'
                              }`}
                              title={p.rendite_quote}
                            >
                              {prozent(p.rendite_quote)}
                            </td>
                            <td className="zahl">
                              <Betrag wert={p.realisiert} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
                <p className="sicht fussnote">
                  Gewinn laut IB = Veränderung des Kontowerts ohne Ein- und Auszahlungen
                  (realisiert und unrealisiert); Rendite zeitgewichtet. Realisiert =
                  abgeschlossene Geschäfte laut Journal am Tag der Schließung. Wochen nach ISO
                  (Montag bis Sonntag).
                </p>
              </>
            ) : null}
          </section>
        </>
      )}

      {/* Die Überleitung gilt immer für die gesamte Historie. */}
      <Ueberleitung />
      <p className="sicht fussnote">
        Werte in Euro, Kontosicht. Der Zeitraum oben wirkt auf Kennzahlen und Diagramm, nicht auf
        die Überleitung.
      </p>
    </section>
  )
}
