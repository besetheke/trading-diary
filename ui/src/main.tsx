import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import Dashboard from './Dashboard'
import Zeitraumwahl from './Zeitraumwahl'
import { useZeitraum, zeitraumSuche } from './zeitraum'
import Kalender from './Kalender'
import Kampagnen from './Kampagnen'
import KostenErtraege from './KostenErtraege'
import PositionDetail from './PositionDetail'
import Positionen from './Positionen'
import Tag from './Tag'
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
const ZEITRAUM_SEITEN = ['/', '/dashboard', '/kosten']

function Kopf(): JSX.Element {
  const ort = useLocation()
  const [zeitraum] = useZeitraum()
  const mit = zeitraumSuche(zeitraum)
  return (
    <header>
      <h1>
        <Link to={`/${mit}`}>Trading Journal</Link>
      </h1>
      <p className="sicht">
        Alle Geldbeträge in Kontosicht. Der genaue Wert steht jeweils im Tooltip.
      </p>
      <nav className="hauptnav">
        <Link to={`/dashboard${mit}`}>Dashboard</Link>
        <Link to={`/${mit}`}>Positionen</Link>
        <Link to={`/kampagnenliste${mit}`}>Kampagnen</Link>
        <Link to={`/kosten${mit}`}>Kosten &amp; Erträge</Link>
        <Link to={`/monat${mit}`}>Kalender</Link>
        <Link to={`/tag/${heuteDatum()}${mit}`}>Heute</Link>
      </nav>
      <Zeitraumwahl wirkt={ZEITRAUM_SEITEN.includes(ort.pathname)} />
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
            {/* AP-06e: eigene Adresse, kollidiert mit keinem API-Pfad
                (anders als /kalender, /kampagnen — /equity bleibt API). */}
            <Route path="/dashboard" element={<Dashboard />} />
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
            <Route path="/positionen/:chainId" element={<PositionDetail />} />
            <Route path="/tag/:datum" element={<Tag />} />
            <Route path="*" element={<Unbekannt />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  </React.StrictMode>,
)
