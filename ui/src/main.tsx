import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from './Dashboard'
import Depot from './Depot'
import Titel from './Titel'
import RollKosten from './RollKosten'
import DaxSynthetic from './DaxSynthetic'
import Zeitraumwahl from './Zeitraumwahl'
import { useZeitraum, zeitraumSuche } from './zeitraum'
import Kalender from './Kalender'
import Kampagnen from './Kampagnen'
import KostenErtraege from './KostenErtraege'
import Steuer from './Steuer'
import PositionDetail from './PositionDetail'
import Positionen from './Positionen'
import Rollkandidaten from './Rollkandidaten'
import Strategien from './Strategien'
import OaAbgleich from './OaAbgleich'
import Backtests from './Backtests'
import Tag from './Tag'
import Uebersicht from './Uebersicht'
import { BreakoutSeite, MomentumSeite, RollerSeite, SystemSeite } from './Station'
import './stil.css'

// AP-08j: „Heute" zeigt das Datum der lokalen Zeit des Browsers — kein
// toISOString, das je Zeitzone auf den Vortag rutschen würde.
function heuteDatum(): string {
  const jetzt = new Date()
  const monat = String(jetzt.getMonth() + 1).padStart(2, '0')
  const tag = String(jetzt.getDate()).padStart(2, '0')
  return `${jetzt.getFullYear()}-${monat}-${tag}`
}

// AP-08f2: Seiten, auf die der Zeitraum schon wirkt. Die übrigen zeigen den
// Wähler trotzdem (Z1: ein Zeitraum für alles) und sagen ehrlich, dass er
// dort noch nichts filtert. AP-08g2: /kosten wirkt ebenfalls; AP-08z: die
// Positionsliste (/) ebenso.
const ZEITRAUM_SEITEN = ['/', '/dashboard', '/kosten', '/strategie', '/abgleich', '/backtest', '/titel']

// AP-14a: Bereiche der Station. Jede Seite gehört zu genau einem Bereich; die
// erste Zeile wählt den Bereich, die zweite die Seiten darin.
type Bereich = 'journal' | 'pruefen' | 'roller' | 'momentum' | 'breakout' | 'system'

function bereichVon(pfad: string): Bereich {
  if (['/abgleich', '/backtest', '/rolls'].includes(pfad)) return 'pruefen'
  if (pfad === '/roller') return 'roller'
  if (pfad === '/momentum') return 'momentum'
  if (pfad === '/breakout') return 'breakout'
  if (pfad === '/zustand') return 'system'
  return 'journal'
}

// Seiten ohne Zeitraum: Der Wähler bleibt dort aus (Momentum Lab, System …).
const OHNE_ZEITRAUM: Bereich[] = ['roller', 'momentum', 'breakout', 'system']

function Kopf(): JSX.Element {
  const ort = useLocation()
  const [zeitraum] = useZeitraum()
  const mit = zeitraumSuche(zeitraum)
  const bereich = bereichVon(ort.pathname)
  const aktiv = (b: Bereich) => (b === bereich ? 'aktiv' : undefined)
  return (
    <header>
      <h1>
        <Link to="/start">Trading Station</Link>
      </h1>
      <nav className="bereichsnav">
        <Link className={aktiv('journal')} to="/start">Journal</Link>
        <Link className={aktiv('pruefen')} to={`/backtest${mit}`}>Abgleich &amp; Tests</Link>
        <Link className={aktiv('roller')} to="/roller">Roller</Link>
        <Link className={aktiv('momentum')} to="/momentum">Momentum Lab</Link>
        <Link className={aktiv('breakout')} to="/breakout">Breakout</Link>
        <Link className={aktiv('system')} to="/zustand">System</Link>
      </nav>
      {bereich === 'journal' && (
        <nav className="hauptnav">
          <Link to="/start">Übersicht</Link>
          <Link to={`/dashboard${mit}`}>Dashboard</Link>
          <Link to={`/bestand${mit}`}>Depot</Link>
          <Link to={`/${mit}`}>Positionen</Link>
          <Link to={`/titel${mit}`}>Titel</Link>
          <Link to={`/strategie${mit}`}>Strategien</Link>
          <Link to={`/kampagnenliste${mit}`}>Kampagnen</Link>
          <Link to={`/kosten${mit}`}>Kosten &amp; Erträge</Link>
          <Link to="/roll-kosten">Roll-Kosten</Link>
          {/* DAX Synthetic ist zurückgestellt (20.10.2026): Seite bleibt unter /dax-synthetic erreichbar, nicht im Menü. */}
          <Link to="/steuer">Steuer</Link>
          <Link to={`/monat${mit}`}>Kalender</Link>
          <Link to={`/tag/${heuteDatum()}${mit}`}>Heute</Link>
        </nav>
      )}
      {bereich === 'pruefen' && (
        <nav className="hauptnav">
          <Link to={`/backtest${mit}`}>Backtests</Link>
          <Link to={`/abgleich${mit}`}>Abgleich OA</Link>
          <Link to="/rolls">Rolls prüfen</Link>
        </nav>
      )}
      {!OHNE_ZEITRAUM.includes(bereich) && (
        <>
          <p className="sicht">
            Alle Geldbeträge in Kontosicht. Der genaue Wert steht jeweils im Tooltip.
          </p>
          <Zeitraumwahl wirkt={ZEITRAUM_SEITEN.includes(ort.pathname)} />
        </>
      )}
    </header>
  )
}

