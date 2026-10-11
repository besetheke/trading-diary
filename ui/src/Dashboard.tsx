import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fehlerText, holeDepot, holeEquity, holeKapital, holeNav } from './api'
import type { Depot, Equity, Kapital, Nav, NavTag } from './api'
import Betrag from './Betrag'
import Balken from './diagramm/Balken'
import Flaeche from './diagramm/Flaeche'
import Linie from './diagramm/Linie'
import ZweiLinien from './diagramm/ZweiLinien'
import { datumDe, prozent, vorzeichen } from './format'
import { useZeitraum } from './zeitraum'

// AP-06e/Dashboard: Equity-Kurve und Drawdown. Seit AP-08g1 (D1–D3 in
// auftraege/AP-08f.md) stehen über den Tabellen eigene SVG-Diagramme —
// Linie, Fläche, Balken, ohne Diagramm-Bibliothek; die Tabellen bleiben
// darunter (D3: Nachvollziehen geht vor). Geld bleibt Zeichenkette, nichts
// wird hier gerechnet (Vertrag 8/9 wie überall; Ausnahme nur für Pixel in
// den Bausteinen, D2). AP-08f1: deutsche Schreibweise, Rohwert im title.
// AP-08h: Abschnitt „Kontowert laut IB" (GET /nav) unter der Equity-Sektion
// — Kontowert und Einzahlungen als zwei Linien mit Fläche, umschaltbar auf
// „Gewinn laut IB" neben der realisierten Equity; alles Werte der API.
// AP-08g2: Kapitalentwicklung (GET /kapital) unter der Drawdown-Fläche —
// realisiertes Kapital, Kopf-Kennzahlen alles Werte der API.

// Bestandteile des Kontowerts am letzten Tag — Feld null heißt Zeile weg.
const BESTANDTEILE: { titel: string; feld: 'cash' | 'aktien' | 'optionen' | 'rohstoffe' }[] = [
  { titel: 'Cash', feld: 'cash' },
  { titel: 'Aktien', feld: 'aktien' },
  { titel: 'Optionen', feld: 'optionen' },
  { titel: 'Rohstoffe', feld: 'rohstoffe' },
]

