import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiFehler, fehlerText, holeAusfuehrungen, holeKette, holeStruktur } from './api'
import type { Ausfuehrung, KetteDetail, Kettenglied, StrukturDetail } from './api'
import Journal from './Journal'
import { betrag, datumDe, zeitDe } from './format'
import Betrag from './Betrag'

// Bezeichner aus der Datenbank, deutsch gelesen — ein unbekannter Schlüssel
// wird unverändert gezeigt statt verschwiegen.
const VERKNUEPFUNGEN: Record<string, string> = {
  open: 'Eröffnung',
  roll: 'Roll',
  close: 'Schluss',
  adjust: 'Anpassung',
  // AP-04z: zugeteilte Aktie und Covered Call gehören zur Position (OF-81).
  zuteilung: 'Zuteilung (Aktie)',
  covered_call: 'Covered Call',
}

const ERKENNUNGEN: Record<string, string> = {
  auto: 'automatisch belegt',
  heuristik: 'Heuristik',
  manuell: 'manuell gesetzt',
}

function verknuepfung(schluessel: string): string {
  return VERKNUEPFUNGEN[schluessel] ?? schluessel
}

function erkennung(schluessel: string): string {
  return ERKENNUNGEN[schluessel] ?? schluessel
}

// AP-13x, Regel 7: Die OA-Zuordnung ist automatisch erzeugt — und bei
// Unsicherheit (Fingerabdruck weicht ab) muss das erkennbar bleiben, statt
// als stille Tatsache serviert zu werden. Ein Tooltip genügt (Vertrag).
function oaErkennungsHinweis(wert: string | null): string | undefined {
  if (wert === 'auto') return 'automatisch'
  if (wert === 'heuristik') return 'unsicher, Fingerabdruck weicht ab'
  return undefined
}

// Dichte wie in der Positionsliste (gleicher gemerkter Wert, Nutzerwunsch 17.10.2026).
type Dichte = 'normal' | 'kompakt' | 'sehr'
const DICHTEN: [Dichte, string, string][] = [
  ['normal', 'Normal', 'Wie bisher'],
  ['kompakt', 'Kompakt', 'Kleinere Schrift, Kennzahlen eng in einer Zeile'],
  ['sehr', 'Sehr kompakt', 'Kleinste Schrift, Glieder ohne Abstand'],
]
const DICHTE_SCHLUESSEL = 'positionen-dichte'

function leseDichte(): Dichte {
  try {
    const wert = window.localStorage.getItem(DICHTE_SCHLUESSEL)
    return wert === 'normal' || wert === 'sehr' || wert === 'kompakt' ? wert : 'kompakt'
  } catch {
    return 'kompakt'
  }
}