function Unbekannt(): JSX.Element {
  return (
    <section className="hinweis">
      <p>Diese Adresse gehört zu keiner Ansicht.</p>
      <p>
        <Link to="/">Zur Positionsliste</Link>
      </p>
    </section>
  )
}

ReactDOM.createRoot(document.getElementById('wurzel') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <div className="geruest">
        <Kopf />
        <main>
          <Routes>
            <Route path="/" element={<Positionen />} />
            {/* AP-08ue: Startseite; /uebersicht ist der API-Endpunkt. */}
            <Route path="/start" element={<Uebersicht />} />
            {/* AP-06e: eigene Adresse, kollidiert mit keinem API-Pfad
                (anders als /kalender, /kampagnen — /equity bleibt API). */}
            <Route path="/dashboard" element={<Dashboard />} />
            {/* AP-08d: Bestand laut IB. /depot ist der API-Endpunkt, die Seite
                heißt /bestand. */}
            <Route path="/bestand" element={<Depot />} />
            {/* AP-16: Ergebnis je Titel über alle Instrumente. /titel-auswertung ist der
                API-Endpunkt, die Seite heißt /titel. */}
            <Route path="/titel" element={<Titel />} />
            {/* AP-17g (M01): Roll-Kosten und Kommission; API-Weg ist /roll-kosten-auswertung. */}
            <Route path="/roll-kosten" element={<RollKosten />} />
            <Route path="/dax-synthetic" element={<DaxSynthetic />} />
            {/* AP-08j2: /kalender ist der API-Endpunkt (AP-07t). Die Seite
                heißt /monat, damit Neuladen und Lesezeichen die Oberfläche
                erreichen und nicht den JSON-Fehler 422 des Endpunkts. */}
            <Route path="/monat" element={<Kalender />} />
            {/* AP-08-kampagnen: ebenso heißt die Seite /kampagnenliste —
                /kampagnen und /kampagnen/{id} sind API-Endpunkte. */}
            <Route path="/kampagnenliste" element={<Kampagnen />} />
            {/* AP-08g2: Kosten & Erträge; /kosten ist kein API-Pfad —
                /cashflows bleibt der Endpunkt. */}
            <Route path="/kosten" element={<KostenErtraege />} />
            {/* AP-10: /steuer-auswertung ist der API-Endpunkt, die Seite heißt /steuer. */}
            <Route path="/steuer" element={<Steuer />} />
            <Route path="/positionen/:chainId" element={<PositionDetail />} />
            <Route path="/tag/:datum" element={<Tag />} />
            {/* AP-08r: /rollkandidaten ist der API-Endpunkt, die Seite /rolls. */}
            <Route path="/rolls" element={<Rollkandidaten />} />
            {/* AP-06sc: /strategien ist der API-Endpunkt, die Seite /strategie. */}
            <Route path="/strategie" element={<Strategien />} />
            {/* AP-13ab: /oa-abgleich ist der API-Endpunkt, die Seite /abgleich. */}
            <Route path="/abgleich" element={<OaAbgleich />} />
            {/* AP-12a: /backtests ist der API-Endpunkt, die Seite /backtest. */}
            <Route path="/backtest" element={<Backtests />} />
            {/* AP-14a: Station. /system ist der API-Endpunkt, die Seite /zustand. */}
            <Route path="/zustand" element={<SystemSeite />} />
            <Route path="/roller" element={<RollerSeite />} />
            <Route path="/momentum" element={<MomentumSeite />} />
            <Route path="/breakout" element={<BreakoutSeite />} />
            <Route path="*" element={<Unbekannt />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  </React.StrictMode>,
)