export default function Dashboard(): JSX.Element {
  const [zeitraum] = useZeitraum()
  const [equity, setzeEquity] = useState<Equity | null>(null)
  const [fehler, setzeFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    setzeEquity(null)
    setzeFehler(null)
    holeEquity(zeitraum.von, zeitraum.bis)
      .then((ergebnis) => {
        if (!abgebrochen) setzeEquity(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  // AP-08h: Kontowert laut IB — eigene Quelle, eigener Fehlertext, eigener
  // Ladezustand; der Abschnitt hängt nicht an der Equity.
  const [nav, setzeNav] = useState<Nav | null>(null)
  const [navFehler, setzeNavFehler] = useState<string | null>(null)
  // Welche der beiden Ansichten des Kontowerts gezeigt wird.
  const [ibAnsicht, setzeIbAnsicht] = useState<'kontowert' | 'gewinn'>('kontowert')
  // AP-08d: unrealisiertes Ergebnis der offenen Positionen laut IB (letzter
  // Stichtag, kein Zeitverlauf) — eigene Quelle, fällt still weg, wenn sie fehlt.
  const [depot, setzeDepot] = useState<Depot | null>(null)
  useEffect(() => {
    holeDepot()
      .then(setzeDepot)
      .catch(() => setzeDepot(null))
  }, [])

  useEffect(() => {
    let abgebrochen = false
    setzeNav(null)
    setzeNavFehler(null)
    holeNav(zeitraum.von, zeitraum.bis)
      .then((ergebnis) => {
        if (!abgebrochen) setzeNav(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeNavFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  // AP-08g2: Kapitalentwicklung (realisiert, AP-06g) — eigene Quelle wie der
  // Kontowert, eigener Ladezustand; Abschnitt unter der Drawdown-Fläche.
  const [kapital, setzeKapital] = useState<Kapital | null>(null)
  const [kapitalFehler, setzeKapitalFehler] = useState<string | null>(null)

  useEffect(() => {
    let abgebrochen = false
    setzeKapital(null)
    setzeKapitalFehler(null)
    holeKapital(zeitraum.von, zeitraum.bis)
      .then((ergebnis) => {
        if (!abgebrochen) setzeKapital(ergebnis)
      })
      .catch((ursache: unknown) => {
        if (!abgebrochen) setzeKapitalFehler(fehlerText(ursache))
      })
    return () => {
      abgebrochen = true
    }
  }, [zeitraum.von, zeitraum.bis])

  const imZeitraum = zeitraum.von !== null || zeitraum.bis !== null

  if (fehler) {
    return (
      <section className="fehler">
        <h3>Das Dashboard konnte nicht geladen werden</h3>
        <p>{fehler}</p>
      </section>
    )
  }

  if (equity === null) {
    return <p className="laedt">Lade Dashboard …</p>
  }

  const letzterTag = equity.tage.length > 0 ? equity.tage[equity.tage.length - 1] : null

  // AP-08h: Der Abschnitt „Kontowert laut IB" — Kopf, Umschalter, Diagramm
  // und Bestandteile. Alles Werte der API (Vertrag 8); im Zeitraum ist die
  // Journal-Equity nicht vergleichbar und bleibt weg (keine Umrechnung im
  // Browser).
  function ibAbschnitt(navWert: Nav, letzter: NavTag, equityWert: Equity): JSX.Element {
    return (
      <>
        <dl className="kopf">
          <div>
            <dt>Kontowert am Ende ({datumDe(letzter.datum)})</dt>
            <dd>
              <Betrag wert={navWert.endwert} />
            </dd>
          </div>
          {imZeitraum && navWert.anfangswert !== null ? (
            <div>
              <dt>Kontowert am Anfang</dt>
              <dd>
                <Betrag wert={navWert.anfangswert} />
              </dd>
            </div>
          ) : null}
          <div>
            <dt>Gewinn laut IB</dt>
            <dd>
              <Betrag wert={letzter.gewinn} />
            </dd>
          </div>
          <div>
            <dt>Einzahlungen kumuliert</dt>
            <dd>
              <Betrag wert={letzter.einzahlungen_kumuliert} />
            </dd>
          </div>
          {depot !== null && depot.stichtag !== null ? (
            <div>
              <dt title="Unrealisiertes Ergebnis aller offenen Positionen laut IB, Stand des letzten Berichts">
                Unrealisiert laut IB ({datumDe(depot.stichtag)}) · <Link to="/bestand">Depot</Link>
              </dt>
              <dd>
                <Betrag wert={depot.summen.unrealisiert_eur} />
              </dd>
            </div>
          ) : null}
        </dl>

        <div className="diagramm-wahl" role="group" aria-label="Ansicht des Kontowerts">
          <button
            type="button"
            aria-pressed={ibAnsicht === 'kontowert'}
            onClick={() => setzeIbAnsicht('kontowert')}
          >
            Kontowert
          </button>
          <button
            type="button"
            aria-pressed={ibAnsicht === 'gewinn'}
            onClick={() => setzeIbAnsicht('gewinn')}
          >
            Gewinn laut IB
          </button>
        </div>

        {ibAnsicht === 'kontowert' ? (
          <ZweiLinien
            oben={navWert.tage.map((t) => ({ x: t.datum, y: t.gesamt }))}
            unten={navWert.tage.map((t) => ({ x: t.datum, y: t.einzahlungen_kumuliert }))}
            flaeche
            farbe={vorzeichen(letzter.gewinn) === 'negativ' ? 'negativ' : 'positiv'}
            legendeOben="Kontowert gesamt"
            legendeUnten="Einzahlungen kumuliert"
          />
        ) : (
          <>
            <ZweiLinien
              oben={navWert.tage.map((t) => ({ x: t.datum, y: t.gewinn }))}
              unten={
                imZeitraum || equityWert.tage.length === 0
                  ? null
                  : equityWert.tage.map((t) => ({ x: t.datum, y: t.kumuliert_eur }))
              }
              legendeOben="Gewinn laut IB (realisiert + unrealisiert)"
              legendeUnten={
                imZeitraum || equityWert.tage.length === 0 ? null : 'realisiert laut Journal'
              }
            />
            <p className="sicht fussnote">
              {imZeitraum
                ? 'Im Zeitraum beginnt die Equity bei 0, der Gewinn laut IB nicht — im Zeitraum nicht vergleichbar. '
                : ''}
              Seit AP-06i enthält die Journal-Linie auch Aktien ohne Struktur; der verbleibende
              Abstand ist im Wesentlichen unrealisiert und Andienungsmethode (OF-78).
            </p>
          </>
        )}

        {navWert.anzahl_kurs_fehlt > 0 ? (
          <p className="sicht fussnote">{navWert.anzahl_kurs_fehlt} Einzahlungen ohne Kurs.</p>
        ) : null}

        <h4>Bestandteile am {datumDe(letzter.datum)}</h4>
        <table className="bestandteile">
          <tbody>
            {BESTANDTEILE.filter((teil) => letzter[teil.feld] !== null).map((teil) => (
              <tr key={teil.feld}>
                <td>{teil.titel}</td>
                <td className="zahl">
                  <Betrag wert={letzter[teil.feld]} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </>
    )
  }

  return (
    <section>
      <h2>Dashboard</h2>
      <p className="sicht fussnote">
        Equity-Kurve und Monatsübersicht, Kontosicht, in EUR — Ergebnis am Tag der
        Schließung.
        {imZeitraum
          ? ' Im gewählten Zeitraum beginnt die Kurve bei 0; der Drawdown zählt nur darin.'
          : ''}
      </p>

      {equity.tage.length === 0 ? (
        <section className="hinweis">
          <p>
            {imZeitraum
              ? 'Im gewählten Zeitraum wurde keine Struktur mit Kurs geschlossen.'
              : 'Noch keine abgeschlossene Struktur mit Kurs — die Equity-Kurve ist leer.'}
          </p>
        </section>
      ) : (
        <>
          <dl className="kopf">
            <div>
              <dt>
                {imZeitraum ? 'Ergebnis im Zeitraum' : 'Stand'}{' '}
                {letzterTag ? `(bis ${datumDe(letzterTag.datum)})` : ''}
              </dt>
              <dd>
                <Betrag wert={letzterTag ? letzterTag.kumuliert_eur : null} />
              </dd>
            </div>
            <div>
              <dt>
                Maximaler Drawdown
                {equity.max_drawdown_datum ? ` (${datumDe(equity.max_drawdown_datum)})` : ''}
              </dt>
              <dd>
                <Betrag wert={equity.max_drawdown_eur} />
              </dd>
            </div>
            <div>
              <dt>Tage mit Aktivität</dt>
              <dd>{equity.tage.length}</dd>
            </div>
          </dl>

          <h3>Equity-Kurve</h3>
          <Linie punkte={equity.tage.map((t) => ({ x: t.datum, y: t.kumuliert_eur }))} />

          <h3>Drawdown</h3>
          <Flaeche punkte={equity.tage.map((t) => ({ x: t.datum, y: t.drawdown_eur }))} />

          <h3>Monatsübersicht</h3>
          <Balken balken={equity.monate.map((m) => ({ x: m.monat, y: m.summe_netto_eur }))} />
          <table>
            <thead>
              <tr>
                <th>Monat</th>
                <th className="zahl">Strukturen</th>
                <th className="zahl">Summe netto</th>
                <th className="zahl">Durchschnitt</th>
                <th className="zahl">Trefferquote</th>
                <th className="zahl">Kursmangel</th>
              </tr>
            </thead>
            <tbody>
              {equity.monate
                .slice()
                .reverse()
                .map((m) => (
                  <tr key={m.monat}>
                    <td>{m.monat}</td>
                    <td className="zahl">{m.anzahl_strukturen}</td>
                    <td className="zahl">
                      <Betrag wert={m.summe_netto_eur} />
                    </td>
                    <td className="zahl">
                      <Betrag wert={m.durchschnitt_netto_eur} />
                    </td>
                    <td className="zahl">{prozent(m.trefferquote)}</td>
                    <td className="zahl">{m.anzahl_strukturen_kurs_fehlt || ''}</td>
                  </tr>
                ))}
            </tbody>
          </table>

          <details className="tagesreihe">
            <summary>Tagesreihe ({equity.tage.length} Tage)</summary>
            <table>
              <thead>
                <tr>
                  <th>Datum</th>
                  <th className="zahl">Strukturen</th>
                  <th className="zahl">Netto</th>
                  <th className="zahl">Kumuliert</th>
                  <th className="zahl">Drawdown</th>
                  <th className="zahl">Kursmangel</th>
                </tr>
              </thead>
              <tbody>
                {equity.tage
                  .slice()
                  .reverse()
                  .map((t) => (
                    <tr key={t.datum}>
                      <td>{datumDe(t.datum)}</td>
                      <td className="zahl">{t.anzahl_strukturen}</td>
                      <td className="zahl">
                        <Betrag wert={t.netto_eur} />
                      </td>
                      <td className="zahl">
                        <Betrag wert={t.kumuliert_eur} />
                      </td>
                      <td className="zahl">
                        <Betrag wert={t.drawdown_eur} />
                      </td>
                      <td className="zahl">{t.anzahl_strukturen_kurs_fehlt || ''}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </details>
        </>
      )}

      {/* AP-08g2: Kapitalentwicklung unter der Drawdown-Fläche — realisiert,
          unrealisierte Ergebnisse offener Positionen fehlen bewusst. */}
      <h3>Kapitalentwicklung</h3>
      {kapitalFehler !== null ? (
        <section className="fehler">
          <h4>Die Kapitalentwicklung konnte nicht geladen werden</h4>
          <p>{kapitalFehler}</p>
        </section>
      ) : kapital === null ? (
        <p className="laedt">Lade Kapitalentwicklung …</p>
      ) : (
        <>
          <Linie punkte={kapital.tage.map((t) => ({ x: t.datum, y: t.kapital }))} />
          <dl className="kopf">
            <div>
              <dt>Anfangskapital</dt>
              <dd>
                <Betrag wert={kapital.anfangskapital} />
              </dd>
            </div>
            <div>
              <dt>Endkapital</dt>
              <dd>
                <Betrag wert={kapital.endkapital} />
              </dd>
            </div>
            <div>
              <dt>Einzahlungen</dt>
              <dd>
                <Betrag wert={kapital.einzahlungen_im_zeitraum} />
              </dd>
            </div>
            <div>
              <dt>Ergebnis</dt>
              <dd>
                <Betrag wert={kapital.ergebnis_im_zeitraum} />
              </dd>
            </div>
            <div>
              <dt>Cash</dt>
              <dd>
                <Betrag wert={kapital.cash_im_zeitraum} />
              </dd>
            </div>
          </dl>
          <p className="sicht fussnote">
            realisiert — Einzahlungen, abgeschlossene Geschäfte und Cash-Posten;
            unrealisierte Ergebnisse offener Positionen sind nicht enthalten.
          </p>
        </>
      )}

      {/* AP-08h: Kontowert laut IB unter der Equity-Sektion — IBs eigene
          Zahl, keine Rechnung des Journals. */}
      <h3>Kontowert laut IB</h3>
      {navFehler !== null ? (
        <section className="fehler">
          <h4>Der Kontowert konnte nicht geladen werden</h4>
          <p>{navFehler}</p>
        </section>
      ) : nav === null ? (
        <p className="laedt">Lade Kontowert laut IB …</p>
      ) : nav.tage.length === 0 ? (
        <section className="hinweis">
          <p>
            Noch kein Kontowert importiert — die Flex-Query braucht den Abschnitt NAV
            (Net Asset Value) in Base.
          </p>
        </section>
      ) : (
        ibAbschnitt(nav, nav.tage[nav.tage.length - 1], equity)
      )}
    </section>
  )
}