export default function PositionDetail(): JSX.Element {
  const { chainId } = useParams()
  const [dichte, setzeDichteZustand] = useState<Dichte>(() => leseDichte())
  function setzeDichte(wert: Dichte): void {
    setzeDichteZustand(wert)
    try {
      window.localStorage.setItem(DICHTE_SCHLUESSEL, wert)
    } catch {
      /* Speicher fehlt — die Wahl gilt dann nur für diese Sitzung. */
    }
  }
  const nummer = Number.parseInt(chainId ?? '', 10)
  const [kette, setzeKette] = useState<KetteDetail | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)
  const [nichtGefunden, setzeNichtGefunden] = useState(false)

  useEffect(() => {
    if (Number.isNaN(nummer)) return
    let abgebrochen = false
    setzeKette(null)
    setzeFehler(null)
    setzeNichtGefunden(false)
    holeKette(nummer)
      .then((ergebnis) => {
        if (!abgebrochen) setzeKette(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (abgebrochen) return
        if (ursache instanceof ApiFehler && ursache.status === 404) {
          setzeNichtGefunden(true)
        } else {
          setzeFehler(fehlerText(ursache))
        }
      })
    return () => {
      abgebrochen = true
    }
  }, [nummer])

  if (Number.isNaN(nummer)) {
    return (
      <section className="hinweis">
        <p>Diese Adresse nennt keine Positionsnummer.</p>
        <p>
          <Link to="/">Zur Positionsliste</Link>
        </p>
      </section>
    )
  }

  if (nichtGefunden) {
    return (
      <section className="hinweis">
        <p>Position {chainId} nicht gefunden — vielleicht veralteter Verweis.</p>
        <p>
          <Link to="/">Zur Positionsliste</Link>
        </p>
      </section>
    )
  }

  if (fehler) {
    return (
      <section className="fehler">
        <h3>Die Position konnte nicht geladen werden</h3>
        <p>{fehler}</p>
      </section>
    )
  }

  if (kette === null) {
    return <p className="laedt">Lade Position {nummer} …</p>
  }

  return (
    <section className={`kettendetail dichte-${dichte}`}>
      <nav className="zurueck">
        <Link to="/">← Zur Positionsliste</Link>
      </nav>
      <h2>
        {kette.underlying} · Kette {kette.chain_id}
      </h2>
      <dl className="kopf">
        <div>
          <dt>Anlageklasse</dt>
          <dd>{kette.asset_class}</dd>
        </div>
        <div>
          <dt>Seite</dt>
          <dd>{kette.seite ?? '—'}</dd>
        </div>
        <div>
          <dt>Eröffnet</dt>
          <dd title={kette.eroeffnet_am}>{zeitDe(kette.eroeffnet_am)}</dd>
        </div>
        <div>
          <dt>Beendet</dt>
          <dd title={kette.beendet_am ?? undefined}>
            {kette.beendet_am ? zeitDe(kette.beendet_am) : '—'}
          </dd>
        </div>
        <div>
          <dt>Rolls</dt>
          <dd className="zahl">{kette.anzahl_rolls}</dd>
        </div>
        <div>
          <dt>Endzustand</dt>
          <dd>{kette.endzustand ?? '—'}</dd>
        </div>
        <div>
          <dt>Glieder</dt>
          <dd className="zahl">{kette.anzahl_glieder}</dd>
        </div>
        <div>
          <dt>Ergebnis netto (Kontosicht)</dt>
          <dd className="zahl">
            <Betrag wert={kette.struktur_summe_netto} waehrung={kette.waehrung ?? undefined} />
            {kette.struktur_summe_netto === null && kette.waehrungen.length > 1
              ? ` (${kette.waehrungen.join(' / ')} — keine Summe)`
              : ''}
          </dd>
        </div>
      </dl>

      <h3>Verlauf</h3>
      <div className="diagramm-wahl" role="group" aria-label="Dichte der Ansicht">
        {DICHTEN.map(([wert, name, hinweis]) => (
          <button
            key={wert}
            type="button"
            aria-pressed={dichte === wert}
            title={hinweis}
            onClick={() => setzeDichte(wert)}
          >
            {name}
          </button>
        ))}
      </div>
      <ol className="verlauf">
        {kette.glieder.map((glied) => (
          <GliedKarte key={glied.struktur.structure_id} glied={glied} />
        ))}
      </ol>

      {/* AP-08j: Journal der Kette — unterhalb aller bestehenden Inhalte. */}
      <Journal scopeTyp="chain" scopeId={String(nummer)} />
    </section>
  )
}

function GliedKarte({ glied }: { glied: Kettenglied }): JSX.Element {
  const struktur = glied.struktur
  const [offen, setzeOffen] = useState(false)
  const [detail, setzeDetail] = useState<StrukturDetail | null>(null)
  const [ausfuehrungen, setzeAusfuehrungen] = useState<Ausfuehrung[] | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  function umschalten(): void {
    if (!offen && detail === null && ausfuehrungen === null && fehler === null) {
      // Drilldown erst auf Wunsch — die Ansicht bleibt so schnell wie der
      // Einzelabruf der Kette (Vertrag 10).
      Promise.all([holeStruktur(struktur.structure_id), holeAusfuehrungen(struktur.structure_id)])
        .then(([s, a]) => {
          setzeDetail(s)
          setzeAusfuehrungen(a)
        })
        .catch((ursache: unknown) => setzeFehler(fehlerText(ursache)))
    }
    setzeOffen(!offen)
  }

  return (
    <li className="glied">
      <header>
        <span className="marke" aria-hidden="true">
          {glied.sequenz}
        </span>
        <div>
          <h4>
            {verknuepfung(glied.verknuepfungstyp)} · {struktur.typ}
          </h4>
          <p className="erkennung">
            Verknüpfung: {glied.verknuepfungstyp} · Erkennung: {erkennung(glied.erkennung)}
          </p>
        </div>
        <button type="button" onClick={umschalten}>
          {offen ? 'Legs und Ausführungen ausblenden' : 'Legs und Ausführungen anzeigen'}
        </button>
      </header>

      <dl className="struktur">
        {/* AP-08lk, Punkt 1: Der Naturschlüssel (zehnstellige IB-Nummern,
            durch | getrennt — je Leg eine) läuft aus einer gewöhnlichen
            Rasterzelle heraus und verdeckt die Nachbarbeschriftung. Er
            bekommt eine eigene Zeile über die volle Breite; der vollständige
            Wert bleibt im Text und zusätzlich im title — kopierbar für die
            Durchsicht (`journal kandidaten-einlesen`). */}
        <div className="voll">
          <dt>Struktur</dt>
          <dd className="schluessel" title={struktur.natur_schluessel}>
            {struktur.natur_schluessel}
          </dd>
        </div>
        {/* AP-13x: OA-Strategie und -Status der Struktur (AP-13wk), direkt
            nach der Verknüpfungs-Erkennung im Kartenkopf — reines
            Durchreichen, leer bleibt —. Die OA-Erkennung wird nur als
            Hinweis (title) beim Status sichtbar, kein eigenes Element. */}
        <div>
          <dt>OA-Strategie</dt>
          <dd>{struktur.oa_strategie ?? '—'}</dd>
        </div>
        <div>
          <dt>OA-Status</dt>
          <dd title={oaErkennungsHinweis(struktur.oa_erkennung)}>
            {struktur.oa_status ?? '—'}
          </dd>
        </div>
        <div>
          <dt>Basiswert</dt>
          <dd>{struktur.underlying}</dd>
        </div>
        <div>
          <dt>Klasse</dt>
          <dd>{struktur.asset_class}</dd>
        </div>
        <div>
          <dt>Verfall</dt>
          <dd>{datumDe(struktur.expiry)}</dd>
        </div>
        <div>
          <dt>Short-Strike</dt>
          <dd className="zahl">{struktur.short_strike ?? '—'}</dd>
        </div>
        <div>
          <dt>Long-Strike</dt>
          <dd className="zahl">{struktur.long_strike ?? '—'}</dd>
        </div>
        <div>
          <dt>Breite</dt>
          <dd className="zahl">{struktur.breite ?? '—'}</dd>
        </div>
        <div>
          <dt>Menge</dt>
          <dd className="zahl">{struktur.menge}</dd>
        </div>
        <div>
          <dt>DTE bei Eröffnung</dt>
          <dd>{struktur.dte_bei_eroeffnung ?? '—'}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{struktur.status ?? '—'}</dd>
        </div>
        <div>
          <dt>Eröffnet</dt>
          <dd title={struktur.eroeffnet_am}>{zeitDe(struktur.eroeffnet_am)}</dd>
        </div>
        <div>
          <dt>Geschlossen</dt>
          <dd title={struktur.geschlossen_am ?? undefined}>
            {zeitDe(struktur.geschlossen_am)}
          </dd>
        </div>
        {/* AP-08fp, Vertrag 3 und 4, AP-08f1: Der Eröffnungs- und Schlusspreis
            gehören fachlich neben das Ergebnis — deutsch über betrag(), ohne
            Farbe, der Rohwert im title. Leer bleibt leer: eine offene
            Struktur hat keinen Schlusspreis und zeigt —. */}
        <div>
          <dt>Preis auf</dt>
          <dd className="zahl" title={struktur.eroeffnungspreis ?? undefined}>
            {struktur.eroeffnungspreis === null
              ? '—'
              : `${betrag(struktur.eroeffnungspreis)} ${struktur.waehrung}`}
          </dd>
        </div>
        <div>
          <dt>Preis zu</dt>
          <dd className="zahl" title={struktur.schlusspreis ?? undefined}>
            {struktur.schlusspreis === null
              ? '—'
              : `${betrag(struktur.schlusspreis)} ${struktur.waehrung}`}
          </dd>
        </div>
        <div>
          <dt>Brutto</dt>
          <dd className="zahl">
            <Betrag wert={struktur.brutto_pnl} waehrung={struktur.waehrung} />
          </dd>
        </div>
        <div>
          <dt>Kommission</dt>
          <dd className="zahl">
            <Betrag wert={struktur.kommission} waehrung={struktur.waehrung} />
          </dd>
        </div>
        <div>
          <dt>Netto (Kontosicht)</dt>
          <dd className="zahl">
            <Betrag wert={struktur.netto_pnl} waehrung={struktur.waehrung} />
          </dd>
        </div>
      </dl>

      {offen && fehler && (
        <section className="fehler">
          <h4>Drilldown fehlgeschlagen</h4>
          <p>{fehler}</p>
        </section>
      )}

      {offen && detail !== null && (
        <details className="drilldown" open>
          <summary>Legs ({detail.legs.length})</summary>
          {detail.legs.length === 0 ? (
            <p className="sicht">Keine Legs zu dieser Struktur.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Conid</th>
                  <th className="zahl">Menge</th>
                  <th>Eröffnung</th>
                  <th>Schluss</th>
                  <th>Matching</th>
                  <th>offen?</th>
                  <th className="zahl">Brutto</th>
                  <th className="zahl">Kommission</th>
                </tr>
              </thead>
              <tbody>
                {detail.legs.map((leg) => (
                  <tr key={leg.leg_id} className={leg.offen_ja_nein ? 'offen' : undefined}>
                    <td title={leg.basis_ungeklaert ? 'Basiszuordnung ungeklärt' : undefined}>
                      {leg.conid}
                      {leg.basis_ungeklaert ? ' ⚠' : ''}
                    </td>
                    <td className="zahl">{leg.menge}</td>
                    <td>{leg.open_exec_id}</td>
                    <td>{leg.close_exec_id ?? '—'}</td>
                    <td>{leg.matching_methode}</td>
                    <td>{leg.offen_ja_nein ? 'ja' : 'nein'}</td>
                    <td className="zahl">
                      <Betrag wert={leg.brutto_pnl} waehrung={struktur.waehrung} />
                    </td>
                    <td className="zahl">
                      <Betrag wert={leg.kommission_gesamt} waehrung={struktur.waehrung} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </details>
      )}

      {offen && ausfuehrungen !== null && (
        <details className="drilldown" open>
          <summary>Ausführungen ({ausfuehrungen.length})</summary>
          {ausfuehrungen.length === 0 ? (
            <p className="sicht">Keine Ausführungen zu dieser Struktur.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Zeit</th>
                  <th>Rolle</th>
                  <th>Symbol</th>
                  <th>Seite</th>
                  <th className="zahl">Menge</th>
                  <th className="zahl">Preis</th>
                  <th className="zahl">Kommission</th>
                  <th>Ereignis</th>
                  <th>Batch</th>
                </tr>
              </thead>
              <tbody>
                {ausfuehrungen.map((ausfuehrung) => (
                  <tr key={ausfuehrung.exec_id}>
                    <td className="zeit" title={ausfuehrung.handelszeit}>
                      {zeitDe(ausfuehrung.handelszeit)}
                    </td>
                    <td>{ausfuehrung.rolle}</td>
                    <td title={`Conid ${ausfuehrung.conid}`}>{ausfuehrung.symbol}</td>
                    <td>{ausfuehrung.side}</td>
                    <td className="zahl">{ausfuehrung.menge}</td>
                    <td className="zahl" title={ausfuehrung.preis}>
                      {betrag(ausfuehrung.preis)} {ausfuehrung.waehrung}
                    </td>
                    <td className="zahl">
                      <Betrag wert={ausfuehrung.kommission} waehrung={ausfuehrung.waehrung} />
                    </td>
                    <td>{ausfuehrung.ereignistyp}</td>
                    <td title={ausfuehrung.oa_trade ?? undefined}>
                      {ausfuehrung.exec_batch ?? '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </details>
      )}
    </li>
  )
}
